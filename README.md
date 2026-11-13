# 👁️ Ojo Avizor

Chatbot de ciberseguridad para la comunidad UDES. La persona le escribe **con sus propias palabras**
y un **Transformer entrenado** (DistilBERT multilingüe, el mismo de la guía del curso) interpreta el
mensaje. Con eso, Ojo Avizor:

- revisa **correos falsos, enlaces sospechosos y suplantaciones por WhatsApp/SMS/llamada**;
- hace la pregunta clave: **¿ya hiciste clic, diste datos o enviaste dinero?**;
- si no cayó, calcula un **nivel de riesgo (bajo / medio / alto)** a partir de las señales que encuentra
  en lo que la persona pega (remitente, enlace, texto);
- si ya cayó, activa el **modo «ya caí»**: contener → preservar evidencia → reportar, con pasos
  específicos según lo que pasó (dio contraseña, envió dinero, compartió un código, virus, cuenta robada);
- también responde dudas de **prevención** (contraseñas, verificación en dos pasos, cómo guardar evidencia,
  dónde denunciar).

**Reglas que cumple siempre (y que verifican las pruebas automáticas):** nunca afirma que algo «es un
ataque», habla de señales y riesgo, cierra remitiendo al canal oficial, nunca pide contraseñas y
**oculta** contraseñas, códigos o tarjetas si alguien los escribe por error.

---

## Cómo funciona

```
 Mensaje de la persona
        │
        ▼
 ┌──────────────────────┐     probabilidades de 15 intenciones
 │ Transformer          │ ──► (correo_sospechoso 0.96, cai_dinero 0.02, ...)
 │ (modelo.py)          │
 └──────────────────────┘
        │                        ┌──────────────────────────┐
        ├──────────────────────► │ Analizador de señales    │  dominios que imitan a la UDES,
        │                        │ (senales.py)             │  acortadores, truco del @, adjuntos
        ▼                        └──────────────────────────┘  .zip/.exe, prisa, pide códigos...
 ┌──────────────────────┐                 │
 │ Cerebro (cerebro.py) │ ◄───────────────┘
 │ recuerda el contexto │  ¿qué caso es? ¿ya respondió si cayó? ¿qué señales van?
 └──────────────────────┘
        │
        ▼
 Respuesta + panel con lo que entendió el modelo, nivel de riesgo y señales (app.py, Gradio)
```

- El **Transformer** responde a *¿qué quiere decir la persona?* Entiende frases que nunca vio, como
  «le giré 50 mil al que decía ser mi tío» → *Ya caí: envié dinero*.
- El **analizador de señales** responde a *¿qué evidencia hay en el texto?* Revisa dominios y enlaces,
  algo que se verifica mejor con reglas exactas que con un modelo.
- El **cerebro** une ambos y recuerda la conversación. Las respuestas son textos revisados, no generados
  libremente: así el chatbot nunca inventa pasos ni afirma que algo es un ataque.

Si el modelo no está seguro (confianza < 45 %), pregunta en vez de adivinar: *«¿Me hablas de un correo
sospechoso o de un enlace sospechoso?»*.

📘 La explicación técnica completa (tipo de sistema, si es un agente o no, cómo funciona el Transformer
por dentro, entrenamiento y evaluación) está en [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md).

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `app.py` | La aplicación: carga el modelo y abre la interfaz Gradio. **Es lo que se ejecuta.** |
| `entrenar.py` | Entrena el Transformer y muestra qué tan bien entiende frases nuevas. |
| `evaluar.py` | Evalúa un modelo con los 3 conjuntos de prueba (sirve para comparar versiones). |
| `datos.py` | Las 454 frases de entrenamiento, agrupadas por intención. **Aquí se mejora el modelo.** |
| `datos/prueba_frases_nuevas*.csv` | 165 frases de prueba que el modelo nunca ve al entrenar. |
| `modelo.py` | Entrenamiento y predicción del Transformer. |
| `cerebro.py` | La conversación: contexto, decisión clave, modo «ya caí», recomendaciones. |
| `senales.py` | Detección de señales de riesgo y ocultamiento de datos sensibles. |
| `config.py` | Dominio oficial, canales de soporte y umbral de confianza. **Revísalo.** |
| `tests/` | Pruebas automáticas de las reglas (`python -m pytest -q`). |
| `Ojo_Avizor_Colab.ipynb` | Notebook para correr todo en Google Colab. |

---

## Opción A: Google Colab (lo más fácil)

1. Abre [colab.research.google.com](https://colab.research.google.com) → **Subir** → `Ojo_Avizor_Colab.ipynb`.
2. (Opcional, más rápido) *Entorno de ejecución → Cambiar tipo de entorno → GPU T4*.
3. Ejecuta las celdas en orden. En la primera, sube un `.zip` con la carpeta del proyecto
   (por ejemplo, comprime la carpeta `ojo-avizor` que clonaste).
4. La celda final imprime un enlace `https://xxxx.gradio.live`: ábrelo (funciona hasta en el celular).

## Opción B: en tu computador (Windows, macOS o Linux, sin GPU)

Necesitas **Python 3.10 a 3.13** ([python.org](https://www.python.org/downloads/); en Windows marca
*Add Python to PATH*) y **git**.

**0. Obtener el código** (elige una forma):

Desde el archivo `ojo-avizor.bundle` (trae todo el historial de commits):
```bash
git clone ojo-avizor.bundle ojo-avizor
```

Desde GitHub, si ya está publicado allí:
```bash
git clone https://github.com/SneatX/ojo-avizor.git
```

Luego entra a la carpeta (los siguientes comandos se ejecutan dentro de ella):
```bash
cd ojo-avizor
```

**1. Crear un entorno virtual**

Windows:
```bash
python -m venv .venv
```
```bash
.venv\Scripts\activate
```

macOS / Linux:
```bash
python3 -m venv .venv
```
```bash
source .venv/bin/activate
```

**2. Instalar PyTorch para CPU** (unos 200 MB; la versión normal con GPU pesa varios GB):
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

**3. Instalar el resto**
```bash
pip install -r requirements.txt
```

**4. Abrir el chatbot**
```bash
python app.py
```

La primera vez descarga DistilBERT (~540 MB) y **entrena el modelo solo** (2-5 minutos en CPU).
Luego abre en **http://127.0.0.1:7860**. Las siguientes veces abre en segundos.

Otras opciones:

```bash
python app.py --share        # además crea un enlace público temporal para compartir
python app.py --reentrenar   # vuelve a entrenar (después de agregar frases)
python app.py --port 8000    # usa otro puerto
```

---

## ¿Qué tan bien entiende el modelo?

Se midió con **frases escritas de otra forma** (informales, sin tildes, con errores), que el modelo
**nunca vio** al entrenar. Todo corrió en CPU (2-3 minutos por entrenamiento).

| Versión | Frases de entrenamiento | Prueba 3 (juez limpio) | Las 3 pruebas juntas |
|---|---|---|---|
| v1 | 334 (~22 por intención) | **88,9 %** (40/45) | 87,3 % |
| v2 | 454 (~30 por intención) | **93,3 %** (42/45) | 94,5 % |

**Cómo leer esto con honestidad:**

- Las frases agregadas en la v2 se escribieron después de ver los errores en las pruebas 1 y 2. Por eso
  esas pruebas suben más (+8 puntos) de lo que subiría con frases realmente nuevas. **La prueba 3 se
  escribió antes de entrenar la v2**: su mejora (+4,4 puntos) es la cifra confiable.
- Con 45 frases, cada error equivale a ~2 puntos. Las cifras orientan, pero no son exactas.
- Casos fáciles («me llegó un correo raro», «le mandé plata»): el modelo acierta con 90-98 % de confianza.
- **Dónde todavía falla:** frases que mezclan dos ideas. Por ejemplo, «le di mi clave a uno que dijo ser de
  soporte» la confunde con *acceso a mi cuenta*, y «salen correos enviados que yo no escribí» con
  *correo sospechoso*. Son confusiones razonables (incluso para una persona), pero muestran el límite.

**Por qué el chatbot es más confiable que el modelo solo:**

- Ante una situación, siempre pregunta **«¿ya hiciste clic / diste datos / enviaste dinero?»**. Si el
  modelo no detectó que la persona ya cayó, la pregunta lo corrige.
- Si el modelo le da al menos 15 % a «ya caí», lo recuerda: cuando la persona responde «sí», va directo
  al plan correcto sin volver a preguntar.
- Con confianza baja, pide aclarar en vez de responder cualquier cosa.

## Cómo mejorarlo

1. **Más frases reales (lo que más ayuda).** Pidan a compañeros que escriban cómo contarían cada caso y
   agréguenlas a `datos.py` o a `datos/extra.csv` (columnas `texto,intencion`). Apunten a 50+ por intención.
2. **Ciclo de mejora:** `python evaluar.py --errores` → agregar frases *parecidas a los errores, pero
   distintas* → `python entrenar.py` → evaluar de nuevo.
3. **Escribir un conjunto de prueba nuevo antes de cada mejora** (como la prueba 3). Si corrigen mirando
   las mismas frases con las que miden, el resultado se infla.
4. **Probar un modelo en español** (BETO, entrenado solo en español) y comparar con `evaluar.py`.
   En macOS/Linux: `OJO_MODELO_BASE=dccuchile/bert-base-spanish-wwm-uncased python entrenar.py`.
   En Windows (PowerShell): `$env:OJO_MODELO_BASE="dccuchile/bert-base-spanish-wwm-uncased"; python entrenar.py`.
5. **Revisar `config.py`** con el dominio y los canales reales de soporte de la universidad.

## Probar las reglas

```bash
python -m pytest -q
```

Son 29 pruebas, entre ellas: nunca dice «es un ataque»; la conversación de correo da riesgo alto y
cierra con Soporte TI; enviar dinero activa contener/preservar/reportar; las contraseñas y tarjetas
se ocultan; el dominio oficial `udes.edu.co` no cuenta como señal.

## Limitaciones

- Es una **herramienta de orientación** académica, no un antivirus ni un análisis forense. No abre
  enlaces ni descarga archivos: solo lee el texto que la persona pega.
- La lista de señales cubre los engaños más comunes, no todos.
- Las conversaciones no se guardan. Igual, **nunca escribas contraseñas reales**.
