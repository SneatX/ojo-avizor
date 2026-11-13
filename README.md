# 👁️ Ojo Avizor

**Chatbot de ciberseguridad para la comunidad UDES.** Ayuda a estudiantes, docentes y administrativos a
revisar correos, enlaces y mensajes sospechosos, y les dice qué hacer si ya cayeron en un engaño.

La persona escribe **con sus propias palabras** y un **Transformer entrenado** (DistilBERT multilingüe)
interpreta el mensaje. Con eso, el chatbot conversa, revisa la evidencia y da recomendaciones.

> Proyecto académico, Ingeniería de Software, Universidad de Santander (UDES).
> Autor: Santiago Alexander Ospina Pabón.

---

## Qué hace

| Situación | Qué hace Ojo Avizor |
|---|---|
| **Correo sospechoso** («su cuenta será desactivada en 24 horas») | Revisa el remitente, la prisa y a dónde lleva el enlace |
| **Enlace sospechoso** (por correo, WhatsApp o redes) | Detecta dominios que imitan a la UDES, acortadores, el truco del `@`, hosting gratuito |
| **Suplantación por WhatsApp, SMS o llamada** («hola, cambié de número») | Detecta peticiones de dinero o de códigos, números nuevos y presión |
| **Ya caí** (di mi contraseña, envié dinero, compartí un código) | Activa un plan en tres pasos: **contener → preservar evidencia → reportar** |
| **Virus o archivo malicioso** | Indica desconectar el equipo, no formatearlo y reportar |
| **Alguien entró a mi cuenta** | Guía la recuperación: cambiar la contraseña, cerrar sesiones, activar la verificación en dos pasos |
| **Dudas de prevención** | Explica contraseñas seguras, verificación en dos pasos y cómo guardar evidencia |

Cómo conversa:

1. Entiende lo que pasó, aunque esté escrito informal, sin tildes o con errores.
2. Hace la pregunta clave: **¿ya hiciste clic, diste datos o enviaste dinero?**
3. Si **no** cayó, calcula un **nivel de riesgo (bajo / medio / alto)** con las señales que encuentra en lo
   que la persona pega (remitente, enlace, texto del mensaje).
4. Si **sí** cayó, da los pasos según lo que pasó.
5. Si no entiende bien, pregunta en vez de adivinar.

**Reglas que cumple siempre** (verificadas con pruebas automáticas):

- Nunca afirma que algo «es un ataque»: habla de señales y nivel de riesgo.
- Toda recomendación termina remitiendo al canal oficial (Soporte TI de la UDES).
- Nunca pide contraseñas y **oculta** las contraseñas, códigos o números de tarjeta que alguien escriba por error.

La interfaz muestra al lado del chat **lo que entendió el modelo** (probabilidad de cada intención),
el **nivel de riesgo** y las **señales encontradas**.

## Cómo funciona

```
Mensaje ──► Transformer (modelo.py) ──► ¿qué quiere decir? (15 intenciones con su probabilidad)
        └─► Analizador (senales.py) ──► ¿qué evidencia hay? (dominios, enlaces, adjuntos, prisa...)
                      │
                      ▼
            Cerebro (cerebro.py): recuerda la conversación y decide la respuesta
                      │
                      ▼
            Interfaz web (app.py, Gradio)
```

La explicación técnica completa está en [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md).

---

## Ejecución en tu computador

Funciona en **Windows, macOS y Linux**, **sin GPU**.

### Requisitos

- **Python 3.10 a 3.13** ([python.org](https://www.python.org/downloads/)). En Windows, al instalarlo,
  marca *Add Python to PATH*.
- Unos **3 GB libres** (librerías, modelo base y modelo entrenado).
- Internet la primera vez (para descargar las librerías y el modelo base).

### 1. Obtener el código

```bash
git clone <URL-de-este-repositorio> ojo-avizor
```
```bash
cd ojo-avizor
```

Todos los comandos siguientes se ejecutan **dentro de la carpeta del proyecto**.

### 2. Crear y activar un entorno virtual

Windows (PowerShell o CMD):
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

Sabrás que está activo porque la terminal muestra `(.venv)` al inicio.

### 3. Instalar dependencias

Primero PyTorch en versión para CPU (unos 200 MB; la versión con GPU pesa varios GB):
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Luego el resto:
```bash
pip install -r requirements.txt
```

### 4. Ejecutar el chatbot

```bash
python app.py
```

- **La primera vez** descarga el modelo base (~540 MB) y **entrena el Transformer automáticamente**
  (2 a 5 minutos en CPU). Verás el progreso en la terminal.
- Cuando aparezca `Running on local URL: http://127.0.0.1:7860`, abre esa dirección en el navegador.
- Las siguientes veces abre en segundos, porque el modelo queda guardado en `modelo_entrenado/`.
- Para cerrarlo: `Ctrl + C` en la terminal.

Opciones:

| Comando | Para qué |
|---|---|
| `python app.py --share` | Crea además un enlace público temporal (`https://....gradio.live`) para abrirlo desde otro dispositivo |
| `python app.py --reentrenar` | Vuelve a entrenar antes de abrir (por ejemplo, después de agregar frases) |
| `python app.py --port 8000` | Usa otro puerto si el 7860 está ocupado |

### Otros comandos

| Comando | Para qué |
|---|---|
| `python entrenar.py` | Solo entrena el modelo y muestra qué tan bien entiende frases nuevas |
| `python evaluar.py --errores` | Mide el modelo con 165 frases de prueba y lista las que clasifica mal |
| `python -m pytest -q` | Corre las 29 pruebas automáticas de las reglas |

### Problemas comunes

| Problema | Solución |
|---|---|
| `python` no se reconoce (Windows) | Reinstala Python marcando *Add Python to PATH*, o usa `py` en vez de `python` |
| PowerShell no deja activar el entorno | Ejecuta `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelve a intentar |
| `Address already in use` | Usa otro puerto: `python app.py --port 8000` |
| La primera ejecución tarda | Es normal: está descargando el modelo base y entrenando. Solo pasa una vez |

---

## Ejecución en Google Colab

1. Comprime la carpeta del proyecto en un `.zip`.
2. Abre [colab.research.google.com](https://colab.research.google.com) → **Subir** → `Ojo_Avizor_Colab.ipynb`.
3. (Opcional, más rápido) *Entorno de ejecución → Cambiar tipo de entorno → GPU T4*.
4. Ejecuta las celdas en orden. En la primera, sube el `.zip`.
5. La última celda imprime un enlace `https://....gradio.live`. Ábrelo; también funciona desde el celular.

---

## Estructura del proyecto

| Archivo | Contenido |
|---|---|
| `app.py` | Interfaz web (Gradio). **Es lo que se ejecuta.** |
| `modelo.py` | Entrenamiento y predicción del Transformer |
| `cerebro.py` | Lógica de conversación: contexto, pregunta clave, modo «ya caí», recomendaciones |
| `senales.py` | Detección de señales de riesgo y ocultamiento de datos sensibles |
| `config.py` | Dominio oficial, canales de soporte y umbral de confianza |
| `datos.py` | 454 frases de entrenamiento agrupadas en 15 intenciones |
| `datos/prueba_frases_nuevas*.csv` | 165 frases de prueba que el modelo no ve al entrenar |
| `entrenar.py`, `evaluar.py` | Entrenar y medir el modelo |
| `tests/` | Pruebas automáticas |
| `Ojo_Avizor_Colab.ipynb` | Notebook para Google Colab |
| `docs/ARQUITECTURA.md` | Explicación técnica |

## Resultados del modelo

Medido con frases que el modelo **nunca vio** al entrenar (informales, sin tildes, con errores):

| Versión | Frases de entrenamiento | Acierto en frases nuevas |
|---|---|---|
| v1 | 334 | 88,9 % |
| v2 (actual) | 454 | **93,3 %** |

Acierta con alta confianza en los casos claros. Todavía se confunde con frases que mezclan dos ideas
(por ejemplo, «le di mi clave a uno que dijo ser de soporte»). Para compensarlo, el chatbot siempre
hace la pregunta clave y, si no está seguro, pide aclarar.

**Para mejorarlo:** agregar frases reales a `datos.py` (o a `datos/extra.csv` con columnas
`texto,intencion`), ejecutar `python evaluar.py --errores` y volver a entrenar con
`python app.py --reentrenar`.

## Personalización

Antes de presentarlo, revisa `config.py` y completa los canales reales de Soporte TI de la universidad.

## Limitaciones

- Es una **herramienta de orientación**, no un antivirus ni un análisis forense. No abre enlaces ni
  descarga archivos: solo lee el texto que la persona escribe.
- Las señales cubren los engaños más comunes, no todos.
- Las conversaciones no se guardan. Aun así, **nunca escribas contraseñas reales**.
