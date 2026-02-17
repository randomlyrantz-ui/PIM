import json
import logging
from collections import defaultdict

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Article, ArticleScore, Domain
from app.services.relevance import compute_relevance

logger = logging.getLogger(__name__)


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
                logger.exception("LLM scoring failed for article %s, using keyword fallback", article.id)
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
                logger.exception("LLM summary failed for article %s, using fallback", article.id)
                summary = self._fallback_summary(article)
        else:
            summary = self._fallback_summary(article)
        article.summary = summary.get("summary", article.title)
        article.stance = summary.get("stance", "nuances")
        article.key_data = json.dumps(summary.get("key_data", []))
        article.notable_quotes = json.dumps(summary.get("notable_quotes", []))
        article.contrarian_flag = article.stance == "challenges"
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
        base_relevance = compute_relevance(content, self.db).score_1_to_10 * 10
        scores = {}
        for domain in domains:
            keywords = [k.strip().lower() for k in domain.keywords.split(",") if k.strip()]
            hits = sum(lowered.count(keyword) for keyword in keywords)
            domain_score = min(100, (hits * 12) + base_relevance)
            scores[domain.name] = domain_score
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
        prompt = f"""You are an expert research assistant monitoring sources for leadership, cognition, ethics, systems, and tools (including AI).\nEvaluate relevance with a strict bias toward evidence over hype, case studies over press releases, and trend divergence over repetition.\nGiven the article below, score relevance for each domain on a 0-100 scale.\nOnly score above 50 when there is substantive depth and system-level insight.\n\nTopic Domains:\n{domain_text}\n\nArticle:\nTitle: {article.title}\nSource: {article.source.name}\nContent: {article.content[:6000]}\n\nReturn JSON only with key 'scores'."""
        resp = self.client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        payload = json.loads(resp.choices[0].message.content)
        return payload.get("scores", defaultdict(int))

    def _model_summary(self, article: Article) -> dict:
        prompt = f"""You are a research assistant focused on leadership, cognition, ethics, systems, and AI in human contexts.\nSummarize the article in 2-3 sentences with emphasis on evidence and system-level implications.\nReturn JSON keys: summary, stance(confirms|challenges|nuances), key_data(list), notable_quotes(list).\nTitle: {article.title}\nSource: {article.source.name}\nContent: {article.content[:6000]}"""
        resp = self.client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(resp.choices[0].message.content)
