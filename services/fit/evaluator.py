import json
import os


class EvaluatorInvalidError(Exception):
    pass


class EvaluatorFailedError(Exception):
    pass


EVALUATION_PROMPT = """You are acting as a senior hiring manager with experience in {industry}.

I will give you a Job Description (JD) and my Resume. Evaluate my resume against the JD and give me a score out of 100 using the following weighted framework:

1. Keyword & Skills Match — 30 points
   - How well do my skills and terminology match the JD's required and preferred qualifications?
   - Are exact phrases and tools aligned?

2. Experience Relevance — 25 points
   - Does my past experience mirror the responsibilities in the JD?
   - Is the scope and seniority comparable?

3. Impact & Quantification — 20 points
   - Are my achievements backed by numbers and outcomes?
   - Do bullet points show results or just tasks?

4. Structure & Readability — 15 points
   - Is the resume scannable and well-formatted?
   - Is the most relevant information immediately visible?

5. Customization Signal — 10 points
   - Does the resume feel tailored to this specific role or generic?

For each category:
- Give a score (e.g., 22/30)
- Give 2-3 specific reasons for the score
- Point out what is missing or weak

After the category breakdown:
- Give a TOTAL score out of 100
- List any dealbreaker gaps that would likely disqualify me
- List missed opportunities — experience I have but am not positioning well
- Suggest 3-5 specific resume rewrites or additions (give actual rewritten bullet points, not vague advice)
- Give an honest recommendation: Should I apply as-is, revise first, or is this a significant mismatch?

Do not be diplomatic. Be direct and critical. I want to know what a real hiring manager would think, not an encouraging AI response.

Respond in this exact JSON structure:
{{
  "categories": {{
    "keyword_skills_match": {{
      "score": <integer out of 30>,
      "reasons": [<string>, <string>, <string>],
      "weaknesses": [<string>]
    }},
    "experience_relevance": {{
      "score": <integer out of 25>,
      "reasons": [<string>, <string>],
      "weaknesses": [<string>]
    }},
    "impact_quantification": {{
      "score": <integer out of 20>,
      "reasons": [<string>, <string>],
      "weaknesses": [<string>]
    }},
    "structure_readability": {{
      "score": <integer out of 15>,
      "reasons": [<string>, <string>],
      "weaknesses": [<string>]
    }},
    "customization_signal": {{
      "score": <integer out of 10>,
      "reasons": [<string>, <string>],
      "weaknesses": [<string>]
    }}
  }},
  "total_score": <integer out of 100>,
  "dealbreaker_gaps": [<string>],
  "missed_opportunities": [<string>],
  "rewrite_suggestions": [<string>],
  "recommendation": <"apply_as_is" | "revise_first" | "significant_mismatch">,
  "recommendation_reasoning": <string>
}}

---
JD:
{jd_text}
---
RESUME:
{resume_text}"""


def evaluate_fit(industry: str, jd_text: str, resume_text: str) -> dict:
    api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not api_key:
        raise EvaluatorFailedError("api_error")

    try:
        from groq import Groq
    except Exception:
        raise EvaluatorFailedError("api_error")

    prompt = EVALUATION_PROMPT.format(
        industry=(industry or "unknown"),
        jd_text=(jd_text or ""),
        resume_text=(resume_text or ""),
    )

    try:
        client = Groq(api_key=api_key, timeout=10.0)
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        raise EvaluatorFailedError("api_error")

    raw = ""
    try:
        raw = (res.choices[0].message.content or "").strip()
    except Exception:
        raise EvaluatorInvalidError("json_parse_failed")

    try:
        data = json.loads(raw or "")
    except Exception:
        raise EvaluatorInvalidError("json_parse_failed")

    if not isinstance(data, dict):
        raise EvaluatorInvalidError("missing_keys")

    required_top_level = {
        "categories",
        "total_score",
        "dealbreaker_gaps",
        "missed_opportunities",
        "rewrite_suggestions",
        "recommendation",
        "recommendation_reasoning",
    }
    if not required_top_level.issubset(set(data.keys())):
        raise EvaluatorInvalidError("missing_keys")

    categories = data.get("categories")
    if not isinstance(categories, dict):
        raise EvaluatorInvalidError("missing_keys")

    required_categories = {
        "keyword_skills_match",
        "experience_relevance",
        "impact_quantification",
        "structure_readability",
        "customization_signal",
    }
    if not required_categories.issubset(set(categories.keys())):
        raise EvaluatorInvalidError("missing_keys")

    total_score = data.get("total_score")
    if not isinstance(total_score, int) or total_score < 0 or total_score > 100:
        raise EvaluatorInvalidError("score_invalid")

    return data
