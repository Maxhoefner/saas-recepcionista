"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import type { AISettings, FAQ, ReminderSettings, WeeklyHours, WhatsAppAccount } from "@/lib/types";
import { ApiError } from "@/lib/api";
import { Button, Card, ErrorBanner, Field, Input, PageHeader } from "@/components/ui";

const WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const TABS = ["Horarios", "IA", "WhatsApp", "Recordatorios", "FAQs"] as const;
type Tab = (typeof TABS)[number];

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <h2 className="mb-4 font-medium">{title}</h2>
      {children}
    </Card>
  );
}

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("Horarios");

  return (
    <div>
      <PageHeader title="Configuración" />
      <div className="mb-6 flex gap-2 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`border-b-2 px-3 py-2 text-sm font-medium ${
              tab === t ? "border-primary text-primary" : "border-transparent text-muted"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Horarios" && <HoursSection />}
      {tab === "IA" && <AISection />}
      {tab === "WhatsApp" && <WhatsAppSection />}
      {tab === "Recordatorios" && <ReminderSection />}
      {tab === "FAQs" && <FAQSection />}
    </div>
  );
}

function HoursSection() {
  const { apiFetch, business } = useAuth();
  const [rows, setRows] = useState<
    { enabled: boolean; start_time: string; end_time: string }[]
  >(WEEKDAYS.map(() => ({ enabled: false, start_time: "09:00", end_time: "18:00" })));
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!business) return;
    apiFetch<WeeklyHours[]>(`/api/v1/businesses/${business.id}/business-hours`).then((hours) => {
      setRows((prev) =>
        prev.map((row, weekday) => {
          const match = hours.find((h) => h.weekday === weekday);
          return match
            ? { enabled: true, start_time: match.start_time.slice(0, 5), end_time: match.end_time.slice(0, 5) }
            : row;
        })
      );
    });
  }, [apiFetch, business]);

  async function save() {
    if (!business) return;
    setIsSaving(true);
    setError(null);
    setSaved(false);
    const payload = rows
      .map((row, weekday) => ({ ...row, weekday }))
      .filter((row) => row.enabled)
      .map((row) => ({
        weekday: row.weekday,
        start_time: `${row.start_time}:00`,
        end_time: `${row.end_time}:00`,
      }));
    try {
      await apiFetch(`/api/v1/businesses/${business.id}/business-hours`, {
        method: "PUT",
        body: payload,
      });
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudieron guardar los horarios.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <SectionCard title="Horario de atención semanal">
      {error && (
        <div className="mb-3">
          <ErrorBanner message={error} />
        </div>
      )}
      <div className="space-y-2">
        {WEEKDAYS.map((label, i) => (
          <div key={label} className="flex items-center gap-3">
            <label className="flex w-32 items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={rows[i].enabled}
                onChange={(e) =>
                  setRows((prev) =>
                    prev.map((r, idx) => (idx === i ? { ...r, enabled: e.target.checked } : r))
                  )
                }
              />
              {label}
            </label>
            <Input
              type="time"
              disabled={!rows[i].enabled}
              className="w-32"
              value={rows[i].start_time}
              onChange={(e) =>
                setRows((prev) =>
                  prev.map((r, idx) => (idx === i ? { ...r, start_time: e.target.value } : r))
                )
              }
            />
            <span className="text-muted">a</span>
            <Input
              type="time"
              disabled={!rows[i].enabled}
              className="w-32"
              value={rows[i].end_time}
              onChange={(e) =>
                setRows((prev) =>
                  prev.map((r, idx) => (idx === i ? { ...r, end_time: e.target.value } : r))
                )
              }
            />
          </div>
        ))}
      </div>
      <div className="mt-4 flex items-center gap-3">
        <Button onClick={save} disabled={isSaving}>
          {isSaving ? "Guardando..." : "Guardar horarios"}
        </Button>
        {saved && <span className="text-sm text-success">Guardado ✓</span>}
      </div>
    </SectionCard>
  );
}

function AISection() {
  const { apiFetch, business } = useAuth();
  const [form, setForm] = useState<AISettings | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!business) return;
    apiFetch<AISettings>(`/api/v1/businesses/${business.id}/ai-settings`).then(setForm);
  }, [apiFetch, business]);

  async function save() {
    if (!business || !form) return;
    setIsSaving(true);
    setSaved(false);
    await apiFetch(`/api/v1/businesses/${business.id}/ai-settings`, { method: "PUT", body: form });
    setIsSaving(false);
    setSaved(true);
  }

  if (!form) return <SectionCard title="Personalidad de la IA"><p className="text-sm text-muted">Cargando...</p></SectionCard>;

  return (
    <SectionCard title="Personalidad de la IA">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Nombre del asistente">
          <Input value={form.assistant_name} onChange={(e) => setForm({ ...form, assistant_name: e.target.value })} />
        </Field>
        <Field label="Idioma">
          <Input value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })} />
        </Field>
        <div className="sm:col-span-2">
          <Field label="Tono / personalidad">
            <Input value={form.tone} onChange={(e) => setForm({ ...form, tone: e.target.value })} />
          </Field>
        </div>
        <div className="sm:col-span-2">
          <Field label="Mensaje de bienvenida (opcional)">
            <Input
              value={form.welcome_message ?? ""}
              onChange={(e) => setForm({ ...form, welcome_message: e.target.value || null })}
            />
          </Field>
        </div>
        <div className="sm:col-span-2">
          <Field label="Instrucciones adicionales (opcional)">
            <Input
              value={form.extra_instructions ?? ""}
              onChange={(e) => setForm({ ...form, extra_instructions: e.target.value || null })}
            />
          </Field>
        </div>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <Button onClick={save} disabled={isSaving}>
          {isSaving ? "Guardando..." : "Guardar"}
        </Button>
        {saved && <span className="text-sm text-success">Guardado ✓</span>}
      </div>
    </SectionCard>
  );
}

function WhatsAppSection() {
  const { apiFetch, business } = useAuth();
  const [account, setAccount] = useState<WhatsAppAccount | null | undefined>(undefined);
  const [form, setForm] = useState({
    phone_number_id: "",
    waba_id: "",
    display_phone_number: "",
    access_token: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!business) return;
    apiFetch<WhatsAppAccount>(`/api/v1/businesses/${business.id}/whatsapp-account`)
      .then((acc) => {
        setAccount(acc);
        setForm({ ...acc, access_token: "" });
      })
      .catch(() => setAccount(null));
  }, [apiFetch, business]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!business) return;
    setIsSaving(true);
    setError(null);
    try {
      const acc = await apiFetch<WhatsAppAccount>(`/api/v1/businesses/${business.id}/whatsapp-account`, {
        method: "PUT",
        body: form,
      });
      setAccount(acc);
      setForm({ ...acc, access_token: "" });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo conectar la cuenta.");
    } finally {
      setIsSaving(false);
    }
  }

  if (account === undefined) {
    return <SectionCard title="WhatsApp"><p className="text-sm text-muted">Cargando...</p></SectionCard>;
  }

  return (
    <SectionCard title="Cuenta de WhatsApp">
      {!account && (
        <p className="mb-4 text-sm text-muted">
          Todavía no conectaste un número. Los datos salen del panel de tu app en Meta for Developers.
        </p>
      )}
      <form onSubmit={save} className="grid gap-4 sm:grid-cols-2">
        {error && (
          <div className="sm:col-span-2">
            <ErrorBanner message={error} />
          </div>
        )}
        <Field label="Phone number ID">
          <Input
            required
            value={form.phone_number_id}
            onChange={(e) => setForm({ ...form, phone_number_id: e.target.value })}
          />
        </Field>
        <Field label="WABA ID">
          <Input required value={form.waba_id} onChange={(e) => setForm({ ...form, waba_id: e.target.value })} />
        </Field>
        <Field label="Número visible">
          <Input
            required
            value={form.display_phone_number}
            onChange={(e) => setForm({ ...form, display_phone_number: e.target.value })}
          />
        </Field>
        <Field label={account ? "Nuevo access token (dejar vacío para no cambiarlo)" : "Access token"}>
          <Input
            type="password"
            required={!account}
            value={form.access_token}
            onChange={(e) => setForm({ ...form, access_token: e.target.value })}
          />
        </Field>
        <div className="sm:col-span-2">
          <Button type="submit" disabled={isSaving}>
            {isSaving ? "Guardando..." : account ? "Actualizar conexión" : "Conectar"}
          </Button>
        </div>
      </form>
    </SectionCard>
  );
}

function ReminderSection() {
  const { apiFetch, business } = useAuth();
  const [form, setForm] = useState<ReminderSettings | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!business) return;
    apiFetch<ReminderSettings>(`/api/v1/businesses/${business.id}/reminder-settings`).then(setForm);
  }, [apiFetch, business]);

  async function save() {
    if (!business || !form) return;
    setIsSaving(true);
    setSaved(false);
    await apiFetch(`/api/v1/businesses/${business.id}/reminder-settings`, { method: "PUT", body: form });
    setIsSaving(false);
    setSaved(true);
  }

  if (!form) return <SectionCard title="Recordatorios"><p className="text-sm text-muted">Cargando...</p></SectionCard>;

  return (
    <SectionCard title="Recordatorios automáticos">
      <label className="mb-4 flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={form.enabled}
          onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
        />
        Activados
      </label>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Horas antes del turno">
          <Input
            type="number"
            min={1}
            max={168}
            value={form.hours_before}
            onChange={(e) => setForm({ ...form, hours_before: Number(e.target.value) })}
          />
        </Field>
        <div className="sm:col-span-2">
          <Field label="Mensaje (placeholders: {customer_name} {service} {date} {time})">
            <Input
              value={form.message_template}
              onChange={(e) => setForm({ ...form, message_template: e.target.value })}
            />
          </Field>
        </div>
      </div>
      <p className="mt-2 text-xs text-muted">
        Fuera de la ventana de 24hs de conversación, WhatsApp exige usar templates pre-aprobados —
        este texto libre sirve para desarrollo; en producción real hay que migrar a un template aprobado por Meta.
      </p>
      <div className="mt-4 flex items-center gap-3">
        <Button onClick={save} disabled={isSaving}>
          {isSaving ? "Guardando..." : "Guardar"}
        </Button>
        {saved && <span className="text-sm text-success">Guardado ✓</span>}
      </div>
    </SectionCard>
  );
}

function FAQSection() {
  const { apiFetch, business } = useAuth();
  const [faqs, setFaqs] = useState<FAQ[] | null>(null);
  const [form, setForm] = useState({ question: "", answer: "" });
  const [isSaving, setIsSaving] = useState(false);

  function load() {
    if (!business) return;
    apiFetch<FAQ[]>(`/api/v1/businesses/${business.id}/faqs`).then(setFaqs);
  }

  useEffect(load, [apiFetch, business]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!business) return;
    setIsSaving(true);
    await apiFetch(`/api/v1/businesses/${business.id}/faqs`, { method: "POST", body: form });
    setForm({ question: "", answer: "" });
    setIsSaving(false);
    load();
  }

  async function remove(id: string) {
    if (!business) return;
    await apiFetch(`/api/v1/businesses/${business.id}/faqs/${id}`, { method: "DELETE" });
    load();
  }

  return (
    <SectionCard title="Preguntas frecuentes">
      <form onSubmit={add} className="mb-6 grid gap-3 sm:grid-cols-2">
        <Field label="Pregunta">
          <Input
            required
            value={form.question}
            onChange={(e) => setForm({ ...form, question: e.target.value })}
          />
        </Field>
        <Field label="Respuesta">
          <Input
            required
            value={form.answer}
            onChange={(e) => setForm({ ...form, answer: e.target.value })}
          />
        </Field>
        <div className="sm:col-span-2">
          <Button type="submit" disabled={isSaving}>
            + Agregar
          </Button>
        </div>
      </form>
      <div className="divide-y divide-border">
        {faqs?.map((f) => (
          <div key={f.id} className="flex items-center justify-between gap-3 py-3">
            <div>
              <p className="font-medium">{f.question}</p>
              <p className="text-sm text-muted">{f.answer}</p>
            </div>
            <Button variant="danger" onClick={() => remove(f.id)}>
              Eliminar
            </Button>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
