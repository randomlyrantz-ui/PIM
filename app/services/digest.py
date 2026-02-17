from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.db import Article, ArticleScore, Domain


class DigestService:
    def __init__(self, db: Session):
        self.db = db

    def generate_digest(self, days: int = 1) -> str:
        since = datetime.now(UTC) - timedelta(days=days)
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

        now = datetime.now(UTC)
        lines = [f"# PIM Digest ({now.date()})", ""]
        for domain, items in grouped.items():
            lines.append(f"## {domain}")
            for article, score in items[:5]:
                lines.append(f"- **{article.title}** ({score:.0f}) - {article.summary or 'Summary pending'} [{article.url}]({article.url})")
            lines.append("")

        contrarian = []
        seen_contrarian: set[int] = set()
        for article, _, _ in rows:
            if article.contrarian_flag and article.id not in seen_contrarian:
                contrarian.append(article)
                seen_contrarian.add(article.id)
        lines.append("## Contrarian / Alternative Views")
        for article in contrarian[:5]:
            lines.append(f"- {article.title} - {article.url}")

        lines.append("")
        lines.append("## Emerging Patterns")
        lines.append("- Placeholder: connect weekly pattern-detection LLM prompt for cross-source themes.")

        digest = "\n".join(lines)
        output_dir = Path(settings.digest_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"digest_{now.strftime('%Y%m%d_%H%M%S')}.md"
        output_file.write_text(digest)
        return str(output_file)
