import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, Loader2, LogOut, RefreshCw } from "lucide-react";
import { Toaster } from "sonner";
import { AppShell } from "./components/layout/AppShell";
import { AppProvider, useApp } from "./context/AppContext";
import { guardarTokenLocal } from "./lib/api";
import { CopilotPage } from "./pages/CopilotPage";
import { DashboardPage } from "./pages/DashboardPage";
import { HardwarePage } from "./pages/HardwarePage";
import { IrrigationPage } from "./pages/IrrigationPage";
import { LoginPage } from "./pages/LoginPage";
import { ParcelsPage } from "./pages/ParcelsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TelemetryPage } from "./pages/TelemetryPage";

interface ErrorBoundaryState {
  error: Error | null;
}

class AppErrorBoundary extends Component<
  { children: ReactNode },
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Error inesperado en interfaz AquaTerra:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-dvh items-center justify-center bg-[var(--bg-canvas)] p-6 text-[var(--text-primary)]">
          <div className="surface-card max-w-md space-y-4 p-6">
            <div className="flex items-center gap-2.5 text-[var(--status-critical)]">
              <AlertTriangle className="h-5 w-5 shrink-0" aria-hidden="true" />
              <h1 className="text-base font-bold">
                Se interceptó un error de renderizado
              </h1>
            </div>
            <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
              {this.state.error.message || "Error inesperado en el componente."}
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => window.location.reload()}
                className="inline-flex items-center gap-1.5 rounded-xl bg-[var(--accent-primary)] px-3.5 py-2 text-xs font-semibold text-[var(--accent-contrast)]"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                Recargar interfaz
              </button>
              <button
                type="button"
                onClick={() => {
                  guardarTokenLocal(null);
                  window.location.reload();
                }}
                className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3.5 py-2 text-xs font-semibold text-[var(--text-primary)]"
              >
                <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
                Reiniciar sesión
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function ContenidoAplicacion() {
  const { usuario, cargandoSesion, vistaActiva } = useApp();

  if (cargandoSesion) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-3 bg-[var(--bg-canvas)] text-[var(--text-secondary)]">
        <Loader2
          className="h-7 w-7 animate-spin text-[var(--accent-primary)]"
          aria-hidden="true"
        />
        <span className="text-sm font-medium">
          Inicializando AquaTerra Matrix…
        </span>
      </div>
    );
  }

  if (!usuario) {
    return <LoginPage />;
  }

  const renderVista = () => {
    switch (vistaActiva) {
      case "radar":
        return <DashboardPage />;
      case "telemetria":
        return <TelemetryPage />;
      case "parcelas":
        return <ParcelsPage />;
      case "riego":
        return <IrrigationPage />;
      case "copiloto":
        return <CopilotPage />;
      case "hardware":
        return <HardwarePage />;
      case "config":
        return <SettingsPage />;
    }
  };

  return <AppShell>{renderVista()}</AppShell>;
}

export default function App() {
  return (
    <AppErrorBoundary>
      <AppProvider>
        <ContenidoAplicacion />
        <Toaster
          position="bottom-right"
          richColors
          closeButton
          toastOptions={{
            style: {
              fontFamily: "var(--font-sans)",
            },
          }}
        />
      </AppProvider>
    </AppErrorBoundary>
  );
}
