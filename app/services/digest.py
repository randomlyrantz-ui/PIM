from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.db import Article, ArticleScore, Domain
from app.services.relevance import compute_relevance


class DigestService:
    def __init__(self, db: Session):
        self.db = db

    def generate_digest(self, days: int = 1) -> str:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            self.db.query(Article, Domain.name, ArticleScore.score)
            .join(ArticleScore, Article.id == ArticleScore.article_id)
            .join(Domain, Domain.id == ArticleScore.domain_id)
            .filter(Article.created_at >= since)
            .order_by(ArticleScore.score.desc())
            .all()
        )
        grouped: dict[str, list[tuple[Article, float]]] = defaultdict(list)
        seen_ids: set[int] = set()
        for article, domain_name, score in rows:
            if score >= 50 and article.id not in seen_ids:
                grouped[domain_name].append((article, score))
                seen_ids.add(article.id)

        now = datetime.now(timezone.utc)
        lines = [f"# PIM Digest ({now.date()})", ""]
        for domain, items in grouped.items():
            lines.append(f"## {domain}")
            for article, _score in items[:5]:
                relevance = compute_relevance(article.content, self.db)
                lines.extend(
                    [
                        f"title: {article.title}",
                        f"source_url: {article.url}",
                        f"date_published: {article.published_at.date() if article.published_at else now.date()}",
                        f"summary: {article.summary or 'Summary pending'}",
                        f"tags: {relevance.tags}",
                        f"relevance_score: {relevance.score_1_to_10}",
                        "",
                    ]
                )

        lines.append("## Emerging Patterns")
        lines.append("- Prioritize evidence-rich, system-level analyses and trend reversals over repeated hype narratives.")

        digest = "\n".join(lines)
        output_dir = Path(settings.digest_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"digest_{now.strftime('%Y%m%d_%H%M%S')}.md"
        output_file.write_text(digest)
        return str(output_file)
