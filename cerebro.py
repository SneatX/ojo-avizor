"""Cerebro de conversación de Ojo Avizor.

Recibe lo que escribió la persona y las probabilidades del Transformer, recuerda
el contexto (qué situación es, qué señales van, si ya contestó si cayó) y arma
la respuesta.

Reglas que se cumplen siempre:
  * Nunca afirma que algo "es un ataque": habla de señales y nivel de riesgo.
  * Toda recomendación cierra remitiendo al canal oficial.
  * Nunca pide contraseñas y oculta las que alguien escriba por error.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from config import DENUNCIA, NOMBRE, SOPORTE_TI, UMBRAL_CONFIANZA
from modelo import normalizar
from senales import Senal, analizar, nivel_riesgo, proteger

NOMBRES = {
    "saludo": "Saludo", "despedida": "Despedida", "fuera_de_tema": "Fuera de tema",
    "afirmacion": "Respuesta: sí", "negacion": "Respuesta: no",
    "correo_sospechoso": "Correo sospechoso", "enlace_sospechoso": "Enlace sospechoso",
    "suplantacion_mensaje": "Suplantación (WhatsApp/SMS)", "archivo_malware": "Archivo o virus",
    "acceso_no_autorizado": "Acceso a mi cuenta", "prevencion": "Consejos de prevención",
    "cai_credenciales": "Ya caí: di datos", "cai_dinero": "Ya caí: envié dinero",
    "cai_codigo": "Ya caí: di un código", "abri_sin_datos": "Abrí sin dar datos",
}
SITUACIONES = {"correo_sospechoso", "enlace_sospechoso", "suplantacion_mensaje"}
CAIDAS = {"cai_credenciales", "cai_dinero", "cai_codigo"}

CIERRE = (f"\n\n<sub>Esto es una orientación basada en señales, no un diagnóstico. "
          f"La confirmación la da el canal oficial: {SOPORTE_TI}.</sub>")
CIERRE_SUAVE = f"\n\n<sub>Ante cualquier duda con tus cuentas, el canal oficial es {SOPORTE_TI}.</sub>"
PISTA_MINIMA = 0.15  # probabilidad desde la que se toma en cuenta una posible "ya caí"

INTRO = {
    "correo_sospechoso": "Gracias por preguntar antes de actuar. Con los correos, lo que más delata un engaño es "
                         "**el remitente, la prisa y a dónde lleva el enlace**.",
    "enlace_sospechoso": "Bien hecho en no confiar a ciegas. Con los enlaces importa **por dónde llegó, quién lo "
                         "mandó y a qué dominio lleva de verdad**.",
    "suplantacion_mensaje": "Ese tipo de mensaje es muy común. Lo clave es **si el número es nuevo, quién dice ser "
                            "y qué te pide**.",
}
PIDE_DETALLES = {
    "correo_sospechoso": "Si quieres, **pega aquí la dirección completa del remitente, el asunto y el enlace** "
                         "(copiando el texto, sin abrirlo). Nunca pegues tu contraseña.",
    "enlace_sospechoso": "Si quieres, **pega el enlace tal cual** (cópialo sin abrirlo) y dime por dónde te llegó.",
    "suplantacion_mensaje": "Si quieres, **pega el texto del mensaje** y cuéntame si el número lo tenías guardado.",
}
PREGUNTA_CLAVE = {
    "correo_sospechoso": "Antes de seguir: **¿ya hiciste clic, escribiste tu contraseña o respondiste con tus datos?**",
    "enlace_sospechoso": "Antes de seguir: **¿ya lo abriste? Y si lo abriste, ¿escribiste algo o descargaste algo?**",
    "suplantacion_mensaje": "Antes de seguir: **¿ya respondiste, enviaste dinero o compartiste algún código?**",
}
RECOMENDACION = {
    ("correo_sospechoso", "alto"): "No hagas clic ni respondas. Entra tú mismo al portal escribiendo la dirección "
                                   "oficial a mano y reenvía el correo a soporte TI para que lo revisen. Después, bórralo de la bandeja de entrada solo cuando soporte te lo diga.",
    ("correo_sospechoso", "medio"): "Hay señales para desconfiar. No uses el enlace del correo: si necesitas revisar "
                                    "tu cuenta, entra escribiendo la dirección oficial y, ante la duda, consulta a soporte TI.",
    ("correo_sospechoso", "bajo"): "No veo señales fuertes, pero eso no lo vuelve seguro. Si te pide hacer algo con "
                                   "tu cuenta, hazlo entrando tú al portal oficial, no desde el correo.",
    ("enlace_sospechoso", "alto"): "No lo abras. Si necesitas ese servicio, búscalo escribiendo la dirección oficial a "
                                   "mano. Reporta el mensaje y, si llegó por un grupo, avisa a los demás.",
    ("enlace_sospechoso", "medio"): "Mejor no abrirlo. Llega al sitio por tu cuenta (escribiendo la dirección o desde la "
                                    "app oficial) y confirma con quien te lo envió por otro medio.",
    ("enlace_sospechoso", "bajo"): "No veo señales fuertes. Aun así, abre solo si esperabas ese enlace y confirmaste "
                                   "con quien lo envió. Recuerda: el candado (HTTPS) no garantiza que el sitio sea legítimo.",
    ("suplantacion_mensaje", "alto"): "No envíes nada. Llama a la persona **a su número de siempre** para confirmar. "
                                      "El código de verificación no se comparte con nadie. Toma capturas del chat y "
                                      "del número antes de bloquear y reportar.",
    ("suplantacion_mensaje", "medio"): "Desconfía hasta confirmar: llama a la persona a su número de siempre o hazle una "
                                       "pregunta que solo ella sabría. No envíes dinero ni códigos mientras tanto.",
    ("suplantacion_mensaje", "bajo"): "No veo señales fuertes, pero si te piden dinero, datos o códigos, confirma siempre "
                                      "por llamada al número que ya conocías.",
}
NIVEL_TXT = {"alto": "🔴 **Riesgo alto**", "medio": "🟠 **Riesgo medio**", "bajo": "🟢 **Riesgo bajo**"}

PRESERVAR = ("**Guarda la evidencia** (no la borres): toma capturas completas, guarda el correo o el número "
             "del remitente, la fecha y la hora, y el enlace tal como llegó. Eso es lo que necesitan soporte "
             "y las autoridades.")
REPORTAR = f"Avisa a {SOPORTE_TI} y, si hubo pérdida de dinero o datos, denuncia en {DENUNCIA}."

YA_CAI = {
    "cai_credenciales": [
        "**Cambia esa contraseña ya, desde otro equipo o celular de confianza.** Si la usas en otras cuentas, "
        "cámbiala también allá.",
        "**Cierra todas las sesiones abiertas** y activa la verificación en dos pasos.",
        "Si diste datos de tarjeta, **llama a tu banco** para bloquearla.",
    ],
    "cai_dinero": [
        "**Llama de inmediato a tu banco o billetera** (Nequi, Daviplata…) y pide que intenten frenar o "
        "reversar la transferencia. Mientras más rápido, mejor.",
        "No envíes más dinero aunque te prometan devolverlo o te presionen.",
    ],
    "cai_codigo": [
        "**Intenta recuperar la cuenta ya**: vuelve a registrar tu número en WhatsApp (o en el servicio del código) "
        "para sacar al otro.",
        "**Activa la verificación en dos pasos** con un PIN que solo tú sepas.",
        "Avisa a tus contactos por otro medio que no respondan pedidos de dinero desde tu cuenta.",
    ],
    "archivo_malware": [
        "**Desconecta el equipo de internet** (wifi o cable) para cortar la comunicación del programa.",
        "**No lo apagues ni lo formatees** antes de hablar con soporte: se perdería evidencia útil.",
        "No pagues ningún rescate. Desde **otro equipo**, cambia las contraseñas importantes.",
    ],
    "acceso_no_autorizado": [
        "**Cambia la contraseña desde un dispositivo de confianza** y cierra todas las sesiones abiertas.",
        "**Activa la verificación en dos pasos** y revisa el correo/teléfono de recuperación y las reglas de "
        "reenvío (a veces el intruso deja una).",
        "Si no puedes entrar, usa la opción oficial de recuperación de cuenta del servicio.",
        "Avisa a tus contactos que ignoren mensajes raros enviados desde tu cuenta.",
    ],
}
TITULO_YA_CAI = {
    "cai_credenciales": "Diste tus datos o tu contraseña",
    "cai_dinero": "Enviaste dinero",
    "cai_codigo": "Compartiste un código",
    "archivo_malware": "Posible archivo malicioso en tu equipo",
    "acceso_no_autorizado": "Posible acceso indebido a tu cuenta",
}

PREVENCION = [
    (r"contrasen|clave|password|gestor|administrador", "**Contraseñas fuertes**\n\n"
     "- Usa una frase larga (12+ caracteres), por ejemplo cuatro palabras al azar.\n"
     "- Una contraseña distinta para cada cuenta, sobre todo para el correo.\n"
     "- Un gestor de contraseñas (Bitwarden, por ejemplo) te las recuerda.\n"
     "- Cámbiala si sospechas que alguien la vio; no hace falta cambiarla cada mes."),
    (r"dos pasos|dos factores|2fa|doble|autenticacion", "**Verificación en dos pasos**\n\n"
     "- Agrega un segundo paso además de la contraseña (app autenticadora o código).\n"
     "- En WhatsApp: Ajustes → Cuenta → Verificación en dos pasos → crea un PIN.\n"
     "- En Google/Microsoft: Seguridad → Verificación en dos pasos.\n"
     "- Nunca compartas los códigos que te lleguen, ni con quien diga ser soporte."),
    (r"evidencia|custodia|guardo|captura", "**Cómo guardar evidencia**\n\n"
     "- No borres el mensaje, correo o chat.\n"
     "- Capturas completas que muestren número/remitente, fecha y hora.\n"
     "- En correos, guarda el mensaje original (en Gmail: ⋮ → Descargar mensaje).\n"
     "- Anota qué pasó y cuándo. La *cadena de custodia* es documentar quién tuvo la evidencia y "
     "cuándo, para que no se dude de ella."),
    (r"denunci|reporto|reportar|donde", f"**Dónde reportar**\n\n- Incidentes con cuentas de la universidad: {SOPORTE_TI}.\n"
     f"- Fraudes y delitos informáticos: {DENUNCIA}.\n- Si hubo dinero de por medio: tu banco, de inmediato."),
    (r"whatsapp", "**Protege tu WhatsApp**\n\n- Activa la verificación en dos pasos con PIN.\n"
     "- Nunca compartas el código de 6 dígitos que llega por SMS.\n"
     "- Si alguien \"cambió de número\" y pide plata, llámalo a su número de siempre."),
]
PREVENCION_GENERAL = ("**Tres hábitos que evitan la mayoría de engaños**\n\n"
                      "1. **Desconfía de la prisa**: \"urgente\", \"24 horas\" o \"tu cuenta se cierra\" buscan que "
                      "no pienses.\n2. **Llega tú al sitio**: escribe la dirección oficial en vez de usar el enlace "
                      "que te mandaron.\n3. **Confirma por otro canal**: llama a la persona o a la entidad al número "
                      "que ya conocías.\n\nTambién puedo explicarte contraseñas seguras, verificación en dos pasos o "
                      "cómo guardar evidencia.")

SALUDO = (f"¡Hola! Soy **{NOMBRE}** 👁️. Te ayudo a revisar si un **correo, un enlace o un mensaje** se ve "
          "sospechoso y, si ya caíste en algo, te digo qué hacer paso a paso.\n\n"
          "Cuéntame con tus palabras qué pasó. Puedes pegar el remitente, el enlace o el texto del mensaje. "
          "**Nunca escribas tu contraseña**: no la necesito.")


@dataclass
class Estado:
    situacion: str | None = None
    senales: dict = field(default_factory=dict)  # id -> (texto, peso)
    decision: str | None = None                  # None | "no" | "si"
    esperando: str | None = None                 # "decision" | "que_hiciste" | None
    ultimo_plan: str | None = None
    pista_caida: str | None = None               # "ya caí" que el modelo intuyó con baja confianza

    def lista_senales(self) -> list[Senal]:
        return [Senal(i, t, p) for i, (t, p) in self.senales.items()]


@dataclass
class Respuesta:
    texto: str
    intencion: str
    confianza: float
    probabilidades: dict
    riesgo: str | None
    senales: list
    oculto_sensible: bool
    modo_ya_cai: bool = False


def _riesgo_md(estado: Estado) -> tuple[str, str]:
    senales = estado.lista_senales()
    nivel, puntos = nivel_riesgo(senales)
    if senales:
        detalle = "\n".join(f"- {s.texto}" for s in senales)
        texto = f"{NIVEL_TXT[nivel]} ({len(senales)} señal{'es' if len(senales) != 1 else ''}):\n\n{detalle}"
    else:
        texto = (f"{NIVEL_TXT[nivel]} con lo que me contaste: no veo señales concretas todavía. "
                 "Si pegas el remitente, el enlace o el texto del mensaje, lo reviso con más detalle.")
    return texto, nivel


def _plan_ya_cai(tipo: str, estado: Estado) -> str:
    pasos = YA_CAI[tipo]
    contener = "\n".join(f"- {p}" for p in pasos)
    estado.ultimo_plan = tipo
    estado.esperando = None
    return (f"Tranquilo/a, todavía se puede **contener el daño**. Mucha gente cae en esto; lo importante es "
            f"actuar rápido y sin borrar nada.\n\n### {TITULO_YA_CAI[tipo]}\n\n**1. Contener**\n\n{contener}\n\n"
            f"**2. Preservar.** {PRESERVAR}\n\n**3. Reportar.** {REPORTAR}")


def _evaluar(estado: Estado) -> tuple[str, str]:
    riesgo_txt, nivel = _riesgo_md(estado)
    sit = estado.situacion or "correo_sospechoso"
    rec = RECOMENDACION[(sit, nivel)]
    return f"{riesgo_txt}\n\n**Qué te recomiendo:** {rec}", nivel


def responder(texto: str, probabilidades: dict, estado: Estado) -> Respuesta:
    """Decide la respuesta a partir del texto, las probabilidades del modelo y el contexto."""
    texto_mostrable, oculto = proteger(texto)
    intencion, confianza = next(iter(probabilidades.items()))
    nuevas = analizar(texto)
    plano = normalizar(texto)

    # Respuestas cortas ("sí", "no") solo tienen sentido con contexto.
    if estado.esperando and confianza < UMBRAL_CONFIANZA:
        top2 = list(probabilidades)[:2]
        for alt in top2:
            if alt in {"afirmacion", "negacion", "abri_sin_datos"} | CAIDAS:
                intencion = alt
                break

    # Si la persona pega evidencia (enlaces, remitentes) en medio de la charla, no hay que reiniciar.
    hay_evidencia = bool(nuevas) and (estado.situacion is not None)
    if hay_evidencia and intencion in {"afirmacion", "negacion", "fuera_de_tema", "saludo"} and len(plano) > 25:
        intencion = estado.situacion

    for s in nuevas:
        estado.senales[s.id] = (s.texto, s.peso)

    riesgo = None
    partes: list[str] = []
    cerrar = True
    cierre = CIERRE
    plan = False

    if oculto:
        partes.append("🔒 **Oculté lo que parecía una contraseña, un código o una tarjeta.** No lo compartas con "
                      "nadie, ni conmigo. Si era real, cámbialo cuanto antes.")

    if confianza < UMBRAL_CONFIANZA and intencion == next(iter(probabilidades)) and not hay_evidencia:
        a, b = list(probabilidades)[:2]
        partes.append(f"No estoy seguro de haberte entendido. ¿Me hablas de **{NOMBRES[a].lower()}** o de "
                      f"**{NOMBRES[b].lower()}**? Cuéntamelo con un poco más de detalle, por ejemplo: "
                      "*\"me llegó un correo de soporte que pide mi clave\"* o *\"ya le mandé plata a un número\"*.")
        cerrar = False

    elif intencion == "saludo":
        partes.append(SALUDO)
        cerrar = False

    elif intencion == "despedida":
        partes.append("¡Con gusto! Recuerda: **desconfía de la prisa, llega tú al sitio y confirma por otro "
                      "canal.** Si algo vuelve a parecer raro, aquí estoy.")
        cierre = CIERRE_SUAVE

    elif intencion == "fuera_de_tema":
        partes.append("Eso se sale de lo mío 😅. Yo solo ayudo con **seguridad digital**: correos, enlaces o "
                      "mensajes sospechosos, cuentas robadas, virus, o qué hacer si ya caíste en algo. "
                      "¿Te pasó algo así?")
        cerrar = False

    elif intencion in SITUACIONES:
        if estado.situacion != intencion:
            estado.situacion = intencion
            estado.decision = None
            estado.senales = {s.id: (s.texto, s.peso) for s in nuevas}
        # ¿El modelo intuye que además ya cayó? Lo recordamos para no volver a preguntar.
        caida = max(CAIDAS, key=lambda c: probabilidades.get(c, 0))
        estado.pista_caida = caida if probabilidades.get(caida, 0) >= PISTA_MINIMA else None
        if estado.decision == "no":
            ev, riesgo = _evaluar(estado)
            partes.append("Gracias, con eso reviso mejor.\n\n" + ev)
        else:
            if nuevas:
                partes.append(INTRO[intencion] + "\n\nYa noto esto en lo que me contaste:\n\n" +
                              "\n".join(f"- {s.texto}" for s in nuevas))
            else:
                partes.append(INTRO[intencion])
            partes.append(PIDE_DETALLES[intencion])
            partes.append(PREGUNTA_CLAVE[intencion])
            estado.esperando = "decision"
            cerrar = False

    elif intencion == "negacion":
        if estado.situacion:
            estado.decision = "no"
            estado.esperando = None
            ev, riesgo = _evaluar(estado)
            partes.append("¡Bien! Llegaste a tiempo 👍.\n\n" + ev)
        else:
            partes.append("Listo. Cuéntame qué te llegó o qué pasó y lo revisamos juntos.")
            cerrar = False

    elif intencion == "afirmacion":
        if estado.esperando == "decision" and estado.pista_caida:
            # Ya lo había dicho en su primer mensaje: no le preguntamos otra vez.
            partes.append(_plan_ya_cai(estado.pista_caida, estado))
            plan = True
            estado.decision = "si"
        elif estado.esperando in ("decision", "que_hiciste") or estado.situacion:
            estado.decision = "si"
            estado.esperando = "que_hiciste"
            partes.append("Entiendo. Para darte los pasos correctos, dime **qué hiciste exactamente**: ¿escribiste "
                          "tu contraseña o datos, enviaste dinero, compartiste un código, descargaste algo, o solo "
                          "abriste el enlace sin escribir nada?")
            cerrar = False
        else:
            partes.append("¿Me cuentas un poco más? Por ejemplo, qué te llegó y qué hiciste.")
            cerrar = False

    elif intencion in CAIDAS or intencion in ("archivo_malware", "acceso_no_autorizado"):
        estado.decision = "si"
        # "ya caí" suelto, sin más detalle: preguntar qué pasó si no se sabe.
        if intencion == "cai_credenciales" and re.fullmatch(r"(creo que )?ya cai( en algo)?|me estafaron", plano):
            estado.esperando = "que_hiciste"
            partes.append("Tranquilo/a, vamos a contener el daño. Dime **qué pasó exactamente**: ¿escribiste tu "
                          "contraseña o datos, enviaste dinero, compartiste un código o descargaste algo?")
            cerrar = False
        else:
            partes.append(_plan_ya_cai(intencion, estado))
            plan = True
            if estado.senales:
                riesgo = nivel_riesgo(estado.lista_senales())[0]

    elif intencion == "abri_sin_datos":
        estado.decision = "si"
        estado.esperando = "que_hiciste"
        partes.append("Abrir un enlace sin escribir nada **suele ser de bajo impacto**, así que tranquilo/a:\n\n"
                      "- Cierra la pestaña y no vuelvas a entrar.\n- No descargues ni instales nada que te ofrezca.\n"
                      "- Revisa en los próximos días si llegan alertas de inicio de sesión raras.\n\n"
                      "Una pregunta para estar seguros: **¿se descargó algo o llegaste a escribir algún dato?**")

    elif intencion == "prevencion":
        tema = next((t for p, t in PREVENCION if re.search(p, plano)), PREVENCION_GENERAL)
        partes.append(tema)
        cierre = CIERRE_SUAVE

    texto_resp = "\n\n".join(partes)
    if cerrar:
        texto_resp += cierre
    return Respuesta(texto=texto_resp, intencion=intencion, confianza=confianza,
                     probabilidades=probabilidades, riesgo=riesgo,
                     senales=estado.lista_senales(), oculto_sensible=oculto,
                     modo_ya_cai=plan)
