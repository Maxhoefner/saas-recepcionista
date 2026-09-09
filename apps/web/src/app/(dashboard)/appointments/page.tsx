"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import type { Appointment, Customer, Professional, Service } from "@/lib/types";
import { formatDate, formatTime, statusLabel } from "@/lib/format";
import { ApiError } from "@/lib/api";
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, Input, PageHeader } from "@/components/ui";

function dayBounds(date: Date): { from: string; to: string } {
  const from = new Date(date);
  from.setHours(0, 0, 0, 0);
  const to = new Date(from);
  to.setDate(to.getDate() + 1);
  return { from: from.toISOString(), to: to.toISOString() };
}

function toDatetimeLocalValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

const STATUS_TONE: Record<string, "neutral" | "success" | "warning" | "danger"> = {
  PENDING: "warning",
  CONFIRMED: "success",
  COMPLETED: "neutral",
  CANCELLED: "danger",
  NO_SHOW: "danger",
};

interface CreateForm {
  customer_id: string;
  professional_id: string;
  service_id: string;
  start_datetime: string;
}

export default function AppointmentsPage() {
  const { apiFetch, business } = useAuth();
  const [day, setDay] = useState(() => new Date());
  const [appointments, setAppointments] = useState<Appointment[] | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [professionals, setProfessionals] = useState<Professional[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CreateForm>({
    customer_id: "",
    professional_id: "",
    service_id: "",
    start_datetime: toDatetimeLocalValue(new Date()),
  });
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  function loadAppointments() {
    if (!business) return;
    const { from, to } = dayBounds(day);
    apiFetch<Appointment[]>(
      `/api/v1/businesses/${business.id}/appointments?date_from=${from}&date_to=${to}`
    ).then(setAppointments);
  }

  useEffect(loadAppointments, [apiFetch, business, day]);

  useEffect(() => {
    if (!business) return;
    apiFetch<Customer[]>(`/api/v1/businesses/${business.id}/customers`).then(setCustomers);
    apiFetch<Service[]>(`/api/v1/businesses/${business.id}/services`).then(setServices);
    apiFetch<Professional[]>(`/api/v1/businesses/${business.id}/professionals`).then(setProfessionals);
  }, [apiFetch, business]);

  const serviceName = (id: string) => services.find((s) => s.id === id)?.name ?? "?";
  const professionalName = (id: string) => professionals.find((p) => p.id === id)?.name ?? "?";
  const customerName = (id: string) => customers.find((c) => c.id === id)?.name ?? "?";

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!business) return;
    setIsSaving(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/businesses/${business.id}/appointments`, {
        method: "POST",
        body: {
          customer_id: form.customer_id,
          professional_id: form.professional_id,
          service_id: form.service_id,
          start_datetime: new Date(form.start_datetime).toISOString(),
        },
      });
      setShowForm(false);
      loadAppointments();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear el turno.");
    } finally {
      setIsSaving(false);
    }
  }

  async function act(appointment: Appointment, action: "cancel" | "confirm" | "complete" | "no-show") {
    if (!business) return;
    await apiFetch(`/api/v1/businesses/${business.id}/appointments/${appointment.id}/${action}`, {
      method: "POST",
    });
    loadAppointments();
  }

  return (
    <div>
      <PageHeader
        title="Turnos"
        actions={<Button onClick={() => setShowForm(true)}>+ Nuevo turno</Button>}
      />

      <div className="mb-4 flex items-center gap-2">
        <Button variant="secondary" onClick={() => setDay(new Date(day.getTime() - 86400000))}>
          ← Anterior
        </Button>
        <Button variant="secondary" onClick={() => setDay(new Date())}>
          Hoy
        </Button>
        <Button variant="secondary" onClick={() => setDay(new Date(day.getTime() + 86400000))}>
          Siguiente →
        </Button>
        <span className="ml-2 text-sm font-medium capitalize">{formatDate(day.toISOString())}</span>
      </div>

      {showForm && (
        <Card className="mb-6">
          <form onSubmit={handleCreate} className="grid gap-4 sm:grid-cols-2">
            {error && (
              <div className="sm:col-span-2">
                <ErrorBanner message={error} />
              </div>
            )}
            <Field label="Cliente">
              <select
                required
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
                value={form.customer_id}
                onChange={(e) => setForm({ ...form, customer_id: e.target.value })}
              >
                <option value="">Elegir...</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.phone})
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Servicio">
              <select
                required
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
                value={form.service_id}
                onChange={(e) => setForm({ ...form, service_id: e.target.value })}
              >
                <option value="">Elegir...</option>
                {services.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Profesional">
              <select
                required
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
                value={form.professional_id}
                onChange={(e) => setForm({ ...form, professional_id: e.target.value })}
              >
                <option value="">Elegir...</option>
                {professionals.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Fecha y hora">
              <Input
                type="datetime-local"
                required
                value={form.start_datetime}
                onChange={(e) => setForm({ ...form, start_datetime: e.target.value })}
              />
            </Field>
            <div className="flex gap-2 sm:col-span-2">
              <Button type="submit" disabled={isSaving}>
                {isSaving ? "Creando..." : "Crear turno"}
              </Button>
              <Button type="button" variant="secondary" onClick={() => setShowForm(false)}>
                Cancelar
              </Button>
            </div>
          </form>
        </Card>
      )}

      <Card>
        {appointments === null && <p className="text-sm text-muted">Cargando...</p>}
        {appointments?.length === 0 && <EmptyState>No hay turnos para este día.</EmptyState>}
        <div className="divide-y divide-border">
          {appointments?.map((a) => (
            <div key={a.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div>
                <p className="font-medium">
                  {formatTime(a.start_datetime)} · {serviceName(a.service_id)}
                </p>
                <p className="text-sm text-muted">
                  {customerName(a.customer_id)} con {professionalName(a.professional_id)}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={STATUS_TONE[a.status]}>{statusLabel(a.status)}</Badge>
                {a.status === "PENDING" && (
                  <Button variant="secondary" onClick={() => act(a, "confirm")}>
                    Confirmar
                  </Button>
                )}
                {(a.status === "PENDING" || a.status === "CONFIRMED") && (
                  <>
                    <Button variant="secondary" onClick={() => act(a, "complete")}>
                      Completar
                    </Button>
                    <Button variant="secondary" onClick={() => act(a, "no-show")}>
                      No asistió
                    </Button>
                    <Button variant="danger" onClick={() => act(a, "cancel")}>
                      Cancelar
                    </Button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
