import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { EChartsCoreOption } from "echarts";
import { useApp } from "../../context/AppContext";

export interface TemaECharts {
  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  borderSubtle: string;
  surface: string;
  accent: string;
  optimal: string;
  warning: string;
  critical: string;
  info: string;
}

export function obtenerPaletaECharts(tema: "light" | "dark"): TemaECharts {
  if (tema === "dark") {
    return {
      textPrimary: "#F1F5F2",
      textSecondary: "#98A69E",
      textMuted: "#5F6E65",
      borderSubtle: "rgba(255,255,255,0.09)",
      surface: "#17211C",
      accent: "#34D399",
      optimal: "#34D399",
      warning: "#FBBF24",
      critical: "#F87171",
      info: "#38BDF8",
    };
  }
  return {
    textPrimary: "#0F1713",
    textSecondary: "#4B5B52",
    textMuted: "#7C8D82",
    borderSubtle: "rgba(15,23,19,0.09)",
    surface: "#FFFFFF",
    accent: "#059669",
    optimal: "#059669",
    warning: "#D97706",
    critical: "#DC2626",
    info: "#0284C7",
  };
}

export function EChartBox({
  option,
  height = 280,
  ariaLabel,
  className = "",
}: {
  option: EChartsCoreOption;
  height?: number;
  ariaLabel: string;
  className?: string;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const { temaEfectivo } = useApp();

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = echarts.init(el, undefined, { renderer: "canvas" });
    chartRef.current = chart;

    const observer = new ResizeObserver(() => {
      chart.resize();
    });
    observer.observe(el);

    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.setOption(option, { notMerge: true, lazyUpdate: true });
  }, [option, temaEfectivo]);

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label={ariaLabel}
      style={{ height: `${height}px`, width: "100%" }}
      className={className}
    />
  );
}
