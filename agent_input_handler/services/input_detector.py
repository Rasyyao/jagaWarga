import re
from shared.enums import InputType

URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)

def detect_input_type(text: str | None, mime_type: str | None) -> InputType:
    if mime_type and "image" in mime_type:
        return InputType.IMAGE
    
    if text and URL_PATTERN.search(text):
        return InputType.LINK
    
    return InputType.TEXT

def extract_url(text:str) -> str | None:
    match = URL_PATTERN.search(text or "")
    return match.group(0) if match else None

