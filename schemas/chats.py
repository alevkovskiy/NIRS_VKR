import re
from pathlib import PurePath

from pydantic import BaseModel, Field, field_validator, model_validator

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
TEXT_EXTENSIONS = {".log", ".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml"}


class ChatCreate(BaseModel):
    title: str = Field(default="Новый чат", min_length=1, max_length=200)
    run_id: int | None = Field(default=None, gt=0)


class TextAttachment(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    text: str

    @field_validator("name")
    @classmethod
    def filename(cls, value: str) -> str:
        if (
            PurePath(value).suffix.lower() not in TEXT_EXTENSIONS
            or "/" in value
            or "\\" in value
            or re.search(r"[\x00-\x1f\x7f\ud800-\udfff]", value)
        ):
            raise ValueError("Выберите текстовый файл поддерживаемого формата.")
        return value

    @field_validator("text")
    @classmethod
    def utf8_text(cls, value: str) -> str:
        if len(value) > MAX_ATTACHMENT_BYTES:
            raise ValueError("Файл слишком большой. Максимум 10 МБ.")
        if not value.strip() or re.search(
            r"[\x00-\x08\x0b\x0c\x0e-\x1a\x1c-\x1f\ud800-\udfff]", value
        ):
            raise ValueError("Файл должен содержать непустой текст в UTF-8.")
        if len(value.encode("utf-8")) > MAX_ATTACHMENT_BYTES:
            raise ValueError("Файл слишком большой. Максимум 10 МБ.")
        return value


class MessageCreate(BaseModel):
    content: str = ""
    attachment: TextAttachment | None = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if len(value.strip()) > 6000:
            raise ValueError("Сообщение слишком большое. Максимум 6 000 символов.")
        return value.strip()

    @model_validator(mode="after")
    def require_message(self):
        if not self.content and self.attachment is None:
            raise ValueError("Введите сообщение или прикрепите файл.")
        if not self.content:
            self.content = "Проанализируй приложенный файл и кратко объясни результат."
        return self
