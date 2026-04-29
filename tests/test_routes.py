"""
Route tests for v1.3 context, assess-fit, and dashboard routes.
All database and service calls are mocked — no real DB needed.
"""

import json
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest


# ════════════════════════════════════════════════════════════════════════
# Helper: application row from repository
# ════════════════════════════════════════════════════════════════════════

def _make_app_row(
    app_id=1,
    assessment_status="not_run",
    context_id=None,
    fit_confidence=None,
    confidence_score=None,
    fit_score=None,
    failure_reason=None,
    followed_up=False,
    outcome="pending",
    date_applied=None,
    visit_count=0,
):
    """Simulate a row from get_dashboard_fit_summary."""
    return {
        "id": app_id,
        "company_name": "TestCorp",
        "person_name": "Tester",
        "position": "ML Engineer",
        "date_applied": date_applied or date(2026, 4, 1),
        "outcome": outcome,
        "ref_code": f"ref_{app_id}",
        "followed_up": followed_up,
        "assessment_status": assessment_status,
        "outreach_channel": "portal_apply",
        "role_category": "ai_engineer",
        "visit_count": visit_count,
        "first_visit": None,
        "context_id": context_id,
        "fit_score": fit_score,
        "fit_confidence": fit_confidence,
        "confidence_score": confidence_score,
        "failure_reason": failure_reason,
    }


def _make_app_dict(app_id=1):
    """Simulate a row from get_application."""
    return {
        "id": app_id,
        "company_name": "TestCorp",
        "position": "ML Engineer",
        "date_applied": date(2026, 4, 1),
        "outcome": "pending",
        "ref_code": "ref_1",
        "notes": "",
        "outreach_channel": "portal_apply",
        "contact_person": "founder",
        "role_category": "ai_engineer",
        "followed_up": False,
        "follow_up_date": None,
        "follow_up_response": None,
        "assessment_status": "not_run",
    }

def _make_groq_client(content: str):
    client = MagicMock()
    resp = MagicMock()
    choice = MagicMock()
    msg = MagicMock()
    msg.content = content
    choice.message = msg
    resp.choices = [choice]
    client.chat.completions.create.return_value = resp
    return client


def _extract_json_data(resp_text: str) -> list[dict]:
    """Extract RAW_DATA JSON from dashboard HTML response."""
    marker = "RAW_DATA = "
    start = resp_text.find(marker)
    if start == -1:
        marker = "var RAW_DATA = "
        start = resp_text.find(marker)
    assert start != -1, "RAW_DATA not found in response"
    start += len(marker)
    end = resp_text.find(";\n", start)
    if end == -1:
        end = resp_text.find(";\r\n", start)
    return json.loads(resp_text[start:end])


# ════════════════════════════════════════════════════════════════════════
# CONTEXT PAGE ROUTE TESTS
# ════════════════════════════════════════════════════════════════════════


class TestContextRoutes:

    @patch("services.fit.repository.get_assessment_history", return_value=[])
    @patch("services.fit.repository.get_active_context", return_value=None)
    @patch("services.fit.repository.get_application")
    def test_c1_get_context_valid_auth(self, mock_app, mock_ctx, mock_hist, client, valid_auth_cookie):
        """C1: GET /admin/context/{id} with valid auth returns 200."""
        mock_app.return_value = _make_app_dict()
        resp = client.get("/admin/context/1", cookies={"auth": valid_auth_cookie})
        assert resp.status_code == 200
        assert "Fit Context" in resp.text

    def test_c2_get_context_no_auth(self, client):
        """C2: GET /admin/context/{id} with no auth cookie — shows login page."""
        resp = client.get("/admin/context/1")
        assert resp.status_code == 200
        assert "Admin Access" in resp.text or "password" in resp.text.lower()

    def test_c3_get_context_invalid_auth(self, client, invalid_auth_cookie):
        """C3: GET /admin/context/{id} with invalid auth — shows login, not context."""
        resp = client.get("/admin/context/1", cookies={"auth": invalid_auth_cookie})
        assert resp.status_code == 200
        assert "Admin Access" in resp.text or "password" in resp.text.lower()
        assert "Fit Context" not in resp.text

    @patch("services.fit.repository.get_assessment_history", return_value=[])
    @patch("services.fit.repository.get_active_context", return_value=None)
    @patch("services.fit.repository.get_application")
    def test_c4_no_active_context_shows_disabled(self, mock_app, mock_ctx, mock_hist, client, valid_auth_cookie):
        """C4: GET with has_active_context=False — Assess Fit button is disabled."""
        mock_app.return_value = _make_app_dict()
        resp = client.get("/admin/context/1", cookies={"auth": valid_auth_cookie})
        assert resp.status_code == 200
        assert "disabled" in resp.text

    @patch("services.fit.repository.get_assessment_history", return_value=[])
    @patch("services.fit.repository.get_active_context")
    @patch("services.fit.repository.get_application")
    def test_c5_active_context_not_disabled(self, mock_app, mock_ctx, mock_hist, client, valid_auth_cookie):
        """C5: GET with has_active_context=True — textareas pre-filled with context."""
        mock_app.return_value = _make_app_dict()
        mock_ctx.return_value = {
            "id": 10, "application_id": 1,
            "industry": "SaaS",
            "jd_text": "Test JD content here",
            "resume_text": "Test resume content here",
            "created_at": datetime.now(), "is_active": True,
        }
        resp = client.get("/admin/context/1", cookies={"auth": valid_auth_cookie})
        assert resp.status_code == 200
        assert "Test JD content here" in resp.text
        assert "Test resume content here" in resp.text

    @patch("services.fit.repository.get_assessment_history", return_value=[])
    @patch("services.fit.repository.get_active_context", return_value=None)
    @patch("services.fit.repository.get_application", return_value=None)
    def test_c6_nonexistent_application(self, mock_app, mock_ctx, mock_hist, client, valid_auth_cookie):
        """C6: GET /admin/context/99999 for non-existent application_id — never 500."""
        resp = client.get("/admin/context/99999", cookies={"auth": valid_auth_cookie})
        assert resp.status_code != 500
        assert "Application not found" in resp.text or resp.status_code in {200, 404, 302}

    @patch("services.fit.repository.upsert_context")
    def test_c7_post_empty_jd(self, mock_upsert, client, valid_auth_cookie):
        """C7: POST with empty jd_text — error, no save_context call, never 500."""
        resp = client.post(
            "/admin/context/1",
            data={"jd_text": "", "resume_text": "A valid resume text that is long enough to pass validation"},
            cookies={"auth": valid_auth_cookie},
            follow_redirects=False,
        )
        assert resp.status_code != 500
        mock_upsert.assert_not_called()

    @patch("services.fit.repository.upsert_context")
    def test_c8_post_empty_resume(self, mock_upsert, client, valid_auth_cookie):
        """C8: POST with empty resume_text — error, no save_context call, never 500."""
        resp = client.post(
            "/admin/context/1",
            data={"jd_text": "A valid JD text that is long enough for validation checks", "resume_text": ""},
            cookies={"auth": valid_auth_cookie},
            follow_redirects=False,
        )
        assert resp.status_code != 500
        mock_upsert.assert_not_called()

    @patch("services.fit.repository.upsert_context", return_value=42)
    def test_c9_post_valid_context(self, mock_upsert, client, valid_auth_cookie):
        """C9: POST with valid jd and resume — calls upsert_context exactly once."""
        jd = "A valid JD text that is definitely long enough to pass the 20 char minimum"
        resume = "A valid resume text that is definitely long enough to pass"
        resp = client.post(
            "/admin/context/1",
            data={"jd_text": jd, "resume_text": resume},
            cookies={"auth": valid_auth_cookie},
            follow_redirects=False,
        )
        assert resp.status_code != 500
        mock_upsert.assert_called_once_with(1, jd, resume, None)


# ════════════════════════════════════════════════════════════════════════
# ASSESS FIT ROUTE TESTS
# ════════════════════════════════════════════════════════════════════════


class TestAssessFitRoutes:

    @patch("services.fit.repository.insert_assessment")
    @patch("services.fit.repository.get_active_context", return_value=None)
    def test_a1_no_active_context(self, mock_ctx, mock_insert, client, valid_auth_cookie):
        """A1: POST assess-fit with no active context — error, no insert_assessment."""
        resp = client.post(
            "/admin/assess-fit",
            data={"application_id": "1"},
            cookies={"auth": valid_auth_cookie},
            follow_redirects=False,
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["ok"] is False
        mock_insert.assert_not_called()

    @patch("services.fit.repository.insert_assessment")
    @patch("services.fit.repository.get_active_context")
    def test_a1b_industry_required(self, mock_ctx, mock_insert, client, valid_auth_cookie):
        """A1b: POST assess-fit with blank industry — error, no insert_assessment."""
        mock_ctx.return_value = {"id": 10, "industry": "   ", "jd_text": "JD", "resume_text": "Resume"}
        resp = client.post(
            "/admin/assess-fit",
            data={"application_id": "1"},
            cookies={"auth": valid_auth_cookie},
            follow_redirects=False,
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "Industry / Domain is required" in (body.get("error") or "")
        mock_insert.assert_not_called()

    @patch("services.fit.repository.update_assessment_status")
    @patch("services.fit.repository.insert_assessment", return_value=1)
    @patch("services.fit.repository.get_active_context")
    def test_a2_successful_assessment(self, mock_ctx, mock_insert, mock_status, client, valid_auth_cookie):
        """A2: POST assess-fit with valid context, successful assessment → status=completed."""
        mock_ctx.return_value = {
            "id": 10,
            "industry": "fintech",
            "jd_text": "Need SQL and Python skills for this role",
            "resume_text": "I know SQL and Python very well",
        }

        assessment = {
            "categories": {
                "keyword_skills_match": {"score": 25, "reasons": ["a", "b", "c"], "weaknesses": ["x"]},
                "experience_relevance": {"score": 20, "reasons": ["a", "b"], "weaknesses": ["x"]},
                "impact_quantification": {"score": 15, "reasons": ["a", "b"], "weaknesses": ["x"]},
                "structure_readability": {"score": 12, "reasons": ["a", "b"], "weaknesses": ["x"]},
                "customization_signal": {"score": 8, "reasons": ["a", "b"], "weaknesses": ["x"]},
            },
            "total_score": 80,
            "dealbreaker_gaps": [],
            "missed_opportunities": [],
            "rewrite_suggestions": ["Rewrite bullet 1"],
            "recommendation": "revise_first",
            "recommendation_reasoning": "Needs tailoring.",
        }

        with patch("services.fit.evaluator.evaluate_fit", return_value=assessment):
            resp = client.post(
                "/admin/assess-fit",
                data={"application_id": "1"},
                cookies={"auth": valid_auth_cookie},
                follow_redirects=False,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["assessment"]["total_score"] == 80
        mock_status.assert_called_once_with(1, "completed")
        mock_insert.assert_called_once()

    @patch("services.fit.repository.update_assessment_status")
    @patch("services.fit.repository.insert_assessment", return_value=1)
    @patch("services.fit.repository.get_active_context")
    def test_a3_weak_jd_outcome(self, mock_ctx, mock_insert, mock_status, client, valid_auth_cookie):
        """A3: POST assess-fit with another valid assessment → status=completed."""
        mock_ctx.return_value = {
            "id": 10,
            "industry": "SaaS",
            "jd_text": "Nice to have Excel for this role",
            "resume_text": "I know Excel and more things listed here",
        }

        assessment = {
            "categories": {
                "keyword_skills_match": {"score": 12, "reasons": ["a", "b", "c"], "weaknesses": ["x"]},
                "experience_relevance": {"score": 12, "reasons": ["a", "b"], "weaknesses": ["x"]},
                "impact_quantification": {"score": 10, "reasons": ["a", "b"], "weaknesses": ["x"]},
                "structure_readability": {"score": 10, "reasons": ["a", "b"], "weaknesses": ["x"]},
                "customization_signal": {"score": 5, "reasons": ["a", "b"], "weaknesses": ["x"]},
            },
            "total_score": 49,
            "dealbreaker_gaps": [],
            "missed_opportunities": [],
            "rewrite_suggestions": ["Rewrite bullet 1"],
            "recommendation": "revise_first",
            "recommendation_reasoning": "Missing specifics.",
        }

        with patch("services.fit.evaluator.evaluate_fit", return_value=assessment):
            resp = client.post(
                "/admin/assess-fit",
                data={"application_id": "1"},
                cookies={"auth": valid_auth_cookie},
                follow_redirects=False,
            )

        assert resp.status_code == 200
        mock_status.assert_called_once_with(1, "completed")

    @patch("services.fit.repository.update_assessment_status")
    @patch("services.fit.repository.insert_assessment", return_value=1)
    @patch("services.fit.repository.get_active_context")
    def test_a4_jd_extraction_invalid(self, mock_ctx, mock_insert, mock_status, client, valid_auth_cookie):
        """A4: POST assess-fit with evaluator invalid response → status=failed, failure_reason=missing_keys."""
        mock_ctx.return_value = {"id": 10, "industry": "SaaS", "jd_text": "Bad JD", "resume_text": "Resume"}
        from services.fit.evaluator import EvaluatorInvalidError

        with patch("services.fit.evaluator.evaluate_fit", side_effect=EvaluatorInvalidError("missing_keys")):
            resp = client.post(
                "/admin/assess-fit",
                data={"application_id": "1"},
                cookies={"auth": valid_auth_cookie},
                follow_redirects=False,
            )

        assert resp.status_code == 500
        mock_status.assert_called_once_with(1, "failed")
        insert_call = mock_insert.call_args
        assert insert_call[0][5] == "missing_keys"

    @patch("services.fit.repository.update_assessment_status")
    @patch("services.fit.repository.insert_assessment", return_value=1)
    @patch("services.fit.repository.get_active_context")
    def test_a5_matcher_failed(self, mock_ctx, mock_insert, mock_status, client, valid_auth_cookie):
        """A5: POST assess-fit with evaluator failure → status=failed, failure_reason=api_error."""
        mock_ctx.return_value = {"id": 10, "industry": "Fintech", "jd_text": "Need SQL and Python skills", "resume_text": "I know SQL and Python"}
        from services.fit.evaluator import EvaluatorFailedError

        with patch("services.fit.evaluator.evaluate_fit", side_effect=EvaluatorFailedError("api_error")):
            resp = client.post(
                "/admin/assess-fit",
                data={"application_id": "1"},
                cookies={"auth": valid_auth_cookie},
                follow_redirects=False,
            )

        assert resp.status_code == 500
        mock_status.assert_called_once_with(1, "failed")
        insert_call = mock_insert.call_args
        assert insert_call[0][5] == "api_error"

    def test_a6_no_auth_redirects(self, client):
        """A6: POST assess-fit with no auth — 403, assessment never runs."""
        resp = client.post(
            "/admin/assess-fit",
            data={"application_id": "1"},
            follow_redirects=False,
        )
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════════
# DASHBOARD ROUTE TESTS
# ════════════════════════════════════════════════════════════════════════


class TestDashboardRoutes:

    @patch("routers.intelligence.get_cached_insights", return_value=[])
    @patch("services.fit.repository.get_dashboard_fit_summary")
    def test_d1_dashboard_returns_200_with_json_data(self, mock_summary, mock_insights, client, valid_auth_cookie):
        """D1: GET /dashboard with valid auth returns 200 and contains json_data."""
        mock_summary.return_value = [_make_app_row()]
        resp = client.get("/dashboard", cookies={"auth": valid_auth_cookie})
        assert resp.status_code == 200
        assert "RAW_DATA" in resp.text

    @patch("routers.intelligence.get_cached_insights", return_value=[])
    @patch("services.fit.repository.get_dashboard_fit_summary")
    def test_d2_not_run_has_null_priority_disagreement(self, mock_summary, mock_insights, client, valid_auth_cookie):
        """D2: assessment_status=not_run → priority=null, disagreement=null."""
        mock_summary.return_value = [_make_app_row(assessment_status="not_run")]
        resp = client.get("/dashboard", cookies={"auth": valid_auth_cookie})
        assert resp.status_code == 200
        data = _extract_json_data(resp.text)
        row = data[0]
        assert row["priority"] is None
        assert row["disagreement"] is None
        assert row["fit_confidence"] == ""

    @patch("routers.intelligence.get_cached_insights", return_value=[])
    @patch("services.fit.repository.get_dashboard_fit_summary")
    def test_d3_completed_has_priority_disagreement(self, mock_summary, mock_insights, client, valid_auth_cookie):
        """D3: assessment_status=completed → priority/disagreement/fit_confidence populated."""
        mock_summary.return_value = [_make_app_row(
            assessment_status="completed",
            fit_confidence="high",
            confidence_score=0.85,
            fit_score="revise_first",
            context_id=10,
        )]
        resp = client.get("/dashboard", cookies={"auth": valid_auth_cookie})
        assert resp.status_code == 200
        data = _extract_json_data(resp.text)
        row = data[0]
        assert row["priority"] in {"high", "medium", "low"}
        assert isinstance(row["disagreement"], bool)
        assert row["fit_confidence"] in {"high", "medium", "low"}
        assert row["total_score"] == 85

    @patch("routers.intelligence.get_cached_insights", return_value=[])
    @patch("services.fit.repository.get_dashboard_fit_summary")
    def test_d4_failed_has_null_priority_with_failure_reason(self, mock_summary, mock_insights, client, valid_auth_cookie):
        """D4: assessment_status=failed → priority=null, disagreement=null, failure_reason non-empty."""
        mock_summary.return_value = [_make_app_row(
            assessment_status="failed",
            failure_reason="jd_extraction_invalid",
        )]
        resp = client.get("/dashboard", cookies={"auth": valid_auth_cookie})
        assert resp.status_code == 200
        data = _extract_json_data(resp.text)
        row = data[0]
        assert row["priority"] is None
        assert row["disagreement"] is None
        assert len(row["failure_reason"]) > 0

    @patch("routers.intelligence.get_cached_insights", return_value=[])
    @patch("services.fit.repository.get_dashboard_fit_summary")
    def test_d5_every_row_has_followed_up(self, mock_summary, mock_insights, client, valid_auth_cookie):
        """D5: every application row in json_data contains 'followed_up' field."""
        mock_summary.return_value = [
            _make_app_row(app_id=1, followed_up=True),
            _make_app_row(app_id=2, followed_up=False),
        ]
        resp = client.get("/dashboard", cookies={"auth": valid_auth_cookie})
        assert resp.status_code == 200
        data = _extract_json_data(resp.text)
        for row in data:
            assert "followed_up" in row

    @patch("routers.intelligence.get_cached_insights", return_value=[])
    @patch("services.fit.repository.get_dashboard_fit_summary")
    def test_d6_every_row_has_active_context(self, mock_summary, mock_insights, client, valid_auth_cookie):
        """D6: every application row in json_data contains 'has_active_context' field."""
        mock_summary.return_value = [
            _make_app_row(app_id=1, context_id=10),
            _make_app_row(app_id=2, context_id=None),
        ]
        resp = client.get("/dashboard", cookies={"auth": valid_auth_cookie})
        assert resp.status_code == 200
        data = _extract_json_data(resp.text)
        for row in data:
            assert "has_active_context" in row

    @patch("routers.intelligence.get_cached_insights", return_value=[])
    @patch("services.fit.repository.get_dashboard_fit_summary")
    def test_d7_no_context_signals_false(self, mock_summary, mock_insights, client, valid_auth_cookie):
        """D7: application with context_id=None → has_active_context=False."""
        mock_summary.return_value = [_make_app_row(context_id=None)]
        resp = client.get("/dashboard", cookies={"auth": valid_auth_cookie})
        assert resp.status_code == 200
        data = _extract_json_data(resp.text)
        row = data[0]
        assert row["has_active_context"] is False
