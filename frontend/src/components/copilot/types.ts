import type { RecorteParametro } from "../../types/aquaterra";

export type CanalChatId = "general" | number;
export type TabDerecha = "proactivo" | "cotas";

export interface MensajeChat {
  id: string;
  autor: "usuario" | "mandarino";
  textoPrincipal: string;
  recomendacion?: string;
  proveedor?: string;
  confianza?: number;
  alertas?: string[];
  ajustesSeguros?: Record<string, number>;
  recortes?: RecorteParametro[];
  advertencias?: string[];
  clavesRechazadas?: string[];
  interaccionId?: number;
  calibracionAplicadaId?: number | null;
  estacionEtiqueta?: string;
  canalOrigen?: CanalChatId;
  promptOrigen?: string;
  rawJson?: Record<string, unknown>;
  tsIso: string;
}

export interface ChipAccionRapida {
  id: string;
  etiqueta: string;
  tipo: "aplicar" | "prompt" | "cotas";
  prompt?: string;
}
