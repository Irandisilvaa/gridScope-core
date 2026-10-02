import React, { useState, useMemo } from "react";
import type { EvolucaoTemporal, Substation } from "../lib/api";
import { THEME_COLORS } from "../lib/theme";

// =====================================================================
// 1. TEMPORAL EVOLUTION CHART (Série Histórica & Trajetória)
// =====================================================================

type TemporalMetric = "potencia_kw" | "clientes" | "unidades_mmgd";
type TemporalRange = "recent" | "12m" | "24m" | "all";

interface TemporalChartProps {
  data: EvolucaoTemporal[];
}

export const TemporalChart: React.FC<TemporalChartProps> = ({ data }) => {
  const [metric, setMetric] = useState<TemporalMetric>("potencia_kw");
  const [range, setRange] = useState<TemporalRange>("recent");
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  if (!data || data.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-2xl border border-grid-graphite-light bg-grid-surface text-xs text-grid-gray">
        Sem dados históricos suficientes para este ativo.
      </div>
    );
  }

  // Find the index of the first month with non-zero GD or customer data
  const firstActiveIndex = useMemo(() => {
    const idx = data.findIndex((d) => d.potencia_kw > 0 || d.unidades_mmgd > 0);
    // If not found or if it's less than 36 months from end, take at most 48 months
    if (idx === -1) return Math.max(0, data.length - 36);
    return Math.max(0, idx - 2); // Include 2 months prior for baseline context
  }, [data]);

  // Filter data according to selected range
  const filteredData = useMemo(() => {
    if (range === "12m") return data.slice(-12);
    if (range === "24m") return data.slice(-24);
    if (range === "recent") {
      const sliced = data.slice(firstActiveIndex);
      return sliced.length >= 3 ? sliced : data.slice(-24);
    }
    return data;
  }, [data, range, firstActiveIndex]);

  const width = 640;
  const height = 240;
  const padding = { top: 30, right: 30, bottom: 40, left: 60 };

  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  // Extract metric values
  const values = filteredData.map((d) => {
    if (metric === "potencia_kw") return d.potencia_kw;
    if (metric === "clientes") return d.clientes;
    return d.unidades_mmgd;
  });

  const maxVal = Math.max(...values, 1) * 1.15;
  const minVal = 0;

  const points = filteredData.map((d, index) => {
    const val = metric === "potencia_kw" ? d.potencia_kw : metric === "clientes" ? d.clientes : d.unidades_mmgd;
    const x = padding.left + (index / Math.max(filteredData.length - 1, 1)) * chartW;
    const y = padding.top + chartH - ((val - minVal) / (maxVal - minVal)) * chartH;
    return { x, y, data: d, val };
  });

  // SVG Line path
  const linePath = points.reduce((acc, curr, idx) => {
    return `${acc} ${idx === 0 ? "M" : "L"} ${curr.x.toFixed(1)} ${curr.y.toFixed(1)}`;
  }, "");

  const areaPath = points.length > 0
    ? `${linePath} L ${points[points.length - 1].x.toFixed(1)} ${(padding.top + chartH).toFixed(1)} L ${points[0].x.toFixed(1)} ${(padding.top + chartH).toFixed(1)} Z`
    : "";

  const hoveredPoint = hoverIndex !== null && points[hoverIndex] ? points[hoverIndex] : null;

  // Selected tick marks for X axis (max 6 clean, non-overlapping labels)
  const xTicks = useMemo(() => {
    const count = Math.min(filteredData.length, 6);
    if (count <= 1) return [0];
    const step = (filteredData.length - 1) / (count - 1);
    const indices: number[] = [];
    for (let i = 0; i < count; i++) {
      indices.push(Math.round(i * step));
    }
    return Array.from(new Set(indices));
  }, [filteredData]);

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const svgX = ((e.clientX - rect.left) / rect.width) * width;
    if (svgX < padding.left || svgX > width - padding.right) {
      setHoverIndex(null);
      return;
    }
    const relativeX = (svgX - padding.left) / chartW;
    const nearestIdx = Math.round(relativeX * (filteredData.length - 1));
    const clamped = Math.max(0, Math.min(nearestIdx, filteredData.length - 1));
    setHoverIndex(clamped);
  };

  const metricLabel = {
    potencia_kw: "Potência GD Instalada",
    clientes: "Total de Clientes Acumulados",
    unidades_mmgd: "Unidades MMGD Conectadas",
  }[metric];

  const metricUnit = {
    potencia_kw: "kW",
    clientes: "UCs",
    unidades_mmgd: "unidades",
  }[metric];

  return (
    <div className="relative rounded-2xl border border-grid-graphite-light bg-grid-surface p-4 double-bezel space-y-3">
      {/* Controls Bar: Metric Selector & Range Switcher */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-grid-border-subtle pb-3">
        {/* Metric Radio Buttons */}
        <div className="flex items-center gap-1.5 rounded-xl border border-grid-graphite-light bg-grid-surface-elevated p-1 font-mono text-[0.68rem]">
          <button
            type="button"
            onClick={() => setMetric("potencia_kw")}
            className={`rounded-lg px-2.5 py-1 transition-all ${
              metric === "potencia_kw"
                ? "bg-grid-yellow font-bold text-black energy-glow"
                : "text-grid-gray hover:text-white"
            }`}
          >
            Potência (kW)
          </button>
          <button
            type="button"
            onClick={() => setMetric("clientes")}
            className={`rounded-lg px-2.5 py-1 transition-all ${
              metric === "clientes"
                ? "bg-grid-yellow font-bold text-black energy-glow"
                : "text-grid-gray hover:text-white"
            }`}
          >
            Clientes
          </button>
          <button
            type="button"
            onClick={() => setMetric("unidades_mmgd")}
            className={`rounded-lg px-2.5 py-1 transition-all ${
              metric === "unidades_mmgd"
                ? "bg-grid-yellow font-bold text-black energy-glow"
                : "text-grid-gray hover:text-white"
            }`}
          >
            Unidades GD
          </button>
        </div>

        {/* Range Buttons */}
        <div className="flex items-center gap-1 rounded-xl border border-grid-graphite-light bg-grid-surface-elevated p-1 font-mono text-[0.68rem]">
          <button
            type="button"
            onClick={() => setRange("recent")}
            className={`rounded-lg px-2 py-1 transition-all ${
              range === "recent"
                ? "border border-grid-yellow/40 bg-grid-yellow/15 font-bold text-grid-yellow"
                : "text-grid-gray hover:text-white"
            }`}
            title="Inicia a partir do surgimento da GD, eliminando anos zerados antigos"
          >
            Era GD (Foco)
          </button>
          {data.length > 12 && (
            <button
              type="button"
              onClick={() => setRange("12m")}
              className={`rounded-lg px-2 py-1 transition-all ${
                range === "12m"
                  ? "border border-grid-yellow/40 bg-grid-yellow/15 font-bold text-grid-yellow"
                : "text-grid-gray hover:text-white"
              }`}
            >
              12M
            </button>
          )}
          {data.length > 24 && (
            <button
              type="button"
              onClick={() => setRange("24m")}
              className={`rounded-lg px-2 py-1 transition-all ${
                range === "24m"
                  ? "border border-grid-yellow/40 bg-grid-yellow/15 font-bold text-grid-yellow"
                : "text-grid-gray hover:text-white"
              }`}
            >
              24M
            </button>
          )}
          <button
            type="button"
            onClick={() => setRange("all")}
            className={`rounded-lg px-2 py-1 transition-all ${
              range === "all"
                ? "border border-grid-yellow/40 bg-grid-yellow/15 font-bold text-grid-yellow"
                : "text-grid-gray hover:text-white"
            }`}
            title="Histórico total registrado na base"
          >
            Total
          </button>
        </div>
      </div>

      {/* Title Subheader with Metric and Range Info */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-grid-yellow energy-glow" />
          <strong className="font-display font-semibold text-white">
            {metricLabel}
          </strong>
        </div>
        <span className="font-mono text-[0.68rem] text-grid-gray">
          {filteredData.length} meses exibidos ({filteredData[0]?.mes} até {filteredData[filteredData.length - 1]?.mes})
        </span>
      </div>

      {/* SVG Canvas Container */}
      <div className="relative cursor-crosshair">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto select-none overflow-visible"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoverIndex(null)}
        >
          <defs>
            <linearGradient id="temporalYellowGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={THEME_COLORS.brand.yellow} stopOpacity="0.28" />
              <stop offset="100%" stopColor={THEME_COLORS.brand.yellow} stopOpacity="0.0" />
            </linearGradient>
            <filter id="temporalLineGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="3.5" floodColor={THEME_COLORS.brand.yellow} floodOpacity="0.45" />
            </filter>
          </defs>

          {/* Horizontal Grid Lines & Y Axis */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct) => {
            const y = padding.top + chartH * (1 - pct);
            const val = minVal + pct * (maxVal - minVal);
            return (
              <g key={pct}>
                <line
                  x1={padding.left}
                  y1={y}
                  x2={width - padding.right}
                  y2={y}
                  stroke="rgba(255, 255, 255, 0.06)"
                  strokeDasharray="2 3"
                />
                <text
                  x={padding.left - 8}
                  y={y + 3}
                  textAnchor="end"
                  fill={THEME_COLORS.text.muted}
                  className="font-mono text-[9px]"
                >
                  {val >= 1000 ? `${(val / 1000).toFixed(1)}k` : val.toFixed(0)}
                </text>
              </g>
            );
          })}

          {/* Area Fill */}
          <path d={areaPath} fill="url(#temporalYellowGradient)" />

          {/* Continuous Glowing Golden Line */}
          <path
            d={linePath}
            fill="none"
            stroke={THEME_COLORS.brand.yellow}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            filter="url(#temporalLineGlow)"
          />

          {/* Non-overlapping X Axis Reference Dates */}
          {xTicks.map((idx) => {
            const p = points[idx];
            if (!p) return null;
            return (
              <text
                key={p.data.mes}
                x={p.x}
                y={padding.top + chartH + 18}
                textAnchor="middle"
                fill={THEME_COLORS.text.gray}
                className="font-mono text-[9px]"
              >
                {p.data.mes}
              </text>
            );
          })}

          {/* Active Hover Crosshair Line & Glowing Pin */}
          {hoveredPoint && (
            <g pointerEvents="none">
              <line
                x1={hoveredPoint.x}
                y1={padding.top}
                x2={hoveredPoint.x}
                y2={padding.top + chartH}
                stroke={THEME_COLORS.brand.yellow}
                strokeWidth="1.5"
                strokeDasharray="3 3"
              />
              <circle
                cx={hoveredPoint.x}
                cy={hoveredPoint.y}
                r="7"
                fill="none"
                stroke={THEME_COLORS.brand.yellow}
                strokeWidth="2"
                opacity="0.85"
              />
              <circle
                cx={hoveredPoint.x}
                cy={hoveredPoint.y}
                r="3.5"
                fill={THEME_COLORS.text.white}
              />
            </g>
          )}
        </svg>

        {/* Embedded Telemetry Tooltip (placed safely without clipping) */}
        {hoveredPoint && (
          <div
            className="pointer-events-none absolute top-2 rounded-xl border border-grid-yellow/40 bg-grid-surface/95 p-2.5 font-mono text-xs shadow-2xl backdrop-blur-md min-w-[190px] z-20"
            style={{
              left: `${Math.max(12, Math.min(88, (hoveredPoint.x / width) * 100))}%`,
              transform: "translateX(-50%)",
            }}
          >
            <div className="flex items-center justify-between border-b border-grid-graphite-light pb-1 mb-1">
              <span className="text-[0.66rem] text-grid-gray">Mês:</span>
              <strong className="text-white font-bold">{hoveredPoint.data.mes}</strong>
            </div>
            <div className="space-y-0.5 text-[0.7rem]">
              <div className="flex justify-between text-grid-yellow">
                <span>Potência GD:</span>
                <strong className="font-bold">
                  {hoveredPoint.data.potencia_kw.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} kW
                </strong>
              </div>
              <div className="flex justify-between text-grid-gray-subtle">
                <span>Unidades GD:</span>
                <strong>{hoveredPoint.data.unidades_mmgd}</strong>
              </div>
              <div className="flex justify-between text-grid-gray">
                <span>Clientes Acum.:</span>
                <strong>{hoveredPoint.data.clientes.toLocaleString("pt-BR")}</strong>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-[0.66rem] font-mono text-grid-gray-dim">
        <span>Passe o cursor sobre a linha para inspecionar meses</span>
        <span className="text-grid-yellow">Escala: {metricUnit}</span>
      </div>
    </div>
  );
};

// =====================================================================
// 2. DAILY DISPATCH & DUCK CURVE SIMULATION (Simulação Solar 24h)
// =====================================================================

interface DailyDispatchChartProps {
  gdPowerKw: number;
  annualConsumptionMwh?: number;
  irradianceKwhM2?: number; // Solar irradiance (e.g. 5.4 kWh/m²)
  tempMaxC?: number; // Temperature (e.g. 32°C)
  thermalLossPct?: number; // Thermal loss factor (e.g. 6%)
  calculatedGenerationMwh?: number;
  substationName?: string;
}

export const DailyDispatchChart: React.FC<DailyDispatchChartProps> = ({
  gdPowerKw,
  annualConsumptionMwh,
  irradianceKwhM2 = 5.4,
  tempMaxC = 30.0,
  thermalLossPct = 5.8,
  calculatedGenerationMwh,
}) => {
  const [hoverHour, setHoverHour] = useState<number | null>(null);
  const [showDemand, setShowDemand] = useState(true);
  const [showSolar, setShowSolar] = useState(true);
  const [showNet, setShowNet] = useState(true);
  const [scenarioGdKw, setScenarioGdKw] = useState<number | null>(null);

  // Use scenario override if substation has 0 kW
  const activeGdKw = scenarioGdKw ?? gdPowerKw;

  // Dynamic simulation scaling with irradiance and thermal loss
  const solarEfficiencyFactor = useMemo(() => {
    const irradRatio = Math.max(0.4, Math.min(2.0, irradianceKwhM2 / 5.4));
    const lossMultiplier = Math.max(0.5, 1 - thermalLossPct / 100);
    return irradRatio * lossMultiplier;
  }, [irradianceKwhM2, thermalLossPct]);

  // Generate 24 hours of standard power grid load and solar generation
  const hours = Array.from({ length: 24 }, (_, i) => i);
  const effectiveGdPower = Math.max(0, activeGdKw * solarEfficiencyFactor);

  // Average hourly base load derived realistically from annual consumption
  const avgHourlyLoad = annualConsumptionMwh && annualConsumptionMwh > 0
    ? (annualConsumptionMwh * 1000) / 8760
    : Math.max(activeGdKw * 1.3, 40);

  // Peak load is sized so that both base load and solar generation are clearly proportioned and visible
  const baseLoadPeak = Math.max(
    avgHourlyLoad * 1.55,
    activeGdKw > 0 ? activeGdKw * 1.25 : 40,
    25
  );

  const data = hours.map((hour) => {
    // Base load curve: high in morning and evening, moderate in afternoon
    const morningPeak = Math.exp(-Math.pow(hour - 9, 2) / 8);
    const eveningPeak = Math.exp(-Math.pow(hour - 19, 2) / 9);
    const nightLow = hour < 6 ? 0.42 : 0.60;
    const baseDemand = baseLoadPeak * (nightLow + 0.32 * morningPeak + 0.46 * eveningPeak);

    // Solar Bell Curve: active between 6:00 and 18:00, peak at 12:30
    let solarGen = 0;
    if (hour >= 6 && hour <= 18) {
      const solarFactor = Math.sin(((hour - 6) / 12) * Math.PI);
      solarGen = effectiveGdPower * Math.max(0, Math.pow(solarFactor, 1.7));
    }

    const netDemand = baseDemand - solarGen;
    const isReverseFlow = netDemand < 0;

    return {
      hour,
      baseDemand,
      solarGen,
      netDemand: Math.max(0, netDemand),
      rawNetDemand: netDemand,
      isReverseFlow,
    };
  });

  const width = 640;
  const height = 230;
  const padding = { top: 30, right: 30, bottom: 40, left: 60 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  // Max value consideration across visible traces
  const maxCandidates = [10];
  if (showDemand) maxCandidates.push(...data.map((d) => d.baseDemand));
  if (showSolar) maxCandidates.push(...data.map((d) => d.solarGen));
  if (showNet) maxCandidates.push(...data.map((d) => d.netDemand));
  const maxVal = Math.max(...maxCandidates) * 1.15;

  const pointsSolar = data.map((d) => ({
    x: padding.left + (d.hour / 23) * chartW,
    y: padding.top + chartH - (d.solarGen / maxVal) * chartH,
    val: d.solarGen,
  }));

  const pointsDemand = data.map((d) => ({
    x: padding.left + (d.hour / 23) * chartW,
    y: padding.top + chartH - (d.baseDemand / maxVal) * chartH,
    val: d.baseDemand,
  }));

  const pointsNet = data.map((d) => ({
    x: padding.left + (d.hour / 23) * chartW,
    y: padding.top + chartH - (d.netDemand / maxVal) * chartH,
    val: d.netDemand,
  }));

  const pathSolar = pointsSolar.reduce(
    (acc, p, i) => `${acc} ${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`,
    ""
  );
  const pathDemand = pointsDemand.reduce(
    (acc, p, i) => `${acc} ${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`,
    ""
  );
  const pathNet = pointsNet.reduce(
    (acc, p, i) => `${acc} ${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`,
    ""
  );

  const solarArea = `${pathSolar} L ${pointsSolar[pointsSolar.length - 1].x.toFixed(1)} ${(padding.top + chartH).toFixed(1)} L ${pointsSolar[0].x.toFixed(1)} ${(padding.top + chartH).toFixed(1)} Z`;
  const demandArea = `${pathDemand} L ${pointsDemand[pointsDemand.length - 1].x.toFixed(1)} ${(padding.top + chartH).toFixed(1)} L ${pointsDemand[0].x.toFixed(1)} ${(padding.top + chartH).toFixed(1)} Z`;

  const hoveredData = hoverHour !== null ? data[hoverHour] : null;
  const hoverX = hoverHour !== null ? padding.left + (hoverHour / 23) * chartW : null;

  // Check if reverse flow occurred at noon
  const hasReverseFlow = data.some((d) => d.isReverseFlow);

  return (
    <div className="relative rounded-2xl border border-grid-graphite-light bg-grid-surface p-4 double-bezel space-y-3">
      {/* Header with Title and Interactive Toggles */}
      <div className="flex flex-wrap items-center justify-between pb-3 border-b border-grid-border-subtle gap-2">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-grid-yellow energy-glow" />
          <strong className="font-display text-xs font-semibold text-white uppercase tracking-wider">
            Curva do Pato (Despacho 24h)
          </strong>
          {hasReverseFlow && (
            <span className="rounded-md border border-status-warning/40 bg-status-warning/15 px-2 py-0.5 font-mono text-[0.62rem] text-status-warning">
              Fluxo Reverso às 12h
            </span>
          )}
          {gdPowerKw === 0 && (
            <button
              type="button"
              onClick={() => setScenarioGdKw(scenarioGdKw ? null : 500)}
              className="rounded-md border border-grid-yellow/40 bg-grid-yellow/10 px-2 py-0.5 font-mono text-[0.62rem] text-grid-yellow hover:bg-grid-yellow/20 transition-colors"
            >
              {scenarioGdKw ? "Desativar Simulação GD" : "+ Simular 500 kW de GD"}
            </button>
          )}
        </div>

        {/* Interactive Legend Toggles */}
        <div className="flex items-center gap-1.5 font-mono text-[0.68rem]">
          <button
            type="button"
            onClick={() => setShowDemand(!showDemand)}
            className={`flex items-center gap-1.5 px-2 py-1 rounded-lg border transition-all ${
              showDemand
                ? "border-status-info/50 bg-status-info/15 text-white"
                : "border-grid-graphite-light text-grid-gray-dim line-through"
            }`}
            title="Alternar visibilidade da Demanda Base"
          >
            <span className="h-2 w-2 rounded-full bg-status-info" />
            <span>Demanda Base</span>
          </button>

          <button
            type="button"
            onClick={() => setShowSolar(!showSolar)}
            className={`flex items-center gap-1.5 px-2 py-1 rounded-lg border transition-all ${
              showSolar
                ? "border-grid-yellow/50 bg-grid-yellow/15 text-white"
                : "border-grid-graphite-light text-grid-gray-dim line-through"
            }`}
            title="Alternar visibilidade da Geração Solar"
          >
            <span className="h-2 w-2 rounded-full bg-grid-yellow" />
            <span>Geração Solar</span>
          </button>

          <button
            type="button"
            onClick={() => setShowNet(!showNet)}
            className={`flex items-center gap-1.5 px-2 py-1 rounded-lg border transition-all ${
              showNet
                ? "border-status-success/50 bg-status-success/15 text-white"
                : "border-grid-graphite-light text-grid-gray-dim line-through"
            }`}
            title="Alternar visibilidade da Carga Líquida"
          >
            <span className="h-2 w-2 rounded-full bg-status-success" />
            <span>Carga Líquida</span>
          </button>
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="relative">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto select-none overflow-visible">
          <defs>
            <linearGradient id="solarGlowFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={THEME_COLORS.brand.yellow} stopOpacity="0.32" />
              <stop offset="100%" stopColor={THEME_COLORS.brand.yellow} stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="demandBlueArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={THEME_COLORS.status.info} stopOpacity="0.10" />
              <stop offset="100%" stopColor={THEME_COLORS.status.info} stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines and Y-axis */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct) => {
            const y = padding.top + chartH * (1 - pct);
            const val = pct * maxVal;
            return (
              <g key={pct}>
                <line
                  x1={padding.left}
                  y1={y}
                  x2={width - padding.right}
                  y2={y}
                  stroke="rgba(255, 255, 255, 0.06)"
                  strokeDasharray="2 3"
                />
                <text
                  x={padding.left - 8}
                  y={y + 3}
                  textAnchor="end"
                  fill={THEME_COLORS.text.muted}
                  className="font-mono text-[9px]"
                >
                  {val >= 1000 ? `${(val / 1000).toFixed(1)}k` : val.toFixed(0)}
                </text>
              </g>
            );
          })}

          {/* Demand Base Soft Area */}
          {showDemand && <path d={demandArea} fill="url(#demandBlueArea)" />}

          {/* Solar Generation Area */}
          {showSolar && effectiveGdPower > 0 && <path d={solarArea} fill="url(#solarGlowFill)" />}

          {/* Base Demand Line (Azul) - Solid line */}
          {showDemand && (
            <path
              d={pathDemand}
              fill="none"
              stroke={THEME_COLORS.status.info}
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Net Demand Line (Verde) - Dashed so it's always distinct from Blue! */}
          {showNet && (
            <path
              d={pathNet}
              fill="none"
              stroke={THEME_COLORS.status.success}
              strokeWidth="2.2"
              strokeDasharray="6 3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Solar Generation Line (Amarelo) - Solid glowing */}
          {showSolar && (
            <path
              d={pathSolar}
              fill="none"
              stroke={THEME_COLORS.brand.yellow}
              strokeWidth="2.6"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="filter drop-shadow-[0_0_8px_rgba(255,212,0,0.6)]"
            />
          )}

          {/* X Axis Time Labels */}
          {[0, 4, 8, 12, 16, 20, 23].map((h) => {
            const x = padding.left + (h / 23) * chartW;
            return (
              <text
                key={h}
                x={x}
                y={padding.top + chartH + 18}
                textAnchor="middle"
                fill={THEME_COLORS.text.gray}
                className="font-mono text-[9px]"
              >
                {`${String(h).padStart(2, "0")}:00`}
              </text>
            );
          })}

          {/* Interactive Scrub Hover Columns */}
          {hours.map((h) => {
            const x = padding.left + (h / 23) * chartW;
            const wCol = chartW / 24;
            return (
              <rect
                key={h}
                x={x - wCol / 2}
                y={padding.top}
                width={wCol}
                height={chartH}
                fill="transparent"
                className="cursor-pointer"
                onMouseEnter={() => setHoverHour(h)}
                onMouseLeave={() => setHoverHour(null)}
              />
            );
          })}

          {/* Hover indicator line */}
          {hoverX !== null && (
            <line
              x1={hoverX}
              y1={padding.top}
              x2={hoverX}
              y2={padding.top + chartH}
              stroke={THEME_COLORS.brand.yellow}
              strokeWidth="1.5"
              strokeDasharray="3 3"
            />
          )}
        </svg>

        {/* Floating Tooltip positioned inside container */}
        {hoveredData && hoverX !== null && (
          <div
            className="pointer-events-none absolute top-2 rounded-xl border border-grid-yellow/40 bg-grid-surface/95 p-2.5 font-mono text-xs shadow-2xl backdrop-blur-md min-w-[190px] z-20"
            style={{
              left: `${Math.max(12, Math.min(88, (hoverX / width) * 100))}%`,
              transform: "translateX(-50%)",
            }}
          >
            <div className="flex items-center justify-between border-b border-grid-graphite-light pb-1 mb-1">
              <span className="text-[0.66rem] text-grid-gray">Horário:</span>
              <strong className="text-white font-bold">{String(hoveredData.hour).padStart(2, "0")}:00</strong>
            </div>
            <div className="space-y-0.5 text-[0.7rem]">
              <div className="flex justify-between text-grid-yellow">
                <span>Geração Solar:</span>
                <strong>{hoveredData.solarGen.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} kW</strong>
              </div>
              <div className="flex justify-between text-status-info">
                <span>Demanda Base:</span>
                <strong>{hoveredData.baseDemand.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} kW</strong>
              </div>
              <div className="flex justify-between text-status-success">
                <span>Carga Líquida:</span>
                <strong>{hoveredData.netDemand.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} kW</strong>
              </div>
              {hoveredData.isReverseFlow && (
                <div className="mt-1 pt-1 border-t border-grid-border-strong text-[0.65rem] text-status-warning">
                  Excedente para rede: {Math.abs(hoveredData.rawNetDemand).toFixed(1)} kW
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between text-[0.66rem] font-mono text-grid-gray-muted">
        <span>Passe o cursor para inspecionar horários · Clique na legenda acima para isolar curvas</span>
        <span className="text-grid-gray">
          Sensibilidade: {irradianceKwhM2.toFixed(1)} kWh/m² · Perda {thermalLossPct.toFixed(1)}%
        </span>
      </div>
    </div>
  );
};

// =====================================================================
// 3. CLASS BREAKDOWN BAR CHART (Consumo & GD por Classe)
// =====================================================================

interface ClassBarItem {
  name: string;
  value: number;
  secondaryText?: string;
  percentage?: number;
}

interface ClassBarChartProps {
  title: string;
  subtitle?: string;
  items: ClassBarItem[];
  unit: string;
  accentColor?: string;
}

export const ClassBarChart: React.FC<ClassBarChartProps> = ({
  title,
  subtitle,
  items,
  unit,
  accentColor = THEME_COLORS.brand.yellow,
}) => {
  const maxVal = Math.max(...items.map((i) => i.value), 1);

  if (items.length === 0) {
    return (
      <div className="rounded-2xl border border-grid-graphite-light bg-grid-surface p-5 text-center text-xs text-grid-gray">
        Sem dados de distribuição para este ativo.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-grid-surface-border bg-grid-surface p-4 md:p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-grid-border-subtle pb-3">
        <div>
          <span className="font-mono text-[0.66rem] font-bold uppercase tracking-[0.14em] text-grid-yellow">
            {title}
          </span>
          {subtitle && (
            <h4 className="font-display text-sm font-semibold text-white mt-0.5">
              {subtitle}
            </h4>
          )}
        </div>
        <span className="font-mono text-xs text-grid-gray">
          {items.length} classes
        </span>
      </div>

      <div className="space-y-3.5">
        {items.map((item) => {
          const pctOfMax = Math.min(100, Math.max(3, (item.value / maxVal) * 100));
          return (
            <div key={item.name} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-white">{item.name}</span>
                <div className="flex items-center gap-3 font-mono">
                  {item.secondaryText && (
                    <span className="text-grid-gray text-[0.7rem]">{item.secondaryText}</span>
                  )}
                  <strong className="text-white font-bold">
                    {item.value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} {unit}
                  </strong>
                  {item.percentage !== undefined && (
                    <span className="text-grid-yellow text-[0.72rem] font-bold min-w-[38px] text-right">
                      {item.percentage.toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>

              {/* Progress Track */}
              <div className="h-2 w-full overflow-hidden rounded-full bg-grid-border-subtle">
                <div
                  className="h-full rounded-full transition-all duration-500 ease-out"
                  style={{
                    width: `${pctOfMax}%`,
                    backgroundColor: accentColor,
                    boxShadow: `0 0 10px ${accentColor}40`,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// =====================================================================
// 4. OVERVIEW RANKING CHART (Top Subestações em GD no Panorama)
// =====================================================================

interface OverviewRankingChartProps {
  substations: Substation[];
  topN?: number;
  onSelectSubstation?: (id: string) => void;
}

export const OverviewRankingChart: React.FC<OverviewRankingChartProps> = ({
  substations,
  topN = 7,
  onSelectSubstation,
}) => {
  const sorted = useMemo(() => {
    return [...substations]
      .sort((a, b) => b.geracao_distribuida.potencia_total_kw - a.geracao_distribuida.potencia_total_kw)
      .slice(0, topN);
  }, [substations, topN]);

  const maxPower = Math.max(...sorted.map((s) => s.geracao_distribuida.potencia_total_kw), 1);

  return (
    <div className="rounded-2xl border border-grid-surface-border bg-grid-surface p-5 double-bezel space-y-4">
      <div className="flex items-center justify-between border-b border-grid-border-subtle pb-3">
        <div>
          <span className="font-mono text-[0.66rem] font-bold uppercase tracking-[0.14em] text-grid-yellow">
            RANKING OPERACIONAL
          </span>
          <h3 className="font-display text-sm font-semibold text-white mt-0.5">
            Top {topN} Subestações por Capacidade Solar GD
          </h3>
        </div>
        <span className="font-mono text-xs text-grid-gray">
          Capacidade Instalada (kW)
        </span>
      </div>

      <div className="space-y-3">
        {sorted.map((sub, index) => {
          const power = sub.geracao_distribuida.potencia_total_kw;
          const pct = Math.min(100, Math.max(5, (power / maxPower) * 100));
          const name = sub.subestacao.split(" (ID:")[0];
          const critStr = sub.metricas_rede.nivel_criticidade_gd.toUpperCase();
          const isCritical = critStr.includes("CRÍT") || critStr.includes("CRIT");
          const isAttention = critStr.includes("ATEN") || critStr.includes("MÉD") || critStr.includes("MED");

          return (
            <div
              key={sub.id_tecnico}
              onClick={() => onSelectSubstation?.(sub.id_tecnico)}
              className="group cursor-pointer rounded-xl border border-transparent p-2 transition-all hover:border-grid-border-card hover:bg-grid-surface-elevated"
            >
              <div className="flex items-center justify-between text-xs mb-1">
                <div className="flex items-center gap-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-md bg-grid-border-subtle font-mono text-[0.65rem] font-bold text-grid-gray group-hover:bg-grid-yellow group-hover:text-black transition-colors">
                    {index + 1}
                  </span>
                  <span className="font-medium text-white group-hover:text-grid-yellow transition-colors">
                    {name}
                  </span>
                  <span className="font-mono text-[0.65rem] text-grid-gray-dim">
                    ({sub.id_tecnico})
                  </span>
                </div>

                <div className="flex items-center gap-2 font-mono">
                  {isCritical && (
                    <span className="h-1.5 w-1.5 rounded-full bg-status-danger shadow-[0_0_6px_var(--color-status-danger)]" />
                  )}
                  {isAttention && (
                    <span className="h-1.5 w-1.5 rounded-full bg-status-warning shadow-[0_0_6px_var(--color-status-warning)]" />
                  )}
                  <strong className="text-white font-bold text-[0.78rem]">
                    {power.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}{" "}
                    <span className="text-grid-gray font-normal text-[0.68rem]">kW</span>
                  </strong>
                </div>
              </div>

              {/* Bar track */}
              <div className="h-2 w-full overflow-hidden rounded-full bg-grid-border-subtle">
                <div
                  className="h-full rounded-full bg-grid-yellow transition-all duration-500 ease-out group-hover:energy-glow"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// =====================================================================
// 5. CRITICALITY & MATRIX DISTRIBUTION (Visão Geral de Criticidade)
// =====================================================================

interface CriticalityMatrixProps {
  substations: Substation[];
}

export const CriticalityMatrix: React.FC<CriticalityMatrixProps> = ({ substations }) => {
  const counts = useMemo(() => {
    let normal = 0;
    let attention = 0;
    let critical = 0;

    substations.forEach((s) => {
      const crit = s.metricas_rede.nivel_criticidade_gd.toUpperCase();
      if (crit.includes("CRÍT")) critical++;
      else if (crit.includes("ATEN") || crit.includes("MÉD")) attention++;
      else normal++;
    });

    const total = substations.length || 1;
    return {
      normal,
      attention,
      critical,
      normalPct: (normal / total) * 100,
      attentionPct: (attention / total) * 100,
      criticalPct: (critical / total) * 100,
      total: substations.length,
    };
  }, [substations]);

  return (
    <div className="rounded-2xl border border-grid-surface-border bg-grid-surface p-5 double-bezel space-y-4">
      <div className="flex items-center justify-between border-b border-grid-border-subtle pb-3">
        <div>
          <span className="font-mono text-[0.66rem] font-bold uppercase tracking-[0.14em] text-grid-yellow">
            ESTABILIDADE SISTÊMICA
          </span>
          <h3 className="font-display text-sm font-semibold text-white mt-0.5">
            Distribuição de Criticidade da Rede
          </h3>
        </div>
        <span className="font-mono text-xs text-grid-gray">
          {counts.total} subestações
        </span>
      </div>

      {/* Segmented Horizontal Bar */}
      <div className="h-3.5 w-full overflow-hidden rounded-full bg-grid-graphite flex p-0.5 gap-0.5">
        <div
          className="h-full rounded-l-full bg-status-success transition-all duration-500 shadow-[0_0_8px_var(--color-status-success)]"
          style={{ width: `${counts.normalPct}%` }}
          title={`Normal: ${counts.normal} (${counts.normalPct.toFixed(1)}%)`}
        />
        <div
          className="h-full bg-status-warning transition-all duration-500 shadow-[0_0_8px_var(--color-status-warning)]"
          style={{ width: `${counts.attentionPct}%` }}
          title={`Atenção: ${counts.attention} (${counts.attentionPct.toFixed(1)}%)`}
        />
        <div
          className="h-full rounded-r-full bg-status-danger transition-all duration-500 shadow-[0_0_8px_var(--color-status-danger)]"
          style={{ width: `${counts.criticalPct}%` }}
          title={`Crítico: ${counts.critical} (${counts.criticalPct.toFixed(1)}%)`}
        />
      </div>

      {/* Metric Breakdown Cards */}
      <div className="grid grid-cols-3 gap-2.5 pt-1">
        <div className="rounded-xl border border-status-success/30 bg-status-success/10 p-2.5 text-center">
          <span className="block font-mono text-[0.65rem] text-status-success uppercase font-bold">
            Normal
          </span>
          <strong className="block font-mono text-base font-bold text-white mt-0.5">
            {counts.normal}
          </strong>
          <span className="block font-mono text-[0.65rem] text-grid-gray">
            {counts.normalPct.toFixed(0)}% da rede
          </span>
        </div>

        <div className="rounded-xl border border-status-warning/30 bg-status-warning/10 p-2.5 text-center">
          <span className="block font-mono text-[0.65rem] text-status-warning uppercase font-bold">
            Atenção
          </span>
          <strong className="block font-mono text-base font-bold text-white mt-0.5">
            {counts.attention}
          </strong>
          <span className="block font-mono text-[0.65rem] text-grid-gray">
            {counts.attentionPct.toFixed(0)}% da rede
          </span>
        </div>

        <div className="rounded-xl border border-status-danger/30 bg-status-danger/10 p-2.5 text-center">
          <span className="block font-mono text-[0.65rem] text-status-danger uppercase font-bold">
            Crítico
          </span>
          <strong className="block font-mono text-base font-bold text-white mt-0.5">
            {counts.critical}
          </strong>
          <span className="block font-mono text-[0.65rem] text-grid-gray">
            {counts.criticalPct.toFixed(0)}% da rede
          </span>
        </div>
      </div>
    </div>
  );
};
