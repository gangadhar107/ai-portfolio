import json


def _safe_json_loads(text: str) -> dict:
    try:
        data = json.loads(text or "")
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def match_resume_to_jd(
    groq_client,
    jd_text: str,
    resume_text: str,
    canonical_skills: list[str],
) -> dict:
    vocab = ", ".join(canonical_skills)
    prompt = (
        "You are comparing a resume to a job description.\n"
        "Return ONLY valid JSON with exactly these keys:\n"
        '{ "matching_skills": [], "missing_skills": [], "fit_score": "high|medium|low" }\n'
        "Rules:\n"
        "- matching_skills and missing_skills must be chosen ONLY from this canonical vocabulary:\n"
        f"{vocab}\n"
        "- fit_score must be exactly one of: high, medium, low\n"
        "- Keep lists deduplicated.\n\n"
        "JOB DESCRIPTION:\n"
        f"{jd_text}\n\n"
        "RESUME:\n"
        f"{resume_text}"
    )

    res = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    raw = (res.choices[0].message.content or "").strip()
    data = _safe_json_loads(raw)

    matching_skills = data.get("matching_skills")
    missing_skills = data.get("missing_skills")
    fit_score = data.get("fit_score")
    if not isinstance(matching_skills, list) or not isinstance(missing_skills, list) or not isinstance(fit_score, str):
        raise ValueError("matcher_invalid")

    fit_score = fit_score.strip()
    if fit_score not in {"high", "medium", "low"}:
        raise ValueError("matcher_invalid")

    if not all(isinstance(x, str) for x in matching_skills + missing_skills):
        raise ValueError("matcher_invalid")

    matching_skills = [x for x in matching_skills if x.strip()]
    missing_skills = [x for x in missing_skills if x.strip()]

    def _dedupe(xs: list[str]) -> list[str]:
        seen = set()
        out: list[str] = []
        for x in xs:
            v = x.strip().lower()
            if not v or v in seen:
                continue
            seen.add(v)
            out.append(v)
        return out

    return {
        "matching_skills": _dedupe(matching_skills),
        "missing_skills": _dedupe(missing_skills),
        "fit_score": fit_score,
    }
