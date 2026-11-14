import type { TipoEstacion } from "../types/aquaterra";

export function etiquetarTipoEstacion(tipo: TipoEstacion | string): string {
  switch (String(tipo).toLowerCase()) {
    case "terrabit_inti":
      return "TerraBit INTI";
    case "inbeersa":
      return "InBeersa Meliponas";
    case "sigatoka":
      return "Sigatoka Foliar";
    case "conservacion":
      return "Conservación Páramo";
    case "otro":
      return "Estación Genérica";
    default:
      return String(tipo);
  }
}

export function formatearFechaHora(epochSegundos: number | null | undefined): string {
  if (!epochSegundos || !Number.isFinite(epochSegundos)) return "Sin registro";
  const d = new Date(epochSegundos * 1000);
  return new Intl.DateTimeFormat("es-CO", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

export function formatearFechaIso(iso: string | null | undefined): string {
  if (!iso) return "Sin registro";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("es-CO", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

export function minutosDesdeEpoch(epochSegundos: number | null | undefined): number | null {
  if (!epochSegundos || !Number.isFinite(epochSegundos)) return null;
  return Math.max(0, Date.now() / 1000 - epochSegundos) / 60;
}

export function formatearHaceMinutos(minutos: number | null | undefined): string {
  if (minutos === null || minutos === undefined || !Number.isFinite(minutos)) {
    return "Sin datos";
  }
  if (minutos < 1) return "Hace instantes";
  if (minutos < 60) return `Hace ${Math.round(minutos)} min`;
  const h = Math.floor(minutos / 60);
  const m = Math.round(minutos % 60);
  if (h < 24) return m > 0 ? `Hace ${h} h ${m} m` : `Hace ${h} h`;
  const dias = Math.floor(h / 24);
  return `Hace ${dias} d`;
}

export function formatearNumero(
  valor: number | null | undefined,
  decimales = 1,
  sufijo = ""
): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor)) {
    return "—";
  }
  const texto = valor.toFixed(decimales);
  return sufijo ? `${texto}${sufijo}` : texto;
}

const NOMBRES_VARIABLES: Record<string, string> = {
  suelo_a: "Humedad Suelo A",
  suelo_b: "Humedad Suelo B",
  temp_aire: "Temperatura Aire",
  hum_aire: "Humedad Relativa",
  presion: "Presión Atmosférica",
  temp_raiz: "Temperatura Radicular",
  voltaje: "Voltaje Batería",
  vpd: "Déficit de Presión de Vapor (VPD)",
  temp_c: "Temperatura Ambiental",
  temp_suelo_c: "Temperatura de Suelo",
  humedad_suelo_pct: "Humedad de Suelo",
  humedad_rel_pct: "Humedad Relativa",
  vpd_kpa: "Déficit de Presión de Vapor (VPD)",
  radiacion_wm2: "Radiación Solar",
  lux: "Iluminancia",
  bateria_pct: "Batería",
  bateria_v: "Voltaje Batería",
  rssi_dbm: "Señal RSSI",
  mojado_foliar_pct: "Mojado Foliar",
  temp_interna_c: "Temperatura Interna Nido",
  temp_externa_c: "Temperatura Externa",
  humedad_interna_pct: "Humedad Interna Nido",
  peso_colmena_kg: "Peso Colmena",
  nivel_agua_cm: "Nivel Freático",
  caudal_l_min: "Caudal",
  lluvia_mm: "Precipitación",
  tasa_secado_suelo_a_pct_h: "Tasa Secado Suelo A (%/h)",
  diferencial_horizontes_ab_pct: "Diferencial A-B (%)",
  horas_estres_vpd: "Horas Estrés VPD",
  horas_riesgo_fungico_vpd: "Horas Riesgo Fúngico",
  horas_hasta_estres_suelo_a: "Horas hasta Estrés",
  voltaje_bateria_v: "Voltaje Batería (V)",
  delta_temp_medio_c: "Delta Térmico Medio (°C)",
  desviacion_termica_nido_c: "Desviación Térmica Nido (°C)",
  en_rango_homeostasis: "Homeostasis Térmica",
  tasa_actividad_pir_por_hora: "Actividad PIR (/h)",
  conteo_audios_bioacusticos: "Audios Bioacústicos",
  umbral_humedad_pct: "Umbral Disparo Riego (%)",
  capacidad_campo_pct: "Capacidad de Campo (%)",
  lamina_max_l_m2: "Lámina Máx. por Evento (L/m²)",
  adc_seco: "Calibración ADC Seco",
  adc_agua: "Calibración ADC Agua",
  ema_alpha: "Factor Filtro EMA (α)",
  vpd_alerta_kpa: "Alerta VPD (kPa)",
  temp_nido_min_c: "Temp. Mín. Nido (°C)",
  umbral_mojado_foliar_pct: "Umbral Mojado Foliar (%)",
};

export function nombreLegibleVariable(clave: string): string {
  return (
    NOMBRES_VARIABLES[clave] ??
    clave
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

export function etiquetarProveedorIA(proveedor?: string | null): string {
  if (!proveedor) return "Motor IA";
  if (proveedor.startsWith("local_reglas")) return "Motor Determinista Local";
  if (proveedor.startsWith("gemini")) return "Google Gemini AI";
  if (proveedor.startsWith("ollama")) return "Ollama Local";
  if (proveedor === "alerta-despacho") return "Despacho 24h";
  return proveedor.replace(/_/g, " ");
}

export function etiquetarFuerzaCorrelacion(valor?: string | null): string {
  if (!valor) return "";
  const limpio = valor.toLowerCase();
  const mapa: Record<string, string> = {
    muy_fuerte: "Correlación muy fuerte",
    fuerte: "Correlación fuerte",
    moderada: "Correlación moderada",
    debil: "Correlación débil",
    debil_o_nula: "Correlación débil o nula",
    nula: "Sin correlación lineal",
  };
  return mapa[limpio] ?? valor.replace(/_/g, " ");
}

export function limpiarTextoCopiloto(texto: string): string {
  return texto
    .replace(/`([a-z0-9_]+)`/gi, (_m, clave: string) =>
      nombreLegibleVariable(clave)
    )
    .replace(
      /\b(suelo_a|suelo_b|hum_aire|temp_aire|temp_raiz|temp_interna_c|temp_externa_c|humedad_interna_pct|umbral_humedad_pct|capacidad_campo_pct|lamina_max_l_m2|temp_nido_min_c|umbral_mojado_foliar_pct|vpd_alerta_kpa|ema_alpha|adc_seco|adc_agua)\b/g,
      (clave: string) => nombreLegibleVariable(clave)
    )
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .trim();
}
