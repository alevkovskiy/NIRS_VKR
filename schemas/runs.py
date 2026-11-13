from pydantic import BaseModel, Field, field_validator

from models.enums import RunResult, RunStatus

__all__ = ["RunCreate", "RunResult", "RunStatus"]


class RunCreate(BaseModel):
    branch: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("branch")
    @classmethod
    def valid_branch(cls, value):
        if value and (
            any(c.isspace() for c in value)
            or ".." in value
            or value.startswith("-")
            or "@{" in value
        ):
            raise ValueError("Некорректное имя ветки")
        return value
