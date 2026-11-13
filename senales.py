"""Revisa el texto que pega la persona y encuentra señales de riesgo concretas.

El Transformer entiende la intención ("me llegó un correo raro"). Este módulo
mira la evidencia: dominios, enlaces, adjuntos y frases típicas de engaño. Las
señales suman puntos y los puntos dan el nivel de riesgo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from config import DOMINIOS_OFICIALES
from modelo import normalizar


@dataclass(frozen=True)
class Senal:
    id: str
    texto: str
    peso: int  # 2 = señal fuerte, 1 = señal moderada


ACORTADORES = ("bit.ly", "tinyurl.com", "cutt.ly", "is.gd", "t.co", "goo.gl", "ow.ly",
               "rebrand.ly", "shorturl.at", "acortar.link", "rb.gy", "t.ly", "tiny.cc", "s.id")
HOSTING_GRATIS = ("ngrok", "trycloudflare.com", "loca.lt", "serveo", "000webhost", "weebly",
                  "wixsite.com", "blogspot.", "firebaseapp.com", "web.app", "netlify.app",
                  "vercel.app", "glitch.me", "repl.co", "github.io", "pages.dev", "sites.google.com",
                  "forms.gle", "typeform.com", "jotform")
EXT_PELIGROSAS = ("exe", "scr", "zip", "rar", "7z", "js", "vbs", "bat", "cmd", "iso", "apk",
                  "msi", "docm", "xlsm", "pptm", "html", "htm", "lnk")

RE_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"')]+|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|co|net|org|ly|info|xyz|top|site|online|link|app|io|me|gl|at|gd|edu\.co|gov\.co)(?:/[^\s<>\"')]*)?",
                    re.IGNORECASE)
RE_EMAIL = re.compile(r"[a-z0-9._%+-]+@([a-z0-9.-]+\.[a-z]{2,})", re.IGNORECASE)

FRASES = [
    Senal("urgencia", "Mete prisa o amenaza (\"24 horas\", \"será suspendida\", \"urgente\").", 1),
    Senal("pide_credenciales", "Pide contraseña, usuario o que \"verifiques\" tu cuenta.", 2),
    Senal("pide_codigo", "Pide un código de verificación, clave dinámica u OTP.", 2),
    Senal("pide_dinero", "Pide dinero, una transferencia o una recarga.", 2),
    Senal("cambio_numero", "Dice que \"cambió de número\" o escribe desde un número nuevo.", 1),
    Senal("evita_llamada", "Evita llamada o videollamada y solo quiere chatear.", 1),
    Senal("saludo_generico", "Saludo genérico (\"estimado usuario\") en vez de tu nombre.", 1),
    Senal("premio", "Promete premios, regalos u ofertas demasiado buenas.", 1),
    Senal("macros", "Pide habilitar macros o \"habilitar contenido\".", 2),
    Senal("candado", "Se confía en el candado (HTTPS): solo indica conexión cifrada, no que el sitio sea legítimo.", 1),
    Senal("datos_bancarios", "Pide datos de tarjeta o de cuenta bancaria.", 2),
]
_PATRONES = {
    "urgencia": r"\b(urgente|inmediat\w*|24 ?h(oras)?|48 ?h(oras)?|hoy mismo|ultimo aviso|de lo contrario|"
                r"sera (suspendid|desactivad|bloquead|cerrad|eliminad)\w*|se (bloquea|suspende|desactiva|cierra)\w*|"
                r"vence hoy|plazo|antes de que)",
    "pide_credenciales": r"\b(pid\w*|solicit\w*|ingres\w*|confirm\w*|verific\w*|actualiz\w*|valid\w*|digit\w*)\b"
                         r"(\s+\w+){0,5}\s+(contrasen\w*|clave|credencial\w*|usuario|cuenta|datos)",
    "pide_codigo": r"\b(pid\w*|pas\w*|envi\w*|mand\w*|dame|solicit\w*|comparte|compartir|dicta\w*)\b(\s+\w+){0,5}\s+"
                   r"(codigo|clave dinamica|otp|token|pin|\d ?digitos)",
    "pide_dinero": r"\b(pid\w*|necesit\w*|prest\w*|consign\w*|transfi\w*|gir\w*|mand\w*|envi\w*|pag\w*)\b(\s+\w+){0,5}\s+"
                   r"(plata|dinero|transferencia|consignacion|nequi|daviplata|recarga|giro|pago|envio)",
    "cambio_numero": r"(cambie de (numero|celular|cel)|nuevo numero|numero nuevo|mi otro numero|"
                     r"guardame este|este es mi nuevo|numero (que no (tengo|tenia)|desconocido))",
    "evita_llamada": r"(no puedo (hablar|contestar|llamar)|no (quiere|acepta) (llamada|videollamada|hacer videollamada)|"
                     r"solo por (chat|mensaje)|sin videollamada|niega a (llamar|hacer videollamada))",
    "saludo_generico": r"(estimad[oa] (usuari|client|estudiant)\w*|querid[oa] usuari\w*|apreciad[oa] usuari\w*)",
    "premio": r"\b(ganaste|gano|ganador\w*|premio|regalo|gratis|sorteo|beneficiari\w*|bono|subsidio|iphone)\b",
    "macros": r"(habilit\w* (las )?macros|habilit\w* (el )?contenido|activar macros)",
    "candado": r"(tiene (el )?candado|con candado|tiene https|es https)",
    "datos_bancarios": r"(numero de (la )?tarjeta|datos (de (la|mi|su) )?(tarjeta|cuenta bancaria)|cvv|codigo de seguridad de la tarjeta)",
}


def _dominio(url: str) -> tuple[str, bool]:
    """Devuelve (dominio, usa_truco_arroba)."""
    if not re.match(r"https?://", url, re.I):
        url = "http://" + url
    parte = urlsplit(url)
    netloc = parte.netloc.lower()
    arroba = "@" in netloc
    host = netloc.rsplit("@", 1)[-1].split(":")[0]
    return host, arroba


def es_oficial(host: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in DOMINIOS_OFICIALES)


def imita_oficial(host: str) -> bool:
    """udes-edu.co, udess.edu.co, soporte.udes.com, ud3s... imitan sin ser oficiales."""
    if es_oficial(host):
        return False
    plano = host.replace("3", "e").replace("0", "o").replace("1", "l")
    return any(d.split(".")[0] in plano for d in DOMINIOS_OFICIALES)


def analizar(texto: str) -> list[Senal]:
    """Lista de señales encontradas en el texto (sin repetir)."""
    encontradas: dict[str, Senal] = {}
    plano = normalizar(texto)
    menciona_institucion = bool(re.search(r"\b(udes|universidad|institucional|aula extendida|rectoria|"
                                          r"soporte|mesa de ayuda|biblioteca)\b", plano))

    def add(s: Senal):
        encontradas.setdefault(s.id, s)

    # Primero los enlaces con http(s)://: así "http://udes.edu.co@malo.com" se trata como enlace
    # (truco del @) y no como un correo electrónico.
    con_esquema = re.findall(r"https?://[^\s<>\"')]+", texto, re.IGNORECASE)
    resto = re.sub(r"https?://[^\s<>\"')]+", " ", texto, flags=re.IGNORECASE)

    for email_dom in RE_EMAIL.findall(resto):
        dom = email_dom.lower()
        if imita_oficial(dom):
            add(Senal("remitente_imita", f"El remitente usa «{dom}», que imita el dominio oficial sin serlo.", 2))
        elif not es_oficial(dom) and menciona_institucion:
            add(Senal("remitente_externo", f"Dice ser de la institución pero escribe desde «{dom}».", 2))

    sin_correos = RE_EMAIL.sub(" ", resto)  # el dominio de un remitente no es un enlace
    for url in con_esquema + RE_URL.findall(sin_correos):
        host, arroba = _dominio(url)
        if not host:
            continue
        if arroba:
            add(Senal("truco_arroba", f"El enlace usa el truco del @: en realidad lleva a «{host}».", 2))
        if any(host == a or host.endswith("." + a) for a in ACORTADORES):
            add(Senal("acortador", f"Enlace acortado ({host}): oculta el destino real.", 1))
        if any(h in host for h in HOSTING_GRATIS):
            add(Senal("hosting_gratis", f"Página en un servicio gratuito o túnel ({host}).", 1))
        if host.startswith("xn--") or ".xn--" in host:
            add(Senal("punycode", f"Dominio con caracteres disfrazados ({host}).", 2))
        if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host):
            add(Senal("ip_directa", f"El enlace apunta a una dirección IP ({host}), no a un dominio.", 2))
        if imita_oficial(host):
            add(Senal("dominio_imita", f"«{host}» imita a la UDES pero no es el dominio oficial.", 2))
        elif not es_oficial(host) and menciona_institucion and not arroba:
            add(Senal("dominio_externo", f"Habla de la institución pero el enlace va a «{host}».", 1))
        if host.count(".") >= 4:
            add(Senal("subdominios", f"Dominio con muchos subdominios ({host}).", 1))

    for nombre in re.findall(r"[\w-]+\.([a-z0-9]{2,4})\b", plano):
        if nombre in EXT_PELIGROSAS and re.search(r"(adjunt|archivo|descarg|abr|document|factura|\.%s\b)" % nombre, plano):
            add(Senal("adjunto_peligroso", f"Archivo .{nombre}: ese tipo puede ejecutar código o esconder malware.", 2))
            break

    for s in FRASES:
        if re.search(_PATRONES[s.id], plano):
            add(s)
    return list(encontradas.values())


def nivel_riesgo(senales: list[Senal]) -> tuple[str, int]:
    """Suma los pesos: 0-1 bajo, 2-3 medio, 4 o más alto."""
    puntos = sum(s.peso for s in senales)
    if puntos >= 4:
        return "alto", puntos
    if puntos >= 2:
        return "medio", puntos
    return "bajo", puntos


_SENSIBLE_CON_VERBO = re.compile(
    r"(?i)\b(contrase[nñ]a|clave|password|pass|pin|c[oó]digo|otp|token)(\s+(?:es|era|seria|:|=)\s*|\s*[:=]\s*)"
    r"(?!(?:segur|fuert|d[eé]bil|buen|mal|larg|cort|nuev|viej|robad|igual|la\b|el\b|mi\b|una?\b|muy\b|de\b|que\b)\w*)(\S+)")
_SENSIBLE_NUM = re.compile(r"(?i)\b(contrase[nñ]a|clave|pin|c[oó]digo|otp|token)\s+(\S*\d\S*)")
_TARJETA = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def proteger(texto: str) -> tuple[str, bool]:
    """Oculta contraseñas, códigos y números de tarjeta antes de mostrarlos.

    Devuelve (texto_protegido, se_oculto_algo).
    """
    nuevo = _SENSIBLE_CON_VERBO.sub(lambda m: m.group(1) + m.group(2) + "••••••", texto)
    nuevo = _SENSIBLE_NUM.sub(lambda m: m.group(1) + " ••••••", nuevo)
    nuevo = _TARJETA.sub("•••• •••• •••• ••••", nuevo)
    return nuevo, nuevo != texto
