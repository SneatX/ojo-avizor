# Ojo Avizor

### Chatbot de ciberseguridad para la comunidad UDES

**Autor:** Santiago Alexander Ospina Pabón  
**Código:** 01220371058  
**Programa:** Ingeniería de Software, Universidad de Santander (UDES)  
**Repositorio:** [https://github.com/SneatX/ojo-avizor](https://github.com/SneatX/ojo-avizor)

---

## 1. Descripción del proyecto

Ojo Avizor es un chatbot que ayuda a estudiantes, docentes y administrativos de la UDES a revisar
correos, enlaces y mensajes sospechosos, y les indica qué hacer si ya cayeron en un engaño
(phishing, suplantación, malware o acceso no autorizado a una cuenta).

La persona escribe con sus propias palabras, aunque sea de forma informal, sin tildes o con errores.
Un modelo Transformer (DistilBERT multilingüe), entrenado para este proyecto, interpreta la intención
del mensaje. Con esa interpretación, el chatbot conversa, revisa la evidencia que la persona
comparte y le da recomendaciones concretas.

## 2. Qué casos atiende

| Situación | Respuesta del chatbot |
|---|---|
| Correo sospechoso | Revisa el remitente, la urgencia del mensaje y el destino del enlace |
| Enlace sospechoso | Detecta dominios que imitan a la UDES, acortadores, el truco del `@` y hosting gratuito |
| Suplantación por WhatsApp, SMS o llamada | Detecta peticiones de dinero o códigos, números nuevos y presión |
| «Ya caí» (di mi clave, envié dinero, compartí un código) | Plan en tres pasos: contener, preservar evidencia y reportar |
| Virus o archivo malicioso | Indica desconectar el equipo, no formatearlo y reportar |
| Alguien entró a mi cuenta | Guía la recuperación: cambio de contraseña, cierre de sesiones y verificación en dos pasos |
| Dudas de prevención | Explica contraseñas seguras, verificación en dos pasos y cómo guardar evidencia |

## 3. Cómo funciona

1. **Transformer** (`modelo.py`): clasifica el mensaje en una de 15 intenciones y da la probabilidad de cada una.
2. **Analizador de señales** (`senales.py`): busca evidencia de riesgo en el texto (dominios, enlaces, adjuntos, urgencia).
3. **Cerebro** (`cerebro.py`): recuerda la conversación, hace la pregunta clave (*¿ya hiciste clic, diste datos o enviaste dinero?*) y decide la respuesta. Si la persona no cayó, calcula un nivel de riesgo (bajo, medio o alto); si cayó, da los pasos según lo ocurrido; si el modelo no está seguro, pide aclarar.
4. **Interfaz web** (`app.py`, Gradio): muestra el chat y, al lado, lo que entendió el modelo, el nivel de riesgo y las señales encontradas.

**Reglas que cumple siempre**, verificadas con 29 pruebas automáticas:

- Nunca afirma que algo «es un ataque»; habla de señales y nivel de riesgo.
- Toda recomendación remite al canal oficial (Soporte TI de la UDES).
- Nunca pide contraseñas y oculta las contraseñas, códigos o números de tarjeta que alguien escriba por error.

## 4. Resultados

El modelo se evaluó con 165 frases que no vio durante el entrenamiento (informales, sin tildes y con errores):

| Versión | Frases de entrenamiento | Acierto en frases nuevas |
|---|---|---|
| v1 | 334 | 88,9 % |
| v2 (actual) | 454 | **93,3 %** |

Acierta con alta confianza en los casos claros. Todavía se confunde con frases que mezclan dos ideas;
para compensarlo, el chatbot siempre hace la pregunta clave y pide aclarar cuando no está seguro.

## 5. Ejecución

Funciona en Windows, macOS y Linux sin GPU (Python 3.10 a 3.13):

```bash
git clone https://github.com/SneatX/ojo-avizor.git
cd ojo-avizor
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python app.py
```

La primera ejecución descarga el modelo base y lo entrena (2 a 5 minutos en CPU). Luego se abre en
`http://127.0.0.1:7860`. También se puede ejecutar en Google Colab con el notebook
`Ojo_Avizor_Colab.ipynb` incluido en el repositorio.

## 6. Limitaciones

- Es una herramienta de orientación, no un antivirus ni un análisis forense: no abre enlaces ni descarga archivos, solo lee el texto que la persona escribe.
- Las señales cubren los engaños más comunes, no todos.
- Las conversaciones no se guardan.
