from rapidfuzz import fuzz, process


FUZZY_THRESHOLD = 88


def _clean(term: str) -> str:
    return " ".join((term or "").strip().lower().split())


def normalize_terms(terms: list[str], canonical_skills: list[str], synonym_map: dict[str, str]) -> tuple[list[str], list[str]]:
    canonical_set = set(canonical_skills)
    normalized: list[str] = []
    rejected: list[str] = []

    for raw in terms or []:
        t = _clean(raw)
        if not t:
            continue

        if t in canonical_set:
            normalized.append(t)
            continue

        if t in synonym_map:
            mapped = _clean(synonym_map[t])
            if mapped in canonical_set:
                normalized.append(mapped)
            else:
                rejected.append(raw)
            continue

        match = process.extractOne(
            t,
            canonical_skills,
            scorer=fuzz.ratio,
            score_cutoff=FUZZY_THRESHOLD,
        )
        if match:
            normalized.append(match[0])
        else:
            rejected.append(raw)

    seen = set()
    deduped: list[str] = []
    for s in normalized:
        if s in seen:
            continue
        seen.add(s)
        deduped.append(s)

    return deduped, rejected


def build_jd_weights(
    must_have: list[str],
    important: list[str],
    nice_to_have: list[str],
    canonical_skills: list[str],
    synonym_map: dict[str, str],
) -> tuple[dict[str, int], list[str]]:
    rejected: list[str] = []

    mh, rej1 = normalize_terms(must_have, canonical_skills, synonym_map)
    imp, rej2 = normalize_terms(important, canonical_skills, synonym_map)
    nth, rej3 = normalize_terms(nice_to_have, canonical_skills, synonym_map)
    rejected.extend(rej1)
    rejected.extend(rej2)
    rejected.extend(rej3)

    weights: dict[str, int] = {}
    for s in nth:
        weights[s] = max(weights.get(s, 0), 1)
    for s in imp:
        weights[s] = max(weights.get(s, 0), 2)
    for s in mh:
        weights[s] = max(weights.get(s, 0), 3)

    return weights, rejected

