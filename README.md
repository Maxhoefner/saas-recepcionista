# AI Receptionist

Recepcionista virtual con IA que atiende WhatsApp 24/7 y gestiona turnos para negocios basados en reservas (peluquerías, consultorios, spas, etc.). SaaS multi-tenant: cada negocio (`business`) es un tenant completamente aislado.

Ver [`docs/architecture.md`](docs/architecture.md) para la arquitectura completa y el roadmap por fases.

## Stack

- **Frontend**: Next.js + TypeScript + Tailwind (`apps/web`)
- **Backend**: FastAPI + SQLAlchemy (async) + Alembic (`apps/api`)
- **DB**: PostgreSQL
- **Cola de jobs**: Redis (Fase 6+)
- **IA**: proveedor abstraído (Claude por defecto), tool-calling contra servicios de negocio
- **WhatsApp**: WhatsApp Business Cloud API, abstraída detrás de una interfaz propia

## Requisitos

- Docker Desktop (requiere WSL2 habilitado en Windows — ver nota abajo)
- Node.js LTS (para `apps/web`)
- Python 3.11+ (para correr `apps/api` fuera de Docker, opcional)

> **Windows sin WSL2**: si `docker` no funciona, habilitá WSL2 con `wsl --install` en una terminal como administrador, reiniciá Windows, y abrí Docker Desktop una vez para que termine su setup.

## Desarrollo local

1. Copiar `.env.example` a `.env` y ajustar valores (como mínimo, generar un `JWT_SECRET`).
2. Levantar los servicios:

   ```bash
   docker compose up --build
   ```

3. API disponible en `http://localhost:8000` (docs interactivas en `/docs`).
4. Correr migraciones:

   ```bash
   docker compose exec api alembic upgrade head
   ```

5. (Opcional) Sembrar 2 negocios de prueba con sus dueños, para desarrollar siempre contra más de un tenant:

   ```bash
   docker compose exec api python -m app.db.seed
   ```

   Crea `ana@peluqueriabella-demo.com` / `pedro@consultoriodrperez-demo.com`, contraseña `test1234` en ambos casos.

## Backend sin Docker (opcional)

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

## Tests / lint / typecheck (backend)

```bash
cd apps/api
pytest
ruff check .
mypy app
```

## API implementada hasta ahora

- `POST /api/v1/auth/register` — crea usuario + su primer negocio + membership OWNER
- `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`
- `GET /api/v1/businesses`, `POST /api/v1/businesses` — negocios del usuario logueado, con su rol
- `GET/POST/PATCH/DELETE /api/v1/businesses/{id}/services`
- `GET/POST/PATCH/DELETE /api/v1/businesses/{id}/professionals` (+ `GET/PUT .../{id}/hours`)
- `GET/PUT /api/v1/businesses/{id}/business-hours`, `GET/POST/DELETE .../blocked-times`, `.../holidays`
- `GET/POST/PATCH /api/v1/businesses/{id}/customers`
- `GET/POST /api/v1/businesses/{id}/appointments`, `GET .../{id}`, `POST .../{id}/{cancel,reschedule,confirm,complete,no-show}`
- `GET /api/v1/businesses/{id}/availability?service_id=&day=&professional_id=`
- `GET/PUT /api/v1/businesses/{id}/ai-settings` — personalidad del asistente (nombre, tono, idioma)
- `GET/POST/PATCH/DELETE /api/v1/businesses/{id}/faqs`
- `GET/POST /api/v1/businesses/{id}/conversations`, `GET .../{id}/messages`, `POST .../{id}/messages` (dispara al agente), `POST .../{id}/{handoff,return-to-ai}`
- `GET/PUT /api/v1/businesses/{id}/whatsapp-account` — conectar el número de WhatsApp del negocio
- `GET/POST /api/v1/webhooks/whatsapp` — webhook público (verificación de Meta / recepción de mensajes), no requiere login

El login del dashboard (UI) se construye en la Fase 8; por ahora la auth es solo backend.

### Para probar el agente de IA con un LLM real

Necesitás tu propia API key de Anthropic (console.anthropic.com) en `ANTHROPIC_API_KEY` dentro de `.env`, y reiniciar `docker compose up -d api`. Sin key configurada, todo lo demás (catálogo, turnos, CRUD de conversaciones) funciona igual — solo `POST .../messages` fallará al intentar generar una respuesta (con un mensaje de fallback prolijo, no un error feo).

### Para probar WhatsApp de verdad

Necesitás una WhatsApp Business App en [developers.facebook.com](https://developers.facebook.com), su App Secret (`WHATSAPP_APP_SECRET` en `.env`), un `WHATSAPP_VERIFY_TOKEN` (lo elegís vos) para registrar el webhook, y exponer tu `localhost:8000` con algo como `ngrok` para que Meta pueda llamarlo durante desarrollo. Una vez con la App, conectás el número de prueba gratuito de Meta vía `PUT /businesses/{id}/whatsapp-account`. Sin esto, el resto de la Fase 6 (webhook, idempotencia, resolución de negocio/cliente) ya está construido y testeado — solo falta un número real conectado para probarlo con mensajes de verdad.

## Estado del proyecto

Ver el roadmap de fases en [`docs/architecture.md`](docs/architecture.md#roadmap). Actualmente: **Fase 6 (WhatsApp) completa**.
