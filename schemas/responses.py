from datetime import datetime

from pydantic import BaseModel, ConfigDict

from models.enums import RunResult, RunStatus


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRead(ReadModel):
    id: int
    email: str


class TokenRead(BaseModel):
    access_token: str
    token_type: str


class IdRead(BaseModel):
    id: int


class PipelineRead(ReadModel):
    id: int
    name: str
    description: str
    default_branch: str


class ChatSummary(ReadModel):
    id: int
    title: str
    run_id: int | None
    created_at: datetime
    last_activity_at: datetime


class MessageRead(ReadModel):
    id: int
    role: str
    content: str
    created_at: datetime


class ChatRead(ChatSummary):
    messages: list[MessageRead]


class AssistantMessage(BaseModel):
    role: str
    content: str


class MessageReply(BaseModel):
    assistant_message: AssistantMessage


class JobRead(ReadModel):
    id: int
    run_id: int
    name: str
    status: str
    result: str | None
    started_at: datetime | None
    finished_at: datetime | None


class ArtifactRead(ReadModel):
    id: int
    name: str


class RunSummary(ReadModel):
    id: int
    name: str
    pipeline_id: int
    pipeline_name: str
    status: RunStatus
    result: RunResult | None
    branch: str
    commit_sha: str | None
    submission_error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RunRead(RunSummary):
    jobs: list[JobRead]
    artifacts: list[ArtifactRead]
