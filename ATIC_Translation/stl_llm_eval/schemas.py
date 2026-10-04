from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class TranslationDecision(BaseModel):
    """Provider-neutral structured response."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["translate", "clarify", "abstain"]
    stl: str | None
    defect_types: list[str]
    clarification_question: str | None
    assumptions: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class ProviderResult(BaseModel):
    """Normalized result returned by every provider adapter."""

    model_config = ConfigDict(extra="allow")

    decision: TranslationDecision
    raw_response: dict | str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    request_id: str | None = None
