import logging
import uuid
from typing import Any, Literal, cast
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from groq import AsyncGroq
from app.config import settings
from app.services.agent import run_agent

log = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])

_PLAIN_CHAT_SYSTEM_PROMPT = "You are JobScout's assistant, having a general conversation with the user."
_MAX_PLAIN_MESSAGES = 20
_MAX_PLAIN_MESSAGE_CHARS = 4000


class ChatRequest(BaseModel):
    message: str
    thread_id: str = ""


class PlainMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=_MAX_PLAIN_MESSAGE_CHARS)


class PlainChatRequest(BaseModel):
    messages: list[PlainMessage] = Field(max_length=_MAX_PLAIN_MESSAGES)


@router.post("/chat")
async def chat(request: ChatRequest):
    thread_id = request.thread_id or str(uuid.uuid4())
    try:
        response = await run_agent(request.message, thread_id)
    except Exception:
        log.exception("agent chat failed", extra={"thread_id": thread_id})
        raise HTTPException(status_code=500, detail="The assistant hit an error. Please try again.") from None
    return {"response": response, "thread_id": thread_id}


@router.post("/plain")
async def plain_chat(request: PlainChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")
    client = AsyncGroq(api_key=settings.api_key)
    messages = [{"role": "system", "content": _PLAIN_CHAT_SYSTEM_PROMPT}]
    messages += [{"role": m.role, "content": m.content} for m in request.messages]
    completion = await client.chat.completions.create(
        model="openai/gpt-oss-120b",
        max_tokens=1000,
        reasoning_effort="low",
        messages=cast(Any, messages),
    )
    return {"response": completion.choices[0].message.content or ""}
