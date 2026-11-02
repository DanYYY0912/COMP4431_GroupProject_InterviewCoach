from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Language = Literal["en-HK", "zh-HK"]
State = Literal[
    "setup",
    "ready",
    "listening",
    "transcribing",
    "thinking",
    "speaking",
    "paused",
    "completed",
    "error",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Citation(StrictModel):
    chunk_id: str
    source: str
    text: str


class CoachTurn(StrictModel):
    interviewer_text: str = Field(min_length=1, max_length=4000)
    question_type: Literal["opening", "behavioral", "technical", "follow_up", "closing"]
    targeted_competencies: list[str] = Field(max_length=8)
    adaptive_follow_up_reason: str | None
    citations: list[Citation] = Field(max_length=4)


class ClientSpeechMetrics(StrictModel):
    pause_count: int | None = Field(default=None, ge=0, le=1000)
    silence_seconds: float | None = Field(default=None, ge=0, le=3600)


class AnswerSubmission(StrictModel):
    turn_id: str | None = Field(default=None, max_length=64)
    transcript: str = Field(min_length=1, max_length=12000)
    language: Language
    elapsed_seconds: float = Field(ge=0, le=3600)
    corrected: bool = False
    speech_metrics: ClientSpeechMetrics | None = None

    @field_validator("transcript")
    @classmethod
    def reject_silence(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("An answer cannot be empty. Type an answer or skip this question.")
        return value.strip()


class Turn(StrictModel):
    id: str
    question: CoachTurn
    answer: AnswerSubmission | None
    created_at: str


class ProfileInput(StrictModel):
    text: str = Field(min_length=20, max_length=100000)
    title: str | None = Field(default=None, max_length=160)


class Profile(StrictModel):
    id: str
    title: str
    competencies: list[str]
    warnings: list[str]
    sources: list[Citation]


class SessionInput(StrictModel):
    job_profile_id: str = Field(min_length=1, max_length=64)
    language: Language = "en-HK"
    difficulty: Literal["foundation", "standard", "stretch"] = "standard"
    question_count: Literal[3, 5, 8] = 5
    store_transcript: Literal[True]


class Session(StrictModel):
    id: str
    job_profile_id: str
    role_title: str
    language: Language
    difficulty: str
    question_count: int
    state: State
    current_question: int
    turns: list[Turn]
    created_at: str
    provider: str


class Control(StrictModel):
    action: Literal["pause", "resume", "skip", "retry", "end", "cancel"]


class AnswerEvent(StrictModel):
    version: Literal[1]
    type: Literal["answer"]
    payload: AnswerSubmission


class ControlEvent(StrictModel):
    version: Literal[1]
    type: Literal["control"]
    payload: Control


ClientEvent = Annotated[AnswerEvent | ControlEvent, Field(discriminator="type")]


class StarEvidence(StrictModel):
    element: Literal["Situation", "Task", "Action", "Result"]
    present: bool
    evidence: str
    coaching: str


class CompetencyFeedback(StrictModel):
    name: str
    evidence: str
    feedback: str
    citations: list[Citation]


class SpeechMetrics(StrictModel):
    word_count: int
    duration_seconds: float
    words_per_minute: float | None
    filler_count: int
    pause_count: int | None
    silence_seconds: float | None
    answer_count: int


class SessionReport(StrictModel):
    session_id: str
    role_title: str
    language: Language
    summary: str
    star: list[StarEvidence]
    competencies: list[CompetencyFeedback]
    strengths: list[str]
    prioritized_improvement: str
    retry_exercise: str
    speech_metrics: SpeechMetrics
    citations: list[Citation]
    limitations: list[str]


class SpeechConsent(StrictModel):
    consent: Literal[True]
