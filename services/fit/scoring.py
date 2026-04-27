import math


def compute_confidence_score(jd_weights: dict[str, int], matching_skills: list[str]) -> float:
    total = float(sum(jd_weights.values()))
    if total <= 0:
        return 0.0
    matched = 0.0
    for s in set(matching_skills or []):
        matched += float(jd_weights.get(s, 0))
    return matched / total


def validate_confidence_score(score: float) -> float:
    if not isinstance(score, (int, float)):
        raise ValueError("score_invalid")
    if not math.isfinite(float(score)):
        raise ValueError("score_invalid")
    if score < 0.0 or score > 1.0:
        raise ValueError("score_invalid")
    return float(score)


def label_confidence(score: float) -> str:
    score = validate_confidence_score(score)
    if score > 0.7:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def signal_conflict(matcher_fit_score: str, confidence_label: str) -> bool:
    m = (matcher_fit_score or "").strip().lower()
    c = (confidence_label or "").strip().lower()
    if m not in {"high", "medium", "low"} or c not in {"high", "medium", "low"}:
        return False
    return m != c
