import os
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    DataCollatorWithPadding,
)
import torch

# ── Config ─────────────────────────────────────────────────────────────────────
BASE_MODEL   = "indobenchmark/indobert-base-p1"
DATASET_PATH = "./data/intent_dataset.csv"
OUTPUT_DIR   = "./models/indobert-intent"
MAX_LENGTH   = 128
BATCH_SIZE   = 16
EPOCHS       = 10
LR           = 2e-5

LABELS = [
    "laporan_penipuan",
    "laporan_hoaks",
    "laporan_pengaduan_layanan",
    "tidak_relevan",
    "spam",
]
LABEL2ID = {l: i for i, l in enumerate(LABELS)}
ID2LABEL = {i: l for i, l in enumerate(LABELS)}

# ── Device ─────────────────────────────────────────────────────────────────────
if torch.backends.mps.is_available():
    device = "mps"
elif torch.cuda.is_available():
    device = "cuda"
else:
    device = "cpu"
print(f"Using device: {device}")

# ── Load dataset ───────────────────────────────────────────────────────────────
df = pd.read_csv(DATASET_PATH)
df = df.dropna(subset=["text", "label"])
df = df[df["label"].isin(LABELS)]
df = df.drop_duplicates(subset=["text"])

print(f"\nDataset loaded: {len(df)} rows")
print(df["label"].value_counts())

train_df, val_df = train_test_split(
    df,
    test_size=0.2,
    stratify=df["label"],
    random_state=42,
)
print(f"\nTrain: {len(train_df)} | Val: {len(val_df)}")

train_dataset = Dataset.from_pandas(train_df.reset_index(drop=True))
val_dataset   = Dataset.from_pandas(val_df.reset_index(drop=True))

# ── Tokenizer ──────────────────────────────────────────────────────────────────
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

def preprocess(examples):
    tokenized = tokenizer(
        examples["text"],
        max_length=MAX_LENGTH,
        truncation=True,
        padding=False,
    )
    tokenized["labels"] = [LABEL2ID[l] for l in examples["label"]]
    return tokenized

train_dataset = train_dataset.map(preprocess, batched=True, remove_columns=["text", "label"])
val_dataset   = val_dataset.map(preprocess, batched=True, remove_columns=["text", "label"])

for col in ["__index_level_0__"]:
    if col in train_dataset.column_names:
        train_dataset = train_dataset.remove_columns([col])
    if col in val_dataset.column_names:
        val_dataset = val_dataset.remove_columns([col])

# ── Model ──────────────────────────────────────────────────────────────────────
model = AutoModelForSequenceClassification.from_pretrained(
    BASE_MODEL,
    num_labels=len(LABELS),
    id2label=ID2LABEL,
    label2id=LABEL2ID,
)

# ── Training args ──────────────────────────────────────────────────────────────
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    per_device_eval_batch_size=BATCH_SIZE,
    warmup_ratio=0.1,
    weight_decay=0.01,
    learning_rate=LR,
    eval_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="accuracy",
    logging_steps=10,
    fp16=False,
    report_to="none",
)

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    acc = accuracy_score(labels, preds)
    return {"accuracy": acc}

# ── Train ──────────────────────────────────────────────────────────────────────
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=val_dataset,
    processing_class=tokenizer,    
    data_collator=DataCollatorWithPadding(tokenizer),
    compute_metrics=compute_metrics,
)

print("\nStarting training...")
trainer.train()

# ── Save ───────────────────────────────────────────────────────────────────────
trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print(f"\nModel saved to: {OUTPUT_DIR}")

# ── Evaluation ─────────────────────────────────────────────────────────────────
print("\n=== Classification Report ===")
preds_output = trainer.predict(val_dataset)
pred_labels  = np.argmax(preds_output.predictions, axis=-1)
true_labels  = [LABEL2ID[l] for l in val_df["label"].tolist()]

print(classification_report(true_labels, pred_labels, target_names=LABELS))
print(f"Overall Accuracy: {accuracy_score(true_labels, pred_labels)*100:.2f}%")