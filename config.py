"""Datos institucionales que Ojo Avizor usa en sus respuestas.

Revísenlos y complétenlos con los datos reales de la universidad antes de
presentar (por ejemplo, el correo o la extensión de la mesa de ayuda).
"""

NOMBRE = "Ojo Avizor"

# Dominios legítimos de la institución. Un remitente o enlace fuera de esta
# lista que diga ser de la universidad cuenta como señal de riesgo.
DOMINIOS_OFICIALES = ["udes.edu.co"]

# Cómo nombrar los canales oficiales en las respuestas.
SOPORTE_TI = "Soporte TI de la UDES (por los canales publicados en udes.edu.co)"
DENUNCIA = "el CAI Virtual de la Policía Nacional (caivirtual.policia.gov.co)"

# Por debajo de esta confianza el chatbot pide aclarar en vez de adivinar.
UMBRAL_CONFIANZA = 0.45
