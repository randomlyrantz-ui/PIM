from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db import Article, Feedback

PRIMARY_KEYWORDS = [
    "leadership",
    "decision-making",
    "organizational systems",
    "cognition",
    "literacy",
    "workforce development",
    "ethics",
    "policy impact",
    "ai ethics",
    "automation roi",
    "tool misuse",
    "framework evaluation",
    "systems thinking failure",
    "human in the loop",
    "behavioral evidence",
]

SECONDARY_KEYWORDS = [
    "case study",
    "empirical study",
    "white paper",
    "report",
    "systematic review",
    "policy brief",
    "industry research",
    "automation rollback",
    "education reform",
]

TAGS_BY_TOPIC = {
    "AI & Automation": ["ai", "automation", "machine learning", "agentic"],
    "Leadership & Culture": ["leadership", "management", "culture", "organizational behavior"],
    "Workforce & Education": ["workforce", "skills", "education", "literacy", "upskilling"],
    "Policy & Regulation": ["policy", "regulation", "governance", "law"],
    "Systems Thinking": ["system", "systems thinking", "externalities", "second-order"],
    "Ethics": ["ethics", "fairness", "harm", "bias", "accountability"],
    "Empirical Evidence": ["empirical", "dataset", "randomized", "evidence", "study"],
    "Case Study": ["case study", "pilot", "implementation", "field report"],
    "Trend Shift": ["reversal", "trend", "shift", "inflection", "rollback"],
}

EVIDENCE_TERMS = ["empirical", "data", "trial", "systematic", "cohort", "causal", "evidence"]
HYPE_TERMS = ["revolutionary", "game-changing", "disruption", "must-have", "unprecedented"]


@dataclass
class RelevanceResult:
    score_1_to_10: int
    tags: list[str]


def infer_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags = [tag for tag, keywords in TAGS_BY_TOPIC.items() if any(keyword in lowered for keyword in keywords)]
    return tags or ["Systems Thinking"]


def compute_relevance(content: str, db: Session | None = None) -> RelevanceResult:
    lowered = content.lower()
    primary_hits = sum(lowered.count(keyword) for keyword in PRIMARY_KEYWORDS)
    secondary_hits = sum(lowered.count(keyword) for keyword in SECONDARY_KEYWORDS)
    evidence_hits = sum(lowered.count(term) for term in EVIDENCE_TERMS)
    hype_hits = sum(lowered.count(term) for term in HYPE_TERMS)

    raw = (primary_hits * 2.2) + (secondary_hits * 1.4) + (evidence_hits * 1.6) - (hype_hits * 1.3)
    normalized = max(1, min(10, round(raw / 3.2)))

    if db is not None:
        normalized = _apply_feedback_adjustment(db, lowered, normalized)

    return RelevanceResult(score_1_to_10=normalized, tags=infer_tags(content))


def _apply_feedback_adjustment(db: Session, lowered_content: str, base_score: int) -> int:
    feedback_rows = db.query(Feedback, Article).join(Article, Feedback.article_id == Article.id).all()
    if not feedback_rows:
        return base_score

    votes = 0
    weighted_votes = 0
    for feedback, article in feedback_rows:
        overlap = sum(1 for kw in PRIMARY_KEYWORDS[:8] if kw in lowered_content and kw in (article.content or "").lower())
        if overlap == 0:
            continue
        votes += overlap
        weighted_votes += overlap if feedback.positive else -overlap

    if votes == 0:
        return base_score

    adjustment = round((weighted_votes / votes) * 1.5)
    return max(1, min(10, base_score + adjustment))
