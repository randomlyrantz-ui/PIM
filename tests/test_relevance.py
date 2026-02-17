from app.services.relevance import compute_relevance


def test_compute_relevance_weights_evidence_over_hype():
    evidence_text = "Empirical study with dataset evidence on leadership decision-making and policy impact."
    hype_text = "Revolutionary game-changing disruption in AI tools with unprecedented outcomes."

    evidence_score = compute_relevance(evidence_text).score_1_to_10
    hype_score = compute_relevance(hype_text).score_1_to_10

    assert evidence_score > hype_score
    assert 1 <= evidence_score <= 10
