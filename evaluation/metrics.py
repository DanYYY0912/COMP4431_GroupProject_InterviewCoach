"""Dependency-free metrics with explicit denominators and no fabricated samples."""

import math
import re
from collections import Counter

from ml.schemas import SCHEMAS, validate


def edit_distance(reference, hypothesis):
    previous = list(range(len(hypothesis) + 1))
    for i, left in enumerate(reference, 1):
        current = [i]
        for j, right in enumerate(hypothesis, 1):
            current.append(
                min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (left != right))
            )
        previous = current
    return previous[-1]


def tokens(text, unit="word"):
    if unit == "character":
        return [c for c in text if c.isalnum()]
    if unit != "word":
        raise ValueError("unit must be word or character")
    return re.findall(r"[\w]+(?:'[\w]+)?", text.casefold())


def error_rate(reference, hypothesis, unit="word"):
    ref = tokens(reference, unit)
    hyp = tokens(hypothesis, unit)
    if not ref:
        raise ValueError(
            "Reference transcript is empty; report separately as a silence test"
        )
    return edit_distance(ref, hyp) / len(ref)


def percentile(values, p):
    if not values or not 0 <= p <= 100:
        raise ValueError("Nonempty measurements and percentile in [0,100] required")
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("Measurements must be finite and nonnegative")
    ordered = sorted(values)
    position = (len(ordered) - 1) * p / 100
    lo = math.floor(position)
    hi = math.ceil(position)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def recall_at_k(retrieved, relevant, k=5):
    if not relevant:
        raise ValueError("Known relevant passages are required")
    return len(set(retrieved[:k]) & set(relevant)) / len(set(relevant))


def citation_precision(cited, supporting):
    if not cited:
        return None
    return len(set(cited) & set(supporting)) / len(set(cited))


def cohens_kappa(left, right):
    if len(left) != len(right) or not left:
        raise ValueError("Paired nonempty ratings are required")
    observed = sum(a == b for a, b in zip(left, right)) / len(left)
    lc, rc = Counter(left), Counter(right)
    expected = sum(lc[k] * rc[k] for k in lc.keys() | rc.keys()) / (len(left) ** 2)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def sus_score(answers):
    if len(answers) != 10 or any(
        type(v) is not int or not 1 <= v <= 5 for v in answers
    ):
        raise ValueError("SUS requires ten integer responses from 1 to 5")
    return sum(v - 1 if i % 2 == 0 else 5 - v for i, v in enumerate(answers)) * 2.5


def validate_output(value, task):
    return task in SCHEMAS and not validate(value, SCHEMAS[task])


def language_proxy(output, language):
    """Script check only; it cannot establish Cantonese fluency or correctness."""
    if not isinstance(output, dict):
        return False
    text = " ".join(
        str(output.get(k, ""))
        for k in (
            "interviewer_text",
            "summary",
            "prioritized_improvement",
            "retry_exercise",
        )
    )
    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if language == "en-HK":
        return latin > 5 and cjk / max(cjk + latin, 1) < 0.05
    if language == "zh-HK":
        return cjk >= 5
    return cjk >= 3 and latin >= 3
