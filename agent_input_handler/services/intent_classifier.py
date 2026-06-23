import csv
import os
import numpy as np
from sentence_transformers import SentenceTransformer
from shared.enums import IntentLabel
from shared.schemas import IntentResult
from shared.config import get_settings

settings = get_settings()

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_model: SentenceTransformer | None = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


DATASET_PATH = os.path.join(
    os.path.dirname(__file__),    
    "..", "..", "data",           
    "intent_dataset.csv"
)

def load_label_examples() -> dict[IntentLabel, list[str]]:
    """
    Baca intent_dataset.csv, kelompokkan teks per label.
    Format CSV: text,label
    """
    examples: dict[IntentLabel, list[str]] = {label: [] for label in IntentLabel}

    with open(DATASET_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row.get("text", "").strip()
            label_str = row.get("label", "").strip()

            if not text or not label_str:
                continue  # skip baris kosong

            try:
                label = IntentLabel(label_str)
                examples[label].append(text)
            except ValueError:
                continue  

    return examples

_label_embeddings: dict[IntentLabel, np.ndarray] | None = None

def _get_label_embeddings() -> dict[IntentLabel, np.ndarray]:
    global _label_embeddings
    if _label_embeddings is not None:
        return _label_embeddings

    model = get_model()
    label_examples = load_label_examples()
    _label_embeddings = {}

    for label, examples in label_examples.items():
        if not examples:
            continue
        embeddings = model.encode(examples, normalize_embeddings=True)
        mean_embedding = embeddings.mean(axis=0)
        mean_embedding = mean_embedding / (np.linalg.norm(mean_embedding) + 1e-10)
        _label_embeddings[label] = mean_embedding

    return _label_embeddings


def classify_intent(text: str) -> IntentResult:
    model = get_model()
    label_embeddings = _get_label_embeddings()

    input_embedding = model.encode(text, normalize_embeddings=True)

    scores: dict[str, float] = {}
    for label, label_emb in label_embeddings.items():
        similarity = float(np.dot(input_embedding, label_emb))
        scores[label.value] = round(similarity, 4)

    best_label_value = max(scores, key=scores.get)
    best_score = scores[best_label_value]
    best_label = IntentLabel(best_label_value)

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