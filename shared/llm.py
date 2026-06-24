from typing import List, Dict

import httpx

from .config import get_settings


def _call_openai_compatible(messages: List[Dict[str, str]], temperature: float) -> str:
    settings = get_settings()
    base_url = settings.LLM_BASE_URL.rstrip("/")
    response = httpx.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.LLM_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.LLM_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": settings.LLM_MAX_TOKENS,
        },
        timeout=settings.LLM_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def _call_groq(messages: List[Dict[str, str]], temperature: float) -> str:
    from groq import Groq

    settings = get_settings()
    client = Groq(api_key=settings.LLM_API_KEY)
    completion = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=settings.LLM_MAX_TOKENS,
    )
    return completion.choices[0].message.content


def call_llm(messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
    settings = get_settings()
    provider = settings.LLM_PROVIDER.lower().replace("_", "-")
    if provider in {"deepseek", "openai-compatible", "openai"}:
        return _call_openai_compatible(messages, temperature)
    if provider == "groq":
        return _call_groq(messages, temperature)
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")
