from enum import StrEnum


class RunStatus(StrEnum):
    PENDING = "pending"
    SUBMISSION_UNKNOWN = "submission_unknown"
    SUBMISSION_FAILED = "submission_failed"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class RunResult(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
