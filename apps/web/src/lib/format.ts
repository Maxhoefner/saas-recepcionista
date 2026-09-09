export function formatMoney(cents: number): string {
  return (cents / 100).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("es-AR", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
  });
}

const STATUS_LABELS: Record<string, string> = {
  PENDING: "Pendiente",
  CONFIRMED: "Confirmado",
  COMPLETED: "Completado",
  CANCELLED: "Cancelado",
  NO_SHOW: "No asistió",
  AI_ACTIVE: "IA activa",
  HUMAN_HANDOFF: "Requiere atención",
  CLOSED: "Cerrada",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}
