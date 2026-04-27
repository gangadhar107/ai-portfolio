"""
Unit tests for services/fit modules.
Covers normalization, scoring, jd_parser, and matcher per v1.3 test plan.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.fit.vocabulary import CANONICAL_SKILLS, SYNONYM_MAP, VOCAB_VERSION
from services.fit.normalization import normalize_terms, build_jd_weights
from services.fit.scoring import (
    compute_confidence_score,
    validate_confidence_score,
    label_confidence,
    signal_conflict,
)
from services.fit.jd_parser import parse_job_description
from services.fit.matcher import match_resume_to_jd


# ════════════════════════════════════════════════════════════════════════
# NORMALIZATION TESTS
# ════════════════════════════════════════════════════════════════════════


def test_n1_exact_match_returns_canonical():
    """N1: exact match returns the canonical term for a lowercase input."""
    normalized, rejected = normalize_terms(["python"], CANONICAL_SKILLS, SYNONYM_MAP)
    assert normalized == ["python"]
    assert rejected == []


def test_n2_exact_match_is_case_insensitive():
    """N2: exact match is case-insensitive — 'SQL', 'sql', 'Sql' all resolve."""
    n1, r1 = normalize_terms(["SQL"], CANONICAL_SKILLS, SYNONYM_MAP)
    n2, r2 = normalize_terms(["sql"], CANONICAL_SKILLS, SYNONYM_MAP)
    n3, r3 = normalize_terms(["Sql"], CANONICAL_SKILLS, SYNONYM_MAP)
    assert n1 == ["sql"]
    assert n2 == ["sql"]
    assert n3 == ["sql"]
    assert r1 == []
    assert r2 == []
    assert r3 == []


def test_n3_synonym_resolution():
    """N3: synonym resolution for ml, gtm, apis."""
    n1, r1 = normalize_terms(["ml"], CANONICAL_SKILLS, SYNONYM_MAP)
    assert n1 == ["machine learning"]
    assert r1 == []

    n2, r2 = normalize_terms(["gtm"], CANONICAL_SKILLS, SYNONYM_MAP)
    assert n2 == ["go-to-market"]
    assert r2 == []

    n3, r3 = normalize_terms(["apis"], CANONICAL_SKILLS, SYNONYM_MAP)
    assert n3 == ["api integration"]
    assert r3 == []


def test_n4_fuzzy_match_accepts_above_threshold():
    """N4: fuzzy match accepts a variant scoring at or above 88."""
    # "data analys" should fuzzy-match "data analysis" (high similarity)
    normalized, rejected = normalize_terms(
        ["data analyss"], CANONICAL_SKILLS, SYNONYM_MAP
    )
    assert len(normalized) == 1
    assert normalized[0] == "data analysis"
    assert rejected == []


def test_n5_fuzzy_match_rejects_below_threshold():
    """N5: fuzzy match rejects a term below 88; term appears in rejected list."""
    normalized, rejected = normalize_terms(["xyzgarbage"], CANONICAL_SKILLS, SYNONYM_MAP)
    assert normalized == []
    assert "xyzgarbage" in rejected


def test_n6_all_layers_fail_appears_in_rejected():
    """N6: a term failing all three layers appears in rejected_terms, not normalized."""
    normalized, rejected = normalize_terms(
        ["quantumfluxcapacitor"], CANONICAL_SKILLS, SYNONYM_MAP
    )
    assert "quantumfluxcapacitor" not in normalized
    assert "quantumfluxcapacitor" in rejected


def test_n7_normalize_list_mixed_input():
    """N7: normalize_list on ['SQL', 'unknownjunk999', 'ml'] returns correct split."""
    normalized, rejected = normalize_terms(
        ["SQL", "unknownjunk999", "ml"], CANONICAL_SKILLS, SYNONYM_MAP
    )
    assert "sql" in normalized
    assert "machine learning" in normalized
    assert len(normalized) == 2
    assert "unknownjunk999" in rejected


def test_n8_duplicate_skill_keeps_higher_weight():
    """N8: duplicate skill in must_have and important keeps weight 3, not 2."""
    weights, rejected = build_jd_weights(
        must_have=["SQL"],
        important=["SQL"],
        nice_to_have=[],
        canonical_skills=CANONICAL_SKILLS,
        synonym_map=SYNONYM_MAP,
    )
    assert weights["sql"] == 3


# ════════════════════════════════════════════════════════════════════════
# SCORING TESTS
# ════════════════════════════════════════════════════════════════════════


def test_s1_high_confidence_at_071():
    """S1: confidence_score of 0.71 → label 'high'."""
    assert label_confidence(0.71) == "high"


def test_s2_medium_at_070_boundary():
    """S2: confidence_score of 0.70 → label 'medium' (boundary, not high)."""
    assert label_confidence(0.70) == "medium"


def test_s3_medium_at_040_boundary():
    """S3: confidence_score of 0.40 → label 'medium' (boundary, not low)."""
    assert label_confidence(0.40) == "medium"


def test_s4_low_at_039():
    """S4: confidence_score of 0.39 → label 'low'."""
    assert label_confidence(0.39) == "low"


def test_s5_high_at_upper_bound():
    """S5: confidence_score of 1.0 → label 'high'."""
    assert label_confidence(1.0) == "high"


def test_s6_low_at_lower_bound():
    """S6: confidence_score of 0.0 → label 'low'."""
    assert label_confidence(0.0) == "low"


def test_s7_weighted_total_zero_no_division_error():
    """S7: weighted_total = 0 → function returns 0.0, ZeroDivisionError never raised."""
    result = compute_confidence_score({}, ["sql"])
    assert result == 0.0


def test_s8_signal_conflict_false_when_fit_score_none():
    """S8: signal_conflict is False when fit_score is None."""
    assert signal_conflict(None, "high") is False


def test_s9_signal_conflict_false_when_confidence_none():
    """S9: signal_conflict is False when fit_confidence is None."""
    assert signal_conflict("high", None) is False


def test_s10_signal_conflict_false_when_both_none():
    """S10: signal_conflict is False when both are None."""
    assert signal_conflict(None, None) is False


def test_s11_signal_conflict_true_when_mismatch():
    """S11: signal_conflict is True when fit_score='high' and fit_confidence='medium'."""
    assert signal_conflict("high", "medium") is True


def test_s12_signal_conflict_false_when_match():
    """S12: signal_conflict is False when fit_score='high' and fit_confidence='high'."""
    assert signal_conflict("high", "high") is False


def test_s13_failed_row_signal_conflict_false():
    """S13: failed row always stores signal_conflict = False regardless of other values."""
    # A failed row has no valid fit_score or fit_confidence — represented as None
    assert signal_conflict(None, None) is False
    assert signal_conflict(None, "high") is False
    assert signal_conflict("high", None) is False
    # Even with empty strings (another representation of missing)
    assert signal_conflict("", "high") is False
    assert signal_conflict("high", "") is False


# ════════════════════════════════════════════════════════════════════════
# JD PARSER TESTS
# ════════════════════════════════════════════════════════════════════════


def _make_groq_mock(content: str):
    """Build a mock Groq client that returns the given content string."""
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


def test_j1_valid_output_all_arrays():
    """J1: valid output with all three arrays populated → returns parsed dict, no failure."""
    content = json.dumps({
        "must_have": ["SQL", "Python"],
        "important": ["Tableau"],
        "nice_to_have": ["machine learning"],
    })
    client = _make_groq_mock(content)
    result = parse_job_description(client, "Some JD text")
    assert result["must_have"] == ["SQL", "Python"]
    assert result["important"] == ["Tableau"]
    assert result["nice_to_have"] == ["machine learning"]
    assert result["weak_jd"] is False


def test_j2_non_json_string():
    """J2: Groq returns non-JSON string → failure_reason = jd_extraction_invalid."""
    client = _make_groq_mock("This is not valid JSON at all")
    with pytest.raises(ValueError, match="jd_extraction_invalid"):
        parse_job_description(client, "Some JD text")


def test_j3_missing_important_key():
    """J3: Groq returns JSON missing 'important' key → jd_extraction_invalid."""
    content = json.dumps({
        "must_have": ["SQL"],
        "nice_to_have": ["Excel"],
    })
    client = _make_groq_mock(content)
    with pytest.raises(ValueError, match="jd_extraction_invalid"):
        parse_job_description(client, "Some JD text")


def test_j4_string_not_array():
    """J4: Groq returns {'must_have': 'SQL'} — string not array → jd_extraction_invalid."""
    content = json.dumps({
        "must_have": "SQL",
        "important": [],
        "nice_to_have": [],
    })
    client = _make_groq_mock(content)
    with pytest.raises(ValueError, match="jd_extraction_invalid"):
        parse_job_description(client, "Some JD text")


def test_j5_non_string_item():
    """J5: Groq returns {'must_have': ['SQL', 123]} — non-string item → jd_extraction_invalid."""
    content = json.dumps({
        "must_have": ["SQL", 123],
        "important": [],
        "nice_to_have": [],
    })
    client = _make_groq_mock(content)
    with pytest.raises(ValueError, match="jd_extraction_invalid"):
        parse_job_description(client, "Some JD text")


def test_j6_all_arrays_empty():
    """J6: Groq returns all three arrays empty → failure_reason = jd_extraction_empty."""
    content = json.dumps({
        "must_have": [],
        "important": [],
        "nice_to_have": [],
    })
    client = _make_groq_mock(content)
    with pytest.raises(ValueError, match="jd_extraction_empty"):
        parse_job_description(client, "Some JD text")


def test_j7_only_nice_to_have_is_weak_jd():
    """J7: must_have=[], important=[], nice_to_have=['Excel'] → weak_jd, NOT jd_extraction_empty."""
    content = json.dumps({
        "must_have": [],
        "important": [],
        "nice_to_have": ["Excel"],
    })
    client = _make_groq_mock(content)
    result = parse_job_description(client, "Some JD text")
    assert result["weak_jd"] is True
    assert result["nice_to_have"] == ["Excel"]


def test_j8_must_have_content_is_normal():
    """J8: must_have=['SQL'], important=[], nice_to_have=[] → normal (not weak_jd)."""
    content = json.dumps({
        "must_have": ["SQL"],
        "important": [],
        "nice_to_have": [],
    })
    client = _make_groq_mock(content)
    result = parse_job_description(client, "Some JD text")
    assert result["weak_jd"] is False
    assert result["must_have"] == ["SQL"]


# ════════════════════════════════════════════════════════════════════════
# MATCHER TESTS
# ════════════════════════════════════════════════════════════════════════


def test_m1_valid_output():
    """M1: valid output with fit_score='high' → returns parsed dict, no failure."""
    content = json.dumps({
        "matching_skills": ["sql", "python"],
        "missing_skills": ["tableau"],
        "fit_score": "high",
    })
    client = _make_groq_mock(content)
    result = match_resume_to_jd(client, "JD text", "Resume text", CANONICAL_SKILLS)
    assert result["fit_score"] == "high"
    assert "sql" in result["matching_skills"]
    assert "python" in result["matching_skills"]
    assert "tableau" in result["missing_skills"]


def test_m2_invalid_fit_score_value():
    """M2: Groq returns fit_score='strong' → failure_reason = matcher_invalid."""
    content = json.dumps({
        "matching_skills": ["sql"],
        "missing_skills": [],
        "fit_score": "strong",
    })
    client = _make_groq_mock(content)
    with pytest.raises(ValueError, match="matcher_invalid"):
        match_resume_to_jd(client, "JD", "Resume", CANONICAL_SKILLS)


def test_m3_uppercase_fit_score_is_invalid():
    """M3: Groq returns fit_score='HIGH' — uppercase → matcher_invalid, not normalized."""
    content = json.dumps({
        "matching_skills": ["sql"],
        "missing_skills": [],
        "fit_score": "HIGH",
    })
    client = _make_groq_mock(content)
    # Per the v1.3 spec: fit_score outside {high, medium, low} is rejected, not normalised.
    # The implementation currently normalises case. This test verifies spec compliance.
    with pytest.raises(ValueError, match="matcher_invalid"):
        match_resume_to_jd(client, "JD", "Resume", CANONICAL_SKILLS)


def test_m4_phrase_not_enum():
    """M4: Groq returns fit_score='medium match' — phrase not enum → matcher_invalid."""
    content = json.dumps({
        "matching_skills": ["sql"],
        "missing_skills": [],
        "fit_score": "medium match",
    })
    client = _make_groq_mock(content)
    with pytest.raises(ValueError, match="matcher_invalid"):
        match_resume_to_jd(client, "JD", "Resume", CANONICAL_SKILLS)


def test_m5_non_json_string():
    """M5: Groq returns non-JSON string → matcher_invalid."""
    client = _make_groq_mock("Not valid JSON at all")
    with pytest.raises(ValueError, match="matcher_invalid"):
        match_resume_to_jd(client, "JD", "Resume", CANONICAL_SKILLS)


def test_m6_missing_matching_skills_key():
    """M6: Groq returns JSON missing 'matching_skills' key → matcher_invalid."""
    content = json.dumps({
        "missing_skills": ["sql"],
        "fit_score": "high",
    })
    client = _make_groq_mock(content)
    with pytest.raises(ValueError, match="matcher_invalid"):
        match_resume_to_jd(client, "JD", "Resume", CANONICAL_SKILLS)


def test_m7_matching_skills_as_string():
    """M7: Groq returns matching_skills as a string not array → matcher_invalid."""
    content = json.dumps({
        "matching_skills": "sql",
        "missing_skills": [],
        "fit_score": "high",
    })
    client = _make_groq_mock(content)
    with pytest.raises(ValueError, match="matcher_invalid"):
        match_resume_to_jd(client, "JD", "Resume", CANONICAL_SKILLS)


def test_m8_timeout_exception():
    """M8: Groq call raises a timeout exception → failure_reason = matcher_failed."""
    client = MagicMock()
    client.chat.completions.create.side_effect = TimeoutError("connection timed out")
    with pytest.raises(TimeoutError):
        match_resume_to_jd(client, "JD", "Resume", CANONICAL_SKILLS)


def test_m9_api_error():
    """M9: Groq call raises an API error → failure_reason = matcher_failed."""
    client = MagicMock()
    client.chat.completions.create.side_effect = Exception("API rate limit exceeded")
    with pytest.raises(Exception, match="API rate limit exceeded"):
        match_resume_to_jd(client, "JD", "Resume", CANONICAL_SKILLS)


def test_m10_no_jd_weights_in_prompt():
    """M10: matcher input does NOT contain jd_weights — inspect the Groq call."""
    content = json.dumps({
        "matching_skills": ["sql"],
        "missing_skills": [],
        "fit_score": "high",
    })
    client = _make_groq_mock(content)
    match_resume_to_jd(client, "Some JD text", "Some resume text", CANONICAL_SKILLS)

    # Inspect the actual call made to the Groq client
    call_args = client.chat.completions.create.call_args
    messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
    prompt_content = messages[0]["content"]

    # Assert jd_weights is absent from the prompt
    assert "jd_weights" not in prompt_content.lower()
    assert "must_have" not in prompt_content.lower()
    assert "important" not in prompt_content.lower()
    assert "nice_to_have" not in prompt_content.lower()
    # But vocabulary IS in the prompt
    assert "sql" in prompt_content.lower()
