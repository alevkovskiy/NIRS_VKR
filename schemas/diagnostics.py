from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.chats import Diagnosis, TextAttachment
from schemas.responses import ReadModel

RequestId = Annotated[str, Field(pattern=r"^[a-zA-Z0-9-]{16,36}$")]
Outcome = Literal["passed", "failed", "inconclusive"]
DiagnosticStatus = Literal["open", "resolved"]


class DiagnosticCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    request_id: RequestId
    title: str = Field(min_length=1, max_length=120)
    diagnosis: Diagnosis
    attachment: TextAttachment | None = None
    run_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_evidence(self):
        if not (self.diagnosis.observed or self.attachment or self.run_id):
            raise ValueError("Добавьте наблюдение, журнал или связанный прогон.")
        return self


class CheckCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    request_id: RequestId
    name: str = Field(min_length=1, max_length=120)
    outcome: Outcome
    note: str = Field(default="", max_length=1000)


class StandSnapshot(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    check_id: RequestId
    bench: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    outcome: Outcome
    note: str = Field(default="", max_length=1000)
    measured_at: datetime


class RepeatRun(BaseModel):
    request_id: RequestId


class StatusUpdate(BaseModel):
    status: DiagnosticStatus


class DiagnosticSummary(ReadModel):
    id: int
    title: str
    bench: str
    status: DiagnosticStatus
    created_at: datetime


class CheckRead(ReadModel):
    id: int
    name: str
    outcome: Outcome
    source: Literal["manual", "stand", "ci"]
    note: str
    run_id: int | None
    recorded_at: datetime


class DiagnosticRead(DiagnosticSummary):
    environment: str
    steps: str
    expected: str
    observed: str
    chat_id: int
    run_id: int | None
    log_name: str | None
    log_excerpt: str | None
    stand_available: bool
    checks: list[CheckRead]
