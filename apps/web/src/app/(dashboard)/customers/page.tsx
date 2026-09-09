"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import type { Customer } from "@/lib/types";
import { ApiError } from "@/lib/api";
import { Button, Card, EmptyState, ErrorBanner, Field, Input, PageHeader } from "@/components/ui";

interface CustomerForm {
  phone: string;
  name: string;
  email: string;
  notes: string;
}

const EMPTY_FORM: CustomerForm = { phone: "", name: "", email: "", notes: "" };

export default function CustomersPage() {
  const { apiFetch, business } = useAuth();
  const [customers, setCustomers] = useState<Customer[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CustomerForm>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  function load() {
    if (!business) return;
    apiFetch<Customer[]>(`/api/v1/businesses/${business.id}/customers`).then(setCustomers);
  }

  useEffect(load, [apiFetch, business]);

  function startCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
    setError(null);
  }

  function startEdit(c: Customer) {
    setEditingId(c.id);
    setForm({ phone: c.phone, name: c.name, email: c.email ?? "", notes: c.notes ?? "" });
    setShowForm(true);
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!business) return;
    setIsSaving(true);
    setError(null);
    try {
      if (editingId) {
        await apiFetch(`/api/v1/businesses/${business.id}/customers/${editingId}`, {
          method: "PATCH",
          body: { name: form.name, email: form.email || null, notes: form.notes || null },
        });
      } else {
        await apiFetch(`/api/v1/businesses/${business.id}/customers`, {
          method: "POST",
          body: { phone: form.phone, name: form.name, email: form.email || null, notes: form.notes || null },
        });
      }
      setShowForm(false);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar el cliente.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Clientes"
        subtitle="Se cargan solos cuando escriben por WhatsApp — acá podés verlos y editarlos"
        actions={<Button onClick={startCreate}>+ Nuevo cliente</Button>}
      />

      {showForm && (
        <Card className="mb-6">
          <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
            {error && (
              <div className="sm:col-span-2">
                <ErrorBanner message={error} />
              </div>
            )}
            <Field label="Teléfono">
              <Input
                required
                disabled={!!editingId}
                placeholder="+5491122334455"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </Field>
            <Field label="Nombre">
              <Input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </Field>
            <Field label="Email (opcional)">
              <Input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </Field>
            <Field label="Notas (opcional)">
              <Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
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
        {customers === null && <p className="text-sm text-muted">Cargando...</p>}
        {customers?.length === 0 && <EmptyState>Todavía no hay clientes cargados.</EmptyState>}
        <div className="divide-y divide-border">
          {customers?.map((c) => (
            <div key={c.id} className="flex items-center justify-between gap-3 py-3">
              <div>
                <p className="font-medium">{c.name}</p>
                <p className="text-sm text-muted">
                  {c.phone}
                  {c.email && <> · {c.email}</>}
                  {c.notes && <> · {c.notes}</>}
                </p>
              </div>
              <Button variant="secondary" onClick={() => startEdit(c)}>
                Editar
              </Button>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
