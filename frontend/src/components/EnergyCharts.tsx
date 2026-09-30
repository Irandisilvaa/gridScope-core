import React, { useState } from "react";
import type { EvolucaoTemporal } from "../lib/api";

interface TemporalChartProps {
  data: EvolucaoTemporal[];
}

export const TemporalChart: React.FC<TemporalChartProps> = ({ data }) => {
  const [range, setRange] = useState<"all" | "24m" | "12m">("all");
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  if (!data || data.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-xl border border-[#222222] bg-[#0c0c0c] text-xs text-[#8A8A8A]">
        Sem dados históricos suficientes nesta carga.
      </div>
    );
  }

  // Filter data according to selected range
  const filteredData = React.useMemo(() => {
    if (range === "12m") return data.slice(-12);
    if (range === "24m") return data.slice(-24);
    return data;
  }, [data, range]);

  const width = 640;
  const height = 230;
  const padding = { top: 25, right: 30, bottom: 35, left: 55 };

  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  const powers = filteredData.map((d) => d.potencia_kw);
  const maxPower = Math.max(...powers, 100) * 1.15;
  const minPower = 0;

  const points = filteredData.map((d, index) => {
    const x = padding.left + (index / Math.max(filteredData.length - 1, 1)) * chartW;
    const y = padding.top + chartH - ((d.potencia_kw - minPower) / (maxPower - minPower)) * chartH;
    return { x, y, data: d };
  });

  // Build SVG path
  const linePath = points.reduce((acc, curr, idx) => {
    return `${acc} ${idx === 0 ? "M" : "L"} ${curr.x.toFixed(1)} ${curr.y.toFixed(1)}`;
  }, "");

  const areaPath = `${linePath} L ${points[points.length - 1].x.toFixed(1)} ${(padding.top + chartH).toFixed(1)} L ${points[0].x.toFixed(1)} ${(padding.top + chartH).toFixed(1)} Z`;

  const hoveredPoint = hoverIndex !== null && points[hoverIndex] ? points[hoverIndex] : null;

  // Selected tick marks for X axis (max 6 clean, non-overlapping labels)
  const xTicks = React.useMemo(() => {
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

  return (
    <div className="relative overflow-hidden rounded-2xl border border-[#222222] bg-[#0C0C0C] p-4 double-bezel space-y-3">
      {/* Header with Title and Range Switcher */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#1A1A1A] pb-3">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-[#FFD400] shadow-[0_0_8px_#FFD400]" />
          <span className="font-mono text-xs font-semibold text-white uppercase tracking-wider">
            Trajetória de Potência GD (kW)
          </span>
          <span className="font-mono text-[0.68rem] text-[#8A8A8A]">
            ({filteredData.length} meses)
          </span>
        </div>

        {/* Range Buttons */}
        <div className="flex items-center gap-1 rounded-lg border border-[#222222] bg-[#141414] p-1 font-mono text-[0.68rem]">
          {data.length > 12 && (
            <button
              type="button"
              onClick={() => {
                setRange("12m");
                setHoverIndex(null);
              }}
              className={`rounded px-2 py-0.5 transition-colors ${
                range === "12m"
                  ? "bg-[#FFD400] font-bold text-black"
                  : "text-[#8A8A8A] hover:text-white"
              }`}
            >
              12 Meses
            </button>
          )}
          {data.length > 24 && (
            <button
              type="button"
              onClick={() => {
                setRange("24m");
                setHoverIndex(null);
              }}
              className={`rounded px-2 py-0.5 transition-colors ${
                range === "24m"
                  ? "bg-[#FFD400] font-bold text-black"
                  : "text-[#8A8A8A] hover:text-white"
              }`}
            >
              24 Meses
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              setRange("all");
              setHoverIndex(null);
            }}
            className={`rounded px-2 py-0.5 transition-colors ${
              range === "all"
                ? "bg-[#FFD400] font-bold text-black"
                : "text-[#8A8A8A] hover:text-white"
            }`}
          >
            Série Completa
          </button>
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="relative cursor-crosshair">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto select-none overflow-visible"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoverIndex(null)}
        >
          <defs>
            <linearGradient id="yellowAreaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#FFD400" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#FFD400" stopOpacity="0.0" />
            </linearGradient>
            <filter id="yellowGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor="#FFD400" floodOpacity="0.5" />
            </filter>
          </defs>

          {/* Horizontal Grid Lines & Y Axis */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct) => {
            const y = padding.top + chartH * (1 - pct);
            const val = minPower + pct * (maxPower - minPower);
            return (
              <g key={pct}>
                <line
                  x1={padding.left}
                  y1={y}
                  x2={width - padding.right}
                  y2={y}
                  stroke="rgba(255, 255, 255, 0.05)"
                  strokeDasharray="2 3"
                />
                <text
                  x={padding.left - 8}
                  y={y + 3}
                  textAnchor="end"
                  className="font-mono text-[9px] fill-[#777777]"
                >
                  {val >= 1000 ? `${(val / 1000).toFixed(1)}k` : val.toFixed(0)}
                </text>
              </g>
            );
          })}

          {/* Base Area Fill */}
          <path d={areaPath} fill="url(#yellowAreaGradient)" />

          {/* Single High-Contrast Continuous Golden Line (NO STATIC DOTS) */}
          <path
            d={linePath}
            fill="none"
            stroke="#FFD400"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            filter="url(#yellowGlow)"
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
                className="font-mono text-[9px] fill-[#8A8A8A]"
              >
                {p.data.mes}
              </text>
            );
          })}

          {/* Active Hover Crosshair & Single Glowing Indicator Node */}
          {hoveredPoint && (
            <g pointerEvents="none">
              <line
                x1={hoveredPoint.x}
                y1={padding.top}
                x2={hoveredPoint.x}
                y2={padding.top + chartH}
                stroke="#FFD400"
                strokeWidth="1.5"
                strokeDasharray="3 3"
              />
              {/* Outer pulsing ring */}
              <circle
                cx={hoveredPoint.x}
                cy={hoveredPoint.y}
                r="7"
                fill="none"
                stroke="#FFD400"
                strokeWidth="2"
                opacity="0.8"
              />
              {/* Solid center dot */}
              <circle
                cx={hoveredPoint.x}
                cy={hoveredPoint.y}
                r="4"
                fill="#FFFFFF"
              />
            </g>
          )}
        </svg>

        {/* Floating Telemetry HUD Tooltip */}
        {hoveredPoint && (
          <div
            className="pointer-events-none absolute -top-1 -translate-y-full -translate-x-1/2 rounded-xl border border-[#FFD400]/40 bg-[#0A0A0A]/95 p-2.5 font-mono text-xs shadow-2xl backdrop-blur-md min-w-[170px]"
            style={{
              left: `${Math.max(15, Math.min(85, (hoveredPoint.x / width) * 100))}%`,
            }}
          >
            <div className="flex items-center justify-between border-b border-[#222222] pb-1 mb-1">
              <span className="text-[0.68rem] text-[#8A8A8A]">Mês de Referência:</span>
              <strong className="text-white">{hoveredPoint.data.mes}</strong>
            </div>
            <div className="space-y-0.5 text-[0.7rem]">
              <div className="flex justify-between text-[#FFD400]">
                <span>Potência GD:</span>
                <strong className="font-bold">
                  {hoveredPoint.data.potencia_kw.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} kW
                </strong>
              </div>
              <div className="flex justify-between text-[#CCCCCC]">
                <span>Unidades MMGD:</span>
                <strong>{hoveredPoint.data.unidades_mmgd}</strong>
              </div>
              <div className="flex justify-between text-[#8A8A8A]">
                <span>Clientes Total:</span>
                <strong>{hoveredPoint.data.clientes.toLocaleString("pt-BR")}</strong>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-[0.66rem] font-mono text-[#666666]">
        <span>Passe o cursor sobre a linha para inspecionar os meses</span>
        <span className="text-[#FFD400]">Linha contínua sem aglomeração</span>
      </div>
    </div>
  );
};

interface DailyDispatchChartProps {
  gdPowerKw: number;
}

export const DailyDispatchChart: React.FC<DailyDispatchChartProps> = ({ gdPowerKw }) => {
  const [hoverHour, setHoverHour] = useState<number | null>(null);

  // Generate 24 hours of standard power grid load and solar generation
  const hours = Array.from({ length: 24 }, (_, i) => i);
  const baseLoadPeak = Math.max(gdPowerKw * 1.4, 2000);

  const data = hours.map((hour) => {
    // Base load curve: high in morning and evening, moderate in afternoon
    const morningPeak = Math.exp(-Math.pow(hour - 9, 2) / 8);
    const eveningPeak = Math.exp(-Math.pow(hour - 19, 2) / 9);
    const nightLow = hour < 6 ? 0.4 : 0.6;
    const baseDemand = baseLoadPeak * (nightLow + 0.3 * morningPeak + 0.45 * eveningPeak);

    // Solar Bell Curve: active between 6:00 and 18:00, peak at 12:30
    let solarGen = 0;
    if (hour >= 6 && hour <= 18) {
      const solarFactor = Math.sin(((hour - 6) / 12) * Math.PI);
      solarGen = gdPowerKw * Math.max(0, Math.pow(solarFactor, 1.8));
    }

    const netDemand = Math.max(0, baseDemand - solarGen);
    const isReverseFlow = solarGen > baseDemand;

    return {
      hour,
      baseDemand,
      solarGen,
      netDemand,
      isReverseFlow,
    };
  });

  const width = 600;
  const height = 220;
  const padding = { top: 25, right: 30, bottom: 40, left: 55 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  const maxVal = Math.max(...data.map((d) => Math.max(d.baseDemand, d.solarGen))) * 1.15;

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

  const hoveredData = hoverHour !== null ? data[hoverHour] : null;
  const hoverX = hoverHour !== null ? padding.left + (hoverHour / 23) * chartW : null;

  return (
    <div className="relative overflow-hidden rounded-xl border border-[#222222] bg-[#0C0C0C] p-4">
      <div className="flex flex-wrap items-center justify-between pb-2 mb-2 border-b border-[#1A1A1A] gap-2">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-[#FFD400]" />
          <span className="font-mono text-xs font-semibold text-white uppercase tracking-wider">
            Simulação de Despacho 24h & Curva do Pato
          </span>
        </div>
        <div className="flex items-center gap-3 font-mono text-[0.65rem]">
          <span className="flex items-center gap-1 text-[#8A8A8A]">
            <span className="h-1.5 w-3 rounded-full bg-[#3B82F6]" />
            Demanda Base
          </span>
          <span className="flex items-center gap-1 text-[#FFD400]">
            <span className="h-1.5 w-3 rounded-full bg-[#FFD400]" />
            Geração Solar GD
          </span>
          <span className="flex items-center gap-1 text-[#22C55E]">
            <span className="h-1.5 w-3 rounded-full bg-[#22C55E]" />
            Carga Líquida
          </span>
        </div>
      </div>

      <div className="relative">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto select-none">
          <defs>
            <linearGradient id="solarGlow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#FFD400" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#FFD400" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0, 0.33, 0.66, 1].map((pct) => {
            const y = padding.top + chartH * (1 - pct);
            return (
              <line
                key={pct}
                x1={padding.left}
                y1={y}
                x2={width - padding.right}
                y2={y}
                stroke="rgba(255, 255, 255, 0.05)"
                strokeDasharray="2 3"
              />
            );
          })}

          {/* Solar Area */}
          <path d={solarArea} fill="url(#solarGlow)" />

          {/* Lines */}
          <path d={pathDemand} fill="none" stroke="#3B82F6" strokeWidth="1.8" strokeDasharray="4 2" />
          <path d={pathNet} fill="none" stroke="#22C55E" strokeWidth="2" />
          <path
            d={pathSolar}
            fill="none"
            stroke="#FFD400"
            strokeWidth="2.5"
            className="filter drop-shadow-[0_0_8px_rgba(255,212,0,0.6)]"
          />

          {/* X Axis Time Labels */}
          {[0, 4, 8, 12, 16, 20, 23].map((h) => {
            const x = padding.left + (h / 23) * chartW;
            return (
              <text
                key={h}
                x={x}
                y={padding.top + chartH + 18}
                textAnchor="middle"
                className="font-mono text-[9px] fill-[#8A8A8A]"
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

          {/* Hover indicator */}
          {hoverX !== null && (
            <line
              x1={hoverX}
              y1={padding.top}
              x2={hoverX}
              y2={padding.top + chartH}
              stroke="#FFD400"
              strokeWidth="1"
              strokeDasharray="3 3"
            />
          )}
        </svg>

        {/* Hover Tooltip */}
        {hoveredData && hoverX !== null && (
          <div
            className="pointer-events-none absolute -top-1 -translate-y-full -translate-x-1/2 rounded-xl border border-[#2B2B2B] bg-[#0A0A0A]/95 p-2.5 font-mono text-xs shadow-2xl backdrop-blur-md min-w-[170px]"
            style={{
              left: `${(hoverX / width) * 100}%`,
            }}
          >
            <div className="font-bold text-white border-b border-[#222222] pb-1 mb-1">
              Horário: {String(hoveredData.hour).padStart(2, "0")}:00
            </div>
            <div className="space-y-0.5 text-[0.68rem]">
              <div className="flex justify-between text-[#FFD400]">
                <span>Geração Solar:</span>
                <strong>{hoveredData.solarGen.toFixed(0)} kW</strong>
              </div>
              <div className="flex justify-between text-[#3B82F6]">
                <span>Demanda Base:</span>
                <strong>{hoveredData.baseDemand.toFixed(0)} kW</strong>
              </div>
              <div className="flex justify-between text-[#22C55E]">
                <span>Carga Líquida:</span>
                <strong>{hoveredData.netDemand.toFixed(0)} kW</strong>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
