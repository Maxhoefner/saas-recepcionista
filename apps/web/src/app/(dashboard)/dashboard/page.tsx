"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import type { Appointment, Conversation, Customer, Professional, Service } from "@/lib/types";
import { formatTime, statusLabel } from "@/lib/format";
import { Badge, Card, PageHeader } from "@/components/ui";

function startOfDayISO(date: Date): string {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}

export default function DashboardHomePage() {
  const { apiFetch, business } = useAuth();
  const [appointments, setAppointments] = useState<Appointment[] | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [professionals, setProfessionals] = useState<Professional[]>([]);
  const [customerCount, setCustomerCount] = useState<number | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);

  useEffect(() => {
    if (!business) return;
    const todayStart = startOfDayISO(new Date());
    const tomorrowStart = startOfDayISO(new Date(Date.now() + 24 * 60 * 60 * 1000));

    Promise.all([
      apiFetch<Appointment[]>(
        `/api/v1/businesses/${business.id}/appointments?date_from=${todayStart}&date_to=${tomorrowStart}`
      ),
      apiFetch<Service[]>(`/api/v1/businesses/${business.id}/services`),
      apiFetch<Professional[]>(`/api/v1/businesses/${business.id}/professionals`),
      apiFetch<Customer[]>(`/api/v1/businesses/${business.id}/customers`),
      apiFetch<Conversation[]>(`/api/v1/businesses/${business.id}/conversations`),
    ]).then(([appts, svcs, pros, customers, convos]) => {
      setAppointments(appts);
      setServices(svcs);
      setProfessionals(pros);
      setCustomerCount(customers.length);
      setConversations(convos);
    });
  }, [apiFetch, business]);

  const serviceName = (id: string) => services.find((s) => s.id === id)?.name ?? "—";
  const professionalName = (id: string) => professionals.find((p) => p.id === id)?.name ?? "—";
  const handoffCount = conversations.filter((c) => c.status === "HUMAN_HANDOFF").length;
  const activeCount = conversations.filter((c) => c.status === "AI_ACTIVE").length;

  return (
    <div>
      <PageHeader title="Dashboard" subtitle={business?.name} />

      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <p className="text-xs text-muted">Turnos hoy</p>
          <p className="text-2xl font-semibold">{appointments?.length ?? "—"}</p>
        </Card>
        <Card>
          <p className="text-xs text-muted">Clientes</p>
          <p className="text-2xl font-semibold">{customerCount ?? "—"}</p>
        </Card>
        <Card>
          <p className="text-xs text-muted">Conversaciones con IA</p>
          <p className="text-2xl font-semibold">{activeCount}</p>
        </Card>
        <Card>
          <p className="text-xs text-muted">Requieren atención</p>
          <p className="text-2xl font-semibold text-danger">{handoffCount}</p>
        </Card>
      </div>

      <Card>
        <h2 className="mb-3 font-medium">Turnos de hoy</h2>
        {appointments === null && <p className="text-sm text-muted">Cargando...</p>}
        {appointments?.length === 0 && (
          <p className="text-sm text-muted">No hay turnos programados para hoy.</p>
        )}
        <div className="divide-y divide-border">
          {appointments?.map((a) => (
            <div key={a.id} className="flex items-center justify-between py-2.5 text-sm">
              <div>
                <span className="font-medium">{formatTime(a.start_datetime)}</span>{" "}
                <span className="text-muted">— {serviceName(a.service_id)}</span>
                <span className="text-muted"> con {professionalName(a.professional_id)}</span>
              </div>
              <Badge
                tone={
                  a.status === "CANCELLED" || a.status === "NO_SHOW"
                    ? "danger"
                    : a.status === "COMPLETED" || a.status === "CONFIRMED"
                      ? "success"
                      : "neutral"
                }
              >
                {statusLabel(a.status)}
              </Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
