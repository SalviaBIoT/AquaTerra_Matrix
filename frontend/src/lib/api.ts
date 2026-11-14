export class ApiError extends Error {
  status: number;
  detail: string;
  code: string;

  constructor(status: number, detail: string, code = "error_api") {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

const TOKEN_STORAGE_KEY = "aquaterra_session_token";

type ManejadorNoAutorizado = (detail: string, code: string) => void;
const manejadoresNoAutorizado = new Set<ManejadorNoAutorizado>();

export function registrarManejadorNoAutorizado(
  cb: ManejadorNoAutorizado
): () => void {
  manejadoresNoAutorizado.add(cb);
  return () => {
    manejadoresNoAutorizado.delete(cb);
  };
}

function notificarNoAutorizado(detail: string, code: string): void {
  guardarTokenLocal(null);
  for (const cb of manejadoresNoAutorizado) {
    cb(detail, code);
  }
}

export function obtenerTokenLocal(): string | null {
  try {
    return (
      localStorage.getItem(TOKEN_STORAGE_KEY) ??
      sessionStorage.getItem(TOKEN_STORAGE_KEY)
    );
  } catch {
    return null;
  }
}

export function guardarTokenLocal(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
      sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // Modo restringido sin storage; la cookie HttpOnly sigue operando.
  }
}

async function solicitar<T>(
  ruta: string,
  opciones: RequestInit = {}
): Promise<T> {
  const headers = new Headers(opciones.headers);
  if (
    opciones.body &&
    !(opciones.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }
  const token = obtenerTokenLocal();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const respuesta = await fetch(ruta, {
    ...opciones,
    headers,
    credentials: "include",
  });

  if (respuesta.status === 204) {
    return undefined as T;
  }

  const tipoContenido = respuesta.headers.get("Content-Type") ?? "";
  let cuerpo: unknown = null;
  if (tipoContenido.includes("application/json")) {
    cuerpo = await respuesta.json().catch(() => null);
  } else {
    const texto = await respuesta.text().catch(() => "");
    cuerpo = texto ? { detail: texto } : null;
  }

  if (!respuesta.ok) {
    const dataObj =
      cuerpo && typeof cuerpo === "object"
        ? (cuerpo as Record<string, unknown>)
        : {};
    let detail = `Error HTTP ${respuesta.status}`;
    if (typeof dataObj.detail === "string") {
      detail = dataObj.detail;
    } else if (Array.isArray(dataObj.detail) && dataObj.detail.length > 0) {
      detail = dataObj.detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as Record<string, unknown>).msg);
          }
          return String(item);
        })
        .join(" · ");
    }
    const code =
      typeof dataObj.codigo === "string" ? dataObj.codigo : `http_${respuesta.status}`;
    if (respuesta.status === 401 && !ruta.startsWith("/api/auth/login")) {
      notificarNoAutorizado(detail, code);
    }
    throw new ApiError(respuesta.status, detail, code);
  }

  return cuerpo as T;
}

export const api = {
  get: <T>(ruta: string) => solicitar<T>(ruta, { method: "GET" }),
  post: <T>(ruta: string, body?: unknown) =>
    solicitar<T>(ruta, {
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  patch: <T>(ruta: string, body?: unknown) =>
    solicitar<T>(ruta, {
      method: "PATCH",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  del: <T>(ruta: string) => solicitar<T>(ruta, { method: "DELETE" }),
};

export async function descargarArchivo(
  ruta: string,
  nombreFallback: string
): Promise<void> {
  const headers = new Headers();
  const token = obtenerTokenLocal();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const resp = await fetch(ruta, { headers, credentials: "include" });
  if (!resp.ok) {
    if (resp.status === 401) {
      notificarNoAutorizado(
        "Tu sesión expiró al descargar el archivo. Inicia sesión nuevamente.",
        "sesion_expirada"
      );
    }
    throw new ApiError(
      resp.status,
      `No se pudo descargar el archivo (${resp.status}).`
    );
  }
  const blob = await resp.blob();
  const disposition = resp.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  const filename = match ? match[1] : nombreFallback;

  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = filename;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1500);
}
