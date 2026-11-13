"""Entrena el Transformer de Ojo Avizor y muestra qué tan bien entiende.

Uso:
    python entrenar.py              # 12 épocas (recomendado)
    python entrenar.py --epocas 6   # más rápido en un computador lento
"""
import argparse
import time

from modelo import CARPETA_MODELO, entrenar

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Entrena el modelo de Ojo Avizor")
    p.add_argument("--epocas", type=int, default=12)
    a = p.parse_args()
    inicio = time.time()
    r = entrenar(epocas=a.epocas)
    print("\n================ RESUMEN ================")
    print(f"Validación      : accuracy {r['validacion'].get('eval_accuracy')} | "
          f"F1 {r['validacion'].get('eval_f1_macro')}")
    if "frases_nuevas" in r:
        fn = r["frases_nuevas"]
        print(f"Frases nuevas   : accuracy {fn['accuracy']} | F1 {fn['f1_macro']} ({fn['total']} frases)")
    print(f"Tiempo          : {(time.time() - inicio) / 60:.1f} min")
    print(f"Modelo guardado : {CARPETA_MODELO}")
    print("Ahora ejecuta:  python app.py")
