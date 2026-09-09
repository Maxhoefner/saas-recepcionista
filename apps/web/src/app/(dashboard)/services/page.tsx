"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import type { Service } from "@/lib/types";
import { formatMoney } from "@/lib/format";
import { ApiError } from "@/lib/api";
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, Input, PageHeader } from "@/components/ui";

interface ServiceForm {
  name: string;
  description: string;
  price_cents: string;
  duration_minutes: string;
}

const EMPTY_FORM: ServiceForm = { name: "", description: "", price_cents: "", duration_minutes: "" };

export default function ServicesPage() {
  const { apiFetch, business } = useAuth();
  const [services, setServices] = useState<Service[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<ServiceForm>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  function load() {
    if (!business) return;
    apiFetch<Service[]>(`/api/v1/businesses/${business.id}/services`).then(setServices);
  }

  useEffect(load, [apiFetch, business]);

  function startCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
    setError(null);
  }

  function startEdit(service: Service) {
    setEditingId(service.id);
    setForm({
      name: service.name,
      description: service.description ?? "",
      price_cents: String(service.price_cents),
      duration_minutes: String(service.duration_minutes),
    });
    setShowForm(true);
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!business) return;
    setIsSaving(true);
    setError(null);
    const payload = {
      name: form.name,
      description: form.description || null,
      price_cents: Math.round(Number(form.price_cents)),
      duration_minutes: Math.round(Number(form.duration_minutes)),
    };
    try {
      if (editingId) {
        await apiFetch(`/api/v1/businesses/${business.id}/services/${editingId}`, {
          method: "PATCH",
          body: payload,
        });
      } else {
        await apiFetch(`/api/v1/businesses/${business.id}/services`, {
          method: "POST",
          body: payload,
        });
      }
      setShowForm(false);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar el servicio.");
    } finally {
      setIsSaving(false);
    }
  }

  async function toggleActive(service: Service) {
    if (!business) return;
    await apiFetch(`/api/v1/businesses/${business.id}/services/${service.id}`, {
      method: "PATCH",
      body: { active: !service.active },
    });
    load();
  }

  async function remove(service: Service) {
    if (!business) return;
    if (!confirm(`¿Eliminar "${service.name}"?`)) return;
    await apiFetch(`/api/v1/businesses/${business.id}/services/${service.id}`, { method: "DELETE" });
    load();
  }

  return (
    <div>
      <PageHeader
        title="Servicios"
        subtitle="El catálogo que la IA ofrece a tus clientes"
        actions={<Button onClick={startCreate}>+ Nuevo servicio</Button>}
      />

      {showForm && (
        <Card className="mb-6">
          <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
            {error && (
              <div className="sm:col-span-2">
                <ErrorBanner message={error} />
              </div>
            )}
            <Field label="Nombre">
              <Input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </Field>
            <Field label="Descripción (opcional)">
              <Input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </Field>
            <Field label="Precio (ARS)">
              <Input
                type="number"
                min={0}
                required
                value={form.price_cents ? Number(form.price_cents) / 100 : ""}
                onChange={(e) => setForm({ ...form, price_cents: String(Number(e.target.value) * 100) })}
              />
            </Field>
            <Field label="Duración (minutos)">
              <Input
                type="number"
                min={1}
                required
                value={form.duration_minutes}
                onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })}
              />
            </Field>
            <div className="flex gap-2 sm:col-span-2">
              <Button type="submit" disabled={isSaving}>
                {isSaving ? "Guardando..." : "Guardar"}
              </Button>
              <Button type="button" variant="secondary" onClick={() => setShowForm(false)}>
                Cancelar
              </Button>
            </div>
          </form>
        </Card>
      )}

      <Card>
        {services === null && <p className="text-sm text-muted">Cargando...</p>}
        {services?.length === 0 && <EmptyState>Todavía no cargaste ningún servicio.</EmptyState>}
        <div className="divide-y divide-border">
          {services?.map((s) => (
            <div key={s.id} className="flex items-center justify-between gap-3 py-3">
              <div>
                <p className="font-medium">
                  {s.name} {!s.active && <Badge tone="neutral">Inactivo</Badge>}
                </p>
                <p className="text-sm text-muted">
                  {formatMoney(s.price_cents)} · {s.duration_minutes} min
                  {s.description && <> · {s.description}</>}
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                <Button variant="secondary" onClick={() => startEdit(s)}>
                  Editar
                </Button>
                <Button variant="secondary" onClick={() => toggleActive(s)}>
                  {s.active ? "Desactivar" : "Activar"}
                </Button>
                <Button variant="danger" onClick={() => remove(s)}>
                  Eliminar
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
