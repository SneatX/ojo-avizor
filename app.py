"""Ojo Avizor: chatbot de ciberseguridad con un Transformer entrenado + Gradio.

Uso:
    python app.py            # abre en http://127.0.0.1:7860
    python app.py --share    # además crea un enlace público temporal (útil en Colab)

Si el modelo no está entrenado todavía, lo entrena primero (2-5 minutos en CPU).
"""
from __future__ import annotations

import argparse
import html

import gradio as gr

from cerebro import NOMBRES, SALUDO, Estado, responder
from config import NOMBRE
from modelo import CARPETA_MODELO, Clasificador, entrenar, modelo_existe
from senales import proteger

EJEMPLOS = [
    "Me llegó un correo de soporte-udes@gmail.com que dice que mi cuenta será suspendida en 24 horas",
    "Revisa este link: http://bit.ly/beca-udes-2026",
    "Un número nuevo dice que es mi primo, que cambió de celular y me pide plata urgente",
    "Ya puse mi contraseña en esa página, ¿qué hago?",
    "Le pasé a alguien el código de 6 dígitos que me llegó por SMS",
    "Alguien inició sesión en mi correo y no fui yo",
    "¿Cómo creo una contraseña segura?",
]

COLOR_RIESGO = {"alto": ("#c23a52", "Riesgo alto"), "medio": ("#c97a12", "Riesgo medio"),
                "bajo": ("#1f8a54", "Riesgo bajo")}

CSS = """
.gradio-container {max-width: 1120px !important; margin: auto !important}
#cabecera {background: linear-gradient(118deg,#23366f,#3f3594 60%,#5b45c2); color: #fff;
           border-radius: 18px; padding: 20px 24px}
#cabecera h1 {color: #fff; margin: 0 0 4px; font-size: 26px}
#cabecera p {color: #e4e6ff; margin: 0}
.riesgo {border-radius: 14px; padding: 12px 14px; color: #fff; font-weight: 700}
.riesgo small {display: block; font-weight: 400; opacity: .9; margin-top: 2px}
.sin-riesgo {border: 1px dashed var(--border-color-primary); border-radius: 14px; padding: 12px 14px;
             color: var(--body-text-color-subdued)}
"""


def tarjeta_riesgo(nivel: str | None, senales: list, ya_cai: bool = False) -> str:
    if ya_cai:
        return ('<div class="riesgo" style="background:#a9640f">Modo «ya caí»'
                '<small>Sigue los pasos: contener, preservar la evidencia y reportar.</small></div>')
    if not nivel:
        return ('<div class="sin-riesgo">Aún no hay evaluación. Aparece cuando cuentas un caso y '
                'respondes si ya hiciste clic, diste datos o enviaste dinero.</div>')
    color, texto = COLOR_RIESGO[nivel]
    return (f'<div class="riesgo" style="background:{color}">{texto}'
            f'<small>{len(senales)} señal(es) encontrada(s) en lo que escribiste</small></div>')


def lista_senales(senales: list) -> str:
    if not senales:
        return "_Sin señales todavía. Pega el remitente, el enlace o el texto del mensaje para revisarlo._"
    return "\n".join(f"- {html.escape(s.texto)}" for s in senales)


def construir_app(clf: Clasificador) -> gr.Blocks:
    def conversar(mensaje, historial, estado):
        historial = list(historial or [])
        estado = estado or Estado()
        mensaje = (mensaje or "").strip()
        if not mensaje:
            return historial, estado, gr.update(), gr.update(), gr.update(), ""
        probs = clf.probabilidades(mensaje)
        r = responder(mensaje, probs, estado)
        visible, _ = proteger(mensaje)  # nunca mostramos de vuelta una contraseña
        historial += [{"role": "user", "content": visible}, {"role": "assistant", "content": r.texto}]
        etiquetas = {NOMBRES.get(k, k): v for k, v in list(probs.items())[:5]}
        return (historial, estado, etiquetas, tarjeta_riesgo(r.riesgo, r.senales, r.modo_ya_cai),
                lista_senales(r.senales), "")

    def reiniciar():
        return ([{"role": "assistant", "content": SALUDO}], Estado(), None,
                tarjeta_riesgo(None, []), lista_senales([]), "")

    with gr.Blocks(title=NOMBRE, css=CSS, theme=gr.themes.Soft(primary_hue="indigo")) as demo:
        gr.HTML(f'<div id="cabecera"><h1>👁️ {NOMBRE}</h1><p>Chatbot de ciberseguridad para la comunidad '
                'UDES. Escríbele con tus palabras: un Transformer entrenado interpreta tu mensaje.</p></div>')
        estado = gr.State(Estado())
        with gr.Row(equal_height=False):
            with gr.Column(scale=3, min_width=320):
                chat = gr.Chatbot(value=[{"role": "assistant", "content": SALUDO}], type="messages",
                                  height=520, show_label=False)
                with gr.Row():
                    entrada = gr.Textbox(placeholder="Cuéntame qué pasó… (nunca escribas tu contraseña)",
                                         show_label=False, scale=5, autofocus=True, max_length=2000)
                    enviar = gr.Button("Enviar", variant="primary", scale=1, min_width=90)
                gr.Examples(EJEMPLOS, inputs=entrada, label="Prueba con un ejemplo")
                limpiar = gr.Button("↺ Nueva conversación", variant="secondary")
            with gr.Column(scale=2, min_width=260):
                gr.Markdown("### Lo que entendió el modelo")
                intenciones = gr.Label(num_top_classes=5, show_label=False)
                gr.Markdown("### Nivel de riesgo")
                riesgo = gr.HTML(tarjeta_riesgo(None, []))
                gr.Markdown("### Señales encontradas")
                senales = gr.Markdown(lista_senales([]))
                gr.Markdown("<sub>Ojo Avizor orienta con base en señales; no confirma ataques. "
                            "La confirmación la da el canal oficial (Soporte TI de la UDES).</sub>")

        salidas = [chat, estado, intenciones, riesgo, senales, entrada]
        enviar.click(conversar, [entrada, chat, estado], salidas)
        entrada.submit(conversar, [entrada, chat, estado], salidas)
        limpiar.click(reiniciar, None, salidas)
    return demo


def main():
    p = argparse.ArgumentParser(description="Lanza Ojo Avizor")
    p.add_argument("--share", action="store_true", help="crea un enlace público temporal (Colab)")
    p.add_argument("--port", type=int, default=7860)
    p.add_argument("--host", default="127.0.0.1", help="usa 0.0.0.0 para abrirlo desde otra máquina")
    p.add_argument("--reentrenar", action="store_true", help="vuelve a entrenar antes de abrir")
    a = p.parse_args()

    if a.reentrenar or not modelo_existe():
        print("No hay modelo entrenado: entrenando el Transformer (2-5 min en CPU)...")
        entrenar()
    print(f"Cargando modelo desde {CARPETA_MODELO} ...")
    demo = construir_app(Clasificador())
    demo.queue().launch(server_name=a.host, server_port=a.port, share=a.share, show_error=True)


if __name__ == "__main__":
    main()
