"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import type { Conversation, Customer, Message } from "@/lib/types";
import { formatDateTime, statusLabel } from "@/lib/format";
import { Badge, Button, Card, EmptyState, PageHeader } from "@/components/ui";

export default function ConversationsPage() {
  const { apiFetch, business } = useAuth();
  const [conversations, setConversations] = useState<Conversation[] | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  function loadConversations() {
    if (!business) return;
    apiFetch<Conversation[]>(`/api/v1/businesses/${business.id}/conversations`).then(setConversations);
  }

  useEffect(loadConversations, [apiFetch, business]);

  useEffect(() => {
    if (!business) return;
    apiFetch<Customer[]>(`/api/v1/businesses/${business.id}/customers`).then(setCustomers);
  }, [apiFetch, business]);

  const customerName = (id: string) => customers.find((c) => c.id === id)?.name ?? "Desconocido";
  const selected = conversations?.find((c) => c.id === selectedId) ?? null;

  return (
    <div>
      <PageHeader title="Conversaciones" subtitle="Lo que la IA está hablando con tus clientes por WhatsApp" />

      <div className="grid gap-4 md:grid-cols-[320px_1fr]">
        <Card className="p-0">
          {conversations === null && <p className="p-4 text-sm text-muted">Cargando...</p>}
          {conversations?.length === 0 && (
            <div className="p-4">
              <EmptyState>Todavía no hay conversaciones.</EmptyState>
            </div>
          )}
          <div className="divide-y divide-border">
            {conversations?.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelectedId(c.id)}
                className={`block w-full px-4 py-3 text-left text-sm hover:bg-background ${
                  selectedId === c.id ? "bg-background" : ""
                }`}
              >
                <p className="font-medium">{customerName(c.customer_id)}</p>
                <div className="mt-1 flex items-center gap-2">
                  <Badge tone={c.status === "HUMAN_HANDOFF" ? "danger" : "success"}>
                    {statusLabel(c.status)}
                  </Badge>
                  {c.last_message_at && (
                    <span className="text-xs text-muted">{formatDateTime(c.last_message_at)}</span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </Card>

        <Card>
          {!selected && <EmptyState>Elegí una conversación para ver los mensajes.</EmptyState>}
          {selected && (
            <ConversationDetail
              key={selected.id}
              conversation={selected}
              customerName={customerName(selected.customer_id)}
              onStatusChange={loadConversations}
            />
          )}
        </Card>
      </div>
    </div>
  );
}

function ConversationDetail({
  conversation,
  customerName,
  onStatusChange,
}: {
  conversation: Conversation;
  customerName: string;
  onStatusChange: () => void;
}) {
  const { apiFetch, business } = useAuth();
  const [status, setStatusValue] = useState(conversation.status);
  const [messages, setMessages] = useState<Message[] | null>(null);

  useEffect(() => {
    if (!business) return;
    apiFetch<Message[]>(
      `/api/v1/businesses/${business.id}/conversations/${conversation.id}/messages`
    ).then(setMessages);
    // Re-fetch only when switching to a different conversation (this
    // component remounts via `key` on the parent) — not on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function changeStatus(action: "handoff" | "return-to-ai") {
    if (!business) return;
    const updated = await apiFetch<Conversation>(
      `/api/v1/businesses/${business.id}/conversations/${conversation.id}/${action}`,
      { method: "POST" }
    );
    setStatusValue(updated.status);
    onStatusChange();
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="font-medium">{customerName}</p>
          <Badge tone={status === "HUMAN_HANDOFF" ? "danger" : "success"}>{statusLabel(status)}</Badge>
        </div>
        {status === "HUMAN_HANDOFF" ? (
          <Button onClick={() => changeStatus("return-to-ai")}>Devolver a la IA</Button>
        ) : (
          <Button variant="secondary" onClick={() => changeStatus("handoff")}>
            Tomar control
          </Button>
        )}
      </div>
      <div className="max-h-[60vh] space-y-3 overflow-y-auto">
        {messages === null && <p className="text-sm text-muted">Cargando...</p>}
        {messages
          ?.filter((m) => m.role === "USER" || m.role === "ASSISTANT")
          .map((m) => (
            <div
              key={m.id}
              className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                m.role === "USER" ? "bg-background" : "ml-auto bg-primary text-primary-foreground"
              }`}
            >
              <p>{m.content}</p>
              <p className="mt-1 text-[10px] opacity-70">{formatDateTime(m.created_at)}</p>
            </div>
          ))}
      </div>
    </div>
  );
}
