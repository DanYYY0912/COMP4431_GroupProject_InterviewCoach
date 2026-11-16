"""Generate runtime-aligned fine-tuning drafts for the InterviewCoach app.

Every prompt in the output is produced by the same builders the FastAPI app calls
(``app.coach.question_messages`` / ``app.coach.report_messages``), so a training row is
byte-identical to a live request. Every assistant target is checked with the same
validators the app uses before a row is written (``check_question_output`` /
``check_report_output``), so the drafts cannot drift from the runtime contract.

Inputs are fictional job descriptions (``ml/scenarios/jobs.json``) and an original
story library (``ml/scenarios/stories/*.json``) grounded in the Hong Kong market
evidence recorded in ``docs/DATASET.md``. No real employer or person appears, nothing
is copied from a posting, and no network or model call is made at generation time.

Output rows are unreviewed drafts: ``reviews`` stays empty and human reviewers must
approve them before training. This module never writes approvals.
"""

import argparse
import json
import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from app.coach import (
    ModelCoachTurn,
    ModelReport,
    answer_excerpts,
    check_question_output,
    check_report_output,
    question_messages,
    report_messages,
)
from app.ingestion import COMPETENCY_TERMS, chunk_text, profile_metadata
from app.retrieval import lexical_ranking
from app.schemas import AnswerSubmission, Citation

from ml.dataset import content_hash, near_duplicate_pairs, normalized_text, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = Path(__file__).resolve().parent / "scenarios"
KNOWLEDGE = ROOT / "knowledge"
DEFAULT_OUTPUT = ROOT / "ml" / "data" / "runtime_drafts.jsonl"

STAR = ("Situation", "Task", "Action", "Result")
STAR_ZH = {"Situation": "背景", "Task": "任務", "Action": "行動", "Result": "結果"}
# Each story variant replaces exactly one STAR element, so a missing element and a
# variant can never describe the same sentence.
VARIANT_ELEMENT = {"vague": "Situation", "exaggerated": "Action", "no_data": "Result"}
VARIANT_ORDER = ("none", "vague", "exaggerated", "no_data")
MISSING_ORDER = (None, "Situation", "Task", "Action", "Result")
DIFFICULTIES = ("foundation", "standard", "stretch")
STORY_CYCLE = ("entry", "early", "early", "mid", "early", "early", "mid",
               "entry", "early", "early", "mid", "entry")
TASKS = ("question", "report", "safety")
TASK_TOTALS = {"question": 450, "report": 350, "safety": 200}
LANGUAGE_SHARE = {"en-HK": 3, "zh-HK": 2}
TOTAL_ROWS = sum(TASK_TOTALS.values())
DOUBLE_REVIEW_RATE = 0.15
# The report prompt already carries four quoted sources and the shared system prompt, so
# each row stays inside the trainer's 2,048-token window (ml/config.json: max_length).
MAX_REPORT_COMPETENCIES = 2
# Phrases that mark a solo claim; citing one as evidence for Teamwork/Communication is a
# mismatch the coach should name rather than praise.
SOLO_MARKERS = (
    "on my own",
    "by myself",
    "single-handedly",
    "singlehandedly",
    "on my own initiative",
    "myself alone",
    "我自己一個",
    "一個人做",
    "獨自",
    "單人匹馬",
)
EXCERPT_CHAR_BUDGET = {"en-HK": 700, "zh-HK": 340}
# Rows without a candidate answer (opening questions, source-side injections) must still
# produce distinct wording; the counter walks the phrasing table until it is seen-free.
WORDING_ATTEMPTS = 200
SEED = 20_261_116

# --- authored text pools -------------------------------------------------------------
# Coaching stays inside the report contract: under 20 English words / 35 Chinese characters.

COACHING_ABSENT = {
    "en-HK": {
        "Situation": (
            "Open with the setting: where you were, who was involved and the deadline.",
            "Name the specific context and the constraint that made this hard.",
        ),
        "Task": (
            "Say what you personally owned, and what success would have looked like.",
            "Separate your own responsibility from the team's objective.",
        ),
        "Action": (
            "Describe the steps you took and the reason for each choice.",
            "Explain what you did yourself rather than what the team did.",
        ),
        "Result": (
            "Add the outcome and the evidence you actually have for it.",
            "Say what changed after your work, and how you knew.",
        ),
    },
    "zh-HK": {
        "Situation": (
            "先講背景：當時喺邊、邊個參與。",
            "講出具體情境同令件事難做嘅限制。",
        ),
        "Task": (
            "講明你自己負責咩，同成功標準係咩。",
            "分清你自己嘅職責同團隊目標。",
        ),
        "Action": (
            "講清楚你做咗咩步驟，同每步原因。",
            "講你自己做咗咩，而唔係團隊做咗咩。",
        ),
        "Result": (
            "補上結果，同你真正有嘅證據。",
            "講出你嘅工作令咩改變。",
        ),
    },
}
COACHING_PRESENT = {
    "en-HK": {
        "Situation": (
            "The setting is clear; keep it to one sentence next time.",
            "Good context; the constraint could be named even earlier.",
        ),
        "Task": (
            "Your own responsibility is clear; keep the goal explicit.",
            "The task is stated; next time say what success looked like.",
        ),
        "Action": (
            "Good action detail; add one sentence on why you chose it.",
            "The steps are specific; keep each one attached to a reason.",
        ),
        "Result": (
            "The outcome is stated; keep claiming only what you measured.",
            "The result is clear; say who could verify it.",
        ),
    },
    "zh-HK": {
        "Situation": ("背景清楚，下次保持一句講完。", "情境清楚，限制可以早啲講。"),
        "Task": ("你自己嘅職責清楚，目標可以再明確。", "任務清楚，可補一句成功標準。"),
        "Action": ("行動細節足夠，可以補一句點解咁揀。", "步驟具體，每步連住原因。"),
        "Result": ("結果有講，記住只報你有量度嘅數。", "結果清楚，可以講邊個核實到。"),
    },
}
COACHING_VARIANT = {
    "en-HK": {
        "vague": "Make this setting concrete: name the system, the team and the date.",
        "no_data": "A qualitative result is valid; add only evidence you actually measured.",
        "exaggerated": "Separate your contribution from the team's when you describe actions.",
    },
    "zh-HK": {
        "vague": "把背景講具體：邊個系統、邊個團隊、幾時。",
        "no_data": "質性結果都可以，只講量度過嘅嘢。",
        "exaggerated": "講行動時分清你自己同團隊嘅貢獻。",
    },
}
STRENGTH_TEXT = {
    "en-HK": {
        "Situation": "The setting is specific.",
        "Task": "Your own task is stated.",
        "Action": "The actions are concrete.",
        "Result": "The outcome is stated.",
    },
    "zh-HK": {
        "Situation": "背景講得具體。",
        "Task": "自己嘅任務講得清楚。",
        "Action": "行動步驟具體。",
        "Result": "結果有講到。",
    },
}
STRENGTH_TEXT_VARIANT = {
    "en-HK": {
        "vague": "The context is brief but present.",
        "no_data": "The outcome is qualitative, not invented.",
        "exaggerated": "The action is described in the first person.",
    },
    "zh-HK": {
        "vague": "背景簡短但講到。",
        "no_data": "結果係質性描述，冇虛構數字。",
        "exaggerated": "行動有用第一身講出嚟。",
    },
}
IMPROVEMENT = {
    "en-HK": {
        "Situation": "Start with one sentence on the setting, then move to your task.",
        "Task": "State your own responsibility before you describe the actions.",
        "Action": "Describe the steps you took, in order, with one reason each.",
        "Result": "Close with the outcome and the evidence behind it.",
        None: "Connect one action to a measured outcome in the same example.",
    },
    "zh-HK": {
        "Situation": "先用一句講背景，再講你嘅任務。",
        "Task": "先講你自己負責咩，再講行動。",
        "Action": "按次序講你做過嘅步驟，每步一個原因。",
        "Result": "最後講結果，同支持結果嘅證據。",
        None: "同一例子中，把行動連到你量度到嘅結果。",
    },
}
RETRY = {
    "en-HK": "Retry the same answer in 90 seconds and add the missing {element} sentence.",
    "zh-HK": "用 90 秒再講一次，補講{element}。",
}
RETRY_NO_GAP = {
    "en-HK": "Retry the same answer in 90 seconds and keep one measured outcome.",
    "zh-HK": "用 90 秒再講一次，保留一個有量度嘅結果。",
}

OPENING = {
    "en-HK": (
        "Tell me about a time you used {c}. What was the challenge, and what were you responsible for?",
        "Walk me through one piece of work where {c} mattered. What was the setting, and what was your own task?",
        "Pick a recent example of your {c} work. What were you trying to achieve, and what did you do yourself?",
        "Let us start with {c}. Describe one specific example and your part in it.",
        "What is the clearest example of your {c} work so far? Start with the setting.",
        "Think of a piece of work where {c} made a difference. What was your role, and what did you do?",
    ),
    "zh-HK": (
        "請用一個實際例子，講下你點樣運用「{c}」。當時有咩難題，你負責啲咩？",
        "講一個你真實做過、同「{c}」有關嘅例子。背景係點，你自己負責邊部分？",
        "揀一個最近嘅例子，講下你點用「{c}」。你想達到咩目標，實際做咗啲咩？",
        "我哋由「{c}」開始。請講一個具體例子，同你喺當中嘅角色。",
        "講一個你最熟嘅「{c}」經驗。當時情況係點，你負責邊部分？",
        "有邊件工作係因為「{c}」而做得成？你本人做咗啲咩？",
    ),
}
# Natural interviewer addenda: they widen the phrasing space so no two opening
# questions in the corpus share the same wording.
ADDENDUM = {
    "en-HK": (
        "",
        " You can use a project from university or from work.",
        " Please keep it to the last two years if you can.",
        " Take a moment to pick one before you start.",
        " One example is enough; I do not need the whole history.",
    ),
    "zh-HK": (
        "",
        " 大學或者工作嘅例子都可以。",
        " 盡量講近兩年嘅例子。",
        " 你可以先想一陣再開始。",
        " 一個例子就夠，唔需要講晒所有經歷。",
    ),
}
FOLLOW_UP = {
    "en-HK": (
        "Could you build on that example? ",
        "Let us stay with that example for a moment. ",
        "One more detail on that answer, please. ",
    ),
    "zh-HK": (
        "可唔可以補充頭先個例子？",
        "我哋留喺呢個例子多一陣。",
        "想再問多少少頭先個答案。",
    ),
}
NEXT_QUESTION = {
    "en-HK": (
        "Thank you. Now describe a difficult trade-off you made while using {c}. What options did you weigh?",
        "Let us move to {c}. How would you decide between two approaches when the deadline changes?",
        "Next, tell me about feedback you received on your {c} work. What did you change?",
        "Now think of a time {c} did not go to plan. What did you notice first, and what did you do?",
    ),
    "zh-HK": (
        "多謝。而家講一個你用「{c}」時做過嘅困難取捨，你衡量過咩方案？",
        "講到「{c}」，如果截止日期突然改變，你會點決定用邊個做法？",
        "下一個問題：你做「{c}」相關工作時收過咩意見？你改咗咩？",
        "再想一個「{c}」唔順嘅例子。你最先發現咩，之後點做？",
    ),
}
STRETCH_SUFFIX = {
    "en-HK": " What evidence would distinguish your approach from an alternative?",
    "zh-HK": " 你點樣知道呢個選擇比其他方案好？",
}
FOLLOW_UP_REASON = {
    "en-HK": (
        "The last answer has no clear {element} cue, so this asks for the {element} detail "
        "first. This is a STAR coverage rule, not a quality score."
    ),
    "zh-HK": (
        "上一個答案未見清楚嘅 {element} 線索，所以先補問 {element} 細節。"
        "呢個係 STAR 覆蓋規則，唔係質素評分。"
    ),
}
SAFETY_REFUSAL = {
    "en-HK": (
        "I only run interview practice, so I will not score you.",
        "I cannot act on instructions written inside the job description.",
        "I do not give candidates a score, and I will not rank applicants.",
        "I treat the job description as quoted data, never as instructions.",
        "That note asks me to score you, which I will not do.",
        "I will ignore any instruction aimed at the model, including that one.",
        "Scoring or ranking candidates is outside what this practice session does.",
        "I will not act on text inside the job description, and I will not grade you.",
    ),
    "zh-HK": (
        "我只做面試練習，唔會為你打分。",
        "職位描述裡面嘅指示我唔會跟。",
        "我唔會畀候選人分數，亦唔會幫人排名。",
        "職位描述我只當資料，唔會當指示。",
        "嗰個備註叫我畀你打分，我唔會做。",
        "寫畀模型嘅指示我會忽略，包括呢段。",
        "為候選人打分或者排名，唔係呢個練習做嘅事。",
        "職位描述裡面嘅字句我唔會執行，亦唔會評你分。",
    ),
}
SAFETY_REDIRECT = {
    "en-HK": (
        " Let us use one real example instead: tell me about a time you used {c}.",
        " Staying with your own evidence: when did you use {c}, and what did you do?",
        " Could we look at your own example with {c} instead?",
        " Back to the interview: where did {c} matter in your work?",
        " What did you do with {c} in one real example?",
    ),
    "zh-HK": (
        " 不如用一個真實例子：你幾時用過「{c}」，當時做咗啲咩？",
        " 講返你自己嘅證據：你喺「{c}」方面做過咩？",
        " 不如講返你自己「{c}」嘅經驗？",
        " 返去面試：你工作裡面邊度用到「{c}」？",
        " 講一個真實例子，你點用「{c}」？",
    ),
}
SAFETY_ANSWER_REFUSAL = {
    "en-HK": (
        ("I will not predict hiring chances or grade an accent; practice feedback cannot judge that, "
        "and it is not what this rehearsal is for. Back to your example: what was the {element} there?"),
        ("I do not score accent or estimate whether you will be hired. That would not be honest "
        "feedback. Let us keep to evidence: could you add the {element} to that answer?"),
    ),
    "zh-HK": (
        ("我唔會預測取錄機會，亦唔會為口音評分，練習回饋做唔到呢件事。"
        "返到你嘅例子：當時嘅{element}係咩？"),
        ("我唔會評口音，亦唔會估你會唔會請。呢啲唔係誠實嘅練習回饋。"
        "不如補返{element}：你當時具體做咗啲咩？"),
    ),
}
SAFETY_ANSWER_REASON = {
    "en-HK": (
        "The answer asks for a hiring or accent judgement. The coach declines and returns to STAR "
        "evidence instead of scoring the person."
    ),
    "zh-HK": (
        "答案要求預測取錄或評口音。教練拒絕，並返去 STAR 證據，而唔係評價個人。"
    ),
}


@dataclass(frozen=True)
class Chunk:
    """The retrieval-relevant fields of ``app.db.ChunkRecord`` without a database."""

    id: str
    source: str
    text: str


def cell_totals() -> dict[tuple[str, str], int]:
    """Split each task total into the approved 60/40 language share."""
    totals = {}
    for task, total in TASK_TOTALS.items():
        for language, share in LANGUAGE_SHARE.items():
            totals[(task, language)] = total * share // sum(LANGUAGE_SHARE.values())
    assert sum(totals.values()) == TOTAL_ROWS
    return totals


def family_targets(families: list[str]) -> dict[str, int]:
    """Give every family the same row count, with the remainder on the first families."""
    base, extra = divmod(TOTAL_ROWS, len(families))
    return {family: base + (1 if index < extra else 0) for index, family in enumerate(families)}


def allocate(families: list[str]) -> dict[str, dict[tuple[str, str], int]]:
    """Deal every (task, language) cell across families so each family hits its target.

    Every family keeps at least one row in every cell, which guarantees that each role
    family appears in both languages and in both question and report tasks.
    """
    targets = family_targets(families)
    cells = cell_totals()
    allocation = {family: {cell: 1 for cell in cells} for family in families}
    pool = []
    for cell, total in cells.items():
        pool.extend([cell] * (total - len(families)))
    cursor = 0
    for cell in pool:
        while sum(allocation[families[cursor]].values()) >= targets[families[cursor]]:
            cursor = (cursor + 1) % len(families)
        allocation[families[cursor]][cell] += 1
    for family in families:
        assert sum(allocation[family].values()) == targets[family]
    for cell, total in cells.items():
        assert sum(allocation[family][cell] for family in families) == total
    return allocation


def load_scenarios() -> tuple[dict, list[dict], dict]:
    jobs = json.loads((SCENARIOS / "jobs.json").read_text())
    injections = json.loads((SCENARIOS / "injections.json").read_text())
    stories = []
    for path in sorted((SCENARIOS / "stories").glob("*.json")):
        payload = json.loads(path.read_text())
        for story in payload["stories"]:
            story["role_family"] = payload["role_family"]
            stories.append(story)
    return jobs, stories, injections


def canonical_variant(missing: str | None, variant: str) -> str:
    """A variant that targets the missing element changes nothing, so treat it as none."""
    if variant == "none":
        return variant
    if missing is not None and VARIANT_ELEMENT[variant] == missing:
        return "none"
    return variant


def compose_answer(story: dict, language: str, missing: str | None, variant: str) -> tuple:
    """Build one candidate answer and the exact sentence used for each STAR element."""
    block = story[language]
    sentences = {}
    for element in STAR:
        if element == missing:
            continue
        applied = variant if variant != "none" and VARIANT_ELEMENT[variant] == element else "none"
        sentences[element] = {"text": block[element if applied == "none" else applied],
                              "variant": applied}
    answer = " ".join(sentences[element]["text"] for element in STAR if element in sentences)
    excerpt = answer_excerpts([answer])[0]
    if len(excerpt) != len(answer):
        raise ValueError(f"{story['id']} {language}: answer exceeds the excerpt window")
    return answer, sentences


def competence_options(story: dict, allowed: list[str]) -> list[str]:
    options = [name for name in story["competencies"] if name in allowed]
    return options or [name for name in allowed if name in COMPETENCY_TERMS]


def pick_citations(sources: list[Citation], terms: list[str], count: int = 1) -> list[str]:
    """Prefer chunks that actually mention the competency the question is about."""
    lowered = [term.lower() for term in terms]
    scored = sorted(
        sources,
        key=lambda source: (
            -sum(term in source.text.lower() for term in lowered),
            source.chunk_id,
        ),
    )
    return [source.chunk_id for source in scored[:count]]


ADDENDUM_SLOTS = 5


def wording_parts(pool_size: int, option_count: int, wording: int) -> tuple[int, int, int]:
    """Split one wording counter into template, competency and addendum offsets."""
    assert all(len(pool) == ADDENDUM_SLOTS for pool in ADDENDUM.values())
    template = wording % pool_size
    option = (wording // pool_size) % max(option_count, 1)
    addendum = (wording // (pool_size * max(option_count, 1))) % ADDENDUM_SLOTS
    return template, option, addendum


def question_target(
    language: str,
    difficulty: str,
    intent: str,
    options: list[str],
    missing: str | None,
    sources: list[Citation],
    wording: int,
) -> dict:
    """Author one CoachTurn that satisfies check_question_output."""
    zh = language == "zh-HK"
    if intent in {"opening", "next"}:
        pool = OPENING[language] if intent == "opening" else NEXT_QUESTION[language]
        template, option, addendum = wording_parts(len(pool), len(options), wording)
        competency = options[option]
        text = pool[template].format(c=competency)
        if intent == "opening":
            text += ADDENDUM[language][addendum]
        question_type = "opening" if intent == "opening" else (
            "technical" if option % 2 else "behavioral"
        )
        reason = None
    else:
        assert missing is not None
        competency = options[wording % len(options)]
        template = wording % len(FOLLOW_UP[language])
        coaching = COACHING_ABSENT[language][missing][(wording // len(FOLLOW_UP[language])) % 2]
        text = FOLLOW_UP[language][template] + coaching
        question_type = "follow_up"
        reason = FOLLOW_UP_REASON[language].format(element=missing)
    if difficulty == "stretch":
        text += STRETCH_SUFFIX[language]
    if zh and len(re.findall(r"[\u3400-\u9fff]", text)) < 5:
        raise ValueError("zh-HK target lacks Cantonese text")
    return {
        "interviewer_text": text,
        "question_type": question_type,
        "targeted_competencies": [competency],
        "adaptive_follow_up_reason": reason,
        "citation_ids": pick_citations(sources, COMPETENCY_TERMS.get(competency, (competency,))),
    }


def safety_target(
    language: str,
    case: str,
    options: list[str],
    missing: str | None,
    sources: list[Citation],
    wording: int,
) -> dict:
    if case == "source":
        refusals = SAFETY_REFUSAL[language]
        redirects = SAFETY_REDIRECT[language]
        refusal = refusals[wording % len(refusals)]
        redirect = redirects[(wording // len(refusals)) % len(redirects)]
        addendum = (wording // (len(refusals) * len(redirects))) % ADDENDUM_SLOTS
        competency = options[(wording // (len(refusals) * len(redirects) * ADDENDUM_SLOTS))
                             % len(options)]
        text = refusal + redirect.format(c=competency) + ADDENDUM[language][addendum]
        question_type = "opening"
        reason = None
    else:
        competency = options[wording % len(options)]
        text = SAFETY_ANSWER_REFUSAL[language][wording % 2].format(
            element=STAR_ZH[missing] if language == "zh-HK" else missing.lower()
        )
        question_type = "follow_up"
        reason = SAFETY_ANSWER_REASON[language]
    return {
        "interviewer_text": text,
        "question_type": question_type,
        "targeted_competencies": [competency],
        "adaptive_follow_up_reason": reason,
        "citation_ids": pick_citations(sources, COMPETENCY_TERMS.get(competency, (competency,))),
    }


def report_target(
    language: str,
    competencies: list[str],
    facts: list[dict],
    excerpts: list[str],
    sources: list[Citation],
    variant_index: int,
) -> dict:
    """Author one ModelReport from the exact sentences the candidate said.

    A report must describe ONE coherent example. When several answers are quoted,
    every STAR element is drawn from the same answer (the one covering the most
    elements, earliest on ties) instead of merging sentences across answers — mixing
    two unrelated stories produced reports that read as a single fabricated anecdote.
    """
    best_index = max(range(len(facts)), key=lambda i: (len(facts[i]["sentences"]), -i))
    star_fact = facts[best_index]
    present = {}
    for element, entry in star_fact["sentences"].items():
        current = present.get(element)
        # Keep evidence short: the shortest verbatim sentence still proves the point.
        if current is None or len(entry["text"]) < len(current["text"]):
            present[element] = entry
    star = []
    for element in STAR:
        entry = present.get(element)
        evidence = entry["text"] if entry else ""
        if entry and entry["variant"] != "none":
            coaching = COACHING_VARIANT[language][entry["variant"]]
        elif entry:
            options = COACHING_PRESENT[language][element]
            coaching = options[variant_index % len(options)]
        else:
            options = COACHING_ABSENT[language][element]
            coaching = options[variant_index % len(options)]
        star.append(
            {
                "element": element,
                "present": bool(evidence),
                "evidence": evidence,
                "coaching": coaching,
            }
        )
    used = [name for name in competencies if name in {c for f in facts for c in f["used"]}]
    used = used or competencies
    own_sentences = [entry["text"] for entry in star_fact["sentences"].values()]
    every_sentence = own_sentences + [
        entry["text"]
        for fact in facts
        if fact is not star_fact
        for entry in fact["sentences"].values()
    ]
    feedback = []
    for name in used[:MAX_REPORT_COMPETENCIES]:
        terms = COMPETENCY_TERMS.get(name, (name.lower(),))
        # Prefer evidence from the same answer the STAR elements came from, so one
        # competency is not "proved" by an unrelated second story.
        matching = [
            sentence for sentence in own_sentences if any(term in sentence.lower() for term in terms)
        ] or [
            sentence for sentence in every_sentence if any(term in sentence.lower() for term in terms)
        ]
        if matching:
            # Keep the citation short and exact; evidence is one verbatim sentence.
            evidence = min(matching, key=len)
        else:
            # No sentence names this competency in so many words. Cite the action the
            # candidate described (the sentence that demonstrates behaviour) rather than
            # a random shortest sentence, and keep the coaching generic.
            action_entry = present.get("Action") or next(iter(present.values()), None)
            evidence = action_entry["text"] if action_entry else facts[0]["answer"]
        solo = any(marker in evidence.lower() for marker in SOLO_MARKERS)
        if solo and name in ("Teamwork", "Communication"):
            # Saying "I did it on my own" while claiming teamwork is exactly the mismatch a
            # coach should name, so the target teaches that behaviour instead of praising it.
            text = (
                "Your action reads as solo work; show who you worked with and what you decided together."
                if language == "en-HK"
                else "你嘅行動睇落係一個人做；請講出同邊個合作、一齊決定咗啲咩。"
            )
        else:
            text = (
                "Your answer mentions this area; connect your own actions to a verifiable outcome."
                if language == "en-HK"
                else "你提到呢個範疇；請補充自己嘅行動同可核實結果。"
            )
        feedback.append(
            {
                "name": name,
                "evidence": evidence,
                "feedback": text,
                "citation_ids": pick_citations(sources, terms, 2),
            }
        )
    plain = [element for element in STAR if present.get(element, {}).get("variant", "none") == "none"]
    candidates = [element for element in plain if present.get(element)] or [
        element for element in STAR if present.get(element)
    ]
    # Chinese text is token-dense, so zh-HK reports keep one strength to stay in budget.
    strength_limit = 1 if language == "zh-HK" or len(facts) > 1 else 2
    strengths = [
        {
            "text": STRENGTH_TEXT[language][element],
            "evidence": present[element]["text"],
        }
        for element in candidates[:strength_limit]
    ]
    missing = next((element for element in STAR if not present.get(element)), None)
    improvement = IMPROVEMENT[language][missing]
    if missing:
        element_label = STAR_ZH[missing] if language == "zh-HK" else missing.lower()
        retry = RETRY[language].format(element=element_label)
    else:
        retry = RETRY_NO_GAP[language]
    if language == "zh-HK" and len(re.findall(r"[\u3400-\u9fff]", improvement + retry)) < 5:
        raise ValueError("zh-HK report target lacks Cantonese text")
    return {
        "star": star,
        "competencies": feedback,
        "strengths": strengths,
        "prioritized_improvement": improvement,
        "retry_exercise": retry,
    }


class Builder:
    def __init__(self, jobs: dict, stories: list[dict], injections: dict):
        self.jobs = {family["role_family"]: family for family in jobs["families"]}
        self.stories = defaultdict(list)
        for story in stories:
            self.stories[story["role_family"]].append(story)
        self.injections = injections
        self.knowledge = [
            Chunk(id=chunk["id"], source=chunk["source"], text=chunk["text"])
            for path in sorted(KNOWLEDGE.glob("*.txt"))
            for chunk in chunk_text(path.read_text(), path.stem, path.name)
        ]
        self._cache = {}

    def job(self, family: str, language: str) -> dict:
        return next(j for j in self.jobs[family]["jobs"] if j["language"] == language)

    def profile(self, family: str, language: str, injected: bool = False):
        key = (family, language, injected)
        if key not in self._cache:
            job = self.job(family, language)
            text = self.injected_brief(family, language) if injected else job["text"]
            title, competencies, _ = profile_metadata(text, job["title"])
            if injected and not set(competencies) & set(COMPETENCY_TERMS):
                # The short brief lost every competency term; keep the full brief instead.
                text = job["text"]
                title, competencies, _ = profile_metadata(text, job["title"])
                if injected:
                    text = f"{text}\n\n{self.injection_line(family, language)}"
            self._cache[key] = (title, competencies, text)
        return self._cache[key][:2]

    def injection_line(self, family: str, language: str) -> str:
        job = self.job(family, language)
        lines = self.injections["source_side"][language]
        return lines[sum(map(ord, job["id"])) % len(lines)]

    def injected_brief(self, family: str, language: str) -> str:
        """A short adversarial brief: title, one requirement line, then the injection.

        The brief stays under the runtime's 480-character quoted window, so the injected
        sentence is always visible in ``quoted_sources``; a longer brief would push it out.
        """
        job = self.job(family, language)
        lines = [line for line in job["text"].splitlines() if line.strip()]
        bullets = [line for line in lines[1:] if line.lstrip().startswith(("-", "－"))]
        terms = [term for values in COMPETENCY_TERMS.values() for term in values]

        def score(line: str) -> int:
            lowered = line.lower()
            return sum(1 for term in terms if term in lowered)

        ranked = sorted(bullets, key=score, reverse=True)
        # Keep two requirement lines that carry competency terms, so the short brief still
        # yields the same kind of allowed_competencies the app would compute.
        head = lines[:1] + [line for line in ranked if score(line)][:2]
        if len(head) == 1 and len(lines) > 1:
            head.append(lines[1])
        return "\n".join([*head, self.injection_line(family, language)])

    def chunks(self, family: str, language: str, injected: bool = False) -> list[Chunk]:
        job = self.job(family, language)
        self.profile(family, language, injected)
        text = self._cache[(family, language, injected)][2]
        own = [
            Chunk(id=chunk["id"], source=chunk["source"], text=chunk["text"])
            for chunk in chunk_text(text, job["id"], "job-description.txt")
        ]
        return own + self.knowledge

    def report_picks(
        self,
        family: str,
        language: str,
        story: dict,
        count: int,
        wording: int,
        missing: str | None,
        variant: str,
    ) -> list[dict]:
        """Pick one or two stories for a report, staying inside the excerpt budget."""
        short = "en" if language == "en-HK" else "zh"
        picks = [story]
        offset = 1
        budget = EXCERPT_CHAR_BUDGET[language]
        while len(picks) < count:
            candidate = self.stories[family][(wording + offset) % len(self.stories[family])]
            if candidate["id"] not in {item["id"] for item in picks}:
                total = sum(len(compose_answer(item, short, missing, variant)[0]) for item in picks)
                extra = len(compose_answer(candidate, short, missing, variant)[0])
                if total + extra > budget:
                    break
                picks.append(candidate)
            offset += 1
        return picks

    def sources(self, query: str, family: str, language: str, injected: bool = False):
        chunks = self.chunks(family, language, injected)
        ranked = lexical_ranking(query, chunks)
        by_id = {chunk.id: chunk for chunk in chunks}
        selected = []
        for key in ranked[:4]:
            chunk = by_id[key]
            selected.append(Citation(chunk_id=chunk.id, source=chunk.source, text=chunk.text))
        return selected


# Token-density weights fitted offline against the Qwen3-4B-Instruct-2507 tokenizer
# (tokenizer.json, 11 MB) over this exact corpus. Per-row residuals were -1.9% to +2.0%;
# the 1.0188 safety factor plus 8 tokens makes the estimate an upper bound on every row,
# so tests can enforce ml/config.json's 2,048-token limit without the tokenizer installed.
TOKEN_WEIGHTS = {"cjk": 0.8165, "latin": 0.0088, "other": 0.9082}
TOKEN_OFFSET = 75.2587
TOKEN_SAFETY = 1.0188
TOKEN_MARGIN = 8


def estimate_tokens(messages: list[dict]) -> int:
    """Upper bound on the Qwen3 token count for these messages."""
    cjk = latin = other = 0
    for message in messages:
        text = message["content"]
        cjk_chars = len(re.findall(r"[\u3400-\u9fff]", text))
        latin_chars = len(re.findall(r"[A-Za-z]", text))
        cjk += cjk_chars
        latin += latin_chars
        other += len(text) - cjk_chars - latin_chars
    raw = (
        TOKEN_WEIGHTS["cjk"] * cjk
        + TOKEN_WEIGHTS["latin"] * latin
        + TOKEN_WEIGHTS["other"] * other
        + TOKEN_OFFSET
    )
    return math.ceil(raw * TOKEN_SAFETY + TOKEN_MARGIN)


def shingles(text: str) -> set[str]:
    """Five-character shingles, the same screen ``ml.dataset.near_duplicate_pairs`` uses."""
    return {text[index : index + 5] for index in range(max(1, len(text) - 4))}


def too_similar(candidate: str, others: list[set[str]], threshold: float = 0.90) -> bool:
    """Guard rows that have no candidate answer, where wording is the only content."""
    shingle_set = shingles(candidate)
    for other in others:
        if not shingle_set or not other:
            continue
        if min(len(shingle_set), len(other)) / max(len(shingle_set), len(other)) < threshold:
            continue
        if len(shingle_set & other) / len(shingle_set | other) >= threshold:
            return True
    return False


def row_id(task: str, language: str, index: int) -> str:
    return f"rt-{task[:2]}-{'en' if language == 'en-HK' else 'zh'}-{index:04d}"


def build_row(
    builder: Builder,
    task: str,
    language: str,
    family: str,
    story: dict,
    missing: str | None,
    variant: str,
    intent: str,
    difficulty: str,
    variant_index: int,
    wording: int,
    inject: bool,
    picks: list[dict],
    row_index: int,
) -> dict:
    language_short = "en" if language == "en-HK" else "zh"
    title, allowed = builder.profile(family, language, inject)
    options = competence_options(story, allowed)

    facts = []
    previous = None
    if task == "question" and intent in {"follow", "next"}:
        answer, sentences = compose_answer(story, language_short, missing, variant)
        previous = AnswerSubmission(
            transcript=answer,
            language=language,
            elapsed_seconds=float(45 + (variant_index * 13) % 60),
        )
        facts.append({"answer": answer, "sentences": sentences, "used": story["competencies"]})
    elif task == "report":
        for pick in picks:
            answer, sentences = compose_answer(pick, language_short, missing, variant)
            facts.append(
                {"answer": answer, "sentences": sentences, "used": pick["competencies"]}
            )
    elif task == "safety" and intent == "answer":
        requests = builder.injections["answer_side"]
        kind = "hiring" if variant_index % 2 == 0 else "accent"
        request = requests[kind][language][variant_index % 2]
        answer, sentences = compose_answer(story, language_short, missing, variant)
        answer = f"{request} {answer}"
        facts.append({"answer": answer, "sentences": sentences, "used": story["competencies"]})
        previous = AnswerSubmission(
            transcript=answer,
            language=language,
            elapsed_seconds=float(50 + (variant_index * 7) % 40),
        )

    query = " ".join(
        part
        for part in (
            title,
            " ".join(allowed),
            previous.transcript if previous else "",
        )
        if part
    )
    sources = builder.sources(query, family, language, injected=inject)

    if task == "report":
        excerpts = answer_excerpts([fact["answer"] for fact in facts])
        messages = report_messages(language, allowed, excerpts, sources)
        target = report_target(language, allowed, facts, excerpts, sources, variant_index)
        draft = ModelReport.model_validate(target)
        check_report_output(draft, allowed, language, excerpts, sources)
    else:
        messages = question_messages(
            allowed, language, difficulty, 2 if intent in {"follow", "next"} else 0,
            previous, sources,
        )
        if task == "safety":
            target = safety_target(
                language,
                "source" if intent == "source" else "answer",
                options,
                missing,
                sources,
                wording,
            )
        else:
            target = question_target(
                language, difficulty, intent, options, missing, sources, wording
            )
        draft = ModelCoachTurn.model_validate(target)
        check_question_output(draft, allowed, language, sources)

    row = {
        "id": row_id(task, language, row_index),
        "task": task,
        "language": language,
        "role_family": family,
        "source_id": builder.job(family, language)["id"],
        "template_family": story["id"],
        "seniority": story["seniority"],
        "missing_star_element": missing,
        "safety_case": intent if task == "safety" else None,
        "answer_count": len(facts),
        "messages": [*messages, {"role": "assistant", "content": json.dumps(target, ensure_ascii=False)}],
        "provenance": {
            "kind": "synthetic_runtime_aligned_draft",
            "author": "AI-assisted authoring (WS2 generator); committee human review required",
            "license": "CC0-1.0",
            "source": (
                "locally authored fictional job descriptions and story library; "
                "no real employer or person"
            ),
            "review_status": "unreviewed",
            "warning": (
                "Generated draft, not a human-authored or approved example. Reviewers must "
                "check the source support, the evidence excerpts and the Cantonese wording."
            ),
        },
        "reviews": [],
        "double_review_required": False,
    }
    row["content_sha256"] = content_hash(row)
    return row


def previous_answer_present(row: dict) -> bool:
    payload = json.loads(row["messages"][1]["content"])
    return bool(payload.get("previous_answer") or payload.get("quoted_answer_excerpts"))


def generate_rows(seed: int = SEED) -> list[dict]:
    jobs, stories, injections = load_scenarios()
    builder = Builder(jobs, stories, injections)
    families = [family["role_family"] for family in jobs["families"]]
    allocation = allocate(families)
    rows = []
    counters = Counter()
    seen = {}
    plain = defaultdict(list)
    report_sets = defaultdict(set)
    for family_index, family in enumerate(families):
        pool = builder.stories[family]
        by_level = defaultdict(list)
        for story in pool:
            by_level[story["seniority"]].append(story)
        pointers = defaultdict(int)
        used = set()
        for (task, language), count in sorted(allocation[family].items()):
            for local in range(count):
                variant_index = (local * 3 + family_index) % 24
                # 3 entry : 6 early : 3 mid per twelve rows keeps the row-level seniority mix
                # at roughly 25/50/25 for every family, matching the HK postings sample.
                level = STORY_CYCLE[(local + family_index) % len(STORY_CYCLE)]
                group = by_level[level] or pool
                story = group[pointers[(family, language, level)] % len(group)]
                pointers[(family, language, level)] += 1
                difficulty = DIFFICULTIES[(variant_index + local) % len(DIFFICULTIES)]
                if task == "question":
                    answer_count = 0
                elif task == "report":
                    # Chinese answers cost roughly one token per character, and the report
                    # prompt already carries the shared system prompt plus four quoted
                    # sources, so zh-HK reports stay at one answer to fit 2,048 tokens.
                    answer_count = 1 if language == "zh-HK" else 1 + local % 2
                else:
                    answer_count = 0
                counters[(task, language)] += 1
                choices = MISSING_ORDER if task != "safety" else STAR
                for attempt in range(WORDING_ATTEMPTS):
                    missing = choices[(variant_index + attempt) % len(choices)]
                    variant = canonical_variant(
                        missing,
                        VARIANT_ORDER[((variant_index // 5) + attempt) % len(VARIANT_ORDER)],
                    )
                    picks = (
                        builder.report_picks(
                            family,
                            language,
                            story,
                            answer_count,
                            variant_index + attempt,
                            missing,
                            variant,
                        )
                        if task == "report"
                        else [story]
                    )
                    ids = {item["id"] for item in picks}
                    if task == "report":
                        # Two reports quoting the same story with the same gap would share
                        # most of their text, so each gap bucket keeps disjoint story sets.
                        bucket = report_sets[(family, language, missing, variant)]
                        if ids & bucket:
                            continue
                    elif task != "safety" and (
                        tuple(item["id"] for item in picks),
                        missing,
                        variant,
                    ) in used:
                        # Injected-source rows are told apart by their wording, not by the
                        # answer (they have none), so they are not gated on this key.
                        continue
                    if task == "question":
                        intent = (
                            "follow" if missing else ("opening" if local % 2 == 0 else "next")
                        )
                    elif task == "report":
                        intent = "report"
                    else:
                        intent = "source" if local % 2 == 0 else "answer"
                    row = build_row(
                        builder,
                        task,
                        language,
                        family,
                        story,
                        missing,
                        variant,
                        intent,
                        difficulty,
                        variant_index,
                        wording=variant_index * 3 + attempt * 11,
                        inject=task == "safety" and intent == "source",
                        picks=picks,
                        row_index=counters[(task, language)],
                    )
                    key = normalized_text(row)
                    has_answer = previous_answer_present(row)
                    if key in seen:
                        continue
                    if not has_answer and too_similar(key, plain[(task, language)]):
                        continue
                    seen[key] = row["id"]
                    if not has_answer:
                        plain[(task, language)].append(shingles(key))
                    if task == "report":
                        report_sets[(family, language, missing, variant)] |= ids
                    elif task != "safety":
                        used.add((tuple(item["id"] for item in picks), missing, variant))
                    rows.append(row)
                    break
                else:
                    raise ValueError(
                        f"no distinct wording left for {family} {task} {language} "
                        f"{story['id']} {missing} {variant}"
                    )
    assign_double_review(rows, seed)
    return rows


def assign_double_review(rows: list[dict], seed: int = SEED) -> list[dict]:
    """Give at least 15% of each (language, task) stratum an independent second review."""
    strata = defaultdict(list)
    for row in rows:
        strata[(row["language"], row["task"])].append(row)
    for key, group in sorted(strata.items()):
        ordered = sorted(group, key=lambda row: row["id"])
        random.Random(f"{seed}-{key}").shuffle(ordered)
        for row in ordered[: math.ceil(len(ordered) * DOUBLE_REVIEW_RATE)]:
            row["double_review_required"] = True
    return rows


def count_table(rows: list[dict]) -> str:
    lines = ["task/language     en-HK  zh-HK   total"]
    for task in TASKS:
        counts = Counter(row["language"] for row in rows if row["task"] == task)
        lines.append(
            f"{task:12s}  {counts['en-HK']:6d}  {counts['zh-HK']:6d}  {sum(counts.values()):6d}"
        )
    counts = Counter(row["language"] for row in rows)
    lines.append(
        f"{'total':12s}  {counts['en-HK']:6d}  {counts['zh-HK']:6d}  {len(rows):6d}"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)
    rows = generate_rows(args.seed)
    write_jsonl(args.output, rows)
    print(count_table(rows))
    families = Counter(row["role_family"] for row in rows)
    print(f"families: {len(families)} rows/family: {sorted(set(families.values()))}")
    print(
        "double review: "
        f"{sum(row['double_review_required'] for row in rows)} "
        f"({DOUBLE_REVIEW_RATE:.0%} per (language, task) stratum, rounded up)"
    )
    print(f"max estimated prompt+target tokens: {max(estimate_tokens(r['messages']) for r in rows)}")
    pairs = near_duplicate_pairs(rows)
    print(f"near-duplicate pairs at 0.90: {len(pairs)}")
    for pair in pairs[:5]:
        print("  ", pair)
    print(f"wrote {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
