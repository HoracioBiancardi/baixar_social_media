from pydantic import BaseModel, HttpUrl, field_validator


class DownloadRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def url_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("URL não pode ser vazia.")
        return v.strip()
