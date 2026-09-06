# Arquitectura — AI Receptionist

## Decisiones confirmadas

| Decisión | Elección |
|---|---|
| Proveedor LLM inicial | Claude (Anthropic), abstraído detrás de `LLMProvider` |
| Cola de jobs | Arq (Redis) |
| Auth | Propia (JWT + refresh token), sin proveedor externo |
| Idioma / mercado MVP | Español (LatAm) |
| Multi-tenancy | **No negociable desde el día 1.** Toda entidad de negocio lleva `business_id`. El seed de desarrollo usa al menos 2 negocios de prueba para forzar que cualquier fuga entre tenants se note de inmediato. |

## Estilo

Monolito modular (no microservicios) para el MVP. Separación en módulos (`ai/`, `whatsapp/`, `services/`) que se pueden extraer a servicios independientes más adelante si el volumen lo justifica.

## Componentes

- **`apps/web`** — Next.js. Solo consume la API, sin lógica de negocio.
- **`apps/api`** — FastAPI. Expone la API REST y el webhook de WhatsApp. El webhook nunca procesa el mensaje inline: valida, deduplica y encola.
- **Worker (Arq)** — procesa mensajes entrantes (agente IA + tool calls + envío) y jobs periódicos (recordatorios). Se añade en Fase 6/7.
- **PostgreSQL** — fuente de verdad única.
- **Redis** — cola de jobs, rate limiting, deduplicación de eventos de webhook, locks por conversación.

## Multi-tenancy

- Shared database, shared schema. Columna `business_id` (FK, indexada) en toda tabla tenant-scoped.
- Aislamiento reforzado en la capa de servicios: ninguna consulta se ejecuta sin `business_id` explícito.
- Row-Level Security de PostgreSQL como segunda capa de defensa (política por tabla, `SET LOCAL app.current_business_id` por request). **Pendiente** — todavía no implementada; por ahora el aislamiento es solo a nivel de servicio (`require_business_role`), cubierto por tests (`test_tenant_isolation.py`). Evaluar agregarla antes de producción.
- El agente de IA nunca recibe ni puede inyectar `business_id` — se determina server-side a partir del `whatsapp_account_id`/sesión, nunca del contenido del mensaje del cliente.

## Autenticación (Fase 2)

- Passwords con Argon2 (`argon2-cffi`). JWT de acceso (30 min) y refresh (30 días) firmados con HS256.
- Los refresh tokens se guardan **hasheados** en `refresh_tokens`, no como JWT stateless puro — así `/auth/logout` puede revocarlos de verdad, y `/auth/refresh` rota el token (el anterior queda inválido).
- `POST /auth/register` crea `User` + `Business` + `Membership(OWNER)` en una sola transacción — no existe un usuario "sin negocio".
- `require_business_role(*roles)` (`app/api/deps.py`) es la dependency que van a usar los endpoints tenant-scoped desde la Fase 3: valida que el usuario tenga membership en el `business_id` de la URL con el rol pedido.
- Un usuario puede pertenecer a (y crear) más de un negocio — cada membership es independiente.

## Configuración del negocio (Fase 3)

Todo bajo `/businesses/{business_id}/...`, protegido por `require_business_role`:

- **Servicios** (`Service`): nombre, precio en `price_cents` (nunca float), duración, activo. Lectura: cualquier rol. Escritura: `OWNER/ADMIN`.
- **Profesionales** (`Professional` + `ProfessionalService`): qué servicios realiza cada uno. Crear/editar un profesional valida que los `service_ids` pertenezcan al mismo `business_id` — evita enlazar un servicio de otro tenant.
- **Horarios**: `BusinessHours` (semanal, múltiples franjas por día para turnos partidos), `ProfessionalHours` (override opcional por profesional), `BlockedTime` (bloqueo puntual, de todo el negocio o de un profesional — valida que el profesional sea del mismo negocio), `Holiday`.
- **Clientes** (`Customer`): identificados por `phone` (único por negocio, no globalmente — el mismo número puede ser cliente de dos negocios distintos). Cualquier rol (incluido `STAFF`) puede gestionarlos, a diferencia del catálogo. `get_or_create_by_phone` ya está pensado para que lo use el webhook de WhatsApp en la Fase 6.

## Modelo de datos (resumen)

`users`, `businesses`, `memberships(user_id, business_id, role)`, `customers`, `professionals`, `services`, `professional_services`, `business_hours`, `professional_hours`, `blocked_times`, `holidays`, `appointments` (con `EXCLUDE USING gist` para prevenir double-booking a nivel de DB — pendiente, Fase 4), `whatsapp_accounts`, `conversations`, `messages` (con `whatsapp_message_id` único para idempotencia), `ai_settings`, `faqs`, `ai_tool_calls`, `reminders`, `audit_logs`, `plans`, `subscriptions`, `usage_counters`.

## Flujo de un mensaje de WhatsApp

```
Meta → Webhook (valida firma + idempotencia) → encola → 200 OK
Worker: resuelve business_id por phone_number_id → busca/crea customer y conversation
      → si HUMAN_HANDOFF: guarda y notifica dashboard, no llama al agente
      → si no: arma prompt dinámico → agente IA (tool calls contra servicios) → respuesta
      → guarda mensaje + logs de tool calls → envía por WhatsApp
```

## AI Agent

- Loop de tool-calling estándar (máx. ~5 iteraciones).
- Prompt dinámico por negocio (nombre, tono, reglas). Precios/servicios/disponibilidad **nunca** se embeben en el prompt — siempre se consultan por tool.
- Memoria: ventana deslizante + resumen para conversaciones largas (control de costo de tokens).
- Defensa en profundidad: cada tool re-valida en el servicio de negocio (ej. disponibilidad real en la misma transacción de `create_appointment`).

Tools MVP: `get_business_info`, `get_services`, `get_service_details`, `get_professionals`, `check_availability`, `create_customer`, `get_customer`, `get_customer_appointments`, `create_appointment`, `cancel_appointment`, `reschedule_appointment`, `get_business_hours`, `create_handoff`, `send_confirmation`, `get_faq`.

## Roadmap

1. ✅ **Base del proyecto** — monorepo, Next.js, FastAPI, Postgres, Docker, env config.
2. ✅ **Auth** — users, businesses, memberships, roles.
3. ✅ **Configuración del negocio** — servicios, profesionales, horarios, clientes. ← *estamos acá*
4. Sistema de turnos — crear/cancelar/reprogramar, disponibilidad, anti double-booking.
5. AI Agent — LLM abstraído, prompt dinámico, tool calling, memoria.
6. WhatsApp — webhook, envío/recepción, identificación de cliente.
7. Automatizaciones — recordatorios, confirmaciones.
8. Dashboard — calendario, conversaciones, clientes, estadísticas.
9. Seguridad + testing end-to-end.
10. Deployment a producción.

## Riesgos técnicos principales

- Double booking bajo concurrencia → constraint de DB, no solo lógica de app.
- Ventana de 24h de WhatsApp → recordatorios deben usar templates pre-aprobados por Meta.
- Aprobación de Meta (verificación de negocio + templates) puede tardar días/semanas → iniciar en paralelo al desarrollo.
- Costo de tokens por historial completo → mitigar con resumen/ventana desde Fase 5.
- Prompt injection cross-tenant → `business_id` nunca viaja en el contenido del mensaje.
- Mensajes duplicados del mismo cliente mientras se procesa el primero → lock por conversación en Redis.
- Timezones → todo en UTC en DB, conversión solo para mostrar según `businesses.timezone`.
