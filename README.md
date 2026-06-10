# ZAFIRA-IA

> Microservicio interno de IA para la plataforma ZAFIRA: genera avatares semi-realistas a partir de una foto y hace try-on virtual de prendas sobre el avatar.

**ZAFIRA-IA** es consumido **exclusivamente** por el backend Django (ZAFIRA-CORE) vía HTTP interno firmado con HMAC. Nunca se expone a la app móvil ni al público.

```
App móvil  →  ZAFIRA-CORE (Django)  →  Celery  →  ZAFIRA-IA (FastAPI)  →  Modelos IA + Object Storage
                                                        │
                                                        ├── Backend stub (passthrough, default)
                                                        ├── Backend hosted (API estilo Replicate)
                                                        └── S3 / MinIO (bucket zafira-media)
```

ZAFIRA-CORE sube la foto del usuario al storage, encola una tarea Celery y esa tarea llama a ZAFIRA-IA con una URL (pública o presignada) de la imagen. ZAFIRA-IA descarga la imagen, ejecuta el modelo configurado, persiste el resultado en el bucket compartido y devuelve la *key* del objeto generado.

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Framework | FastAPI + uvicorn |
| Validación | Pydantic v2 |
| Auth | HMAC-SHA256 (X-CLIENT-ID / X-TIMESTAMP / X-SIGNATURE) |
| Storage | boto3 (S3 / MinIO) |
| HTTP saliente | httpx |
| Linting | Ruff |
| Tests | pytest + pytest-cov |

Sin base de datos: el servicio es **stateless** en el MVP. El estado (avatares, try-ons, jobs) vive en ZAFIRA-CORE.

---

## Arquitectura por capas

Calco de la arquitectura de `aether`:

```
src/app/
├── domain/           ← Excepciones de dominio (cero dependencias externas)
├── application/      ← Use cases + DTOs (orquestan, no conocen HTTP ni boto3)
│   ├── dto/                avatar.py, tryon.py, health.py
│   └── use_cases/          avatar/generate.py, tryon/generate.py
├── infrastructure/   ← Adaptadores concretos
│   ├── ai/                 base.py (Protocols), stub.py, hosted.py
│   ├── http/               image_fetcher.py (descarga con guardas)
│   ├── storage/            base.py (Protocol), s3_client.py (boto3)
│   └── security/           hmac_verifier.py (sin imports de FastAPI)
└── interfaces/       ← Rutas HTTP, dependencias, seguridad
    ├── api/v1/             avatar/router.py, tryon/router.py
    ├── security/           hmac_auth.py (Depends), openapi.py
    ├── dependencies.py     factories (settings, fetcher, storage, modelos)
    └── health.py
```

Los use cases reciben `fetcher`, `model` y `storage` como interfaces (`Protocol`), por lo que los backends son intercambiables sin tocar la lógica.

---

## Endpoints

| Endpoint | Auth | Descripción |
|----------|------|-------------|
| `GET /` | ❌ | Metadata del servicio |
| `GET /health` | ❌ | Liveness/readiness probe |
| `POST /api/v1/avatar` | HMAC ✅ | Genera avatar desde una foto |
| `POST /api/v1/tryon` | HMAC ✅ | Try-on virtual de una prenda |

### `POST /api/v1/avatar`

Request:

```json
{
  "external_ref": "9f4e2c1a-7b3d-4f6a-9c1e-2d8b5a0f3e7c",
  "source_image_url": "https://media.zafira.app/uploads/selfie.jpg",
  "params": {}
}
```

Response `200`:

```json
{
  "external_ref": "9f4e2c1a-7b3d-4f6a-9c1e-2d8b5a0f3e7c",
  "avatar_image_key": "avatars/9f4e2c1a-7b3d-4f6a-9c1e-2d8b5a0f3e7c.png",
  "meta": {"model": "StubAvatarModel", "size_bytes": 482133}
}
```

### `POST /api/v1/tryon`

Request:

```json
{
  "external_ref": "5b2d8e0c-1f4a-4c7b-8d3e-9a6f2c5e1b4d",
  "person_image_url": "https://media.zafira.app/avatars/user-1.png",
  "garment_image_url": "https://media.zafira.app/products/jacket-77.jpg",
  "garment_type": "upper_body",
  "params": {}
}
```

`garment_type` ∈ `upper_body` | `lower_body` | `dress`.

Response `200`:

```json
{
  "external_ref": "5b2d8e0c-1f4a-4c7b-8d3e-9a6f2c5e1b4d",
  "result_image_key": "tryons/5b2d8e0c-1f4a-4c7b-8d3e-9a6f2c5e1b4d.png",
  "meta": {"model": "StubTryOnModel", "size_bytes": 391024}
}
```

Errores de dominio (descarga fallida, content-type no imagen, proveedor caído) responden `422` con `{"detail": "...", "code": "IMAGE_FETCH_ERROR" | "PROVIDER_TIMEOUT" | ...}`.

---

## Autenticación HMAC

Todos los endpoints `/api/v1/*` exigen tres headers:

| Header | Descripción |
|--------|-------------|
| `X-CLIENT-ID` | Identificador registrado en `HMAC_ALLOWED_CLIENTS` (ej. `zafira-core`) |
| `X-TIMESTAMP` | Epoch Unix en segundos (ventana de ±`HMAC_CLOCK_SKEW_SECONDS`) |
| `X-SIGNATURE` | `hex(HMAC-SHA256(body_utf8 + timestamp, secret))` |

La comparación de firmas es *constant-time* (`hmac.compare_digest`). Ejemplo de firma desde Python (así lo hace la tarea Celery en ZAFIRA-CORE):

```python
import hashlib, hmac, json, time
import httpx

CLIENT_ID = "zafira-core"
SECRET = "change-me-in-production"

body = json.dumps({
    "external_ref": "9f4e2c1a-7b3d-4f6a-9c1e-2d8b5a0f3e7c",
    "source_image_url": "https://media.zafira.app/uploads/selfie.jpg",
    "params": {},
}).encode()

timestamp = str(int(time.time()))
signature = hmac.new(SECRET.encode(), (body.decode() + timestamp).encode(), hashlib.sha256).hexdigest()

response = httpx.post(
    "http://zafira-ia:8000/api/v1/avatar",
    content=body,
    headers={
        "Content-Type": "application/json",
        "X-CLIENT-ID": CLIENT_ID,
        "X-TIMESTAMP": timestamp,
        "X-SIGNATURE": signature,
    },
)
```

> Importante: firmar exactamente los **bytes crudos** del body que se envían — cualquier re-serialización JSON invalida la firma.

Si `HMAC_ALLOWED_CLIENTS` no está configurada, el servicio **se niega a arrancar** (fail-fast en el lifespan); no existe ningún cliente/secret por defecto.

### Supuesto de confianza sobre las URLs

ZAFIRA-IA descarga las imágenes de las URLs que recibe (`source_image_url`, `person_image_url`, `garment_image_url`) **confiando en que el único caller es ZAFIRA-CORE**, que las genera él mismo (presigned URLs de su storage). No hay denylist SSRF — en local las URLs de MinIO son loopback, así que bloquear rangos privados rompería dev. Si algún día ZAFIRA-CORE propaga URLs derivadas de input de usuario sin validar, este servicio se convertiría en un proxy hacia la red interna: en ese momento hay que añadir validación de esquema/destino aquí.

---

## Variables de entorno

| Variable | Requerida | Descripción |
|----------|-----------|-------------|
| `HMAC_ALLOWED_CLIENTS` | ✅ | JSON `{"client_id": "secret"}` |
| `HMAC_CLOCK_SKEW_SECONDS` | ➖ | Ventana de reloj (default: 60) |
| `AI_BACKEND` | ➖ | `stub` (default) \| `hosted` |
| `PROVIDER_BASE_URL` | hosted | Base URL del proveedor (ej. `https://api.replicate.com/v1`) |
| `PROVIDER_API_KEY` | hosted | API key del proveedor |
| `AVATAR_MODEL_REF` | hosted | Versión del modelo de avatar |
| `TRYON_MODEL_REF` | hosted | Versión del modelo de try-on |
| `PROVIDER_TIMEOUT_SECONDS` | ➖ | Timeout total de la predicción (default: 180) |
| `STORAGE_ENDPOINT_URL` | ➖ | Endpoint S3/MinIO (vacío = AWS S3) |
| `STORAGE_ACCESS_KEY` | ✅ | Access key del storage |
| `STORAGE_SECRET_KEY` | ✅ | Secret key del storage |
| `STORAGE_BUCKET` | ➖ | Bucket destino (default: `zafira-media`) |
| `STORAGE_REGION` | ➖ | Región del storage |
| `API_DOCS_ENABLED` | ➖ | Habilita `/docs` y `/redoc` (default: true) |

---

## Cómo correr

```bash
# Instalar dependencias
make install

# Configurar entorno
cp .env.example .env

# Servidor de desarrollo (puerto 8002 — ZAFIRA-CORE usa 8000 y aether 8001)
make dev

# Lint (ruff format + check)
make lint

# Tests (sin red ni MinIO: los tests usan fakes vía dependency_overrides)
make test
```

Docker:

```bash
# Producción (multi-stage, non-root, puerto 8000 interno)
docker build -t zafira-ia:local .

# Desarrollo (hot reload, .env montado)
docker build -f DockerfileEnv -t zafira-ia-dev:local .
docker run --rm -p 8002:8000 --env-file .env zafira-ia-dev:local
```

---

## Backends de IA

### `stub` (default)

Modelos *passthrough*: devuelven la imagen de entrada tal cual. Validan el pipeline completo (descarga → modelo → upload al storage) sin GPU ni red de proveedor. Es el backend para desarrollo local, CI y para integrar ZAFIRA-CORE end-to-end antes de pagar inferencia real.

> Nota: las keys de salida (`avatars/<external_ref>.png`, `tryons/<external_ref>.png`) asumen que el modelo produce PNG, como harán las implementaciones reales. En modo stub la extensión es nominal: si la imagen de entrada era JPEG, los bytes guardados siguen siendo JPEG.

### `hosted`

Esqueleto httpx contra una API de predicciones estilo Replicate: crea la predicción (`POST /predictions`), hace *polling* hasta estado terminal (con timeout) y descarga el output. Para activarlo:

1. `AI_BACKEND=hosted` + `PROVIDER_BASE_URL` + `PROVIDER_API_KEY`.
2. **Avatar** — apuntar `AVATAR_MODEL_REF` a la versión del modelo elegido (**InstantID** o **PhotoMaker** en Replicate) y mapear su *input schema* en `HostedAvatarModel.generate` (`src/app/infrastructure/ai/hosted.py` — los `TODO` marcan los puntos exactos).
3. **Try-on** — lo mismo con `TRYON_MODEL_REF` (**CatVTON** o **IDM-VTON**) en `HostedTryOnModel.generate` (típicamente las keys `person_image`/`garment_image`/`category` cambian de nombre según el modelo).

Como los modelos corren en la infraestructura del proveedor, este servicio no necesita librerías ML pesadas ni GPU.

---

## Roadmap — Fase 2

- **Modo jobs asíncrono**: `POST /api/v1/avatar/jobs` devuelve `202` + `job_id` inmediato; la generación corre en background y ZAFIRA-IA hace `POST` al webhook de ZAFIRA-CORE firmado con HMAC (mismo patrón `BACKOFFICE_*` de aether). Necesario cuando la inferencia real supere los timeouts HTTP razonables.
- Endpoint de *polling* `GET /api/v1/.../jobs/{job_id}` como fallback si el callback se pierde.
- Idempotencia por `external_ref` (requiere persistencia ligera de jobs).
