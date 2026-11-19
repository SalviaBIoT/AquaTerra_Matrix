import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  Bot,
  Cloud,
  Flame,
  Loader2,
  MapPin,
  Palette,
  Play,
  Radio,
  Save,
  Shield,
  Square,
  UserPlus,
  Users,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "../components/common/Badge";
import { useApp, type TemaPreferencia } from "../context/AppContext";
import { api, ApiError } from "../lib/api";
import { etiquetarTipoEstacion } from "../lib/formatters";
import type { RolUsuario, TipoEstacion, Usuario } from "../types/aquaterra";

type TabConfig = "conectores" | "ia" | "estaciones" | "usuarios";

export function SettingsPage() {
  const {
    usuario,
    estadoSistema,
    estaciones,
    recargarGlobal,
    temaPreferencia,
    establecerTema,
  } = useApp();
  const esAdmin = usuario?.rol === "admin";

  const [tab, setTab] = useState<TabConfig>("conectores");

  // Conectores & IA
  const [ubidotsToken, setUbidotsToken] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [tgToken, setTgToken] = useState("");
  const [tgChatId, setTgChatId] = useState("");

  const [iaProveedor, setIaProveedor] = useState(
    estadoSistema?.ia_proveedor ?? "auto"
  );
  const [geminiKey, setGeminiKey] = useState("");
  const [geminiModelo, setGeminiModelo] = useState(
    estadoSistema?.ia_gemini_modelo ?? "gemini-3.5-flash-lite"
  );
  const [ollamaUrl, setOllamaUrl] = useState(
    estadoSistema?.ia_ollama_url ?? "http://127.0.0.1:11434"
  );
  const [ollamaModelo, setOllamaModelo] = useState(
    estadoSistema?.ia_ollama_modelo ?? "qwen2.5:3b"
  );
  const [guardarEnv, setGuardarEnv] = useState(false);
  const [guardandoConectores, setGuardandoConectores] = useState(false);

  const [precalentando, setPrecalentando] = useState(false);
  const [verificandoOllama, setVerificandoOllama] = useState(false);
  const [ollamaVivo, setOllamaVivo] = useState<boolean | null>(null);
  const [intervaloWorker, setIntervaloWorker] = useState("900");
  const [cambiandoWorker, setCambiandoWorker] = useState(false);

  // Nueva estación
  const [codigoEst, setCodigoEst] = useState("");
  const [nombreEst, setNombreEst] = useState("");
  const [tipoEst, setTipoEst] = useState<TipoEstacion>("terrabit_inti");
  const [latEst, setLatEst] = useState("4.8133");
  const [lonEst, setLonEst] = useState("-75.6961");
  const [altEst, setAltEst] = useState("1411");
  const [creandoEst, setCreandoEst] = useState(false);

  // Usuarios RBAC
  const [usuariosLista, setUsuariosLista] = useState<Usuario[]>([]);
  const [nuevoUsuario, setNuevoUsuario] = useState("");
  const [nuevoNombre, setNuevoNombre] = useState("");
  const [nuevaClave, setNuevaClave] = useState("");
  const [nuevoRol, setNuevoRol] = useState<RolUsuario>("operador");
  const [creandoUsuario, setCreandoUsuario] = useState(false);
  const [claveObjetivoId, setClaveObjetivoId] = useState<number | null>(null);
  const [claveNuevaValor, setClaveNuevaValor] = useState("");
  const [cambiandoClave, setCambiandoClave] = useState(false);

  const cargarUsuarios = useCallback(async () => {
    try {
      const resp = await api.get<{ usuarios: Usuario[] }>("/api/usuarios");
      setUsuariosLista(resp.usuarios ?? []);
    } catch {
      setUsuariosLista([]);
    }
  }, []);

  useEffect(() => {
    if (estadoSistema) {
      setIaProveedor(estadoSistema.ia_proveedor || "auto");
      if (estadoSistema.ia_gemini_modelo) {
        setGeminiModelo(estadoSistema.ia_gemini_modelo);
      }
      setOllamaUrl(estadoSistema.ia_ollama_url || "http://127.0.0.1:11434");
      setOllamaModelo(estadoSistema.ia_ollama_modelo || "qwen2.5:3b");
    }
  }, [estadoSistema]);

  useEffect(() => {
    if (tab === "usuarios") {
      void cargarUsuarios();
    }
  }, [tab, cargarUsuarios]);

  const handleGuardarConectores = async (e: FormEvent) => {
    e.preventDefault();
    setGuardandoConectores(true);
    try {
      await api.post("/api/sistema/conectores", {
        ubidots_token: ubidotsToken || null,
        ia_proveedor: iaProveedor || null,
        ia_gemini_key: geminiKey || null,
        ia_gemini_modelo: geminiModelo || null,
        ia_ollama_url: ollamaUrl || null,
        ia_ollama_modelo: ollamaModelo || null,
        webhook_n8n_url: webhookUrl || null,
        telegram_bot_token: tgToken || null,
        telegram_chat_id: tgChatId || null,
        guardar_en_env_local: guardarEnv,
      });
      toast.success("Conectores actualizados en el contenedor activo.");
      setUbidotsToken("");
      setGeminiKey("");
      setTgToken("");
      await recargarGlobal();
    } catch (err) {
      toast.error(
        err instanceof ApiError
          ? err.detail
          : "No se pudieron actualizar conectores."
      );
    } finally {
      setGuardandoConectores(false);
    }
  };

  const handlePrecalentarOllama = async () => {
    setPrecalentando(true);
    try {
      await api.post("/api/sistema/ollama/precalentar");
      toast.success("Precalentamiento de modelo Ollama lanzado en segundo plano.");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Error precalentando Ollama."
      );
    } finally {
      setPrecalentando(false);
    }
  };

  const handleVerificarOllama = async () => {
    setVerificandoOllama(true);
    try {
      const st = await api.get<{
        ia_ollama_disponible?: boolean;
        ollama_disponible?: boolean;
        ia_ollama_modelo?: string;
      }>("/api/sistema/estado?verificar_ollama=true");
      const ok = Boolean(st.ia_ollama_disponible ?? st.ollama_disponible);
      setOllamaVivo(ok);
      if (ok) {
        toast.success(`Ollama local responde (${st.ia_ollama_modelo ?? ollamaModelo}).`);
      } else {
        toast.warning("Ollama local no responde en este instante; Gemini o motor heurístico actuarán de respaldo.");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "No se pudo verificar Ollama.");
    } finally {
      setVerificandoOllama(false);
    }
  };

  const handleCambiarClave = async (usuarioId: number) => {
    if (!claveNuevaValor || claveNuevaValor.length < 4) {
      toast.error("La nueva contraseña debe tener al menos 4 caracteres.");
      return;
    }
    setCambiandoClave(true);
    try {
      await api.post(`/api/usuarios/${usuarioId}/clave`, {
        nueva_clave: claveNuevaValor,
      });
      toast.success("Contraseña actualizada correctamente.");
      setClaveObjetivoId(null);
      setClaveNuevaValor("");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "No se pudo actualizar la contraseña."
      );
    } finally {
      setCambiandoClave(false);
    }
  };

  const handleToggleWorker = async (activo: boolean) => {
    setCambiandoWorker(true);
    try {
      await api.post("/api/sistema/worker", {
        activo,
        intervalo_segundos: Number(intervaloWorker) || 900,
        precalentar_ollama: true,
      });
      toast.success(
        activo
          ? "Worker autónomo iniciado en segundo plano."
          : "Worker autónomo detenido."
      );
      await recargarGlobal();
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Error controlando el worker."
      );
    } finally {
      setCambiandoWorker(false);
    }
  };

  const handleCrearEstacion = async (e: FormEvent) => {
    e.preventDefault();
    setCreandoEst(true);
    try {
      await api.post("/api/estaciones", {
        codigo: codigoEst.trim(),
        nombre: nombreEst.trim(),
        tipo: tipoEst,
        latitud: latEst ? Number(latEst) : null,
        longitud: lonEst ? Number(lonEst) : null,
        altitud_m: altEst ? Number(altEst) : null,
      });
      toast.success(`Estación ${codigoEst.trim()} registrada.`);
      setCodigoEst("");
      setNombreEst("");
      await recargarGlobal();
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "No se pudo registrar estación."
      );
    } finally {
      setCreandoEst(false);
    }
  };

  const handleCrearUsuario = async (e: FormEvent) => {
    e.preventDefault();
    setCreandoUsuario(true);
    try {
      await api.post("/api/usuarios", {
        usuario: nuevoUsuario.trim(),
        nombre: nuevoNombre.trim(),
        clave: nuevaClave,
        rol: nuevoRol,
      });
      toast.success(`Usuario "${nuevoUsuario.trim()}" creado.`);
      setNuevoUsuario("");
      setNuevoNombre("");
      setNuevaClave("");
      await cargarUsuarios();
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Error creando usuario."
      );
    } finally {
      setCreandoUsuario(false);
    }
  };

  const TABS: { id: TabConfig; titulo: string; sub: string; icono: typeof Cloud }[] = [
    { id: "conectores", titulo: "Conectores & Alertas", sub: "Ubidots, n8n, Telegram y Apariencia", icono: Cloud },
    { id: "ia", titulo: "IA Híbrida & Worker", sub: "Ollama GPU, Gemini y sincronía auto", icono: Bot },
    { id: "estaciones", titulo: "Estaciones IoT & GPS", sub: "Registro y coordenadas Open-Meteo", icono: MapPin },
    { id: "usuarios", titulo: "Usuarios & RBAC", sub: "Cuentas y permisos operativos", icono: Users },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
          Configuración del Ecosistema
        </h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Administración segura de conectores cloud, motores de IA híbrida,
          coordenadas GPS de estaciones y control de acceso basado en roles.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Navegación vertical estilo Linear/Vercel */}
        <nav aria-label="Secciones de configuración" className="lg:col-span-3">
          <ul className="space-y-1.5">
            {TABS.map((t) => {
              const Icono = t.icono;
              const activo = tab === t.id;
              return (
                <li key={t.id}>
                  <button
                    type="button"
                    onClick={() => setTab(t.id)}
                    aria-current={activo ? "page" : undefined}
                    className={`flex w-full items-start gap-3 rounded-xl border p-3 text-left transition-colors ${
                      activo
                        ? "border-[var(--accent-primary)] bg-[var(--accent-primary-soft)] text-[var(--text-primary)]"
                        : "border-transparent bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
                    }`}
                  >
                    <Icono
                      className={`mt-0.5 h-4 w-4 shrink-0 ${
                        activo ? "text-[var(--accent-primary)]" : ""
                      }`}
                      aria-hidden="true"
                    />
                    <div className="min-w-0">
                      <div className="text-xs font-bold">{t.titulo}</div>
                      <div className="truncate text-[11px] text-[var(--text-muted)]">
                        {t.sub}
                      </div>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Contenido derecho */}
        <div className="space-y-6 lg:col-span-9">
          {tab === "conectores" && (
            <>
              {/* Control tri-estado explícito de tema */}
              <section className="surface-card p-5">
                <div className="flex items-center gap-2">
                  <Palette
                    className="h-4 w-4 text-[var(--accent-primary)]"
                    aria-hidden="true"
                  />
                  <h2 className="text-base font-semibold text-[var(--text-primary)]">
                    Apariencia y Tema Visual
                  </h2>
                </div>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">
                  Por defecto SalviaBIoT sigue la preferencia de Windows/SO, o
                  puedes fijar un esquema para operación nocturna o campo abierto.
                </p>

                <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                  {(
                    [
                      { id: "system", nombre: "Seguir al Sistema", desc: "Sincronía automática OS" },
                      { id: "light", nombre: "Field Daylight (Claro)", desc: "Alta legibilidad bajo sol" },
                      { id: "dark", nombre: "Obsidian Canopy (Oscuro)", desc: "Baja fatiga en monitoreo" },
                    ] as { id: TemaPreferencia; nombre: string; desc: string }[]
                  ).map((op) => (
                    <button
                      key={op.id}
                      type="button"
                      onClick={() => establecerTema(op.id)}
                      className={`rounded-xl border p-3.5 text-left transition-colors ${
                        temaPreferencia === op.id
                          ? "border-[var(--accent-primary)] bg-[var(--accent-primary-soft)]"
                          : "border-[var(--border-subtle)] bg-[var(--bg-elevated)] hover:border-[var(--border-strong)]"
                      }`}
                    >
                      <div className="text-xs font-bold text-[var(--text-primary)]">
                        {op.nombre}
                      </div>
                      <div className="mt-0.5 text-[11px] text-[var(--text-secondary)]">
                        {op.desc}
                      </div>
                    </button>
                  ))}
                </div>
              </section>

              <form onSubmit={handleGuardarConectores} className="surface-card space-y-4 p-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold text-[var(--text-primary)]">
                    Conectores Cloud &amp; Despacho de Alertas
                  </h2>
                  <Badge tono={esAdmin ? "optimal" : "neutral"}>
                    {esAdmin ? "Admin habilitado" : "Solo lectura"}
                  </Badge>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="flex flex-col gap-1">
                    <label htmlFor="cfg-ubidots" className="text-xs font-semibold">
                      Token Ubidots (solo reemplazo)
                    </label>
                    <input
                      id="cfg-ubidots"
                      type="password"
                      placeholder={
                        estadoSistema?.ubidots_configurado
                          ? "•••••••• (Ya configurado)"
                          : "BBFF-..."
                      }
                      value={ubidotsToken}
                      onChange={(e) => setUbidotsToken(e.target.value)}
                      className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 font-mono text-xs"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label htmlFor="cfg-n8n" className="text-xs font-semibold">
                      Webhook n8n / WhatsApp URL
                    </label>
                    <input
                      id="cfg-n8n"
                      type="url"
                      placeholder={
                        estadoSistema?.webhook_configurado
                          ? "Configurado (ingresa nuevo URL para reemplazar)"
                          : "https://n8n.local/webhook/..."
                      }
                      value={webhookUrl}
                      onChange={(e) => setWebhookUrl(e.target.value)}
                      className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 font-mono text-xs"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label htmlFor="cfg-tg-token" className="text-xs font-semibold">
                      Telegram Bot Token
                    </label>
                    <input
                      id="cfg-tg-token"
                      type="password"
                      placeholder={
                        estadoSistema?.telegram_configurado
                          ? "•••••••• (Configurado)"
                          : "123456:ABC..."
                      }
                      value={tgToken}
                      onChange={(e) => setTgToken(e.target.value)}
                      className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 font-mono text-xs"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label htmlFor="cfg-tg-chat" className="text-xs font-semibold">
                      Telegram Chat ID
                    </label>
                    <input
                      id="cfg-tg-chat"
                      type="text"
                      placeholder="Ej. -1001234567890"
                      value={tgChatId}
                      onChange={(e) => setTgChatId(e.target.value)}
                      className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 font-mono text-xs"
                    />
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border-subtle)] pt-4">
                  <label className="inline-flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                    <input
                      type="checkbox"
                      checked={guardarEnv}
                      onChange={(e) => setGuardarEnv(e.target.checked)}
                    />
                    Persistir secretos nuevos en archivo <code className="font-mono">.env</code> local
                  </label>

                  <button
                    type="submit"
                    disabled={!esAdmin || guardandoConectores}
                    className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-[var(--accent-contrast)] hover:bg-[var(--accent-primary-hover)] disabled:opacity-45"
                  >
                    <Save className="h-3.5 w-3.5" aria-hidden="true" />
                    {guardandoConectores ? "Guardando…" : "Guardar conectores"}
                  </button>
                </div>
              </form>
            </>
          )}

          {tab === "ia" && (
            <div className="space-y-6">
              <form onSubmit={handleGuardarConectores} className="surface-card space-y-4 p-5">
                <h2 className="text-base font-semibold text-[var(--text-primary)]">
                  Orquestador de IA Híbrida (Ollama Local + Gemini Cloud)
                </h2>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="flex flex-col gap-1">
                    <label htmlFor="ia-prov" className="text-xs font-semibold">
                      Modo de inferencia
                    </label>
                    <select
                      id="ia-prov"
                      value={iaProveedor}
                      onChange={(e) => setIaProveedor(e.target.value)}
                      className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 text-xs"
                    >
                      <option value="auto">Automático (Gemini → Ollama GPU → Heurístico)</option>
                      <option value="ollama">Ollama Local (GPU Offline)</option>
                      <option value="gemini">Google Gemini Cloud</option>
                      <option value="local_reglas">Solo Motor Heurístico Offline</option>
                    </select>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label htmlFor="ia-gem-key" className="text-xs font-semibold">
                      Gemini API Key
                    </label>
                    <input
                      id="ia-gem-key"
                      type="password"
                      placeholder={
                        estadoSistema?.ia_gemini_configurado
                          ? "•••••••• (Configurada)"
                          : "AIza..."
                      }
                      value={geminiKey}
                      onChange={(e) => setGeminiKey(e.target.value)}
                      className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 font-mono text-xs"
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label htmlFor="ia-ol-url" className="text-xs font-semibold">
                      Ollama Endpoint URL
                    </label>
                    <input
                      id="ia-ol-url"
                      type="url"
                      value={ollamaUrl}
                      onChange={(e) => setOllamaUrl(e.target.value)}
                      className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 font-mono text-xs"
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label htmlFor="ia-ol-mod" className="text-xs font-semibold">
                      Modelo Ollama / Gemini
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        id="ia-ol-mod"
                        type="text"
                        value={ollamaModelo}
                        onChange={(e) => setOllamaModelo(e.target.value)}
                        aria-label="Modelo Ollama"
                        className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2.5 font-mono text-xs"
                      />
                      <input
                        type="text"
                        value={geminiModelo}
                        onChange={(e) => setGeminiModelo(e.target.value)}
                        aria-label="Modelo Gemini"
                        className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2.5 font-mono text-xs"
                      />
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px]">
                      <span className="text-[var(--text-muted)]">Presets Gemini:</span>
                      {(
                        [
                          { id: "gemini-3.5-flash-lite", label: "gemini-3.5-flash-lite (Alta cuota)" },
                          { id: "gemini-3.8-flash", label: "gemini-3.8-flash" },
                          { id: "gemini-4-hydrogen", label: "gemini-4-hydrogen" },
                        ] as const
                      ).map((p) => (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => setGeminiModelo(p.id)}
                          className={`rounded-full border px-2 py-0.5 font-mono transition-colors ${
                            geminiModelo === p.id
                              ? "border-[var(--accent-primary)] bg-[var(--accent-primary-soft)] text-[var(--accent-primary)]"
                              : "border-[var(--border-subtle)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                          }`}
                        >
                          {p.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border-subtle)] pt-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      disabled={precalentando}
                      onClick={() => void handlePrecalentarOllama()}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-elevated)] px-3.5 py-2 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-subtle)]"
                    >
                      <Flame className="h-3.5 w-3.5 text-[var(--status-warning)]" aria-hidden="true" />
                      {precalentando ? "Precalentando…" : "Precalentar Ollama VRAM"}
                    </button>
                    <button
                      type="button"
                      disabled={verificandoOllama}
                      onClick={() => void handleVerificarOllama()}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-canvas)] px-3 py-2 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    >
                      {verificandoOllama ? "Comprobando…" : "Probar Ollama local"}
                    </button>
                    {ollamaVivo !== null && (
                      <Badge tono={ollamaVivo ? "optimal" : "warning"}>
                        {ollamaVivo ? "Ollama Online" : "Ollama Offline"}
                      </Badge>
                    )}
                  </div>

                  <button
                    type="submit"
                    disabled={!esAdmin || guardandoConectores}
                    className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-[var(--accent-contrast)] hover:bg-[var(--accent-primary-hover)] disabled:opacity-45"
                  >
                    <Save className="h-3.5 w-3.5" aria-hidden="true" />
                    Guardar IA
                  </button>
                </div>
              </form>

              <section className="surface-card flex flex-wrap items-center justify-between gap-4 p-5">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-base font-semibold text-[var(--text-primary)]">
                      Worker Autónomo en Segundo Plano
                    </h2>
                    <Badge
                      tono={estadoSistema?.worker_activo ? "optimal" : "neutral"}
                    >
                      {estadoSistema?.worker_activo ? "Corriendo" : "Detenido"}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-[var(--text-secondary)]">
                    Sincroniza periódicamente pronóstico Open-Meteo, Ubidots y
                    mantiene caliente la instancia de inferencia local.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={60}
                    max={86400}
                    value={intervaloWorker}
                    onChange={(e) => setIntervaloWorker(e.target.value)}
                    aria-label="Intervalo del worker en segundos"
                    className="tabular-nums h-9 w-24 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2.5 font-mono text-xs"
                  />
                  {estadoSistema?.worker_activo ? (
                    <button
                      type="button"
                      disabled={!esAdmin || cambiandoWorker}
                      onClick={() => void handleToggleWorker(false)}
                      className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-[var(--status-critical)] px-4 text-xs font-semibold text-white disabled:opacity-45"
                    >
                      <Square className="h-3.5 w-3.5" aria-hidden="true" />
                      Detener
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={!esAdmin || cambiandoWorker}
                      onClick={() => void handleToggleWorker(true)}
                      className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-[var(--accent-primary)] px-4 text-xs font-semibold text-[var(--accent-contrast)] disabled:opacity-45"
                    >
                      <Play className="h-3.5 w-3.5" aria-hidden="true" />
                      Iniciar worker
                    </button>
                  )}
                </div>
              </section>
            </div>
          )}

          {tab === "estaciones" && (
            <div className="space-y-6">
              <form onSubmit={handleCrearEstacion} className="surface-card space-y-4 p-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold text-[var(--text-primary)]">
                    Registrar Estación IoT y Coordenadas GPS
                  </h2>
                  <button
                    type="button"
                    onClick={() =>
                      void api
                        .post("/api/estaciones/sembrar-base")
                        .then(() => {
                          toast.success("Nodos base verificados.");
                          return recargarGlobal();
                        })
                    }
                    className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-1.5 text-xs font-semibold text-[var(--text-primary)]"
                  >
                    <Radio className="h-3.5 w-3.5 text-[var(--accent-primary)]" aria-hidden="true" />
                    Sembrar estaciones base
                  </button>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <input
                    type="text"
                    required
                    placeholder="Código (ej. TB_INTI_02)"
                    aria-label="Código de estación"
                    value={codigoEst}
                    onChange={(e) => setCodigoEst(e.target.value)}
                    className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 font-mono text-xs"
                  />
                  <input
                    type="text"
                    required
                    placeholder="Nombre descriptivo"
                    aria-label="Nombre de estación"
                    value={nombreEst}
                    onChange={(e) => setNombreEst(e.target.value)}
                    className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 text-xs"
                  />
                  <select
                    value={tipoEst}
                    onChange={(e) => setTipoEst(e.target.value as TipoEstacion)}
                    aria-label="Familia de estación"
                    className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 text-xs"
                  >
                    <option value="terrabit_inti">TerraBit Station · INTI</option>
                    <option value="inbeersa">InBeersa Meliponas</option>
                    <option value="sigatoka">Sigatoka Foliar</option>
                    <option value="conservacion">Conservación Páramo</option>
                    <option value="otro">Estación Genérica</option>
                  </select>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <input
                    type="number"
                    step="any"
                    placeholder="Latitud"
                    aria-label="Latitud GPS"
                    value={latEst}
                    onChange={(e) => setLatEst(e.target.value)}
                    className="tabular-nums h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 font-mono text-xs"
                  />
                  <input
                    type="number"
                    step="any"
                    placeholder="Longitud"
                    aria-label="Longitud GPS"
                    value={lonEst}
                    onChange={(e) => setLonEst(e.target.value)}
                    className="tabular-nums h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 font-mono text-xs"
                  />
                  <input
                    type="number"
                    step="any"
                    placeholder="Altitud (msnm)"
                    aria-label="Altitud sobre el nivel del mar"
                    value={altEst}
                    onChange={(e) => setAltEst(e.target.value)}
                    className="tabular-nums h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 font-mono text-xs"
                  />
                </div>

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={!esAdmin || creandoEst}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-[var(--accent-contrast)] hover:bg-[var(--accent-primary-hover)] disabled:opacity-45"
                  >
                    {creandoEst && (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                    )}
                    Registrar estación
                  </button>
                </div>
              </form>

              <section className="surface-card overflow-hidden">
                <div className="overflow-x-auto p-4">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-[var(--border-subtle)] text-[var(--text-muted)]">
                        <th scope="col" className="py-2 pr-4">Código</th>
                        <th scope="col" className="py-2 pr-4">Nombre</th>
                        <th scope="col" className="py-2 pr-4">Familia</th>
                        <th scope="col" className="py-2">GPS / Altitud</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border-subtle)]">
                      {estaciones.map((e) => (
                        <tr key={e.id}>
                          <td className="py-2.5 pr-4 font-mono font-semibold text-[var(--accent-primary)]">
                            {e.codigo}
                          </td>
                          <td className="py-2.5 pr-4">{e.nombre}</td>
                          <td className="py-2.5 pr-4">
                            <Badge tono="neutral">{etiquetarTipoEstacion(e.tipo)}</Badge>
                          </td>
                          <td className="tabular-nums py-2.5 font-mono text-[var(--text-secondary)]">
                            {e.latitud ?? "—"}, {e.longitud ?? "—"} ·{" "}
                            {e.altitud_m ? `${e.altitud_m} msnm` : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          )}

          {tab === "usuarios" && (
            <div className="space-y-6">
              <form onSubmit={handleCrearUsuario} className="surface-card space-y-4 p-5">
                <div className="flex items-center gap-2">
                  <Shield
                    className="h-4 w-4 text-[var(--accent-primary)]"
                    aria-hidden="true"
                  />
                  <h2 className="text-base font-semibold text-[var(--text-primary)]">
                    Alta de Usuarios &amp; Control RBAC
                  </h2>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
                  <input
                    type="text"
                    required
                    placeholder="Usuario (login)"
                    aria-label="Nombre de usuario"
                    value={nuevoUsuario}
                    onChange={(e) => setNuevoUsuario(e.target.value)}
                    className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 text-xs"
                  />
                  <input
                    type="text"
                    required
                    placeholder="Nombre completo"
                    aria-label="Nombre completo"
                    value={nuevoNombre}
                    onChange={(e) => setNuevoNombre(e.target.value)}
                    className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 text-xs"
                  />
                  <input
                    type="password"
                    required
                    placeholder="Contraseña"
                    aria-label="Contraseña inicial"
                    value={nuevaClave}
                    onChange={(e) => setNuevaClave(e.target.value)}
                    className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 text-xs"
                  />
                  <select
                    value={nuevoRol}
                    onChange={(e) => setNuevoRol(e.target.value as RolUsuario)}
                    aria-label="Rol RBAC"
                    className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 text-xs"
                  >
                    <option value="operador">Operador (Campo + Riego)</option>
                    <option value="lector">Lector (Solo lectura)</option>
                    <option value="admin">Administrador (Total)</option>
                  </select>
                </div>

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={!esAdmin || creandoUsuario}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-[var(--accent-contrast)] hover:bg-[var(--accent-primary-hover)] disabled:opacity-45"
                  >
                    <UserPlus className="h-3.5 w-3.5" aria-hidden="true" />
                    {creandoUsuario ? "Creando…" : "Crear usuario"}
                  </button>
                </div>
              </form>

              <section className="surface-card overflow-hidden">
                <div className="overflow-x-auto p-4">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-[var(--border-subtle)] text-[var(--text-muted)]">
                        <th scope="col" className="py-2 pr-4">Usuario</th>
                        <th scope="col" className="py-2 pr-4">Nombre</th>
                        <th scope="col" className="py-2 pr-4">Rol RBAC</th>
                        <th scope="col" className="py-2 text-right">Seguridad</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border-subtle)]">
                      {usuariosLista.map((u) => (
                        <tr key={u.id}>
                          <td className="py-2.5 pr-4 font-mono font-semibold text-[var(--text-primary)]">
                            {u.usuario}
                          </td>
                          <td className="py-2.5 pr-4">{u.nombre}</td>
                          <td className="py-2.5 pr-4">
                            <Badge
                              tono={
                                u.rol === "admin"
                                  ? "optimal"
                                  : u.rol === "operador"
                                  ? "info"
                                  : "neutral"
                              }
                            >
                              {u.rol}
                            </Badge>
                          </td>
                          <td className="py-2 text-right">
                            {(esAdmin || usuario?.id === u.id) &&
                              (claveObjetivoId === u.id ? (
                                <div className="inline-flex items-center gap-1.5">
                                  <input
                                    type="password"
                                    placeholder="Nueva clave"
                                    aria-label={`Nueva contraseña para ${u.usuario}`}
                                    value={claveNuevaValor}
                                    onChange={(e) =>
                                      setClaveNuevaValor(e.target.value)
                                    }
                                    className="h-7 w-28 rounded-lg border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2 text-xs"
                                  />
                                  <button
                                    type="button"
                                    disabled={cambiandoClave}
                                    onClick={() => void handleCambiarClave(u.id)}
                                    className="rounded-lg bg-[var(--accent-primary)] px-2.5 py-1 text-[11px] font-semibold text-[var(--accent-contrast)] disabled:opacity-45"
                                  >
                                    {cambiandoClave ? "…" : "Guardar"}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setClaveObjetivoId(null);
                                      setClaveNuevaValor("");
                                    }}
                                    className="rounded-lg border border-[var(--border-subtle)] px-2 py-1 text-[11px] text-[var(--text-secondary)]"
                                  >
                                    Cancelar
                                  </button>
                                </div>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => {
                                    setClaveObjetivoId(u.id);
                                    setClaveNuevaValor("");
                                  }}
                                  className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-subtle)]"
                                >
                                  Cambiar clave
                                </button>
                              ))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
