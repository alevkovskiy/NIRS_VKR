from pydantic import BaseModel, Field, field_validator


class ChatCreate(BaseModel):
    title: str = Field(default="Новый чат", min_length=1, max_length=200)
    run_id: int | None = Field(default=None, gt=0)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=6000)

    @field_validator("content")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Сообщение не должно быть пустым")
        return value.strip()
