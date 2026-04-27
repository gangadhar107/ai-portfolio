import json


def _safe_json_loads(text: str) -> dict:
    try:
        data = json.loads(text or "")
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def parse_job_description(groq_client, jd_text: str) -> dict:
    prompt = (
        "Extract skills/requirements from this job description.\n"
        "Return ONLY valid JSON with exactly these keys:\n"
        '{ "must_have": [], "important": [], "nice_to_have": [] }\n'
        "Rules:\n"
        "- Each value is an array of short skill/requirement phrases.\n"
        "- Do not include long sentences.\n"
        "- Use the wording from the JD when possible.\n\n"
        "JOB DESCRIPTION:\n"
        f"{jd_text}"
    )

    res = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    raw = (res.choices[0].message.content or "").strip()
    data = _safe_json_loads(raw)

    must_have = data.get("must_have")
    important = data.get("important")
    nice_to_have = data.get("nice_to_have")
    if not isinstance(must_have, list) or not isinstance(important, list) or not isinstance(nice_to_have, list):
        raise ValueError("jd_extraction_invalid")

    if not all(isinstance(x, str) for x in must_have + important + nice_to_have):
        raise ValueError("jd_extraction_invalid")

    must_have = [x.strip() for x in must_have if x.strip()]
    important = [x.strip() for x in important if x.strip()]
    nice_to_have = [x.strip() for x in nice_to_have if x.strip()]

    if len(must_have) == 0 and len(important) == 0 and len(nice_to_have) == 0:
        raise ValueError("jd_extraction_empty")

    weak_jd = len(must_have) == 0 and len(important) == 0 and len(nice_to_have) > 0

    return {
        "must_have": must_have,
        "important": important,
        "nice_to_have": nice_to_have,
        "weak_jd": weak_jd,
    }
