import { useState, type FormEvent } from "react";
import {
  AlertCircle,
  Droplets,
  Eye,
  EyeOff,
  Loader2,
  Moon,
  Radio,
  ShieldCheck,
  Sun,
  WifiOff,
} from "lucide-react";
import heroRiego from "../assets/paisajeriego.png";
import { useApp } from "../context/AppContext";
import { ApiError } from "../lib/api";

export function LoginPage() {
  const { login, temaEfectivo, alternarTemaRapido } = useApp();

  const [usuario, setUsuario] = useState("");
  const [clave, setClave] = useState("");
  const [mostrarClave, setMostrarClave] = useState(false);
  const [tocadoUsuario, setTocadoUsuario] = useState(false);
  const [tocadoClave, setTocadoClave] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const errorUsuario =
    tocadoUsuario && !usuario.trim()
      ? "Ingresa tu identificador de usuario."
      : "";
  const errorClave =
    tocadoClave && !clave
      ? "Ingresa tu contraseña de acceso."
      : "";

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setTocadoUsuario(true);
    setTocadoClave(true);
    setErrorBanner(null);

    if (!usuario.trim() || !clave) {
      return;
    }

    setEnviando(true);
    try {
      await login(usuario.trim(), clave);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorBanner(err.detail);
      } else {
        setErrorBanner(
          "No se pudo conectar con el servidor local de AquaTerra Matrix."
        );
      }
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="flex min-h-dvh w-full flex-col bg-[var(--bg-canvas)] text-[var(--text-primary)] lg:flex-row">
      {/* Columna izquierda: Paisaje Bio-Tech con gradiente Obsidian */}
      <aside className="relative flex min-h-[260px] flex-col justify-between overflow-hidden lg:min-h-dvh lg:w-[56%] p-7 sm:p-10 lg:p-14">
        <img
          src={heroRiego}
          alt="Sistema de riego de precisión y sensores ambientales en parcela agrícola"
          className="absolute inset-0 h-full w-full object-cover"
        />
        <div
          aria-hidden="true"
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(155deg, rgba(10,14,12,0.88) 0%, rgba(17,24,20,0.62) 48%, rgba(10,14,12,0.92) 100%)",
          }}
        />

        <div className="relative z-10 flex items-center justify-between">
          <div className="inline-flex items-center gap-2.5 rounded-full border border-white/15 bg-black/40 px-3.5 py-1.5 backdrop-blur-md">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-400/20 text-emerald-300">
              <Droplets className="h-3.5 w-3.5" aria-hidden="true" />
            </span>
            <span className="text-xs font-semibold tracking-wide text-white">
              AQUATERRA MATRIX · v6.0
            </span>
          </div>

          <span className="hidden rounded-full border border-emerald-400/25 bg-emerald-500/10 px-3 py-1 font-mono text-[11px] text-emerald-200 backdrop-blur-md sm:inline-flex">
            UTP · Ecosistema TerraBit
          </span>
        </div>

        <div className="relative z-10 my-auto max-w-xl py-8 lg:py-0">
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-4xl lg:text-[2.65rem] lg:leading-[1.12]">
            Telemetría Bio-Física y Control Hidráulico de Precisión
          </h1>
          <p className="mt-4 max-w-lg text-sm leading-relaxed text-emerald-50/80 sm:text-base">
            Plataforma unificada de monitoreo agrometeorológico, ingesta de
            nodos nRF24L01+ / LoRa y actuación hidráulica con verificación física
            en tiempo real.
          </p>

          <div className="mt-7 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-white/12 bg-black/40 p-3.5 backdrop-blur-md">
              <div className="flex items-center gap-2 text-xs font-semibold text-emerald-300">
                <ShieldCheck className="h-4 w-4 shrink-0" aria-hidden="true" />
                5 Candados Físicos
              </div>
              <p className="mt-1 text-xs text-white/70">
                Enclavamiento por lluvia, saturación, volumen, energía y bomba.
              </p>
            </div>
            <div className="rounded-xl border border-white/12 bg-black/40 p-3.5 backdrop-blur-md">
              <div className="flex items-center gap-2 text-xs font-semibold text-emerald-300">
                <Radio className="h-4 w-4 shrink-0" aria-hidden="true" />
                4 Familias IoT
              </div>
              <p className="mt-1 text-xs text-white/70">
                TerraBit INTI, InBeersa, Sigatoka y Conservación de Páramos.
              </p>
            </div>
            <div className="rounded-xl border border-white/12 bg-black/40 p-3.5 backdrop-blur-md">
              <div className="flex items-center gap-2 text-xs font-semibold text-emerald-300">
                <WifiOff className="h-4 w-4 shrink-0" aria-hidden="true" />
                Rural Offline-First
              </div>
              <p className="mt-1 text-xs text-white/70">
                SQLite WAL local, importación MicroSD e IA híbrida resiliente.
              </p>
            </div>
          </div>
        </div>

        <footer className="relative z-10 text-xs text-white/60">
          Ingeniería Agronómica &amp; Bio-IoT · Universidad Tecnológica de
          Pereira
        </footer>
      </aside>

      {/* Columna derecha: Formulario de acceso limpio */}
      <main
        id="main-content"
        className="relative flex flex-1 flex-col justify-center px-6 py-10 sm:px-12 lg:px-16"
      >
        <div className="absolute right-6 top-6">
          <button
            type="button"
            onClick={alternarTemaRapido}
            aria-label={
              temaEfectivo === "dark"
                ? "Cambiar a tema claro"
                : "Cambiar a tema oscuro"
            }
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
          >
            {temaEfectivo === "dark" ? (
              <Sun className="h-4 w-4" aria-hidden="true" />
            ) : (
              <Moon className="h-4 w-4" aria-hidden="true" />
            )}
          </button>
        </div>

        <div className="mx-auto w-full max-w-sm">
          <div className="mb-8">
            <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--accent-primary-soft)] text-[var(--accent-primary)]">
              <Droplets className="h-5 w-5" aria-hidden="true" />
            </div>
            <h2 className="mt-5 text-2xl font-bold tracking-tight text-[var(--text-primary)]">
              Acceso al Centro de Operaciones
            </h2>
            <p className="mt-1.5 text-sm text-[var(--text-secondary)]">
              Inicia sesión con tu cuenta operativa para gestionar estaciones,
              parcelas y actuadores.
            </p>
          </div>

          {errorBanner && (
            <div
              role="alert"
              className="mb-5 flex items-start gap-2.5 rounded-xl border border-[color-mix(in_srgb,var(--status-critical)_35%,transparent)] bg-[var(--status-critical-soft)] px-3.5 py-3 text-sm text-[var(--status-critical)]"
            >
              <AlertCircle
                className="mt-0.5 h-4 w-4 shrink-0"
                aria-hidden="true"
              />
              <span>{errorBanner}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate className="space-y-5">
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="login-usuario"
                className="text-sm font-medium text-[var(--text-primary)]"
              >
                Usuario <span aria-hidden="true">*</span>
              </label>
              <input
                id="login-usuario"
                name="usuario"
                type="text"
                autoComplete="username"
                autoCorrect="off"
                autoCapitalize="none"
                spellCheck={false}
                required
                enterKeyHint="next"
                value={usuario}
                onChange={(e) => {
                  setUsuario(e.target.value);
                  if (errorBanner) setErrorBanner(null);
                }}
                onBlur={() => setTocadoUsuario(true)}
                aria-invalid={Boolean(errorUsuario)}
                aria-describedby={errorUsuario ? "login-usuario-err" : undefined}
                placeholder="Ej. admin o operador"
                className={`at-input min-h-[44px] w-full rounded-xl border bg-[var(--bg-surface)] px-3.5 py-2.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] transition-colors ${
                  errorUsuario
                    ? "user-invalid-fallback border-[var(--status-critical)]"
                    : "border-[var(--border-strong)] focus:border-[var(--accent-primary)]"
                }`}
              />
              {errorUsuario && (
                <p
                  id="login-usuario-err"
                  className="flex items-center gap-1.5 text-xs text-[var(--status-critical)]"
                >
                  <AlertCircle className="h-3.5 w-3.5" aria-hidden="true" />
                  {errorUsuario}
                </p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="login-clave"
                className="text-sm font-medium text-[var(--text-primary)]"
              >
                Contraseña <span aria-hidden="true">*</span>
              </label>
              <div className="relative">
                <input
                  id="login-clave"
                  name="clave"
                  type={mostrarClave ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  enterKeyHint="done"
                  value={clave}
                  onChange={(e) => {
                    setClave(e.target.value);
                    if (errorBanner) setErrorBanner(null);
                  }}
                  onBlur={() => setTocadoClave(true)}
                  aria-invalid={Boolean(errorClave)}
                  aria-describedby={errorClave ? "login-clave-err" : undefined}
                  placeholder="••••••••"
                  className={`at-input min-h-[44px] w-full rounded-xl border bg-[var(--bg-surface)] py-2.5 pl-3.5 pr-11 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] transition-colors ${
                    errorClave
                      ? "user-invalid-fallback border-[var(--status-critical)]"
                      : "border-[var(--border-strong)] focus:border-[var(--accent-primary)]"
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setMostrarClave((v) => !v)}
                  aria-pressed={mostrarClave}
                  aria-label={
                    mostrarClave
                      ? "Ocultar contraseña"
                      : "Mostrar contraseña"
                  }
                  className="absolute right-2 top-1/2 -translate-y-1/2 inline-flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
                >
                  {mostrarClave ? (
                    <EyeOff className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <Eye className="h-4 w-4" aria-hidden="true" />
                  )}
                </button>
              </div>
              {errorClave && (
                <p
                  id="login-clave-err"
                  className="flex items-center gap-1.5 text-xs text-[var(--status-critical)]"
                >
                  <AlertCircle className="h-3.5 w-3.5" aria-hidden="true" />
                  {errorClave}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={enviando}
              className="inline-flex min-h-[46px] w-full items-center justify-center gap-2 rounded-xl bg-[var(--accent-primary)] px-4 py-2.5 text-sm font-semibold text-[var(--accent-contrast)] transition-colors hover:bg-[var(--accent-primary-hover)] disabled:opacity-60"
            >
              {enviando ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  Verificando credenciales…
                </>
              ) : (
                "Ingresar al Panel Operativo"
              )}
            </button>
          </form>

          <div className="mt-8 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3.5 text-xs text-[var(--text-secondary)]">
            <span className="font-semibold text-[var(--text-primary)]">
              Entorno Local SQLite WAL:
            </span>{" "}
            Sesión segura con cookie <code className="font-mono">HttpOnly</code>{" "}
            y aislamiento de roles (<code className="font-mono">admin</code>,{" "}
            <code className="font-mono">operador</code>,{" "}
            <code className="font-mono">lector</code>).
          </div>
        </div>
      </main>
    </div>
  );
}
