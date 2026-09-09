"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button, ErrorBanner, Field, Input } from "@/components/ui";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    business_name: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function update(field: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await register(form);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear la cuenta.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <h1 className="mb-1 text-center text-2xl font-semibold">Creá tu cuenta</h1>
        <p className="mb-6 text-center text-sm text-muted">
          Registrá tu negocio para empezar a usar el recepcionista virtual
        </p>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-border bg-surface p-6 shadow-sm">
          {error && <ErrorBanner message={error} />}
          <Field label="Nombre del negocio">
            <Input required value={form.business_name} onChange={update("business_name")} />
          </Field>
          <Field label="Tu nombre">
            <Input required value={form.full_name} onChange={update("full_name")} />
          </Field>
          <Field label="Email">
            <Input type="email" required autoComplete="email" value={form.email} onChange={update("email")} />
          </Field>
          <Field label="Contraseña">
            <Input
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={form.password}
              onChange={update("password")}
            />
          </Field>
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Creando cuenta..." : "Crear cuenta"}
          </Button>
        </form>

        <p className="mt-4 text-center text-sm text-muted">
          ¿Ya tenés cuenta?{" "}
          <Link href="/login" className="text-primary hover:underline">
            Iniciá sesión
          </Link>
        </p>
      </div>
    </main>
  );
}
