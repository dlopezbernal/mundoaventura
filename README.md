# 🕰️ Máquina del Tiempo en tu Habitación

Herramienta educativa (para niños de 8 a 12 años) que **genera escenas divertidas combinando
un lugar y un personaje histórico o prehistórico** (¡un T-Rex en un laboratorio!) y, más
adelante, te dejará **conversar con ellos por voz**. Combina varias tecnologías de
Inteligencia Artificial en un pipeline por fases.

> Este repositorio se construye **paso a paso**. Ahora mismo está implementada la
> **generación de la escena** (ubicación + personaje) usando **Replicate.com**.

---

## 🧩 El pipeline

| Paso | Qué hace | Tecnología | Estado |
|------|----------|------------|--------|
| **Elegir lugar y personaje** | Eliges una **ubicación** (laboratorio, bosque del jurásico, renacimiento, época victoriana...) y un **personaje** (T-Rex, Leonardo da Vinci, Sherlock Holmes...). Cualquier combinación vale. | **Flet** (interfaz, sin IA) | ✅ **Implementado** |
| **Generación de la escena** | Combina lugar + personaje + estilo en un prompt y pide la imagen a la nube. Devuelve una escena completa. | **Replicate.com** (FLUX schnell, txt2img) | ✅ **Implementado** |
| Transcripción de voz | Convierte tu pregunta hablada en texto. | Whisper (OpenAI) | ⏳ Pendiente |
| Respuesta documentada (RAG) | Busca en enciclopedias infantiles y el personaje responde "en primera persona". | LangChain + ChromaDB + LLM | ⏳ Pendiente |

> **¿Por qué Replicate y no Stable Diffusion en local?** Generar con Stable Diffusion +
> IP-Adapter en una GPU modesta (p. ej. una GTX 1660 de 6 GB) es lento e inestable. Con
> **Replicate.com** la generación se hace en su GPU: el backend solo manda un prompt y recibe
> la imagen. Así el proyecto es ligero y corre en cualquier ordenador, sin necesidad de GPU.
> El modelo por defecto es **FLUX schnell** (rápido y barato). El estilo "Pixar 3D amigable" y
> la seguridad para niños se integran en el prompt (FLUX schnell no admite *negative prompt*).

---

## 🏗️ Arquitectura

Arquitectura **Cliente-Servidor desacoplada**:

```
┌─────────────────────────┐         HTTP / REST         ┌──────────────────────────────┐
│   FRONTEND (Flet)        │  ─────────────────────────► │   BACKEND (FastAPI)          │
│   - Elegir lugar         │   POST /api/generate        │   - Construye el prompt      │
│   - Elegir personaje     │   { personaje_id,           │   - Llama a Replicate.com    │
│   - Ver el resultado     │     ubicacion_id }          │   - Devuelve la imagen       │
│                          │  ◄───────────────────────── │     (base64)                 │
└─────────────────────────┘     escena (PNG base64)      └──────────────────────────────┘
        tu PC (ligero)                                    tu PC (ligero)  →  Replicate (GPU)
```

El backend ya no necesita GPU: la parte pesada la hace Replicate en la nube.

---

## 📁 Estructura del proyecto

```
capston/
├── backend/                  # Servidor de IA (FastAPI)
│   ├── main.py               # Arranque de la app y rutas globales
│   ├── config.py             # Configuración (token y modelo de Replicate) desde .env
│   ├── personajes.py         # Prompts de cada personaje + estilo común
│   ├── ubicaciones.py        # Prompts de cada ubicación
│   ├── schemas/              # Forma de los datos de entrada/salida
│   ├── services/             # Lógica de generación (generation_service.py → Replicate)
│   └── routers/              # Endpoints HTTP
├── frontend/                 # Interfaz de usuario (Flet)
│   ├── main.py               # La ventana de la app (dos catálogos + resultado)
│   ├── personajes.py         # Catálogo visual de personajes (label, emoji)
│   ├── ubicaciones.py        # Catálogo visual de ubicaciones (label, emoji)
│   └── api_client.py         # Llamadas HTTP al backend
├── requirements-backend.txt
├── requirements-frontend.txt
└── .env.example              # Plantilla de configuración
```

---

## 🚀 Puesta en marcha

### 1. Crear y activar un entorno virtual

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Instalar las dependencias

```powershell
pip install -r requirements-backend.txt
pip install -r requirements-frontend.txt
```

> El backend es ligero: no instala torch ni diffusers.

### 3. Configurar el .env (con tu token de Replicate)

```powershell
Copy-Item .env.example .env
```

Edita `.env` y pega tu token de Replicate en `REPLICATE_API_TOKEN`. Lo creas en
[replicate.com/account/api-tokens](https://replicate.com/account/api-tokens).

### 4. Arrancar el backend (una terminal)

```powershell
uvicorn backend.main:app --reload
```

Comprueba que abre en http://127.0.0.1:8000/docs. En `GET /health` debe aparecer
`"token_configurado": true` y el modelo de Replicate.

### 5. Arrancar el frontend (otra terminal, con el venv activado)

```powershell
flet run frontend/main.py
```

Elige un lugar y un personaje, pulsa «Generar» y verás la escena generada en unos segundos.

---

## 💡 Personalizar

- **Añadir personajes:** edita `backend/personajes.py` (el prompt) y `frontend/personajes.py`
  (la tarjeta), usando el **mismo `id`** en ambos.
- **Añadir ubicaciones:** igual, en `backend/ubicaciones.py` y `frontend/ubicaciones.py`.
- **Cambiar el modelo o el estilo:** `REPLICATE_MODEL` en el `.env` y el `STYLE_SUFFIX` en
  `backend/personajes.py`.
