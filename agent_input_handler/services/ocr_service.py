import base64
import os
from groq import Groq
from shared.config import get_settings
from PIL import Image
import io

settings = get_settings()

_client: Groq | None = None

MAX_SIZE_BYTES = 4 * 1024 * 1024
MAX_HEIGHT = 720

def get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.LLM_API_KEY)
    return _client

OCR_PROMPT = (
    "Extract all text visible in this image. "
    "Output ONLY the raw text, no explanations, no formatting, no bullet points. "
    "Keep the original language, do not translate."
)

def compress_image(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")
    
    w, h = img.size
    if h > MAX_HEIGHT:
        scale = MAX_HEIGHT / h
        new_w = int(w * scale)
        img = img.resize((new_w, MAX_HEIGHT), Image.LANCZOS)
        
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    result = buffer.getvalue()
    
    if len(result) <= MAX_SIZE_BYTES:
        return result

    for quality in [75, 60, 50, 35, 20]:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        result = buffer.getvalue()
        
        if len(result) <= MAX_SIZE_BYTES:
            break
        
    return result

def _image_to_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")

async def extract_text(image_bytes: bytes) -> str:
    image_bytes = compress_image(image_bytes)
    
    b64 = _image_to_base64(image_bytes)
    
    completion = get_client().chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": OCR_PROMPT,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}"
                        },
                    },
                ],
            }
        ],
        temperature=0,        
        max_completion_tokens=2048,
        top_p=1,
        stream=False,
        stop=None,
    )

    return completion.choices[0].message.content.strip()


async def extract_text_from_url(image_url: str) -> str:
    """Extract teks dari image URL langsung."""
    completion = get_client().chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": OCR_PROMPT,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url,
                        },
                    },
                ],
            }
        ],
        temperature=0,
        max_completion_tokens=2048,
        top_p=1,
        stream=False,
        stop=None,
    )

    return completion.choices[0].message.content.strip()