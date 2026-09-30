import React, { useState } from "react";
import type { Substation, Territories } from "../lib/api";
import { StatusPill } from "./StatusPill";

type TerritoryMapProps = {
  data: Territories;
  substations?: Substation[];
  onSelectSubstation?: (id: string) => void;
  selectedId?: string | null;
};

type Position = [number, number];
type Geometry = {
  type?: string;
  coordinates?: unknown;
};

type Project = (position: Position) => [number, number];

function isPosition(value: unknown): value is Position {
  return (
    Array.isArray(value) &&
    value.length >= 2 &&
    typeof value[0] === "number" &&
    typeof value[1] === "number"
  );
}

function collectPositions(value: unknown, positions: Position[]) {
  if (isPosition(value)) {
    positions.push(value);
    return;
  }

  if (Array.isArray(value)) {
    value.forEach((child) => collectPositions(child, positions));
  }
}

function projectPath(value: unknown, project: Project, close = false): string {
  if (!Array.isArray(value)) return "";
  const positions = value.filter(isPosition);
  if (!positions.length) return "";

  const commands = positions.map(([longitude, latitude], index) => {
    const [x, y] = project([longitude, latitude]);
    return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
  });
  return `${commands.join(" ")}${close ? " Z" : ""}`;
}

function geometryPath(geometry: Geometry | undefined, project: Project): string {
  if (!geometry?.coordinates) return "";

  if (geometry.type === "Polygon") {
    return (geometry.coordinates as unknown[])
      .map((ring) => projectPath(ring, project, true))
      .filter(Boolean)
      .join(" ");
  }

  if (geometry.type === "MultiPolygon") {
    return (geometry.coordinates as unknown[][])
      .flatMap((polygon) => polygon.map((ring) => projectPath(ring, project, true)))
      .filter(Boolean)
      .join(" ");
  }

  return projectPath(geometry.coordinates, project);
}

export const TerritoryMap: React.FC<TerritoryMapProps> = ({
  data,
  substations = [],
  onSelectSubstation,
  selectedId,
}) => {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);

  const positions: Position[] = [];
  data.features.forEach((feature) => {
    const geometry = feature.geometry as Geometry | undefined;
    collectPositions(geometry?.coordinates, positions);
  });

  if (!positions.length) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-[#222222] bg-[#0c0c0c] text-sm text-[#8A8A8A]">
        Nenhuma geometria válida disponível na carga atual.
      </div>
    );
  }

  const longitudes = positions.map(([longitude]) => longitude);
  const latitudes = positions.map(([, latitude]) => latitude);
  const minLongitude = Math.min(...longitudes);
  const maxLongitude = Math.max(...longitudes);
  const minLatitude = Math.min(...latitudes);
  const maxLatitude = Math.max(...latitudes);
  const longitudeSpan = Math.max(maxLongitude - minLongitude, 0.001);
  const latitudeSpan = Math.max(maxLatitude - minLatitude, 0.001);

  // SVG dimensions: 900x460 with comfortable padding
  const project: Project = ([longitude, latitude]) => [
    40 + ((longitude - minLongitude) / longitudeSpan) * 820,
    30 + ((maxLatitude - latitude) / latitudeSpan) * 400,
  ];

  const subMap = new Map<string, Substation>();
  substations.forEach((s) => {
    subMap.set(s.id_tecnico, s);
  });

  const activeSubstation = hoveredId ? subMap.get(hoveredId) : null;

  return (
    <div className="relative overflow-hidden rounded-2xl border border-[#222222] bg-[#080808] double-bezel">
      {/* Tactical HUD Header */}
      <div className="flex flex-wrap items-center justify-between border-b border-[#1F1F1F] bg-[#0E0E0E]/90 px-4 py-2.5 text-xs">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-[#FFD400] shadow-[0_0_8px_#FFD400]" />
          <span className="font-mono font-medium uppercase tracking-wider text-[#FFFFFF]">
            Mapeamento Territorial Geoespacial
          </span>
          <span className="font-mono text-[0.7rem] text-[#8A8A8A]">
            ({data.features.length} zonas operacionais)
          </span>
        </div>
        <div className="flex items-center gap-4 text-[0.7rem] font-mono text-[#8A8A8A]">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-3 rounded-sm border border-[#333333] bg-[#181818]" />
            Normal
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-3 rounded-sm border border-[#EF4444] bg-[#EF4444]/30" />
            Crítico / Atenção
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-3 rounded-sm border border-[#FFD400] bg-[#FFD400]/40" />
            Selecionado
          </span>
        </div>
      </div>

      {/* SVG Canvas with Tactical Telemetry Visuals */}
      <div
        className="relative cursor-crosshair"
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
        }}
        onMouseLeave={() => {
          setHoveredId(null);
          setMousePos(null);
        }}
      >
        <svg
          aria-label="Mapa territorial de subestações"
          className="h-[420px] w-full select-none"
          preserveAspectRatio="xMidYMid meet"
          role="img"
          viewBox="0 0 900 460"
        >
          <defs>
            <pattern id="grid-pattern" width="30" height="30" patternUnits="userSpaceOnUse">
              <path d="M 30 0 L 0 0 0 30" fill="none" stroke="rgba(255, 255, 255, 0.03)" strokeWidth="1" />
              <circle cx="0" cy="0" r="1" fill="rgba(255, 212, 0, 0.15)" />
            </pattern>
          </defs>

          {/* Background Grid Pattern */}
          <rect width="900" height="460" fill="url(#grid-pattern)" />

          {/* Telemetry Corner Accents */}
          <path d="M 15 30 L 15 15 L 30 15" stroke="#FFD400" strokeWidth="1.5" fill="none" opacity="0.6" />
          <path d="M 885 30 L 885 15 L 870 15" stroke="#FFD400" strokeWidth="1.5" fill="none" opacity="0.6" />
          <path d="M 15 430 L 15 445 L 30 445" stroke="#FFD400" strokeWidth="1.5" fill="none" opacity="0.6" />
          <path d="M 885 430 L 885 445 L 870 445" stroke="#FFD400" strokeWidth="1.5" fill="none" opacity="0.6" />

          {/* Features Polygons */}
          {data.features.map((feature, index) => {
            const props = (feature.properties ?? {}) as Record<string, unknown>;
            const codId = String(props.COD_ID ?? props.id_tecnico ?? "");
            const name = String(props.NOM ?? props.NOME ?? `Zona ${index + 1}`);
            const path = geometryPath(feature.geometry as Geometry | undefined, project);
            if (!path) return null;

            const sub = subMap.get(codId);
            const isCritical = sub?.metricas_rede.nivel_criticidade_gd.toUpperCase().includes("CRÍT");
            const isAttention = sub?.metricas_rede.nivel_criticidade_gd.toUpperCase().includes("ATEN");
            const isHovered = hoveredId === codId;
            const isSelected = selectedId === codId;

            let fill = "#141414";
            let stroke = "#2E2E2E";
            let strokeWidth = "1";

            if (isCritical) {
              fill = "rgba(239, 68, 68, 0.15)";
              stroke = "rgba(239, 68, 68, 0.7)";
            } else if (isAttention) {
              fill = "rgba(245, 158, 11, 0.12)";
              stroke = "rgba(245, 158, 11, 0.6)";
            }

            if (isHovered) {
              fill = "rgba(255, 212, 0, 0.3)";
              stroke = "#FFD400";
              strokeWidth = "2";
            } else if (isSelected) {
              fill = "rgba(255, 212, 0, 0.22)";
              stroke = "#FFD400";
              strokeWidth = "2.5";
            }

            return (
              <g key={codId || `${name}-${index}`}>
                <path
                  d={path}
                  fill={fill}
                  stroke={stroke}
                  strokeWidth={strokeWidth}
                  strokeLinejoin="round"
                  className="transition-all duration-150 cursor-pointer"
                  onMouseEnter={() => setHoveredId(codId)}
                  onClick={() => onSelectSubstation && codId && onSelectSubstation(codId)}
                >
                  <title>{`${name} (ID: ${codId})`}</title>
                </path>
              </g>
            );
          })}
        </svg>

        {/* Hover Telemetry HUD Card Floating with mouse */}
        {activeSubstation && mousePos && (
          <div
            className="pointer-events-none absolute z-30 min-w-[240px] -translate-x-1/2 -translate-y-[120%] rounded-xl border border-[#FFD400]/40 bg-[#0A0A0A]/95 p-3 shadow-2xl backdrop-blur-md"
            style={{
              left: Math.max(130, Math.min(mousePos.x, 770)),
              top: mousePos.y,
            }}
          >
            <div className="flex items-center justify-between gap-2 border-b border-[#222222] pb-1.5 mb-2">
              <strong className="font-display text-xs text-white">
                {activeSubstation.subestacao.split(" (ID:")[0]}
              </strong>
              <StatusPill
                label={activeSubstation.metricas_rede.nivel_criticidade_gd}
                size="sm"
              />
            </div>
            <div className="grid grid-cols-2 gap-2 font-mono text-[0.68rem] text-[#8A8A8A]">
              <div>
                <span>ID Técnico:</span>
                <strong className="block text-white">{activeSubstation.id_tecnico}</strong>
              </div>
              <div>
                <span>Clientes:</span>
                <strong className="block text-white">
                  {new Intl.NumberFormat("pt-BR").format(activeSubstation.metricas_rede.total_clientes)}
                </strong>
              </div>
              <div>
                <span>Consumo Anual:</span>
                <strong className="block text-[#FFD400]">
                  {new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(
                    activeSubstation.metricas_rede.consumo_anual_mwh
                  )}{" "}
                  MWh
                </strong>
              </div>
              <div>
                <span>Potência GD:</span>
                <strong className="block text-[#FFD400]">
                  {new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(
                    activeSubstation.geracao_distribuida.potencia_total_kw
                  )}{" "}
                  kW
                </strong>
              </div>
            </div>
            <div className="mt-2 text-center text-[0.62rem] text-[#8A8A8A] border-t border-[#1F1F1F] pt-1">
              Clique para abrir telemetria detalhada
            </div>
          </div>
        )}
      </div>

      {/* Footer Status Bar */}
      <div className="flex items-center justify-between border-t border-[#1F1F1F] bg-[#0E0E0E] px-4 py-2 text-[0.72rem] text-[#8A8A8A]">
        <span>Intersecção topológica: Carga de distribuição ativa</span>
        <span className="font-mono text-[#FFD400]">
          {selectedId ? `Subestação ID ${selectedId} focalizada` : "Clique em uma zona para inspecionar"}
        </span>
      </div>
    </div>
  );
};
