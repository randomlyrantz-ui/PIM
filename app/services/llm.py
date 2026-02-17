import json
from collections import defaultdict

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Article, ArticleScore, Domain


class LLMService:
    def __init__(self, db: Session):
        self.db = db
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def score_article(self, article: Article) -> None:
        domains = self.db.query(Domain).all()
        scores = self._keyword_score(article.content, domains)
        if self.client:
            try:
                scores = self._model_score(article, domains)
            except Exception:
                pass
        for domain in domains:
            existing = (
                self.db.query(ArticleScore)
                .filter(ArticleScore.article_id == article.id, ArticleScore.domain_id == domain.id)
                .first()
            )
            if existing:
                existing.score = scores.get(domain.name, 0)
            else:
                self.db.add(ArticleScore(article_id=article.id, domain_id=domain.id, score=scores.get(domain.name, 0)))
        self.db.commit()

    def summarize_article(self, article: Article) -> None:
        if self.client:
            try:
                summary = self._model_summary(article)
            except Exception:
                summary = self._fallback_summary(article)
        else:
            summary = self._fallback_summary(article)
        article.summary = summary["summary"]
        article.stance = summary["stance"]
        article.key_data = json.dumps(summary["key_data"])
        article.notable_quotes = json.dumps(summary["notable_quotes"])
        article.contrarian_flag = summary["stance"] == "challenges"
        self.db.commit()

    def process_unscored_articles(self) -> int:
        processed = 0
        article_ids = {s.article_id for s in self.db.query(ArticleScore.article_id).all()}
        for article in self.db.query(Article).all():
            if article.id not in article_ids:
                self.score_article(article)
                self.summarize_article(article)
                processed += 1
        return processed

    def _keyword_score(self, content: str, domains: list[Domain]) -> dict[str, int]:
        lowered = content.lower()
        scores = {}
        for domain in domains:
            keywords = [k.strip().lower() for k in domain.keywords.split(",") if k.strip()]
            hits = sum(lowered.count(keyword) for keyword in keywords)
            scores[domain.name] = min(100, hits * 15)
        return scores

    def _fallback_summary(self, article: Article) -> dict:
        sentences = [s.strip() for s in article.content.split(".") if s.strip()]
        condensed = ". ".join(sentences[:3])[:500]
        return {
            "summary": condensed or article.title,
            "stance": "nuances",
            "key_data": [],
            "notable_quotes": [],
        }

    def _model_score(self, article: Article, domains: list[Domain]) -> dict[str, int]:
        domain_text = "\n".join([f"- {d.name}: {d.description} ({d.keywords})" for d in domains])
        prompt = f"""You are an expert research assistant helping a writer who focuses on leadership, workforce development, AI's impact on work, and the role of human judgment in tool-driven environments.
Given the following article, score its relevance to each topic domain on a scale of 0-100. Only score above 50 if the article directly addresses the topic with substance, not passing mentions.
Topic Domains:\n{domain_text}\n
Article:\nTitle: {article.title}\nSource: {article.source.name}\nContent: {article.content[:6000]}\n
Return JSON only with key 'scores'."""
        resp = self.client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        payload = json.loads(resp.choices[0].message.content)
        return payload.get("scores", defaultdict(int))

    def _model_summary(self, article: Article) -> dict:
        prompt = f"""You are a research assistant for a writer focused on leadership, workforce development, and AI's role in organizations.
Summarize the following article in 2-3 sentences. Focus on core claim, evidence, and why it matters.
Return JSON keys: summary, stance(confirms|challenges|nuances), key_data(list), notable_quotes(list).
Title: {article.title}\nSource: {article.source.name}\nContent: {article.content[:6000]}"""
        resp = self.client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(resp.choices[0].message.content)
