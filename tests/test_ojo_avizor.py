"""Pruebas de las reglas de Ojo Avizor. No necesitan el modelo entrenado.

Ejecutar:  python -m pytest -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cerebro import NOMBRES, Estado, responder  # noqa: E402
from senales import analizar, nivel_riesgo, proteger  # noqa: E402

INTENCIONES = list(NOMBRES)


def probs(principal, conf=0.9, **otras):
    """Simula la salida del Transformer."""
    d = {k: 0.0 for k in INTENCIONES}
    d.update(otras)
    d[principal] = conf
    return dict(sorted(d.items(), key=lambda x: -x[1]))


def charla(*turnos):
    e = Estado()
    return [responder(t, probs(i, **kw), e) for t, i, kw in turnos], e


PROHIBIDO = ["es un ataque", "esto es un ataque", "es una estafa", "es phishing", "te hackearon"]


@pytest.mark.parametrize("intencion", INTENCIONES)
def test_nunca_afirma_ataque(intencion):
    r = responder("texto de prueba con http://bit.ly/x urgente", probs(intencion), Estado())
    bajo = r.texto.lower()
    assert not any(p in bajo for p in PROHIBIDO)


def test_flujo_correo_no_cayo_da_riesgo_y_canal_oficial():
    (r1, r2), _ = charla(
        ("Me llegó un correo de soporte-udes@gmail.com: estimado usuario, su cuenta será suspendida en 24 horas "
         "http://udes-edu.co.login.xyz", "correo_sospechoso", {}),
        ("no, todavía no", "negacion", {}),
    )
    assert "¿ya hiciste clic" in r1.texto.lower()      # la pregunta clave
    assert r2.riesgo == "alto"
    assert "Soporte TI" in r2.texto                     # cierra con canal oficial


def test_flujo_whatsapp_si_luego_dinero_activa_modo_ya_cai():
    (r1, r2, r3), _ = charla(
        ("un número nuevo dice que es mi primo y pide plata", "suplantacion_mensaje", {}),
        ("sí", "afirmacion", {}),
        ("le mandé 100 mil por nequi", "cai_dinero", {}),
    )
    assert "qué hiciste" in r2.texto.lower()
    for paso in ("Contener", "Preservar", "Reportar"):
        assert paso in r3.texto
    assert "banco" in r3.texto.lower()


def test_pista_de_caida_evita_preguntar_dos_veces():
    (r1, r2), _ = charla(
        ("escribí la contraseña del correo, ¿y ahora?", "correo_sospechoso", {"conf": 0.6, "cai_credenciales": 0.2}),
        ("sí", "afirmacion", {}),
    )
    assert "Contener" in r2.texto and "contraseña" in r2.texto.lower()


def test_baja_confianza_pide_aclarar():
    r = responder("mmm algo raro", probs("correo_sospechoso", conf=0.3, enlace_sospechoso=0.25), Estado())
    assert "no estoy seguro" in r.texto.lower()


def test_oculta_contrasenas_y_tarjetas():
    t, oculto = proteger("mi contraseña es Gato1234 y la tarjeta 4111 1111 1111 1111")
    assert oculto and "Gato1234" not in t and "4111 1111" not in t
    t2, oculto2 = proteger("¿mi contraseña es segura si tiene 12 letras?")
    assert not oculto2 and t2.endswith("letras?")


@pytest.mark.parametrize("texto,senal", [
    ("http://udes.edu.co@malo.com/login", "truco_arroba"),
    ("mira bit.ly/premio", "acortador"),
    ("correo de soporte@udes-edu.co", "remitente_imita"),
    ("abre el adjunto factura.zip", "adjunto_peligroso"),
    ("http://192.168.10.5/udes", "ip_directa"),
    ("hola, cambié de número, guárdame", "cambio_numero"),
    ("pásame el código que te llegó", "pide_codigo"),
])
def test_senales(texto, senal):
    assert senal in {s.id for s in analizar(texto)}


def test_dominio_oficial_no_es_senal():
    ids = {s.id for s in analizar("El correo viene de soporte@udes.edu.co con enlace https://www.udes.edu.co/notas")}
    assert not ids & {"remitente_imita", "remitente_externo", "dominio_imita", "dominio_externo"}


def test_niveles_de_riesgo():
    assert nivel_riesgo([])[0] == "bajo"
    assert nivel_riesgo(analizar("urgente: bit.ly/x"))[0] == "medio"
    assert nivel_riesgo(analizar("estimado usuario, su cuenta será suspendida, ingrese su contraseña en "
                                 "http://udes-login.xyz"))[0] == "alto"
