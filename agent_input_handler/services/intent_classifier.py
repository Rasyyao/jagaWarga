import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from shared.enums import IntentLabel
from shared.schemas import IntentResult
from shared.config import get_settings

settings = get_settings()

MODEL_PATH = settings.CLASSIFIER_MODEL_PATH  # ./models/indobert-intent
MAX_LENGTH = 128

_tokenizer = None
_model = None

def _get_model():
    global _tokenizer, _model
    if _tokenizer is None or _model is None:
        print(f"Loading IndoBERT dari: {MODEL_PATH}")
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
        _model.eval()
    return _tokenizer, _model


# ── Classifier ─────────────────────────────────────────────────────────────────
def classify_intent(text: str) -> IntentResult:
    tokenizer, model = _get_model()

    inputs = tokenizer(
        text,
        max_length=MAX_LENGTH,
        truncation=True,
        padding=True,
        return_tensors="pt",
    )

    with torch.no_grad():
        outputs = model(**inputs)
        probs = F.softmax(outputs.logits, dim=-1).squeeze()

    id2label = model.config.id2label

    scores = {
        id2label[i]: round(probs[i].item(), 4)
        for i in range(len(id2label))
    }

    best_label_str = max(scores, key=scores.get)
    best_score = scores[best_label_str]

    try:
        best_label = IntentLabel(best_label_str)
    except ValueError:
        best_label = IntentLabel.TIDAK_RELEVAN

    return IntentResult(
        label=best_label,
        confidence=best_score,
        all_scores=scores,
    )


def should_drop(result: IntentResult) -> bool:
    DROP_LABELS = {IntentLabel.TIDAK_RELEVAN, IntentLabel.SPAM}

    if result.label in DROP_LABELS:
        return result.confidence >= settings.CLASSIFIER_DROP_THRESHOLD

    if result.confidence < settings.CLASSIFIER_CONFIDENCE_THRESHOLD:
        return True

    return False