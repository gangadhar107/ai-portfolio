from psycopg.rows import dict_row

from database import get_connection, get_cursor


def _fetch_id(row) -> int:
    if row is None:
        raise RuntimeError("missing_returning_id")
    try:
        return int(row["id"])
    except Exception:
        return int(row[0])


def get_application(application_id: int) -> dict | None:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, company_name, position, date_applied, outcome, ref_code, notes,
                   outreach_channel, contact_person, role_category, followed_up, follow_up_date, follow_up_response
            FROM applications
            WHERE id = %s
            """,
            (application_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_active_context(application_id: int) -> dict | None:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, application_id, jd_text, resume_text, created_at, is_active
            FROM application_context
            WHERE application_id = %s AND is_active = TRUE
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (application_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def deactivate_existing_context(application_id: int) -> None:
    with get_cursor() as cur:
        cur.execute(
            "UPDATE application_context SET is_active = FALSE WHERE application_id = %s AND is_active = TRUE",
            (application_id,),
        )


def insert_context(application_id: int, jd_text: str, resume_text: str) -> int:
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO application_context (application_id, jd_text, resume_text, is_active)
            VALUES (%s, %s, %s, TRUE)
            RETURNING id
            """,
            (application_id, jd_text, resume_text),
        )
        context_id = _fetch_id(cur.fetchone())
        cur.execute(
            "UPDATE applications SET assessment_status = 'not_run' WHERE id = %s",
            (application_id,),
        )
        return int(context_id)


def upsert_context(application_id: int, jd_text: str, resume_text: str) -> int:
    with get_connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        try:
            cur.execute(
                "UPDATE application_context SET is_active = FALSE WHERE application_id = %s AND is_active = TRUE",
                (application_id,),
            )
            cur.execute(
                """
                INSERT INTO application_context (application_id, jd_text, resume_text, is_active)
                VALUES (%s, %s, %s, TRUE)
                RETURNING id
                """,
                (application_id, jd_text, resume_text),
            )
            context_id = _fetch_id(cur.fetchone())
            cur.execute(
                "UPDATE applications SET assessment_status = 'not_run' WHERE id = %s",
                (application_id,),
            )
            return int(context_id)
        finally:
            cur.close()


def insert_assessment(
    application_id: int,
    context_id: int | None,
    assessment: dict,
) -> int:
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO fit_assessments (
                application_id,
                context_id,
                fit_score,
                fit_confidence,
                confidence_score,
                signal_conflict,
                matching_skills,
                missing_skills,
                jd_weights,
                rejected_terms,
                failure_reason,
                vocab_version
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s)
            RETURNING id
            """,
            (
                application_id,
                context_id,
                assessment.get("fit_score"),
                assessment.get("fit_confidence"),
                assessment.get("confidence_score"),
                assessment.get("signal_conflict", False),
                assessment.get("matching_skills_json", "[]"),
                assessment.get("missing_skills_json", "[]"),
                assessment.get("jd_weights_json", "{}"),
                assessment.get("rejected_terms_json", "[]"),
                assessment.get("failure_reason"),
                assessment.get("vocab_version"),
            ),
        )
        return _fetch_id(cur.fetchone())


def update_assessment_status(application_id: int, status: str) -> None:
    with get_cursor() as cur:
        cur.execute(
            "UPDATE applications SET assessment_status = %s WHERE id = %s",
            (status, application_id),
        )


def get_assessment_history(application_id: int, limit: int = 10) -> list[dict]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, context_id, created_at, fit_score, fit_confidence, confidence_score, signal_conflict, failure_reason
            FROM fit_assessments
            WHERE application_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (application_id, limit),
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows] if rows else []


def get_dashboard_fit_summary() -> list[dict]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
                a.id,
                a.company_name,
                a.person_name,
                a.position,
                a.date_applied,
                a.outcome,
                a.ref_code,
                a.followed_up,
                a.assessment_status,
                a.outreach_channel,
                a.role_category,
                COALESCE(v.visit_count, 0) AS visit_count,
                v.first_visit,
                ac.id AS context_id,
                usable.fit_score,
                usable.fit_confidence,
                usable.confidence_score,
                usable.signal_conflict,
                attempt.failure_reason
            FROM applications a
            LEFT JOIN (
                SELECT
                    rc.application_id,
                    COUNT(v.id)::INT AS visit_count,
                    MIN(v.timestamp) AS first_visit
                FROM ref_codes rc
                LEFT JOIN visits v ON v.ref_code = rc.ref_code
                GROUP BY rc.application_id
            ) v ON v.application_id = a.id
            LEFT JOIN (
                SELECT application_id, id
                FROM application_context
                WHERE is_active = TRUE
            ) ac ON ac.application_id = a.id
            LEFT JOIN LATERAL (
                SELECT failure_reason
                FROM fit_assessments
                WHERE application_id = a.id
                ORDER BY created_at DESC, id DESC
                LIMIT 1
            ) attempt ON TRUE
            LEFT JOIN LATERAL (
                SELECT fit_score, fit_confidence, confidence_score, signal_conflict
                FROM fit_assessments
                WHERE application_id = a.id
                  AND failure_reason IS NULL
                  AND fit_confidence IN ('high', 'medium', 'low')
                  AND confidence_score IS NOT NULL
                ORDER BY created_at DESC, id DESC
                LIMIT 1
            ) usable ON TRUE
            ORDER BY a.date_applied DESC, a.id DESC
            """
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows] if rows else []
