export type RolUsuario = "admin" | "operador" | "lector";

export type TipoEstacion =
  | "terrabit_inti"
  | "inbeersa"
  | "sigatoka"
  | "conservacion"
  | "otro";

export type NivelSeveridadPulso = "critico" | "atencion" | "optimo" | "sin_datos";

export type VistaId =
  | "radar"
  | "telemetria"
  | "parcelas"
  | "riego"
  | "copiloto"
  | "hardware"
  | "config";

export interface Usuario {
  id: number;
  usuario: string;
  nombre: string;
  rol: RolUsuario;
  activo?: boolean;
  creado_en?: string;
}

export interface Estacion {
  id: number;
  codigo: string;
  nombre: string;
  tipo: TipoEstacion;
  latitud: number | null;
  longitud: number | null;
  altitud_m: number | null;
  activa: boolean;
}

export interface ResumenVariablePulso {
  variable: string;
  unidad?: string | null;
  ultimo_valor: number | null;
  ultimo_ts_epoch: number | null;
  media_24h: number | null;
  min_24h: number | null;
  max_24h: number | null;
  tendencia: string;
  tasa_hora: number | null;
  muestras: number;
  completitud_pct: number;
}

export interface ResumenPulso24h {
  estacion_id: number;
  codigo_estacion: string;
  nombre_estacion: string;
  tipo_estacion: TipoEstacion;
  desde_epoch: number;
  hasta_epoch: number;
  severidad: NivelSeveridadPulso;
  completitud_global_pct: number;
  variables: Record<string, ResumenVariablePulso>;
  alertas_detectadas: string[];
  diagnostico_determinista: string;
  inti?: Record<string, unknown> | null;
  inbeersa?: Record<string, unknown> | null;
  sigatoka?: Record<string, unknown> | null;
  conservacion?: Record<string, unknown> | null;
}

export interface EntradaRadarEstacion {
  estacion: Estacion;
  severidad: NivelSeveridadPulso;
  alertas_activas: number;
  completitud_24h_pct: number;
  ultimo_ts_epoch: number | null;
  diagnostico_resumen: string;
  parcelas_asociadas: string[];
}

export interface ResumenRadar {
  total_estaciones: number;
  criticas: number;
  atenciones: number;
  optimas: number;
  sin_datos: number;
  parcelas_activas: number;
}

export interface RadarResponse {
  resumen: ResumenRadar;
  entradas: EntradaRadarEstacion[];
}

export interface SeriesResponse {
  estacion: Estacion;
  desde_epoch: number;
  hasta_epoch: number;
  unidades: Record<string, string>;
  series: Record<string, [number, number][]>;
}

export interface CorrelacionResponse {
  resultado: {
    variable_x: string;
    variable_y: string;
    pares_alineados: number;
    pearson_r: number | null;
    pendiente_y_sobre_x: number | null;
    interpretacion: string;
  };
  pares: [number, number][];
  recta_ols: [number, number][] | null;
}

export interface PronosticoPunto {
  estacion_id: number;
  ts_objetivo_epoch: number;
  ts_objetivo_iso: string;
  temp_c?: number | null;
  hum_relativa_pct?: number | null;
  lluvia_prob_pct?: number | null;
  lluvia_mm?: number | null;
  viento_ms?: number | null;
  et0_mm?: number | null;
}

export interface EventoEstacion {
  id?: number | null;
  estacion_id: number;
  tipo_evento: string;
  ts_epoch: number;
  ts_iso: string;
  valor_texto?: string | null;
  archivo_ruta?: string | null;
  metadatos?: Record<string, unknown> | null;
}

export interface Parcela {
  id: number;
  nombre: string;
  cultivo: string;
  area_m2: number;
  humedad_pct: number;
  tipo_suelo: string;
  riego_auto: boolean;
  estacion_id: number | null;
  activa?: boolean;
}

export interface ComparativoMonitorResponse {
  humedad_por_parcela: { nombre: string; humedad_pct: number }[];
  consumo_por_parcela: { nombre: string; litros: number }[];
}

export interface EstadoCandado {
  codigo: string;
  superado: boolean;
  recorte_aplicado: boolean;
  detalle: string;
}

export interface VeredictoSeguridad {
  autorizado: boolean;
  litros_autorizados: number;
  apertura_autorizada_pct: number;
  candados: EstadoCandado[];
  motivos_bloqueo: string[];
  advertencias_recorte: string[];
}

export interface RecomendacionRiego {
  accion: string;
  regar: boolean;
  litros_sugeridos: number;
  apertura_sugerida_pct: number;
  humedad_actual_pct: number | null;
  umbral_disparo_pct: number;
  tasa_secado_pct_h: number | null;
  horas_hasta_estres: number | null;
  veredicto_seguridad?: VeredictoSeguridad | null;
  justificacion: string;
}

export interface SaludActuador {
  id: number;
  evento_riego_id: number;
  modo_verificacion: string;
  vibracion_rms_g?: number | null;
  vibracion_freq_hz?: number | null;
  corriente_a?: number | null;
  caudal_lpm?: number | null;
  apertura_max_pct: number;
  diagnostico_mecanico: string;
  registrado_en: string;
}

export interface EventoRiego {
  id: number;
  parcela_id: number;
  ts_iso: string;
  ts_epoch: number;
  humedad_inicial_pct: number;
  humedad_final_pct: number;
  agua_litros: number;
  origen: string;
  usuario_id?: number | null;
}

export interface RiegoProgramado {
  id: number;
  parcela_id: number;
  ts_programado_epoch: number;
  ts_programado_iso: string;
  litros_propuestos: number;
  apertura_max_pct: number;
  origen: string;
  estado: string;
  motivo_bloqueo?: string | null;
  creado_en: string;
}

export interface IncidenciaRiego {
  id: number;
  evento_riego_id: number;
  humedad_a_antes: number;
  humedad_a_despues: number;
  humedad_b_antes?: number | null;
  humedad_b_despues?: number | null;
  delta_a_pct: number;
  delta_b_pct?: number | null;
  efectividad: string;
  observaciones?: string | null;
  evaluado_en: string;
}

export interface ContextoRiegoResponse {
  parcela: Parcela;
  recomendacion: RecomendacionRiego;
  salud_bomba: SaludActuador | null;
  historial: EventoRiego[];
  programados: RiegoProgramado[];
  incidencias: IncidenciaRiego[];
  modos_verificacion: string[];
}

export interface CotaCalibracion {
  clave: string;
  minimo: number;
  maximo: number;
  delta_max_por_paso: number;
  valor_por_defecto: number;
  unidad: string;
  descripcion: string;
}

export interface RecorteParametro {
  clave: string;
  valor_original: number;
  valor_acotado: number;
  motivo: string;
}

export interface InteraccionCopiloto {
  id: number;
  estacion_id: number | null;
  parcela_id: number | null;
  usuario_id: number | null;
  mensaje_usuario: string;
  diagnostico_ia: string;
  ajustes_propuestos: Record<string, number> | null;
  calibracion_aplicada_id: number | null;
  proveedor_ia: string;
  ts_iso: string;
}

export interface VersionCalibracion {
  id: number;
  estacion_id: number | null;
  parcela_id: number | null;
  version: number;
  parametros: Record<string, number | string | boolean>;
  motivo: string;
  autor_id: number | null;
  activa: boolean;
  creado_en: string;
}

export interface EstadoCopilotoResponse {
  version_actual: number;
  parametros_actuales: Record<string, number>;
  catalogo_cotas: Record<string, CotaCalibracion>;
  historial: InteraccionCopiloto[];
  historial_reciente_global?: InteraccionCopiloto[];
  versiones: VersionCalibracion[];
  versiones_globales?: VersionCalibracion[];
}

export interface ConsultarCopilotoResponse {
  respuesta: {
    interaccion: InteraccionCopiloto;
    propuesta: {
      diagnostico_tecnico: string;
      justificacion_agronomica: string;
      ajustes_propuestos: Record<string, number>;
      confianza: number;
      alertas_consideradas: string[];
      proveedor_ia: string;
    };
    auditoria: {
      ajustes_seguros: Record<string, number>;
      recortes_aplicados: RecorteParametro[];
      claves_rechazadas: string[];
      advertencias_seguridad: string[];
    };
    version_aplicada: VersionCalibracion | null;
  };
}

export interface PuertoSerial {
  device: string;
  descripcion: string;
}

export interface ArchivoMicroSD {
  ruta_archivo: string;
  nombre: string;
  tipo_estacion_inferido: TipoEstacion;
  tamano_bytes: number;
}

export interface ResultadoIngestaRadio {
  trama_valida: boolean;
  estacion_codigo: string | null;
  lecturas_recibidas: number;
  lecturas_insertadas: number;
  error: string | null;
}

export interface ReportePulsoLectura {
  clave: string;
  nombre: string;
  valor: number;
  unidad: string;
}

export interface ReportePulsoIA {
  estacion: string;
  codigo: string;
  severidad: NivelSeveridadPulso;
  completitud_pct: number;
  proveedor_ia: string;
  proveedor_legible: string;
  lecturas: ReportePulsoLectura[];
  alertas: string[];
  diagnostico: string;
  justificacion: string;
}

export interface EstadoSistema {
  sqlite_wal: boolean;
  open_meteo_reachable?: boolean;
  ubidots_configurado: boolean;
  ia_proveedor: string;
  ia_gemini_configurado: boolean;
  ia_gemini_modelo?: string;
  ia_ollama_url: string;
  ia_ollama_modelo: string;
  ia_ollama_disponible?: boolean | null;
  ollama_disponible?: boolean | null;
  puertos_serial: PuertoSerial[];
  worker_activo: boolean;
  webhook_configurado: boolean;
  telegram_configurado: boolean;
  version_app: string;
}

export interface ItemBusquedaGlobal {
  categoria: string;
  referencia_id?: number | null;
  titulo: string;
  detalle?: string;
  subtitulo?: string;
  ts_iso?: string;
}

export interface ResultadoBusquedaGlobal {
  consulta: string;
  total_hallazgos: number;
  items: ItemBusquedaGlobal[];
}
