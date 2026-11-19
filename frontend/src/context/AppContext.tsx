import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { toast } from "sonner";
import {
  api,
  ApiError,
  guardarTokenLocal,
  registrarManejadorNoAutorizado,
} from "../lib/api";
import type {
  EntradaRadarEstacion,
  Estacion,
  EstadoSistema,
  RadarResponse,
  ResumenRadar,
  Usuario,
  VistaId,
} from "../types/aquaterra";

export type TemaPreferencia = "system" | "light" | "dark";
export type TemaEfectivo = "light" | "dark";

const THEME_STORAGE_KEY = "aquaterra_color_scheme";

const TITULOS_VISTA: Record<VistaId, string> = {
  radar: "Radar General",
  telemetria: "Telemetría y Analítica",
  parcelas: "Parcelas y Cultivos",
  riego: "Control de Riego",
  copiloto: "Mandarino IA",
  hardware: "Hardware de Campo",
  config: "Configuración del Sistema",
};

function leerPreferenciaSistemaDark(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return true;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function leerTemaGuardado(): TemaPreferencia {
  try {
    const val = localStorage.getItem(THEME_STORAGE_KEY);
    if (val === "light" || val === "dark") return val;
  } catch {
    // ignore storage errors
  }
  return "system";
}

function aplicarMetaYAtributoTema(pref: TemaPreferencia): TemaEfectivo {
  const meta = document.querySelector('meta[name="color-scheme"]');
  const sysDark = leerPreferenciaSistemaDark();
  const efectivo: TemaEfectivo =
    pref === "system" ? (sysDark ? "dark" : "light") : pref;

  if (meta) {
    meta.setAttribute("content", pref === "system" ? "light dark" : pref);
  }
  document.documentElement.setAttribute("data-theme", efectivo);
  return efectivo;
}

interface AppContextValue {
  usuario: Usuario | null;
  cargandoSesion: boolean;
  login: (usuario: string, clave: string) => Promise<Usuario>;
  logout: () => Promise<void>;
  vistaActiva: VistaId;
  setVistaActiva: (vista: VistaId) => void;
  temaPreferencia: TemaPreferencia;
  temaEfectivo: TemaEfectivo;
  alternarTemaRapido: () => void;
  establecerTema: (tema: TemaPreferencia) => void;
  radar: RadarResponse | null;
  estaciones: Estacion[];
  resumenRadar: ResumenRadar | null;
  entradasRadar: EntradaRadarEstacion[];
  estacionActivaId: number | null;
  setEstacionActivaId: (id: number | null) => void;
  estacionActiva: Estacion | null;
  estadoSistema: EstadoSistema | null;
  cargandoGlobal: boolean;
  recargarGlobal: () => Promise<void>;
  sincronizarAhora: () => Promise<string>;
  sincronizando: boolean;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargandoSesion, setCargandoSesion] = useState(true);
  const [vistaActiva, setVistaActiva] = useState<VistaId>("radar");

  const [temaPreferencia, setTemaPreferencia] =
    useState<TemaPreferencia>(leerTemaGuardado);
  const [temaEfectivo, setTemaEfectivo] = useState<TemaEfectivo>(() =>
    aplicarMetaYAtributoTema(leerTemaGuardado())
  );

  const [radar, setRadar] = useState<RadarResponse | null>(null);
  const [estaciones, setEstaciones] = useState<Estacion[]>([]);
  const [estacionActivaId, setEstacionActivaId] = useState<number | null>(null);
  const [estadoSistema, setEstadoSistema] = useState<EstadoSistema | null>(null);
  const [cargandoGlobal, setCargandoGlobal] = useState(false);
  const [sincronizando, setSincronizando] = useState(false);
  const usuarioActivoRef = useRef(false);
  const ultimoAviso401Ref = useRef(0);

  useEffect(() => {
    usuarioActivoRef.current = Boolean(usuario);
  }, [usuario]);

  // Recuperación automática si una petición autenticada responde 401 (sesión expirada/servidor reiniciado)
  useEffect(() => {
    return registrarManejadorNoAutorizado((detail) => {
      const estabaAutenticado = usuarioActivoRef.current;
      setUsuario(null);
      setRadar(null);
      setEstaciones([]);
      setEstacionActivaId(null);
      setEstadoSistema(null);
      setVistaActiva("radar");
      if (estabaAutenticado) {
        const ahora = Date.now();
        if (ahora - ultimoAviso401Ref.current > 2500) {
          ultimoAviso401Ref.current = ahora;
          toast.warning(detail || "Tu sesión expiró. Inicia sesión nuevamente.");
        }
      }
    });
  }, []);

  // Mantener sincronizada la preferencia de color-scheme con OS, <meta> y otras pestañas
  useEffect(() => {
    setTemaEfectivo(aplicarMetaYAtributoTema(temaPreferencia));
  }, [temaPreferencia]);

  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const onSysChange = () => {
      setTemaEfectivo(aplicarMetaYAtributoTema(leerTemaGuardado()));
    };
    const onStorage = (e: StorageEvent) => {
      if (e.key === THEME_STORAGE_KEY) {
        const next = leerTemaGuardado();
        setTemaPreferencia(next);
        setTemaEfectivo(aplicarMetaYAtributoTema(next));
      }
    };
    mq?.addEventListener?.("change", onSysChange);
    window.addEventListener("storage", onStorage);
    return () => {
      mq?.removeEventListener?.("change", onSysChange);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  // Actualizar <title> por vista para navegación accesible
  useEffect(() => {
    if (!usuario) {
      document.title = "Iniciar Sesión · SalviaBIoT";
    } else {
      document.title = `${TITULOS_VISTA[vistaActiva]} · SalviaBIoT`;
    }
  }, [usuario, vistaActiva]);

  const establecerTema = useCallback((nuevo: TemaPreferencia) => {
    try {
      if (nuevo === "system") {
        localStorage.removeItem(THEME_STORAGE_KEY);
      } else {
        localStorage.setItem(THEME_STORAGE_KEY, nuevo);
      }
    } catch {
      // ignore
    }
    setTemaPreferencia(nuevo);
  }, []);

  // Patrón 2 estados (toggle inteligente en barra superior): vuelve a 'system' si coincide con OS
  const alternarTemaRapido = useCallback(() => {
    const sysTheme: TemaEfectivo = leerPreferenciaSistemaDark()
      ? "dark"
      : "light";
    const target: TemaEfectivo = temaEfectivo === "dark" ? "light" : "dark";
    establecerTema(target === sysTheme ? "system" : target);
  }, [temaEfectivo, establecerTema]);

  const recargarGlobal = useCallback(async () => {
    setCargandoGlobal(true);
    try {
      const [radarResp, estResp, sisResp] = await Promise.all([
        api.get<RadarResponse>("/api/radar"),
        api.get<{ estaciones: Estacion[] }>("/api/estaciones"),
        api.get<EstadoSistema>("/api/sistema/estado?verificar_ollama=false"),
      ]);
      setRadar(radarResp);
      setEstaciones(estResp.estaciones);
      setEstadoSistema(sisResp);
      setEstacionActivaId((prev) => {
        if (
          prev !== null &&
          estResp.estaciones.some((est) => est.id === prev)
        ) {
          return prev;
        }
        return (
          radarResp.entradas[0]?.estacion.id ?? estResp.estaciones[0]?.id ?? null
        );
      });
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) {
        toast.error(
          err instanceof Error
            ? err.message
            : "Error cargando datos del servidor."
        );
      }
    } finally {
      setCargandoGlobal(false);
    }
  }, []);

  // Verificar sesión activa al arrancar
  useEffect(() => {
    let cancelado = false;
    (async () => {
      try {
        const resp = await api.get<{ usuario: Usuario }>("/api/auth/me");
        if (!cancelado) {
          setUsuario(resp.usuario);
        }
      } catch {
        if (!cancelado) {
          setUsuario(null);
          guardarTokenLocal(null);
        }
      } finally {
        if (!cancelado) setCargandoSesion(false);
      }
    })();
    return () => {
      cancelado = true;
    };
  }, []);

  useEffect(() => {
    if (usuario) {
      void recargarGlobal();
    } else {
      setRadar(null);
      setEstaciones([]);
      setEstacionActivaId(null);
      setEstadoSistema(null);
    }
  }, [usuario, recargarGlobal]);

  const login = useCallback(async (u: string, clave: string) => {
    const resp = await api.post<{ token: string; usuario: Usuario }>(
      "/api/auth/login",
      { usuario: u, clave }
    );
    guardarTokenLocal(resp.token);
    setUsuario(resp.usuario);
    return resp.usuario;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/api/auth/logout");
    } catch {
      // ignore errors on logout
    } finally {
      guardarTokenLocal(null);
      setUsuario(null);
      setVistaActiva("radar");
    }
  }, []);

  const sincronizarAhora = useCallback(async () => {
    setSincronizando(true);
    try {
      const resp = await api.post<{
        resultado: {
          climas_actualizados?: number;
          lecturas_ubidots?: number;
          errores?: string[];
        };
      }>("/api/sistema/sync", { dias_clima: 2 });
      await recargarGlobal();
      const climas = resp.resultado?.climas_actualizados ?? 0;
      const ubidots = resp.resultado?.lecturas_ubidots ?? 0;
      return `Sincronización completada: ${climas} puntos climáticos, ${ubidots} lecturas Ubidots.`;
    } finally {
      setSincronizando(false);
    }
  }, [recargarGlobal]);

  const estacionActiva = useMemo(
    () => estaciones.find((e) => e.id === estacionActivaId) ?? null,
    [estaciones, estacionActivaId]
  );

  const valor: AppContextValue = {
    usuario,
    cargandoSesion,
    login,
    logout,
    vistaActiva,
    setVistaActiva,
    temaPreferencia,
    temaEfectivo,
    alternarTemaRapido,
    establecerTema,
    radar,
    estaciones,
    resumenRadar: radar?.resumen ?? null,
    entradasRadar: radar?.entradas ?? [],
    estacionActivaId,
    setEstacionActivaId,
    estacionActiva,
    estadoSistema,
    cargandoGlobal,
    recargarGlobal,
    sincronizarAhora,
    sincronizando,
  };

  return <AppContext.Provider value={valor}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) {
    throw new Error("useApp debe usarse dentro de <AppProvider>.");
  }
  return ctx;
}
