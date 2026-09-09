"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/lib/auth-context";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/appointments", label: "Turnos" },
  { href: "/customers", label: "Clientes" },
  { href: "/professionals", label: "Profesionales" },
  { href: "/services", label: "Servicios" },
  { href: "/conversations", label: "Conversaciones" },
  { href: "/settings", label: "Configuración" },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const { isLoading, user, business, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    }
  }, [isLoading, user, router]);

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-muted">
        Cargando...
      </div>
    );
  }

  if (!user) {
    // Redirect effect above is in flight — render nothing to avoid a flash
    // of dashboard content before it fires.
    return null;
  }

  return (
    <div className="flex min-h-screen flex-1">
      <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-surface">
        <div className="border-b border-border px-4 py-4">
          <p className="font-semibold">AI Receptionist</p>
          <p className="truncate text-xs text-muted">{business?.name ?? "Sin negocio"}</p>
        </div>
        <nav className="flex-1 space-y-0.5 p-2">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block rounded-md px-3 py-2 text-sm ${
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-foreground hover:bg-background"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-border p-3">
          <p className="truncate px-1 text-xs text-muted">{user.email}</p>
          <button
            onClick={() => {
              void logout().then(() => router.replace("/login"));
            }}
            className="mt-1 w-full rounded-md px-3 py-2 text-left text-sm text-danger hover:bg-danger/10"
          >
            Cerrar sesión
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto p-6">{children}</main>
    </div>
  );
}
