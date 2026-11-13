"""Entrenamiento y uso del Transformer que interpreta los mensajes.

El modelo es un clasificador de INTENCIONES: lee lo que escribe la persona y
devuelve una probabilidad para cada intención (correo_sospechoso, cai_dinero,
negacion, ...). La lógica de conversación (cerebro.py) decide qué responder a
partir de esas probabilidades.
"""
from __future__ import annotations

import json
import os
import random
import unicodedata
from pathlib import Path

os.environ.setdefault("WANDB_DISABLED", "true")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent
CARPETA_MODELO = RAIZ / "modelo_entrenado"
MODELO_BASE = os.environ.get("OJO_MODELO_BASE", "distilbert-base-multilingual-cased")
SEED = 42
MAX_LEN = 96


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y sin espacios repetidos.

    Así 'Recibí un CORREO' y 'recibi un correo' se ven igual para el modelo,
    que es importante porque mucha gente escribe sin tildes desde el celular.
    """
    texto = unicodedata.normalize("NFD", str(texto).lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return " ".join(texto.split())


def cargar_datos() -> pd.DataFrame:
    from datos import INTENCIONES

    filas = [(t, intencion) for intencion, frases in INTENCIONES.items() for t in frases]
    df = pd.DataFrame(filas, columns=["texto", "intencion"])
    extra = RAIZ / "datos" / "extra.csv"
    if extra.exists():  # frases que agreguen ustedes, sin tocar el código
        df = pd.concat([df, pd.read_csv(extra, encoding="utf-8-sig")[["texto", "intencion"]]])
    df["texto"] = df["texto"].map(normalizar)
    return df.drop_duplicates("texto").reset_index(drop=True)


def entrenar(epocas: int = 12, verbose: bool = True) -> dict:
    """Entrena el Transformer y lo guarda en modelo_entrenado/. Devuelve métricas."""
    import torch
    from datasets import Dataset
    from sklearn.metrics import accuracy_score, classification_report, f1_score
    from sklearn.model_selection import train_test_split
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                              DataCollatorWithPadding, Trainer, TrainingArguments)
    from transformers.utils import logging as hf_logging

    hf_logging.set_verbosity_error()
    random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)

    df = cargar_datos()
    etiquetas = sorted(df["intencion"].unique())
    a_id = {e: i for i, e in enumerate(etiquetas)}
    df["label"] = df["intencion"].map(a_id)

    train_df, val_df = train_test_split(df, test_size=0.15, stratify=df["label"], random_state=SEED)
    if verbose:
        print(f"Ejemplos: {len(df)} | intenciones: {len(etiquetas)} | "
              f"entrenamiento: {len(train_df)} | validación: {len(val_df)}")
        print(f"Modelo base: {MODELO_BASE} | dispositivo: {'GPU' if torch.cuda.is_available() else 'CPU'}")

    tok = AutoTokenizer.from_pretrained(MODELO_BASE)

    def a_dataset(tabla):
        ds = Dataset.from_pandas(tabla[["texto", "label"]].reset_index(drop=True), preserve_index=False)
        return ds.map(lambda b: tok(b["texto"], truncation=True, max_length=MAX_LEN), batched=True)

    modelo = AutoModelForSequenceClassification.from_pretrained(
        MODELO_BASE, num_labels=len(etiquetas),
        id2label={i: e for e, i in a_id.items()}, label2id=a_id)

    def metricas(p):
        pred = np.argmax(p.predictions, axis=1)
        return {"accuracy": accuracy_score(p.label_ids, pred),
                "f1_macro": f1_score(p.label_ids, pred, average="macro", zero_division=0)}

    args = TrainingArguments(
        output_dir=str(RAIZ / ".checkpoints"), num_train_epochs=epocas, learning_rate=5e-5,
        per_device_train_batch_size=16, per_device_eval_batch_size=32, warmup_ratio=0.1,
        weight_decay=0.01, eval_strategy="epoch", save_strategy="no", logging_strategy="epoch",
        report_to="none", seed=SEED, fp16=torch.cuda.is_available(), dataloader_num_workers=0,
        disable_tqdm=not verbose)
    trainer = Trainer(model=modelo, args=args, train_dataset=a_dataset(train_df),
                      eval_dataset=a_dataset(val_df), processing_class=tok,
                      data_collator=DataCollatorWithPadding(tok), compute_metrics=metricas)
    trainer.train()

    CARPETA_MODELO.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(CARPETA_MODELO)
    tok.save_pretrained(CARPETA_MODELO)

    resultado = {"modelo_base": MODELO_BASE, "ejemplos": len(df), "epocas": epocas,
                 "validacion": {k: round(float(v), 3) for k, v in trainer.evaluate().items()
                                if k in ("eval_accuracy", "eval_f1_macro")}}

    # Prueba honesta: frases escritas de otra forma, que el modelo nunca vio.
    clf = Clasificador(CARPETA_MODELO)
    prueba = RAIZ / "datos" / "prueba_frases_nuevas.csv"
    if prueba.exists():
        pdf = pd.read_csv(prueba, encoding="utf-8-sig")
        pred = [clf.predecir(t)[0] for t in pdf["texto"]]
        resultado["frases_nuevas"] = {
            "accuracy": round(accuracy_score(pdf["intencion"], pred), 3),
            "f1_macro": round(f1_score(pdf["intencion"], pred, average="macro", zero_division=0), 3),
            "total": len(pdf)}
        errores = [(t, r, p) for t, r, p in zip(pdf["texto"], pdf["intencion"], pred) if r != p]
        resultado["errores_frases_nuevas"] = errores
        if verbose:
            print("\nReporte con frases NUEVAS (nunca vistas en el entrenamiento):")
            print(classification_report(pdf["intencion"], pred, zero_division=0))
            print(f"Errores ({len(errores)}):")
            for t, r, p in errores:
                print(f"  - '{t}'  esperaba {r}, predijo {p}")

    (CARPETA_MODELO / "metricas.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado


class Clasificador:
    """Carga el Transformer entrenado y predice intenciones."""

    def __init__(self, carpeta: Path | str = CARPETA_MODELO):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        from transformers.utils import logging as hf_logging

        hf_logging.set_verbosity_error()
        self._torch = torch
        self.tok = AutoTokenizer.from_pretrained(carpeta)
        self.modelo = AutoModelForSequenceClassification.from_pretrained(carpeta)
        self.modelo.eval()
        self.etiquetas = [self.modelo.config.id2label[i] for i in range(self.modelo.config.num_labels)]

    def probabilidades(self, texto: str) -> dict[str, float]:
        entrada = self.tok(normalizar(texto), return_tensors="pt", truncation=True, max_length=MAX_LEN)
        with self._torch.no_grad():
            logits = self.modelo(**entrada).logits[0]
        probs = self._torch.softmax(logits, dim=-1).tolist()
        return dict(sorted(zip(self.etiquetas, probs), key=lambda x: -x[1]))

    def predecir(self, texto: str) -> tuple[str, float]:
        intencion, prob = next(iter(self.probabilidades(texto).items()))
        return intencion, prob


def modelo_existe() -> bool:
    return (CARPETA_MODELO / "config.json").exists()
