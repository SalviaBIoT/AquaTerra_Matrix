import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  Clock,
  Cpu,
  FolderSearch,
  HardDriveDownload,
  Loader2,
  Radio,
  RefreshCw,
  Terminal,
  Usb,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "../components/common/Badge";
import { useApp } from "../context/AppContext";
import { api, ApiError } from "../lib/api";
import { etiquetarTipoEstacion, formatearFechaHora } from "../lib/formatters";
import type {
  ArchivoMicroSD,
  EventoEstacion,
  PuertoSerial,
  ResultadoIngestaRadio,
} from "../types/aquaterra";

const TRAMAS_EJEMPLO =
  "TB_INTI_01|T:22.4|H:68.2|HS:44.5|VPD:0.86|BAT:89\nTB_INTI_01|T:22.9|H:66.1|HS:43.8|LUX:42100|BAT:88";

export function HardwarePage() {
  const {
    estaciones,
    estacionActivaId,
    setEstacionActivaId,
    estacionActiva,
    recargarGlobal,
  } = useApp();

  const [puertos, setPuertos] = useState<PuertoSerial[]>([]);
  const [puertoSel, setPuertoSel] = useState("");
  const [baudrate, setBaudrate] = useState("115200");
  const [maxLineas, setMaxLineas] = useState("25");
  const [leyendoSerial, setLeyendoSerial] = useState(false);

  const [tramasTexto, setTramasTexto] = useState(TRAMAS_EJEMPLO);
  const [ingiriendoTramas, setIngiriendoTramas] = useState(false);
  const [resultadosRadio, setResultadosRadio] = useState<
    ResultadoIngestaRadio[]
  >([]);

  const [rutaManual, setRutaManual] = useState("");
  const [unidades, setUnidades] = useState<string[]>([]);
  const [archivosSd, setArchivosSd] = useState<ArchivoMicroSD[]>([]);
  const [escaneandoSd, setEscaneandoSd] = useState(false);
  const [importandoRuta, setImportandoRuta] = useState<string | null>(null);

  const [reparandoRtc, setReparandoRtc] = useState(false);
  const [eventos, setEventos] = useState<EventoEstacion[]>([]);

  const cargarPuertos = useCallback(async () => {
    try {
      const resp = await api.get<{ puertos: PuertoSerial[] }>(
        "/api/hardware/puertos"
      );
      const lista = resp.puertos ?? [];
      setPuertos(lista);
      setPuertoSel((prev) =>
        prev && lista.some((p) => p.device === prev)
          ? prev
          : lista[0]?.device ?? ""
      );
    } catch {
      setPuertos([]);
    }
  }, []);

  const cargarEventos = useCallback(async (id: number) => {
    try {
      const resp = await api.get<{ eventos: EventoEstacion[] }>(
        `/api/estaciones/${id}/eventos?limite=40`
      );
      setEventos(resp.eventos ?? []);
    } catch {
      setEventos([]);
    }
  }, []);

  useEffect(() => {
    void cargarPuertos();
  }, [cargarPuertos]);

  useEffect(() => {
    if (estacionActivaId !== null) {
      void cargarEventos(estacionActivaId);
    }
  }, [estacionActivaId, cargarEventos]);

  const handleLeerSerial = async () => {
    if (!puertoSel) {
      toast.error("No hay ningún puerto COM seleccionado.");
      return;
    }
    setLeyendoSerial(true);
    try {
      const resp = await api.post<{
        resultados: ResultadoIngestaRadio[];
        total_tramas: number;
        total_lecturas_insertadas: number;
      }>("/api/hardware/serial/leer", {
        puerto: puertoSel,
        baudrate: Number(baudrate),
        max_lineas: Number(maxLineas),
      });
      setResultadosRadio(resp.resultados ?? []);
      toast.success(
        `Serial ${puertoSel}: ${resp.total_tramas} tramas leídas, ${resp.total_lecturas_insertadas} lecturas insertadas.`
      );
      await recargarGlobal();
      if (estacionActivaId !== null) void cargarEventos(estacionActivaId);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Error leyendo puerto serial."
      );
    } finally {
      setLeyendoSerial(false);
    }
  };

  const handleIngerirTramas = async (e: FormEvent) => {
    e.preventDefault();
    const lineas = tramasTexto
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean);
    if (lineas.length === 0) {
      toast.error("Ingresa al menos una trama de radio válida.");
      return;
    }
    setIngiriendoTramas(true);
    try {
      const resp = await api.post<{
        resultados: ResultadoIngestaRadio[];
        total_tramas: number;
        total_lecturas_insertadas: number;
      }>("/api/hardware/tramas", { lineas });
      setResultadosRadio(resp.resultados ?? []);
      toast.success(
        `Decodificadas ${resp.total_tramas} tramas · ${resp.total_lecturas_insertadas} lecturas almacenadas.`
      );
      await recargarGlobal();
      if (estacionActivaId !== null) void cargarEventos(estacionActivaId);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Error decodificando tramas."
      );
    } finally {
      setIngiriendoTramas(false);
    }
  };

  const handleEscanearMicroSd = async () => {
    setEscaneandoSd(true);
    try {
      const directorios = rutaManual.trim() ? [rutaManual.trim()] : null;
      const resp = await api.post<{
        unidades_disponibles: string[];
        archivos: ArchivoMicroSD[];
      }>("/api/hardware/microsd/escanear", { directorios });
      setUnidades(resp.unidades_disponibles ?? []);
      setArchivosSd(resp.archivos ?? []);
      toast.success(
        `Escaneo completado: ${(resp.archivos ?? []).length} archivo(s) CSV detectado(s).`
      );
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Error escaneando MicroSD."
      );
    } finally {
      setEscaneandoSd(false);
    }
  };

  const handleImportarArchivo = async (ruta: string) => {
    if (estacionActivaId === null) {
      toast.error("Selecciona una estación destino primero.");
      return;
    }
    setImportandoRuta(ruta);
    try {
      await api.post("/api/hardware/microsd/importar", {
        estacion_id: estacionActivaId,
        ruta_archivo: ruta,
      });
      toast.success(
        `Archivo CSV importado correctamente a ${
          estacionActiva?.codigo ?? `estación #${estacionActivaId}`
        }.`
      );
      await recargarGlobal();
      void cargarEventos(estacionActivaId);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Error importando archivo CSV."
      );
    } finally {
      setImportandoRuta(null);
    }
  };

  const handleRepararRtc = async () => {
    if (estacionActivaId === null) return;
    setReparandoRtc(true);
    try {
      const resp = await api.post<{ reparadas: number }>(
        `/api/estaciones/${estacionActivaId}/reparar-rtc`
      );
      toast.success(
        `Reparación RTC completada: ${resp.reparadas} lectura(s) ajustada(s).`
      );
      void cargarEventos(estacionActivaId);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "No se pudo reparar el reloj RTC."
      );
    } finally {
      setReparandoRtc(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
            Hardware de Campo · nRF24L01+ / LoRa &amp; MicroSD
          </h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Adquisición directa desde gateway USB-Serial ESP32, inyección de
            tramas radio, escáner MicroSD y corrección de deriva RTC.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <select
            value={estacionActivaId ?? ""}
            onChange={(e) =>
              setEstacionActivaId(
                e.target.value ? Number(e.target.value) : null
              )
            }
            aria-label="Estación destino de hardware"
            className="h-9 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 text-xs font-medium text-[var(--text-primary)]"
          >
            {estaciones.map((e) => (
              <option key={e.id} value={e.id}>
                {e.codigo} · {e.nombre}
              </option>
            ))}
          </select>

          <button
            type="button"
            disabled={reparandoRtc || estacionActivaId === null}
            onClick={() => void handleRepararRtc()}
            className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3.5 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] disabled:opacity-45"
          >
            <Clock className="h-3.5 w-3.5 text-[var(--status-warning)]" aria-hidden="true" />
            {reparandoRtc ? "Reparando RTC…" : "Reparar marcas RTC"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        {/* Gateway Serial + Inyector de Tramas (6 cols) */}
        <section className="surface-card flex flex-col gap-5 p-5 xl:col-span-6">
          <div>
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Usb
                  className="h-4 w-4 text-[var(--accent-primary)]"
                  aria-hidden="true"
                />
                <h2 className="text-base font-semibold text-[var(--text-primary)]">
                  Gateway USB-Serial ESP32
                </h2>
              </div>
              <button
                type="button"
                onClick={() => void cargarPuertos()}
                className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
              >
                <RefreshCw className="h-3 w-3" aria-hidden="true" />
                Detectar COM
              </button>
            </div>

            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-4">
              <select
                value={puertoSel}
                onChange={(e) => setPuertoSel(e.target.value)}
                aria-label="Puerto serial COM"
                className="h-9 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2.5 font-mono text-xs sm:col-span-2"
              >
                {puertos.length === 0 ? (
                  <option value="">Sin puertos COM detectados</option>
                ) : (
                  puertos.map((p) => (
                    <option key={p.device} value={p.device}>
                      {p.device} · {p.descripcion}
                    </option>
                  ))
                )}
              </select>

              <select
                value={baudrate}
                onChange={(e) => setBaudrate(e.target.value)}
                aria-label="Velocidad en baudios"
                className="h-9 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2.5 font-mono text-xs"
              >
                <option value="9600">9600 baud</option>
                <option value="115200">115200 baud</option>
              </select>

              <input
                type="number"
                min={1}
                max={200}
                value={maxLineas}
                onChange={(e) => setMaxLineas(e.target.value)}
                aria-label="Máximo de tramas por lote"
                className="tabular-nums h-9 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2.5 font-mono text-xs"
              />
            </div>

            <button
              type="button"
              disabled={!puertoSel || leyendoSerial}
              onClick={() => void handleLeerSerial()}
              className="mt-3 inline-flex items-center gap-2 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-elevated)] px-4 py-2 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-subtle)] disabled:opacity-45"
            >
              <Radio className="h-3.5 w-3.5 text-[var(--accent-primary)]" aria-hidden="true" />
              {leyendoSerial ? "Leyendo puerto serial…" : "Leer lote serial"}
            </button>
          </div>

          <form
            onSubmit={handleIngerirTramas}
            className="border-t border-[var(--border-subtle)] pt-4"
          >
            <div className="mb-2 flex items-center gap-2">
              <Terminal
                className="h-4 w-4 text-[var(--status-info)]"
                aria-hidden="true"
              />
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                Decodificador &amp; Inyector de Tramas Radio
              </h3>
            </div>
            <label htmlFor="tramas-textarea" className="visually-hidden">
              Tramas de texto crudas separadas por línea
            </label>
            <textarea
              id="tramas-textarea"
              rows={4}
              value={tramasTexto}
              onChange={(e) => setTramasTexto(e.target.value)}
              spellCheck={false}
              className="w-full rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] p-3 font-mono text-xs leading-relaxed text-[var(--text-primary)]"
            />
            <div className="mt-3 flex items-center justify-between gap-2">
              <span className="text-[11px] text-[var(--text-muted)]">
                Deduplicación automática por índice `(estacion, variable, epoch)`
              </span>
              <button
                type="submit"
                disabled={ingiriendoTramas}
                className="inline-flex items-center gap-1.5 rounded-xl bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-[var(--accent-contrast)] hover:bg-[var(--accent-primary-hover)] disabled:opacity-50"
              >
                {ingiriendoTramas ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                ) : (
                  <Cpu className="h-3.5 w-3.5" aria-hidden="true" />
                )}
                Decodificar e Ingerir
              </button>
            </div>
          </form>

          {resultadosRadio.length > 0 && (
            <div className="space-y-1.5 border-t border-[var(--border-subtle)] pt-3">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Último lote procesado
              </div>
              {resultadosRadio.map((r, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between gap-2 rounded-lg bg-[var(--bg-elevated)] px-3 py-1.5 text-xs"
                >
                  <span className="font-mono">
                    {r.estacion_codigo ?? "Trama inválida"}
                  </span>
                  <span className="tabular-nums text-[var(--text-secondary)]">
                    {r.trama_valida
                      ? `${r.lecturas_insertadas}/${r.lecturas_recibidas} insertadas`
                      : r.error}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Escáner MicroSD & Importador (6 cols) */}
        <section className="surface-card flex flex-col justify-between gap-4 p-5 xl:col-span-6">
          <div>
            <div className="mb-3 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <FolderSearch
                  className="h-4 w-4 text-[var(--status-info)]"
                  aria-hidden="true"
                />
                <h2 className="text-base font-semibold text-[var(--text-primary)]">
                  Escáner MicroSD &amp; Archivos de Campo (.csv)
                </h2>
              </div>
              {unidades.length > 0 && (
                <Badge tono="optimal">
                  Unidades: {unidades.join(", ")}
                </Badge>
              )}
            </div>

            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                type="text"
                value={rutaManual}
                onChange={(e) => setRutaManual(e.target.value)}
                placeholder="Ruta personalizada opcional (ej. E:\DATALOGGER)"
                aria-label="Directorio opcional a escanear"
                className="h-9 flex-1 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 font-mono text-xs"
              />
              <button
                type="button"
                disabled={escaneandoSd}
                onClick={() => void handleEscanearMicroSd()}
                className="inline-flex h-9 items-center justify-center gap-1.5 rounded-xl bg-[var(--bg-elevated)] px-4 text-xs font-semibold text-[var(--text-primary)] border border-[var(--border-strong)] hover:bg-[var(--bg-subtle)] disabled:opacity-50"
              >
                {escaneandoSd && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                )}
                Escanear MicroSD
              </button>
            </div>

            <div className="mt-4 space-y-2">
              {archivosSd.length === 0 ? (
                <div className="rounded-xl bg-[var(--bg-elevated)] p-5 text-center text-xs text-[var(--text-secondary)]">
                  Ejecuta un escaneo para listar archivos históricos generados
                  por nodos TerraBit Station, InBeersa, Sigatoka o Conservación.
                </div>
              ) : (
                archivosSd.map((a) => (
                  <div
                    key={a.ruta_archivo}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-xs"
                  >
                    <div className="min-w-0">
                      <div className="truncate font-semibold text-[var(--text-primary)]">
                        {a.nombre}
                      </div>
                      <div className="truncate font-mono text-[10px] text-[var(--text-muted)]">
                        {a.ruta_archivo} · {(a.tamano_bytes / 1024).toFixed(1)} KB
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge tono="info">
                        {etiquetarTipoEstacion(a.tipo_estacion_inferido)}
                      </Badge>
                      <button
                        type="button"
                        disabled={
                          estacionActivaId === null ||
                          importandoRuta === a.ruta_archivo
                        }
                        onClick={() => void handleImportarArchivo(a.ruta_archivo)}
                        className="inline-flex items-center gap-1 rounded-lg bg-[var(--accent-primary)] px-2.5 py-1.5 text-[11px] font-semibold text-[var(--accent-contrast)] hover:bg-[var(--accent-primary-hover)] disabled:opacity-45"
                      >
                        <HardDriveDownload className="h-3 w-3" aria-hidden="true" />
                        {importandoRuta === a.ruta_archivo
                          ? "Importando…"
                          : "Importar"}
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>
      </div>

      {/* Bitácora de Eventos de Hardware de la Estación */}
      <section className="surface-card overflow-hidden">
        <div className="border-b border-[var(--border-subtle)] px-5 py-3.5">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            Eventos Recientes de Estación ({estacionActiva?.codigo ?? "—"})
          </h2>
        </div>
        <div className="overflow-x-auto p-4">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] text-[var(--text-muted)]">
                <th scope="col" className="py-2 pr-4">Fecha</th>
                <th scope="col" className="py-2 pr-4">Tipo de Evento</th>
                <th scope="col" className="py-2 pr-4">Valor / Detalle</th>
                <th scope="col" className="py-2">Artefacto / Ruta</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {eventos.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-4 text-center text-[var(--text-secondary)]">
                    Sin eventos recientes registrados para esta estación.
                  </td>
                </tr>
              ) : (
                eventos.map((ev, idx) => (
                  <tr key={ev.id ?? `${ev.ts_epoch}-${idx}`}>
                    <td className="py-2.5 pr-4 font-mono">
                      {formatearFechaHora(ev.ts_epoch)}
                    </td>
                    <td className="py-2.5 pr-4">
                      <Badge tono="neutral">{ev.tipo_evento}</Badge>
                    </td>
                    <td className="py-2.5 pr-4 text-[var(--text-secondary)]">
                      {ev.valor_texto ?? "—"}
                    </td>
                    <td className="py-2.5 font-mono text-[11px] text-[var(--text-muted)]">
                      {ev.archivo_ruta ?? "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
