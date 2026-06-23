from typing import List, Dict
from groq import Groq
from .config import get_settings


def call_llm(messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
    settings = get_settings()
    client = Groq(api_key=settings.LLM_API_KEY)
    completion = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=1024,
    )
    return completion.choices[0].message.content
