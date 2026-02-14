from pydantic import BaseModel, Field


class EmbedChatMessageRequest(BaseModel):
    conversation_id: int | None = None
    message: str = Field(min_length=1, max_length=4000)
    page_url: str | None = Field(default=None, max_length=500)
    referrer: str | None = Field(default=None, max_length=500)


class EmbedPropertySuggestion(BaseModel):
    id: int
    title: str
    location: str
    price: float
    image_url: str | None = None


class EmbedChatMessageResponse(BaseModel):
    conversation_id: int
    reply: str
    lead_id: int | None = None
    recommendations: list[EmbedPropertySuggestion] = []

