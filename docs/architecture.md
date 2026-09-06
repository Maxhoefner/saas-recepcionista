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

## Turnos y disponibilidad (Fase 4)

- **Anti double-booking real, no solo aplicativo**: `appointments` tiene un `EXCLUDE USING gist (professional_id WITH =, tstzrange(start_datetime, end_datetime) WITH &&) WHERE status <> 'CANCELLED'`. Dos requests concurrentes para el mismo profesional y horario chocan en Postgres, no en una condición de carrera del código Python. Requiere la extensión `btree_gist` (habilitada en la migración).
- **`availability_service.py`** calcula disponibilidad real: toma `ProfessionalHours` del día (o `BusinessHours` si el profesional no tiene override), le resta feriados, `BlockedTime` (del negocio o del profesional) y turnos ya ocupados, y devuelve slots del tamaño de `duration_minutes` del servicio. Todo convertido correctamente entre el timezone del negocio y UTC (nunca se asume UTC para horarios de atención).
- **`validate_slot_available`** se corre en `create_appointment`/`reschedule_appointment` para rechazar turnos fuera de horario o sobre un bloqueo/feriado — deliberadamente NO chequea solapamiento con otros turnos ahí (eso lo cierra el constraint de la DB, el único lugar seguro contra una carrera real).
- Estados: `PENDING → CONFIRMED → COMPLETED`, con `CANCELLED`/`NO_SHOW` como salidas — transiciones inválidas (cancelar un turno ya completado, etc.) rechazadas explícitamente.
- Permisos igual que `customers`: cualquier rol de la membership puede gestionar turnos (trabajo operativo diario).

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

## AI Agent (Fase 5)

- **Abstracción de proveedor** (`app/ai/providers/`): `LLMProvider` es la única interfaz que el resto del código conoce. `AnthropicProvider` es la implementación concreta; agregar otro proveedor es implementar la interfaz, no tocar el agente. El formato de mensajes interno (`ChatMessage`/`ChatRole`) es propio, no el de Anthropic — el provider traduce en ambas direcciones.
- **Tools** (`app/ai/tools/`): cada una es un `ToolDefinition` (nombre, descripción, schema de argumentos vía Pydantic, handler). Los handlers llaman a los *services* de las Fases 3/4 — nunca SQL directo. El `business_id` se inyecta desde el `ToolContext` server-side; el LLM nunca lo ve ni lo puede pasar como argumento. Las tools sobre turnos (`cancel_appointment`, `reschedule_appointment`) además verifican que el turno pertenezca al `customer_id` de la conversación — aislamiento a nivel de cliente, no solo de negocio.
- **Resolución por nombre**: el cliente dice "corte", no un UUID — `find_by_name()` hace el matching (exacto o parcial, case-insensitive) contra servicios/profesionales activos, devolviendo un error legible para el LLM si es ambiguo o no existe. Los turnos sí se referencian por id una vez que `get_customer_appointments` se lo dio al modelo.
- **Loop de tool-calling** (`app/ai/agent.py`): máx. `AGENT_MAX_TOOL_ITERATIONS` (default 5) iteraciones. Cada tool call se audita en `ai_tool_calls` (nombre, argumentos, resultado, éxito, latencia). Un error de tool nunca tira la conversación — se loguea internamente y se le devuelve `{"error": ...}` al modelo para que lo maneje con naturalidad (regla 33).
- **`create_handoff` es terminal**: en cuanto se ejecuta, el loop corta y la conversación pasa a `HUMAN_HANDOFF` — `handle_message` chequea ese estado antes de siquiera invocar al agente, así que los mensajes posteriores del cliente se guardan pero no generan respuesta automática hasta que alguien la devuelva a la IA.
- **Prompt dinámico** (`app/ai/prompts/system_prompt.py`): nombre/tono del asistente desde `AISettings` (configurable por negocio, con defaults perezosos), fecha/hora actual en el timezone del negocio, y las reglas fijas (nunca inventar, confirmar antes de acciones sensibles, no revelar info interna, timezone del negocio no UTC, etc.). Precios/servicios/disponibilidad **nunca** se embeben en el prompt — siempre se consultan por tool.
- **Memoria**: ventana deslizante de los últimos 30 mensajes; resumir conversaciones más largas queda para cuando el volumen real lo justifique, no es necesario para el MVP.
- **Sin WhatsApp todavía**: `POST /businesses/{id}/conversations/{id}/messages` simula un mensaje entrante y devuelve la respuesta del agente — es exactamente lo que el webhook de WhatsApp (Fase 6) va a invocar internamente (`agent.handle_message`) en lugar de HTTP.
- **Tests con proveedor scripteado** (`FakeProvider` en `conftest.py`): nada de llamadas reales a la API de Claude en la suite — cada test encola las respuestas exactas que el "modelo" debe dar y verifica qué tools se ejecutaron y con qué resultado.

Tools implementadas: `get_business_info`, `get_services`, `get_service_details`, `get_professionals`, `get_business_hours`, `check_availability`, `create_appointment`, `get_customer_appointments`, `cancel_appointment`, `reschedule_appointment`, `get_faq`, `create_handoff`. (`send_confirmation` del diseño original se descartó: la confirmación es simplemente la respuesta final del propio modelo, no una acción separada.)

## Roadmap

1. ✅ **Base del proyecto** — monorepo, Next.js, FastAPI, Postgres, Docker, env config.
2. ✅ **Auth** — users, businesses, memberships, roles.
3. ✅ **Configuración del negocio** — servicios, profesionales, horarios, clientes.
4. ✅ **Sistema de turnos** — crear/cancelar/reprogramar, disponibilidad, anti double-booking.
5. ✅ **AI Agent** — LLM abstraído, prompt dinámico, tool calling, memoria. ← *estamos acá*
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
