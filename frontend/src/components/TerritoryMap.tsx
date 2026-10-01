import React, { useState, useRef, useMemo, useEffect } from "react";
import type { Substation, Territories } from "../lib/api";
import { StatusPill } from "./StatusPill";
import {
  MagnifyingGlassPlus,
  MagnifyingGlassMinus,
  ArrowsCounterClockwise,
  ArrowsOut,
  ArrowsIn,
  Compass,
  MapPin,
  Lightning,
  SlidersHorizontal,
  Eye,
  EyeSlash,
  MagnifyingGlass,
  ArrowSquareOut,
  ShieldCheck,
  TrendUp,
  Buildings,
} from "@phosphor-icons/react";

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
type InvertProject = (point: [number, number]) => [number, number];
type MapThemeMode = "criticality" | "gd_power" | "consumption" | "clients";

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
    return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
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

// Compute centroid of polygon coordinates
function calculateCentroid(geometry: Geometry | undefined, project: Project): [number, number] | null {
  if (!geometry?.coordinates) return null;
  const positions: Position[] = [];
  collectPositions(geometry.coordinates, positions);
  if (!positions.length) return null;

  const sumX = positions.reduce((acc, curr) => acc + curr[0], 0);
  const sumY = positions.reduce((acc, curr) => acc + curr[1], 0);
  const avgLon = sumX / positions.length;
  const avgLat = sumY / positions.length;

  return project([avgLon, avgLat]);
}

export const TerritoryMap: React.FC<TerritoryMapProps> = ({
  data,
  substations = [],
  onSelectSubstation,
  selectedId,
}) => {
  // Navigation State: Zoom & Pan
  const [zoom, setZoom] = useState(1.0);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  // Map Controls State
  const [themeMode, setThemeMode] = useState<MapThemeMode>("criticality");
  const [showLabels, setShowLabels] = useState(true);
  const [showNodes, setShowNodes] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "normal" | "attention" | "critical">("all");

  // Hover & Coordinate State
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [cursorGeo, setCursorGeo] = useState<{ lat: number; lon: number } | null>(null);
  const [mouseCanvasPos, setMouseCanvasPos] = useState<{ x: number; y: number } | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);

  // Extract all coordinates to build bounding box
  const positions: Position[] = useMemo(() => {
    const pos: Position[] = [];
    data.features.forEach((feature) => {
      const geometry = feature.geometry as Geometry | undefined;
      collectPositions(geometry?.coordinates, pos);
    });
    return pos;
  }, [data]);

  if (!positions.length) {
    return (
      <div className="flex h-64 items-center justify-center rounded-2xl border border-[#222222] bg-[#0c0c0c] text-sm text-[#8A8A8A]">
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

  // Base SVG Canvas size
  const svgWidth = 920;
  const svgHeight = 480;
  const mapPadding = { top: 35, right: 40, bottom: 45, left: 40 };
  const innerW = svgWidth - mapPadding.left - mapPadding.right;
  const innerH = svgHeight - mapPadding.top - mapPadding.bottom;

  // Projection formula
  const project: Project = ([longitude, latitude]) => [
    mapPadding.left + ((longitude - minLongitude) / longitudeSpan) * innerW,
    mapPadding.top + ((maxLatitude - latitude) / latitudeSpan) * innerH,
  ];

  // Invert projection to get Lat/Lon from canvas point
  const invertProject: InvertProject = ([x, y]) => {
    const lon = minLongitude + ((x - mapPadding.left) / innerW) * longitudeSpan;
    const lat = maxLatitude - ((y - mapPadding.top) / innerH) * latitudeSpan;
    return [lon, lat];
  };

  // Substation lookup map
  const subMap = useMemo(() => {
    const map = new Map<string, Substation>();
    substations.forEach((s) => map.set(s.id_tecnico, s));
    return map;
  }, [substations]);

  // Max values for choropleth gradients
  const maxGdPower = useMemo(() => {
    return Math.max(...substations.map((s) => s.geracao_distribuida.potencia_total_kw), 1);
  }, [substations]);

  const maxConsumption = useMemo(() => {
    return Math.max(...substations.map((s) => s.metricas_rede.consumo_anual_mwh), 1);
  }, [substations]);

  const maxClients = useMemo(() => {
    return Math.max(...substations.map((s) => s.metricas_rede.total_clientes), 1);
  }, [substations]);

  // Compute centroids for each feature
  const featureCentroids = useMemo(() => {
    return data.features.map((feature, idx) => {
      const props = (feature.properties ?? {}) as Record<string, unknown>;
      const codId = String(props.COD_ID ?? props.id_tecnico ?? "");
      const centroid = calculateCentroid(feature.geometry as Geometry | undefined, project);
      return { codId, centroid, idx };
    });
  }, [data, project]);

  // Reset View handler
  const handleResetView = () => {
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
    setHoveredId(null);
  };

  // Zoom handlers
  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 0.35, 4.5));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 0.35, 0.75));

  // Wheel zoom handler
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.15 : -0.15;
    setZoom((prev) => Math.max(0.75, Math.min(4.5, prev + delta)));
  };

  // Mouse drag handlers for fluid panning
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return; // Only left click
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }

    const rect = e.currentTarget.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;
    setMouseCanvasPos({ x: clientX, y: clientY });

    // Map screen pixel to SVG coordinate space taking pan & zoom into account
    const scaleFactor = rect.width / svgWidth;
    const rawSvgX = clientX / scaleFactor;
    const rawSvgY = clientY / scaleFactor;

    // Apply inverse zoom & pan
    const centerX = svgWidth / 2;
    const centerY = svgHeight / 2;
    const transformedX = (rawSvgX - centerX - pan.x) / zoom + centerX;
    const transformedY = (rawSvgY - centerY - pan.y) / zoom + centerY;

    const [lon, lat] = invertProject([transformedX, transformedY]);
    setCursorGeo({ lat, lon });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const activeSubstation = hoveredId ? subMap.get(hoveredId) : (selectedId ? subMap.get(selectedId) : null);

  // Esc key to exit fullscreen
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isFullscreen) setIsFullscreen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isFullscreen]);

  return (
    <div
      ref={containerRef}
      className={`relative overflow-hidden rounded-3xl border border-[#222222] bg-[#070707] double-bezel transition-all ${
        isFullscreen ? "fixed inset-4 z-50 rounded-2xl shadow-[0_0_80px_rgba(0,0,0,0.95)]" : ""
      }`}
    >
      {/* HUD Header Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#1C1C1C] bg-[#0D0D0D]/95 px-4 py-3 text-xs backdrop-blur-md">
        {/* Left: Title & Operational Status */}
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="h-2 w-2 rounded-full bg-[#FFD400] shadow-[0_0_8px_#FFD400]" />
          <strong className="font-display font-semibold text-white tracking-wide uppercase text-xs">
            Mapeamento Territorial Geoespacial
          </strong>
          <span className="font-mono text-[0.68rem] text-[#8A8A8A]">
            ({data.features.length} zonas operacionais Voronoi)
          </span>

          {/* Quick Search Input */}
          <div className="relative ml-2">
            <MagnifyingGlass size={13} className="pointer-events-none absolute left-2.5 top-2 text-[#777777]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Localizar zona..."
              className="rounded-lg border border-[#262626] bg-[#141414] py-1 pl-7 pr-2 font-mono text-[0.7rem] text-white placeholder:text-[#555555] outline-none focus:border-[#FFD400]"
            />
          </div>
        </div>

        {/* Center: Theme Selector Pills */}
        <div className="flex items-center gap-1 rounded-xl border border-[#222222] bg-[#121212] p-1 font-mono text-[0.66rem]">
          <button
            type="button"
            onClick={() => setThemeMode("criticality")}
            className={`rounded-lg px-2 py-1 transition-all ${
              themeMode === "criticality"
                ? "bg-[#FFD400] font-bold text-black shadow-[0_0_8px_rgba(255,212,0,0.3)]"
                : "text-[#8A8A8A] hover:text-white"
            }`}
          >
            Criticidade
          </button>
          <button
            type="button"
            onClick={() => setThemeMode("gd_power")}
            className={`rounded-lg px-2 py-1 transition-all ${
              themeMode === "gd_power"
                ? "bg-[#FFD400] font-bold text-black shadow-[0_0_8px_rgba(255,212,0,0.3)]"
                : "text-[#8A8A8A] hover:text-white"
            }`}
          >
            Calor GD (kW)
          </button>
          <button
            type="button"
            onClick={() => setThemeMode("consumption")}
            className={`rounded-lg px-2 py-1 transition-all ${
              themeMode === "consumption"
                ? "bg-[#FFD400] font-bold text-black shadow-[0_0_8px_rgba(255,212,0,0.3)]"
                : "text-[#8A8A8A] hover:text-white"
            }`}
          >
            Consumo (MWh)
          </button>
          <button
            type="button"
            onClick={() => setThemeMode("clients")}
            className={`rounded-lg px-2 py-1 transition-all ${
              themeMode === "clients"
                ? "bg-[#FFD400] font-bold text-black shadow-[0_0_8px_rgba(255,212,0,0.3)]"
                : "text-[#8A8A8A] hover:text-white"
            }`}
          >
            Clientes
          </button>
        </div>

        {/* Right: Quick Action Controls */}
        <div className="flex items-center gap-2">
          {/* Toggle Labels */}
          <button
            type="button"
            onClick={() => setShowLabels(!showLabels)}
            className={`flex items-center gap-1 rounded-lg border px-2 py-1 font-mono text-[0.68rem] transition-colors ${
              showLabels
                ? "border-[#FFD400]/40 bg-[#FFD400]/10 text-[#FFD400]"
                : "border-[#242424] bg-[#141414] text-[#8A8A8A]"
            }`}
            title="Alternar Rótulos de Nomes"
          >
            {showLabels ? <Eye size={13} /> : <EyeSlash size={13} />}
            <span>Rótulos</span>
          </button>

          {/* Toggle Substation Nodes */}
          <button
            type="button"
            onClick={() => setShowNodes(!showNodes)}
            className={`flex items-center gap-1 rounded-lg border px-2 py-1 font-mono text-[0.68rem] transition-colors ${
              showNodes
                ? "border-[#FFD400]/40 bg-[#FFD400]/10 text-[#FFD400]"
                : "border-[#242424] bg-[#141414] text-[#8A8A8A]"
            }`}
            title="Alternar Nós de Subestação"
          >
            <MapPin size={13} />
            <span>Nós</span>
          </button>

          {/* Zoom Controls */}
          <div className="flex items-center rounded-lg border border-[#242424] bg-[#141414] p-0.5">
            <button
              type="button"
              onClick={handleZoomIn}
              className="p-1 text-[#8A8A8A] hover:text-white transition-colors"
              title="Aproximar Zoom (+)"
            >
              <MagnifyingGlassPlus size={15} />
            </button>
            <button
              type="button"
              onClick={handleZoomOut}
              className="p-1 text-[#8A8A8A] hover:text-white transition-colors"
              title="Afastar Zoom (-)"
            >
              <MagnifyingGlassMinus size={15} />
            </button>
            <button
              type="button"
              onClick={handleResetView}
              className="p-1 text-[#8A8A8A] hover:text-[#FFD400] transition-colors border-l border-[#242424]"
              title="Redefinir Visão (100%)"
            >
              <ArrowsCounterClockwise size={14} />
            </button>
          </div>

          {/* Fullscreen Toggle */}
          <button
            type="button"
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="flex h-7 w-7 items-center justify-center rounded-lg border border-[#242424] bg-[#141414] text-[#8A8A8A] hover:border-[#FFD400] hover:text-[#FFD400] transition-colors"
            title={isFullscreen ? "Restaurar Janela" : "Expandir Mapa"}
          >
            {isFullscreen ? <ArrowsIn size={15} /> : <ArrowsOut size={15} />}
          </button>
        </div>
      </div>

      {/* Interactive Map Canvas Container */}
      <div
        className={`relative select-none overflow-hidden ${
          isFullscreen ? "h-[calc(100%-88px)]" : "h-[460px] md:h-[500px]"
        } ${isDragging ? "cursor-grabbing" : "cursor-grab"}`}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => {
          handleMouseUp();
          setHoveredId(null);
          setCursorGeo(null);
        }}
      >
        <svg
          aria-label="Mapa territorial geoespacial interativo"
          className="h-full w-full select-none"
          preserveAspectRatio="xMidYMid meet"
          role="img"
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        >
          <defs>
            {/* High-tech Blueprint Grid Pattern */}
            <pattern id="tacticalGridPattern" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255, 255, 255, 0.025)" strokeWidth="1" />
              <circle cx="0" cy="0" r="1.2" fill="rgba(255, 212, 0, 0.12)" />
            </pattern>

            {/* Glowing Golden Filter */}
            <filter id="territoryGlow" x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor="#FFD400" floodOpacity="0.6" />
            </filter>

            {/* Critical Red Glow Filter */}
            <filter id="criticalGlow" x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor="#EF4444" floodOpacity="0.5" />
            </filter>
          </defs>

          {/* Background Grid */}
          <rect width={svgWidth} height={svgHeight} fill="url(#tacticalGridPattern)" />

          {/* Interactive Zoom/Pan Transform Group */}
          <g
            transform={`translate(${svgWidth / 2 + pan.x}, ${svgHeight / 2 + pan.y}) scale(${zoom}) translate(${-svgWidth / 2}, ${-svgHeight / 2})`}
            className="transition-transform duration-75 ease-out"
          >
            {/* Voronoi Territory Polygons */}
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

              // Filter out if statusFilter doesn't match
              if (statusFilter === "normal" && (isCritical || isAttention)) return null;
              if (statusFilter === "attention" && !isAttention) return null;
              if (statusFilter === "critical" && !isCritical) return null;

              // Search query highlight
              const matchesSearch =
                searchQuery.trim().length > 0 &&
                (name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                  codId.includes(searchQuery));

              // Compute Theme Fill Color
              let fill = "#101010";
              let stroke = "#242424";
              let strokeWidth = 1.0 / zoom;

              if (themeMode === "criticality") {
                if (isCritical) {
                  fill = "rgba(239, 68, 68, 0.20)";
                  stroke = "#EF4444";
                } else if (isAttention) {
                  fill = "rgba(245, 158, 11, 0.16)";
                  stroke = "#F59E0B";
                } else {
                  fill = "rgba(255, 255, 255, 0.03)";
                  stroke = "rgba(255, 255, 255, 0.12)";
                }
              } else if (themeMode === "gd_power") {
                const gdVal = sub?.geracao_distribuida.potencia_total_kw ?? 0;
                const ratio = Math.min(1.0, gdVal / maxGdPower);
                const alpha = (0.05 + ratio * 0.45).toFixed(2);
                fill = `rgba(255, 212, 0, ${alpha})`;
                stroke = ratio > 0.4 ? "#FFD400" : "rgba(255, 212, 0, 0.3)";
              } else if (themeMode === "consumption") {
                const consVal = sub?.metricas_rede.consumo_anual_mwh ?? 0;
                const ratio = Math.min(1.0, consVal / maxConsumption);
                const alpha = (0.05 + ratio * 0.40).toFixed(2);
                fill = `rgba(59, 130, 246, ${alpha})`;
                stroke = ratio > 0.4 ? "#3B82F6" : "rgba(59, 130, 246, 0.3)";
              } else if (themeMode === "clients") {
                const cliVal = sub?.metricas_rede.total_clientes ?? 0;
                const ratio = Math.min(1.0, cliVal / maxClients);
                const alpha = (0.05 + ratio * 0.40).toFixed(2);
                fill = `rgba(34, 197, 94, ${alpha})`;
                stroke = ratio > 0.4 ? "#22C55E" : "rgba(34, 197, 94, 0.3)";
              }

              // Highlight on hover, selected, or search match
              if (isHovered) {
                fill = "rgba(255, 212, 0, 0.38)";
                stroke = "#FFD400";
                strokeWidth = 2.2 / zoom;
              } else if (isSelected) {
                fill = "rgba(255, 212, 0, 0.28)";
                stroke = "#FFD400";
                strokeWidth = 2.6 / zoom;
              } else if (matchesSearch) {
                fill = "rgba(255, 212, 0, 0.40)";
                stroke = "#FFD400";
                strokeWidth = 2.0 / zoom;
              }

              return (
                <g key={codId || `${name}-${index}`}>
                  <path
                    d={path}
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={strokeWidth}
                    strokeLinejoin="round"
                    className="transition-colors duration-150 cursor-pointer"
                    onMouseEnter={() => setHoveredId(codId)}
                    onClick={() => {
                      if (onSelectSubstation && codId) onSelectSubstation(codId);
                    }}
                    filter={isHovered || isSelected ? "url(#territoryGlow)" : undefined}
                  >
                    <title>{`${name} (ID: ${codId})`}</title>
                  </path>
                </g>
              );
            })}

            {/* Substation Centroid Pins & Labels Overlay */}
            {data.features.map((feature, index) => {
              const props = (feature.properties ?? {}) as Record<string, unknown>;
              const codId = String(props.COD_ID ?? props.id_tecnico ?? "");
              const name = String(props.NOM ?? props.NOME ?? `Zona ${index + 1}`).replace("SUBESTACAO", "SE");
              const centroid = featureCentroids[index]?.centroid;
              if (!centroid) return null;

              const sub = subMap.get(codId);
              const isCritical = sub?.metricas_rede.nivel_criticidade_gd.toUpperCase().includes("CRÍT");
              const isAttention = sub?.metricas_rede.nivel_criticidade_gd.toUpperCase().includes("ATEN");
              const isHovered = hoveredId === codId;
              const isSelected = selectedId === codId;

              const pinColor = isHovered || isSelected ? "#FFD400" : isCritical ? "#EF4444" : isAttention ? "#F59E0B" : "#FFFFFF";

              return (
                <g
                  key={`pin-${codId}-${index}`}
                  transform={`translate(${centroid[0]}, ${centroid[1]})`}
                  className="pointer-events-none"
                >
                  {/* Substation Centroid Node */}
                  {showNodes && (
                    <g>
                      {/* Pulse Ring when Active */}
                      {(isHovered || isSelected || isCritical) && (
                        <circle
                          r={9 / Math.sqrt(zoom)}
                          fill="none"
                          stroke={pinColor}
                          strokeWidth={1.5 / zoom}
                          opacity={0.7}
                        />
                      )}
                      {/* Core Dot */}
                      <circle
                        r={3.8 / Math.sqrt(zoom)}
                        fill={pinColor}
                        stroke="#000000"
                        strokeWidth={1 / zoom}
                      />
                    </g>
                  )}

                  {/* Clean Map Label */}
                  {showLabels && (
                    <g transform={`translate(0, ${showNodes ? 12 / zoom : 0})`}>
                      <text
                        textAnchor="middle"
                        className="select-none font-mono font-bold tracking-tight"
                        style={{
                          fontSize: `${Math.max(7, Math.min(11, 8.5 / Math.sqrt(zoom)))}px`,
                          fill: isHovered || isSelected ? "#FFD400" : "#D4D4D4",
                          textShadow: "0 1px 3px rgba(0,0,0,0.9)",
                        }}
                      >
                        {name}
                      </text>
                    </g>
                  )}
                </g>
              );
            })}
          </g>

          {/* Fixed Tactical Overlays (Never affected by zoom/pan) */}

          {/* Tactical Corner Reticles */}
          <path d="M 16 32 L 16 16 L 32 16" stroke="#FFD400" strokeWidth="2" fill="none" opacity="0.75" />
          <path d="M 904 32 L 904 16 L 888 16" stroke="#FFD400" strokeWidth="2" fill="none" opacity="0.75" />
          <path d="M 16 448 L 16 464 L 32 464" stroke="#FFD400" strokeWidth="2" fill="none" opacity="0.75" />
          <path d="M 904 448 L 904 464 L 888 464" stroke="#FFD400" strokeWidth="2" fill="none" opacity="0.75" />

          {/* Compass Rose / North Indicator */}
          <g transform="translate(865, 55)" className="pointer-events-none opacity-80">
            <circle r="18" fill="#0C0C0C" stroke="#2B2B2B" strokeWidth="1" />
            <polygon points="0,-13 4,0 0,4 -4,0" fill="#FFD400" />
            <polygon points="0,13 4,0 0,-4 -4,0" fill="#444444" />
            <text x="0" y="-15" textAnchor="middle" className="font-mono text-[8px] font-bold fill-[#FFD400]">
              N
            </text>
          </g>

          {/* Graphic Scale Bar */}
          <g transform="translate(45, 445)" className="pointer-events-none opacity-75 font-mono text-[8px] fill-[#8A8A8A]">
            <line x1="0" y1="0" x2="80" y2="0" stroke="#8A8A8A" strokeWidth="1.5" />
            <line x1="0" y1="-3" x2="0" y2="3" stroke="#8A8A8A" strokeWidth="1.5" />
            <line x1="40" y1="-2" x2="40" y2="2" stroke="#8A8A8A" strokeWidth="1" />
            <line x1="80" y1="-3" x2="80" y2="3" stroke="#8A8A8A" strokeWidth="1.5" />
            <text x="0" y="-5" textAnchor="middle">0</text>
            <text x="40" y="-5" textAnchor="middle">2.5km</text>
            <text x="80" y="-5" textAnchor="middle">5km</text>
          </g>
        </svg>

        {/* Floating Active Substation HUD Card */}
        {activeSubstation && (
          <div
            className="absolute bottom-4 right-4 z-30 min-w-[280px] max-w-[340px] rounded-2xl border border-[#FFD400]/40 bg-[#0A0A0A]/95 p-4 shadow-2xl backdrop-blur-xl animate-in fade-in slide-in-from-bottom-2 duration-200"
          >
            <div className="flex items-start justify-between gap-2 border-b border-[#222222] pb-2 mb-2.5">
              <div>
                <span className="font-mono text-[0.65rem] text-[#8A8A8A] block">
                  SUBESTAÇÃO DETECTADA
                </span>
                <strong className="font-display text-sm font-bold text-white block">
                  {activeSubstation.subestacao.split(" (ID:")[0]}
                </strong>
                <span className="font-mono text-[0.68rem] text-[#FFD400]">
                  ID Técnico: {activeSubstation.id_tecnico}
                </span>
              </div>
              <StatusPill
                label={activeSubstation.metricas_rede.nivel_criticidade_gd}
                size="sm"
              />
            </div>

            <div className="grid grid-cols-3 gap-2 font-mono text-center">
              <div className="rounded-lg border border-[#1F1F1F] bg-[#121212] p-1.5">
                <span className="block text-[0.62rem] text-[#8A8A8A]">POTÊNCIA GD</span>
                <strong className="block text-xs font-bold text-[#FFD400] mt-0.5">
                  {activeSubstation.geracao_distribuida.potencia_total_kw.toLocaleString("pt-BR", {
                    maximumFractionDigits: 1,
                  })}{" "}
                  <span className="text-[0.6rem] font-normal text-[#8A8A8A]">kW</span>
                </strong>
              </div>

              <div className="rounded-lg border border-[#1F1F1F] bg-[#121212] p-1.5">
                <span className="block text-[0.62rem] text-[#8A8A8A]">CONSUMO</span>
                <strong className="block text-xs font-bold text-white mt-0.5">
                  {activeSubstation.metricas_rede.consumo_anual_mwh.toLocaleString("pt-BR", {
                    maximumFractionDigits: 0,
                  })}{" "}
                  <span className="text-[0.6rem] font-normal text-[#8A8A8A]">MWh</span>
                </strong>
              </div>

              <div className="rounded-lg border border-[#1F1F1F] bg-[#121212] p-1.5">
                <span className="block text-[0.62rem] text-[#8A8A8A]">CLIENTES</span>
                <strong className="block text-xs font-bold text-white mt-0.5">
                  {activeSubstation.metricas_rede.total_clientes.toLocaleString("pt-BR")}
                </strong>
              </div>
            </div>

            {/* Quick Inspection Action */}
            <button
              type="button"
              onClick={() => onSelectSubstation && onSelectSubstation(activeSubstation.id_tecnico)}
              className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-xl border border-[#FFD400]/40 bg-[#FFD400]/10 py-2 font-mono text-xs font-bold text-[#FFD400] transition-colors hover:bg-[#FFD400]/20"
            >
              <span>Abrir Telemetria do Ativo</span>
              <ArrowSquareOut size={14} />
            </button>
          </div>
        )}
      </div>

      {/* Footer Status Bar with Live Coordinates & Legend */}
      <div className="flex flex-wrap items-center justify-between border-t border-[#1C1C1C] bg-[#0A0A0A] px-4 py-2.5 text-[0.7rem] font-mono text-[#8A8A8A]">
        {/* Live Coordinate Crosshair Readout */}
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1 text-[#CCCCCC]">
            <Compass size={14} className="text-[#FFD400]" />
            <span>
              {cursorGeo
                ? `LAT: ${cursorGeo.lat.toFixed(4)}° | LON: ${cursorGeo.lon.toFixed(4)}°`
                : "POSICIONE O CURSOR SOBRE O MAPA"}
            </span>
          </span>
          <span className="text-[#333333]">|</span>
          <span className="text-[#777777]">
            Zoom: {(zoom * 100).toFixed(0)}% · Arraste para navegar
          </span>
        </div>

        {/* Dynamic Legend based on active Theme */}
        <div className="flex items-center gap-4">
          {themeMode === "criticality" && (
            <>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-3 rounded-sm border border-[#2E2E2E] bg-[#141414]" />
                Normal
              </span>
              <span className="flex items-center gap-1.5 text-[#F59E0B]">
                <span className="h-2 w-3 rounded-sm border border-[#F59E0B] bg-[#F59E0B]/30" />
                Atenção
              </span>
              <span className="flex items-center gap-1.5 text-[#EF4444]">
                <span className="h-2 w-3 rounded-sm border border-[#EF4444] bg-[#EF4444]/30" />
                Crítico
              </span>
            </>
          )}

          {themeMode === "gd_power" && (
            <div className="flex items-center gap-2">
              <span>0 kW</span>
              <div className="h-2 w-20 rounded-full bg-gradient-to-r from-[#141414] via-[#FFD400]/40 to-[#FFD400]" />
              <span className="text-[#FFD400] font-bold">
                {maxGdPower.toLocaleString("pt-BR", { maximumFractionDigits: 0 })} kW
              </span>
            </div>
          )}

          {themeMode === "consumption" && (
            <div className="flex items-center gap-2">
              <span>0 MWh</span>
              <div className="h-2 w-20 rounded-full bg-gradient-to-r from-[#141414] via-[#3B82F6]/40 to-[#3B82F6]" />
              <span className="text-[#3B82F6] font-bold">
                {maxConsumption.toLocaleString("pt-BR", { maximumFractionDigits: 0 })} MWh
              </span>
            </div>
          )}

          {themeMode === "clients" && (
            <div className="flex items-center gap-2">
              <span>0 UCs</span>
              <div className="h-2 w-20 rounded-full bg-gradient-to-r from-[#141414] via-[#22C55E]/40 to-[#22C55E]" />
              <span className="text-[#22C55E] font-bold">
                {maxClients.toLocaleString("pt-BR")} UCs
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
