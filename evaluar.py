"""Mide qué tan bien entiende el modelo frases que nunca vio.

Uso:
    python evaluar.py                          # evalúa modelo_entrenado/
    python evaluar.py --modelo otra_carpeta    # para comparar versiones
"""
import argparse
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

from modelo import CARPETA_MODELO, RAIZ, Clasificador

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--modelo", default=str(CARPETA_MODELO))
    p.add_argument("--errores", action="store_true", help="muestra cada frase mal clasificada")
    a = p.parse_args()
    clf = Clasificador(a.modelo)
    total_ok = total = 0
    for archivo in sorted((RAIZ / "datos").glob("prueba_frases_nuevas*.csv")):
        d = pd.read_csv(archivo, encoding="utf-8-sig")
        pred = [clf.predecir(t)[0] for t in d["texto"]]
        acc = accuracy_score(d["intencion"], pred)
        f1 = f1_score(d["intencion"], pred, average="macro", zero_division=0)
        total_ok += sum(r == q for r, q in zip(d["intencion"], pred)); total += len(d)
        print(f"{archivo.name:32s} accuracy {acc:.3f} | F1 {f1:.3f} | {len(d)} frases")
        if a.errores:
            for t, r, q in zip(d["texto"], d["intencion"], pred):
                if r != q:
                    print(f"    - '{t}'  esperaba {r}, predijo {q}")
    print(f"{'TOTAL':32s} accuracy {total_ok / total:.3f} ({total_ok}/{total})  [{Path(a.modelo).name}]")
