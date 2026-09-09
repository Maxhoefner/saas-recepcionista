"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import type { Professional, Service } from "@/lib/types";
import { ApiError } from "@/lib/api";
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, Input, PageHeader } from "@/components/ui";

interface ProfessionalForm {
  name: string;
  service_ids: string[];
}

const EMPTY_FORM: ProfessionalForm = { name: "", service_ids: [] };

export default function ProfessionalsPage() {
  const { apiFetch, business } = useAuth();
  const [professionals, setProfessionals] = useState<Professional[] | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<ProfessionalForm>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  function load() {
    if (!business) return;
    apiFetch<Professional[]>(`/api/v1/businesses/${business.id}/professionals`).then(setProfessionals);
    apiFetch<Service[]>(`/api/v1/businesses/${business.id}/services`).then(setServices);
  }

  useEffect(load, [apiFetch, business]);

  function startCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
    setError(null);
  }

  function startEdit(p: Professional) {
    setEditingId(p.id);
    setForm({ name: p.name, service_ids: p.service_ids });
    setShowForm(true);
    setError(null);
  }

  function toggleService(id: string) {
    setForm((prev) => ({
      ...prev,
      service_ids: prev.service_ids.includes(id)
        ? prev.service_ids.filter((s) => s !== id)
        : [...prev.service_ids, id],
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!business) return;
    setIsSaving(true);
    setError(null);
    try {
      if (editingId) {
        await apiFetch(`/api/v1/businesses/${business.id}/professionals/${editingId}`, {
          method: "PATCH",
          body: { name: form.name, service_ids: form.service_ids },
        });
      } else {
        await apiFetch(`/api/v1/businesses/${business.id}/professionals`, {
          method: "POST",
          body: { name: form.name, service_ids: form.service_ids },
        });
      }
      setShowForm(false);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar el profesional.");
    } finally {
      setIsSaving(false);
    }
  }

  async function toggleActive(p: Professional) {
    if (!business) return;
    await apiFetch(`/api/v1/businesses/${business.id}/professionals/${p.id}`, {
      method: "PATCH",
      body: { active: !p.active },
    });
    load();
  }

  async function remove(p: Professional) {
    if (!business) return;
    if (!confirm(`¿Eliminar a "${p.name}"?`)) return;
    await apiFetch(`/api/v1/businesses/${business.id}/professionals/${p.id}`, { method: "DELETE" });
    load();
  }

  const serviceName = (id: string) => services.find((s) => s.id === id)?.name ?? "?";

  return (
    <div>
      <PageHeader
        title="Profesionales"
        subtitle="Quién atiende, y qué servicios realiza cada uno"
        actions={<Button onClick={startCreate}>+ Nuevo profesional</Button>}
      />

      {showForm && (
        <Card className="mb-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && <ErrorBanner message={error} />}
            <Field label="Nombre">
              <Input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </Field>
            <Field label="Servicios que realiza">
              <div className="flex flex-wrap gap-2">
                {services.length === 0 && (
                  <p className="text-sm text-muted">Cargá primero algún servicio.</p>
                )}
                {services.map((s) => (
                  <label
                    key={s.id}
                    className={`cursor-pointer rounded-full border px-3 py-1 text-sm ${
                      form.service_ids.includes(s.id)
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-surface"
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="hidden"
                      checked={form.service_ids.includes(s.id)}
                      onChange={() => toggleService(s.id)}
                    />
                    {s.name}
                  </label>
                ))}
              </div>
            </Field>
            <div className="flex gap-2">
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
        {professionals === null && <p className="text-sm text-muted">Cargando...</p>}
        {professionals?.length === 0 && <EmptyState>Todavía no cargaste ningún profesional.</EmptyState>}
        <div className="divide-y divide-border">
          {professionals?.map((p) => (
            <div key={p.id} className="flex items-center justify-between gap-3 py-3">
              <div>
                <p className="font-medium">
                  {p.name} {!p.active && <Badge tone="neutral">Inactivo</Badge>}
                </p>
                <p className="text-sm text-muted">
                  {p.service_ids.length > 0
                    ? p.service_ids.map(serviceName).join(", ")
                    : "Sin servicios asignados"}
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                <Button variant="secondary" onClick={() => startEdit(p)}>
                  Editar
                </Button>
                <Button variant="secondary" onClick={() => toggleActive(p)}>
                  {p.active ? "Desactivar" : "Activar"}
                </Button>
                <Button variant="danger" onClick={() => remove(p)}>
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
