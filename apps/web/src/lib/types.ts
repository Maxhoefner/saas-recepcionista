export type Role = "OWNER" | "ADMIN" | "STAFF";

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
}

export interface Business {
  id: string;
  name: string;
  slug: string;
  timezone: string;
  locale: string;
  role: Role;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface RegisterResponse extends TokenResponse {
  user: User;
}

export interface Service {
  id: string;
  name: string;
  description: string | null;
  price_cents: number;
  duration_minutes: number;
  active: boolean;
}

export interface Professional {
  id: string;
  name: string;
  active: boolean;
  service_ids: string[];
}

export interface Customer {
  id: string;
  phone: string;
  name: string;
  email: string | null;
  notes: string | null;
  last_interaction_at: string | null;
}

export type AppointmentStatus =
  | "PENDING"
  | "CONFIRMED"
  | "COMPLETED"
  | "CANCELLED"
  | "NO_SHOW";

export interface Appointment {
  id: string;
  customer_id: string;
  professional_id: string;
  service_id: string;
  start_datetime: string;
  end_datetime: string;
  status: AppointmentStatus;
  notes: string | null;
}

export interface WeeklyHours {
  id: string;
  weekday: number;
  start_time: string;
  end_time: string;
}

export type ConversationStatus = "AI_ACTIVE" | "HUMAN_HANDOFF" | "CLOSED";

export interface Conversation {
  id: string;
  customer_id: string;
  status: ConversationStatus;
  last_message_at: string | null;
}

export type MessageRole = "USER" | "ASSISTANT" | "SYSTEM" | "TOOL";

export interface Message {
  id: string;
  role: MessageRole;
  content: string | null;
  created_at: string;
}

export interface AISettings {
  assistant_name: string;
  tone: string;
  language: string;
  welcome_message: string | null;
  extra_instructions: string | null;
}

export interface FAQ {
  id: string;
  question: string;
  answer: string;
  active: boolean;
}

export interface WhatsAppAccount {
  id: string;
  phone_number_id: string;
  waba_id: string;
  display_phone_number: string;
}

export interface ReminderSettings {
  enabled: boolean;
  hours_before: number;
  message_template: string;
}
