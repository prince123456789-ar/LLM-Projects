from pydantic import BaseModel, Field


class EmbedLeadCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    message: str | None = None
    property_type: str | None = Field(default=None, max_length=50)
    location: str | None = Field(default=None, max_length=120)
    budget: float | None = None
    timeline: str | None = Field(default=None, max_length=80)
    page_url: str | None = Field(default=None, max_length=500)
    referrer: str | None = Field(default=None, max_length=500)


class EmbedKeyResponse(BaseModel):
    id: int
    masked_key: str
    install_script_url: str
    install_snippet: str
    dev_snippet: str | None = None
