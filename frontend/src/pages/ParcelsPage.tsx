import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  AlertCircle,
  Archive,
  Droplets,
  Edit3,
  Loader2,
  MapPin,
  Plus,
  Search,
  Sprout,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "../components/common/Badge";
import { useApp } from "../context/AppContext";
import { api, ApiError } from "../lib/api";
import { formatearNumero } from "../lib/formatters";
import type { Parcela } from "../types/aquaterra";

interface FormParcelaState {
  nombre: string;
  cultivo: string;
  area_m2: string;
  humedad_pct: string;
  tipo_suelo: string;
  riego_auto: boolean;
  estacion_id: string;
}

export function ParcelsPage() {
  const { usuario, estaciones, recargarGlobal, setVistaActiva } = useApp();
  const puedeEditar = usuario?.rol === "admin" || usuario?.rol === "operador";
  const puedeArchivar = usuario?.rol === "admin" || usuario?.rol === "operador";

  const [parcelas, setParcelas] = useState<Parcela[]>([]);
  const [cultivos, setCultivos] = useState<string[]>([
    "Maiz",
    "Tomate",
    "Fresas",
    "Hortalizas",
    "Flores",
  ]);
  const [tiposSuelo, setTiposSuelo] = useState<string[]>([
    "Arenoso",
    "Franco",
    "Arcilloso",
  ]);
  const [cargando, setCargando] = useState(true);

  const [busqueda, setBusqueda] = useState("");
  const [soloAuto, setSoloAuto] = useState(false);

  // Slide-over <dialog> Crear / Editar
  const drawerRef = useRef<HTMLDialogElement | null>(null);
  const [drawerAbierto, setDrawerAbierto] = useState(false);
  const [editando, setEditando] = useState<Parcela | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [errorForm, setErrorForm] = useState<string | null>(null);
  const [form, setForm] = useState<FormParcelaState>({
    nombre: "",
    cultivo: "Tomate",
    area_m2: "500",
    humedad_pct: "55",
    tipo_suelo: "Franco",
    riego_auto: true,
    estacion_id: "",
  });

  // Confirmación de archivado
  const confirmRef = useRef<HTMLDialogElement | null>(null);
  const [parcelaArchivar, setParcelaArchivar] = useState<Parcela | null>(null);
  const [archivando, setArchivando] = useState(false);

  const cargarParcelas = useCallback(async () => {
    setCargando(true);
    try {
      const resp = await api.get<{
        parcelas: Parcela[];
        cultivos_soportados: string[];
        tipos_suelo: string[];
      }>("/api/parcelas");
      setParcelas(resp.parcelas ?? []);
      if (resp.cultivos_soportados?.length) {
        setCultivos(resp.cultivos_soportados);
      }
      if (resp.tipos_suelo?.length) {
        setTiposSuelo(resp.tipos_suelo);
      }
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Error cargando parcelas."
      );
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void cargarParcelas();
  }, [cargarParcelas]);

  useEffect(() => {
    const dlg = drawerRef.current;
    if (!dlg) return;
    if (drawerAbierto && !dlg.open) dlg.showModal();
    else if (!drawerAbierto && dlg.open) dlg.close();
  }, [drawerAbierto]);

  useEffect(() => {
    const dlg = confirmRef.current;
    if (!dlg) return;
    if (parcelaArchivar && !dlg.open) dlg.showModal();
    else if (!parcelaArchivar && dlg.open) dlg.close();
  }, [parcelaArchivar]);

  const abrirCrear = () => {
    setEditando(null);
    setErrorForm(null);
    setForm({
      nombre: "",
      cultivo: cultivos[0] ?? "Tomate",
      area_m2: "500",
      humedad_pct: "52",
      tipo_suelo: tiposSuelo[1] ?? tiposSuelo[0] ?? "Franco",
      riego_auto: true,
      estacion_id: estaciones[0] ? String(estaciones[0].id) : "",
    });
    setDrawerAbierto(true);
  };

  const abrirEditar = (p: Parcela) => {
    setEditando(p);
    setErrorForm(null);
    setForm({
      nombre: p.nombre,
      cultivo: p.cultivo,
      area_m2: String(p.area_m2),
      humedad_pct: String(p.humedad_pct),
      tipo_suelo: p.tipo_suelo,
      riego_auto: p.riego_auto,
      estacion_id: p.estacion_id ? String(p.estacion_id) : "",
    });
    setDrawerAbierto(true);
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrorForm(null);

    const area = Number(form.area_m2);
    const humedad = Number(form.humedad_pct);
    if (!form.nombre.trim()) {
      setErrorForm("El nombre de la parcela es obligatorio.");
      return;
    }
    if (!Number.isFinite(area) || area <= 0) {
      setErrorForm("El área en m² debe ser un número mayor a cero.");
      return;
    }
    if (!Number.isFinite(humedad) || humedad < 0 || humedad > 100) {
      setErrorForm("La humedad inicial debe estar entre 0% y 100%.");
      return;
    }

    setGuardando(true);
    try {
      const estId = form.estacion_id ? Number(form.estacion_id) : null;
      if (editando) {
        await api.patch(`/api/parcelas/${editando.id}`, {
          nombre: form.nombre.trim(),
          cultivo: form.cultivo,
          area_m2: area,
          humedad_pct: humedad,
          tipo_suelo: form.tipo_suelo,
          riego_auto: form.riego_auto,
          estacion_id: estId,
          desvincular_estacion: estId === null,
        });
        toast.success(`Parcela "${form.nombre.trim()}" actualizada.`);
      } else {
        await api.post("/api/parcelas", {
          nombre: form.nombre.trim(),
          cultivo: form.cultivo,
          area_m2: area,
          humedad_pct: humedad,
          tipo_suelo: form.tipo_suelo,
          riego_auto: form.riego_auto,
          estacion_id: estId,
        });
        toast.success(`Parcela "${form.nombre.trim()}" registrada.`);
      }
      setDrawerAbierto(false);
      await Promise.all([cargarParcelas(), recargarGlobal()]);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorForm(err.detail);
      } else {
        setErrorForm("No se pudo guardar la parcela.");
      }
    } finally {
      setGuardando(false);
    }
  };

  const confirmarArchivado = async () => {
    if (!parcelaArchivar) return;
    setArchivando(true);
    try {
      await api.del(`/api/parcelas/${parcelaArchivar.id}`);
      toast.success(`Parcela "${parcelaArchivar.nombre}" archivada.`);
      setParcelaArchivar(null);
      await Promise.all([cargarParcelas(), recargarGlobal()]);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "No se pudo archivar la parcela."
      );
    } finally {
      setArchivando(false);
    }
  };

  const parcelasFiltradas = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return parcelas.filter((p) => {
      if (soloAuto && !p.riego_auto) return false;
      if (!q) return true;
      return (
        p.nombre.toLowerCase().includes(q) ||
        p.cultivo.toLowerCase().includes(q) ||
        p.tipo_suelo.toLowerCase().includes(q)
      );
    });
  }, [parcelas, busqueda, soloAuto]);

  const resumen = useMemo(() => {
    const areaTotal = parcelas.reduce((s, p) => s + p.area_m2, 0);
    const humMedia =
      parcelas.length > 0
        ? parcelas.reduce((s, p) => s + p.humedad_pct, 0) / parcelas.length
        : 0;
    const autoCount = parcelas.filter((p) => p.riego_auto).length;
    return { areaTotal, humMedia, autoCount };
  }, [parcelas]);

  const mapaEstaciones = useMemo(
    () => new Map(estaciones.map((e) => [e.id, e])),
    [estaciones]
  );

  return (
    <div className="space-y-6">
      {/* Cabecera */}
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
            Parcelas y Unidades de Cultivo
          </h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Registro agronómico, textura edáfica, vinculación con estaciones
            TerraBit y régimen de riego automatizado.
          </p>
        </div>

        <button
          type="button"
          onClick={abrirCrear}
          disabled={!puedeEditar}
          title={
            puedeEditar
              ? "Crear nueva parcela"
              : "Tu rol actual no permite crear parcelas"
          }
          className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent-primary)] px-4 py-2.5 text-xs font-semibold text-[var(--accent-contrast)] transition-colors hover:bg-[var(--accent-primary-hover)] disabled:opacity-45"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          Nueva Parcela
        </button>
      </div>

      {/* KPIs de inventario */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="surface-card p-4">
          <div className="text-xs font-medium text-[var(--text-secondary)]">
            Superficie Total Activa
          </div>
          <div className="tabular-nums mt-1.5 text-2xl font-bold text-[var(--text-primary)]">
            {formatearNumero(resumen.areaTotal, 0)} m²
          </div>
          <div className="tabular-nums mt-0.5 text-xs text-[var(--text-muted)]">
            Equivalente a {formatearNumero(resumen.areaTotal / 10000, 2)} ha
          </div>
        </div>

        <div className="surface-card p-4">
          <div className="text-xs font-medium text-[var(--text-secondary)]">
            Humedad Media del Suelo
          </div>
          <div className="tabular-nums mt-1.5 text-2xl font-bold text-[var(--text-primary)]">
            {formatearNumero(resumen.humMedia, 1, "%")}
          </div>
          <div className="mt-0.5 text-xs text-[var(--text-muted)]">
            Promedio ponderado de {parcelas.length} parcelas
          </div>
        </div>

        <div className="surface-card p-4">
          <div className="text-xs font-medium text-[var(--text-secondary)]">
            Automatización Activa
          </div>
          <div className="tabular-nums mt-1.5 text-2xl font-bold text-[var(--accent-primary)]">
            {resumen.autoCount} / {parcelas.length}
          </div>
          <div className="mt-0.5 text-xs text-[var(--text-muted)]">
            Con enclavamiento por 5 candados físicos
          </div>
        </div>
      </div>

      {/* Tabla / Inventario */}
      <section className="surface-card">
        <div className="flex flex-col justify-between gap-3 border-b border-[var(--border-subtle)] p-4 sm:flex-row sm:items-center sm:px-5">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--text-muted)]"
              aria-hidden="true"
            />
            <input
              type="search"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Buscar parcela, cultivo o suelo..."
              aria-label="Buscar en catálogo de parcelas"
              className="h-9 w-full rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] pl-9 pr-3 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] sm:w-72"
            />
          </div>

          <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)]">
            <input
              type="checkbox"
              checked={soloAuto}
              onChange={(e) => setSoloAuto(e.target.checked)}
            />
            Solo riego automático
          </label>
        </div>

        <div className="overflow-x-auto">
          {cargando ? (
            <div className="space-y-3 p-5">
              <div className="skeleton h-11 w-full" />
              <div className="skeleton h-11 w-full" />
            </div>
          ) : parcelasFiltradas.length === 0 ? (
            <div className="p-8 text-center text-sm text-[var(--text-secondary)]">
              <Sprout
                className="mx-auto mb-2 h-7 w-7 text-[var(--text-muted)]"
                aria-hidden="true"
              />
              No se encontraron parcelas activas con el filtro actual.
            </div>
          ) : (
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--border-subtle)] text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                  <th scope="col" className="px-5 py-3">
                    Parcela &amp; Cultivo
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Suelo &amp; Área
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Humedad Suelo
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Nodo IoT
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Modo Riego
                  </th>
                  <th scope="col" className="px-5 py-3 text-right">
                    Acciones
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)]">
                {parcelasFiltradas.map((p) => {
                  const est = p.estacion_id
                    ? mapaEstaciones.get(p.estacion_id)
                    : null;
                  const hum = Math.max(0, Math.min(100, p.humedad_pct));
                  const colorBarra =
                    hum < 35
                      ? "bg-[var(--status-critical)]"
                      : hum < 48
                      ? "bg-[var(--status-warning)]"
                      : "bg-[var(--status-optimal)]";
                  return (
                    <tr
                      key={p.id}
                      className="transition-colors hover:bg-[var(--bg-elevated)]"
                    >
                      <td className="px-5 py-3.5">
                        <div className="font-semibold text-[var(--text-primary)]">
                          {p.nombre}
                        </div>
                        <div className="mt-0.5 text-xs text-[var(--text-secondary)]">
                          Cultivo: {p.cultivo}
                        </div>
                      </td>
                      <td className="px-3 py-3.5">
                        <div className="text-xs font-medium text-[var(--text-primary)]">
                          {p.tipo_suelo}
                        </div>
                        <div className="tabular-nums font-mono text-[11px] text-[var(--text-muted)]">
                          {formatearNumero(p.area_m2, 0)} m²
                        </div>
                      </td>
                      <td className="px-3 py-3.5">
                        <div className="w-32">
                          <div className="flex items-center justify-between text-xs">
                            <span className="tabular-nums font-mono font-semibold text-[var(--text-primary)]">
                              {formatearNumero(hum, 1, "%")}
                            </span>
                          </div>
                          <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-[var(--bg-subtle)]">
                            <div
                              className={`h-full rounded-full ${colorBarra}`}
                              style={{ width: `${hum}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-3.5">
                        {est ? (
                          <span className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-2.5 py-1 font-mono text-[11px] text-[var(--text-primary)]">
                            <MapPin
                              className="h-3 w-3 text-[var(--accent-primary)]"
                              aria-hidden="true"
                            />
                            {est.codigo}
                          </span>
                        ) : (
                          <span className="text-xs text-[var(--text-muted)]">
                            Sin vincular
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-3.5">
                        <Badge tono={p.riego_auto ? "optimal" : "neutral"}>
                          {p.riego_auto ? "Automático" : "Manual"}
                        </Badge>
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <div className="inline-flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => setVistaActiva("riego")}
                            title="Ir a Control de Riego"
                            className="inline-flex h-8 items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-surface)] hover:text-[var(--accent-primary)]"
                          >
                            <Droplets className="h-3.5 w-3.5" aria-hidden="true" />
                            Riego
                          </button>
                          <button
                            type="button"
                            disabled={!puedeEditar}
                            onClick={() => abrirEditar(p)}
                            aria-label={`Editar parcela ${p.nombre}`}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--bg-surface)] hover:text-[var(--text-primary)] disabled:opacity-40"
                          >
                            <Edit3 className="h-3.5 w-3.5" aria-hidden="true" />
                          </button>
                          <button
                            type="button"
                            disabled={!puedeArchivar}
                            onClick={() => setParcelaArchivar(p)}
                            aria-label={`Archivar parcela ${p.nombre}`}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--status-critical-soft)] hover:text-[var(--status-critical)] disabled:opacity-40"
                          >
                            <Archive className="h-3.5 w-3.5" aria-hidden="true" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {/* Slide-over Drawer nativo <dialog> para Crear / Editar Parcela */}
      <dialog
        ref={drawerRef}
        aria-labelledby="drawer-parcela-title"
        onClose={() => {
          if (drawerRef.current) drawerRef.current.returnValue = "";
          setDrawerAbierto(false);
        }}
        className="ml-auto mr-0 my-0 h-dvh max-h-dvh w-[min(95vw,460px)] rounded-l-2xl rounded-r-none p-0"
      >
        <div className="flex h-full flex-col justify-between">
          <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-6 py-4">
            <h2
              id="drawer-parcela-title"
              className="text-lg font-bold text-[var(--text-primary)]"
            >
              {editando
                ? `Editar ${editando.nombre}`
                : "Registrar Nueva Parcela"}
            </h2>
            <button
              type="button"
              onClick={() => setDrawerAbierto(false)}
              aria-label="Cerrar panel de parcela"
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>

          <form
            id="form-parcela"
            onSubmit={handleSubmit}
            className="flex-1 space-y-4 overflow-y-auto px-6 py-5"
          >
            {errorForm && (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-xl bg-[var(--status-critical-soft)] px-3.5 py-2.5 text-xs text-[var(--status-critical)]"
              >
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <span>{errorForm}</span>
              </div>
            )}

            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="parcela-nombre"
                className="text-xs font-semibold text-[var(--text-primary)]"
              >
                Nombre de la parcela *
              </label>
              <input
                id="parcela-nombre"
                type="text"
                required
                value={form.nombre}
                onChange={(e) =>
                  setForm((f) => ({ ...f, nombre: e.target.value }))
                }
                placeholder="Ej. Lote Experimental B2"
                className="at-input h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 text-sm text-[var(--text-primary)]"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="parcela-cultivo"
                  className="text-xs font-semibold text-[var(--text-primary)]"
                >
                  Cultivo *
                </label>
                <select
                  id="parcela-cultivo"
                  value={form.cultivo}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, cultivo: e.target.value }))
                  }
                  className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 text-sm text-[var(--text-primary)]"
                >
                  {cultivos.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="parcela-suelo"
                  className="text-xs font-semibold text-[var(--text-primary)]"
                >
                  Tipo de suelo *
                </label>
                <select
                  id="parcela-suelo"
                  value={form.tipo_suelo}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, tipo_suelo: e.target.value }))
                  }
                  className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 text-sm text-[var(--text-primary)]"
                >
                  {tiposSuelo.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="parcela-area"
                  className="text-xs font-semibold text-[var(--text-primary)]"
                >
                  Área (m²) *
                </label>
                <input
                  id="parcela-area"
                  type="number"
                  min={1}
                  max={10000000}
                  step="any"
                  required
                  value={form.area_m2}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, area_m2: e.target.value }))
                  }
                  className="at-input tabular-nums h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 font-mono text-sm text-[var(--text-primary)]"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="parcela-humedad"
                  className="text-xs font-semibold text-[var(--text-primary)]"
                >
                  Humedad inicial (%) *
                </label>
                <input
                  id="parcela-humedad"
                  type="number"
                  min={0}
                  max={100}
                  step="0.1"
                  required
                  value={form.humedad_pct}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, humedad_pct: e.target.value }))
                  }
                  className="at-input tabular-nums h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 font-mono text-sm text-[var(--text-primary)]"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="parcela-estacion"
                className="text-xs font-semibold text-[var(--text-primary)]"
              >
                Estación IoT vinculada
              </label>
              <select
                id="parcela-estacion"
                value={form.estacion_id}
                onChange={(e) =>
                  setForm((f) => ({ ...f, estacion_id: e.target.value }))
                }
                className="h-10 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 text-sm text-[var(--text-primary)]"
              >
                <option value="">Sin estación vinculada</option>
                {estaciones.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.codigo} · {e.nombre}
                  </option>
                ))}
              </select>
            </div>

            <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3.5">
              <label className="flex cursor-pointer items-start gap-3">
                <input
                  type="checkbox"
                  checked={form.riego_auto}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, riego_auto: e.target.checked }))
                  }
                  className="mt-1"
                />
                <span>
                  <span className="block text-xs font-semibold text-[var(--text-primary)]">
                    Habilitar automatización y protección por 5 candados
                  </span>
                  <span className="block text-[11px] text-[var(--text-secondary)]">
                    Permite la evaluación proactiva del balance hídrico y
                    programación automática.
                  </span>
                </span>
              </label>
            </div>
          </form>

          <div className="flex items-center justify-end gap-2.5 border-t border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-6 py-4">
            <button
              type="button"
              onClick={() => setDrawerAbierto(false)}
              className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 py-2 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-subtle)]"
            >
              Cancelar
            </button>
            <button
              type="submit"
              form="form-parcela"
              disabled={guardando}
              className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-[var(--accent-contrast)] hover:bg-[var(--accent-primary-hover)] disabled:opacity-50"
            >
              {guardando && (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              )}
              {editando ? "Guardar cambios" : "Registrar parcela"}
            </button>
          </div>
        </div>
      </dialog>

      {/* Modal nativo de confirmación para archivar parcela */}
      <dialog
        ref={confirmRef}
        aria-labelledby="confirm-archive-title"
        onClose={() => {
          if (confirmRef.current) confirmRef.current.returnValue = "";
          setParcelaArchivar(null);
        }}
        className="m-auto w-[min(92vw,420px)] rounded-2xl p-6"
      >
        <h2
          id="confirm-archive-title"
          className="text-base font-bold text-[var(--text-primary)]"
        >
          ¿Archivar parcela &ldquo;{parcelaArchivar?.nombre}&rdquo;?
        </h2>
        <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">
          Esta operación aplica un borrado lógico: conserva todo el historial de
          riegos, incidencias y trazabilidad en SQLite, pero la oculta del
          inventario operativo activo.
        </p>
        <div className="mt-5 flex justify-end gap-2.5">
          <button
            type="button"
            autoFocus
            onClick={() => setParcelaArchivar(null)}
            className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-4 py-2 text-xs font-semibold text-[var(--text-primary)]"
          >
            Conservar
          </button>
          <button
            type="button"
            disabled={archivando}
            onClick={() => void confirmarArchivado()}
            className="rounded-xl bg-[var(--status-critical)] px-4 py-2 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {archivando ? "Archivando…" : "Sí, archivar"}
          </button>
        </div>
      </dialog>
    </div>
  );
}
