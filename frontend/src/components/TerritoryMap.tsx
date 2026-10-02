import React, { useState, useRef, useMemo, useEffect, useCallback } from "react";
import type { Substation, Territories } from "../lib/api";
import { THEME_COLORS } from "../lib/theme";
import { StatusPill } from "./StatusPill";
import { TerritoryMapModal } from "./TerritoryMapModal";
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
  GlobeHemisphereWest,
  Cube,
  HandGrabbing,
  Repeat,
} from "@phosphor-icons/react";

export type TerritoryMapProps = {
  data: Territories;
  substations?: Substation[];
  onSelectSubstation?: (id: string) => void;
  selectedId?: string | null;
  isModalView?: boolean;
  onOpenModal?: () => void;
  onCloseModal?: () => void;
};

type Position = [number, number];
type Geometry = {
  type?: string;
  coordinates?: unknown;
};

type Project = (position: Position) => [number, number];
type InvertProject = (point: [number, number]) => [number, number];
type MapThemeMode = "criticality" | "gd_power" | "consumption" | "clients";
type DragInteractionMode = "pan" | "orbit";

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

function ringCentroid(ring: Position[]): { point: Position; area: number } | null {
  if (ring.length < 3) return null;
  let twiceArea = 0;
  let x = 0;
  let y = 0;
  for (let index = 0; index < ring.length - 1; index += 1) {
    const [currentX, currentY] = ring[index];
    const [nextX, nextY] = ring[index + 1];
    const cross = currentX * nextY - nextX * currentY;
    twiceArea += cross;
    x += (currentX + nextX) * cross;
    y += (currentY + nextY) * cross;
  }
  if (Math.abs(twiceArea) < Number.EPSILON) return null;
  return {
    point: [x / (3 * twiceArea), y / (3 * twiceArea)],
    area: Math.abs(twiceArea / 2),
  };
}

function pointInRing(point: Position, ring: Position[]): boolean {
  let inside = false;
  for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index++) {
    const [x, y] = ring[index];
    const [previousX, previousY] = ring[previous];
    const intersects =
      y > point[1] !== previousY > point[1] &&
      point[0] < ((previousX - x) * (point[1] - y)) / (previousY - y) + x;
    if (intersects) inside = !inside;
  }
  return inside;
}

function pointInPolygon(point: Position, rings: Position[][]): boolean {
  return Boolean(rings[0] && pointInRing(point, rings[0])) &&
    !rings.slice(1).some((ring) => pointInRing(point, ring));
}

function calculateCentroid(geometry: Geometry | undefined, project: Project): [number, number] | null {
  if (!geometry?.coordinates) return null;
  const polygons: Position[][][] = geometry.type === "Polygon"
    ? [geometry.coordinates as Position[][]]
    : geometry.type === "MultiPolygon"
      ? (geometry.coordinates as Position[][][])
      : [];
  const candidates = polygons
    .map((rings) => ({
      rings,
      centroid: ringCentroid(rings[0] ?? []),
    }))
    .filter((candidate) => candidate.centroid !== null)
    .sort((left, right) => (right.centroid?.area ?? 0) - (left.centroid?.area ?? 0));
  const selected = candidates[0];
  if (!selected?.centroid) return null;

  let representative = selected.centroid.point;
  if (!pointInPolygon(representative, selected.rings)) {
    const positions: Position[] = [];
    collectPositions(selected.rings[0], positions);
    const bounds = positions.reduce(
      (current, [longitude, latitude]) => ({
        minLongitude: Math.min(current.minLongitude, longitude),
        maxLongitude: Math.max(current.maxLongitude, longitude),
        minLatitude: Math.min(current.minLatitude, latitude),
        maxLatitude: Math.max(current.maxLatitude, latitude),
      }),
      {
        minLongitude: Number.POSITIVE_INFINITY,
        maxLongitude: Number.NEGATIVE_INFINITY,
        minLatitude: Number.POSITIVE_INFINITY,
        maxLatitude: Number.NEGATIVE_INFINITY,
      },
    );
    const gridSize = 12;
    for (let row = 0; row <= gridSize; row += 1) {
      for (let column = 0; column <= gridSize; column += 1) {
        const candidate: Position = [
          bounds.minLongitude + ((bounds.maxLongitude - bounds.minLongitude) * column) / gridSize,
          bounds.minLatitude + ((bounds.maxLatitude - bounds.minLatitude) * row) / gridSize,
        ];
        if (pointInPolygon(candidate, selected.rings)) {
          representative = candidate;
          row = gridSize + 1;
          break;
        }
      }
    }
  }
  return project(representative);
}

function formatDistanceKm(distanceKm: number): string {
  if (distanceKm < 1) return `${Math.round(distanceKm * 1000)}m`;
  if (distanceKm < 10) return `${distanceKm.toFixed(1)}km`;
  return `${Math.round(distanceKm)}km`;
}

export const TerritoryMap: React.FC<TerritoryMapProps> = ({
  data,
  substations = [],
  onSelectSubstation,
  selectedId,
  isModalView = false,
  onOpenModal,
  onCloseModal,
}) => {
  // Navigation State: Zoom & Pan
  const [zoom, setZoom] = useState(1.0);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  // 3D Perspective & Orbit State (Default is 2D Flat / Plano: pitch=0, bearing=0)
  const [pitch, setPitch] = useState(0); // 0° = Plano (Ortogonal), 45° = 3D Inclinado
  const [bearing, setBearing] = useState(0); // 0° = Alinhado ao Norte
  const [dragMode, setDragMode] = useState<DragInteractionMode>("pan");

  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [dragType, setDragType] = useState<"pan" | "orbit">("pan");

  // Map Controls State
  const [themeMode, setThemeMode] = useState<MapThemeMode>("criticality");
  const [showLabels, setShowLabels] = useState(true);
  const [showNodes, setShowNodes] = useState(true);
  const [internalModalOpen, setInternalModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "normal" | "attention" | "critical">("all");

  // Hover & Coordinate State
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [cursorGeo, setCursorGeo] = useState<{ lat: number; lon: number } | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const [viewportSize, setViewportSize] = useState({ width: 1080, height: 540 });

  // Dynamically observe the viewport size so tactical grid and corner reticles span 100% of where the map appears
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;

    const updateSize = () => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      if (w > 0 && h > 0) {
        setViewportSize((prev) => {
          if (prev.width === w && prev.height === h) return prev;
          return { width: Math.round(w), height: Math.round(h) };
        });
      }
    };

    updateSize();
    const ro = new ResizeObserver(updateSize);
    ro.observe(el);
    window.addEventListener("resize", updateSize);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", updateSize);
    };
  }, [isModalView]);

  useEffect(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setPitch(0);
    setBearing(0);
    setHoveredId(null);
  }, [data]);

  // Extract all coordinates to build bounding box
  const positions: Position[] = useMemo(() => {
    const pos: Position[] = [];
    data.features.forEach((feature) => {
      const geometry = feature.geometry as Geometry | undefined;
      collectPositions(geometry?.coordinates, pos);
    });
    return pos;
  }, [data]);

  const positionsForProjection: Position[] = positions.length ? positions : [[0, 0]];
  const bounds = positionsForProjection.reduce(
    (current, [longitude, latitude]) => ({
      minLongitude: Math.min(current.minLongitude, longitude),
      maxLongitude: Math.max(current.maxLongitude, longitude),
      minLatitude: Math.min(current.minLatitude, latitude),
      maxLatitude: Math.max(current.maxLatitude, latitude),
    }),
    {
      minLongitude: Number.POSITIVE_INFINITY,
      maxLongitude: Number.NEGATIVE_INFINITY,
      minLatitude: Number.POSITIVE_INFINITY,
      maxLatitude: Number.NEGATIVE_INFINITY,
    },
  );
  const { minLongitude, maxLongitude, minLatitude, maxLatitude } = bounds;
  const longitudeSpan = Math.max(maxLongitude - minLongitude, 0.001);
  const latitudeSpan = Math.max(maxLatitude - minLatitude, 0.001);

  // Dynamic Responsive Canvas size based on viewport element
  const svgWidth = Math.max(viewportSize.width, 320);
  const svgHeight = Math.max(viewportSize.height, 320);
  const mapPadding = { top: 40, right: 60, bottom: 50, left: 60 };
  const innerW = Math.max(svgWidth - mapPadding.left - mapPadding.right, 60);
  const innerH = Math.max(svgHeight - mapPadding.top - mapPadding.bottom, 60);

  // Infinite Ground Plane Dimensions in World Coordinates:
  // Repositioned dynamically below camera optical focal point so the ground plane is visually infinite
  const camWorldX = svgWidth / 2 - pan.x / zoom;
  const camWorldY = svgHeight / 2 - pan.y / zoom;
  // Radius expands when zooming out to guarantee coverage far past the 3D horizon frustum
  const groundRadius = (Math.max(svgWidth, svgHeight) * 8) / Math.min(zoom, 1);
  const groundSize = groundRadius * 2;
  const groundX = camWorldX - groundRadius;
  const groundY = camWorldY - groundRadius;

  // TRUE CONFORMAL ASPECT-RATIO PROJECTION (Eliminates horizontal stretching / "mapa deitado")
  const avgLatitude = (minLatitude + maxLatitude) / 2;
  const cosLat = Math.cos((avgLatitude * Math.PI) / 180);
  const geoWidth = longitudeSpan * cosLat;
  const geoHeight = latitudeSpan;

  // Uniform scale to fit perfectly within canvas while preserving 1:1 true geometry
  const scaleGeo = Math.min(innerW / geoWidth, innerH / geoHeight);
  const offsetX = mapPadding.left + (innerW - geoWidth * scaleGeo) / 2;
  const offsetY = mapPadding.top + (innerH - geoHeight * scaleGeo) / 2;

  // Projection formula
  const project: Project = useCallback(
    ([longitude, latitude]: Position) => [
      offsetX + (longitude - minLongitude) * cosLat * scaleGeo,
      offsetY + (maxLatitude - latitude) * scaleGeo,
    ],
    [offsetX, minLongitude, cosLat, scaleGeo, offsetY, maxLatitude]
  );

  // Invert projection to get Lat/Lon from canvas point
  const invertProject: InvertProject = useCallback(
    ([x, y]: Position) => {
      const lon = minLongitude + (x - offsetX) / (cosLat * scaleGeo);
      const lat = maxLatitude - (y - offsetY) / scaleGeo;
      return [lon, lat];
    },
    [minLongitude, offsetX, cosLat, scaleGeo, maxLatitude, offsetY]
  );

  const scaleBar = useMemo(() => {
    const targetPixels = 96;
    const rawDistanceKm = (targetPixels / Math.max(zoom, 0.75) / scaleGeo) * 111.32;
    const magnitude = 10 ** Math.floor(Math.log10(Math.max(rawDistanceKm, 0.001)));
    const normalized = rawDistanceKm / magnitude;
    const preferred = normalized >= 5 ? 5 : normalized >= 2 ? 2 : 1;
    const distanceKm = preferred * magnitude;
    return {
      distanceKm,
      pixels: Math.max(36, (distanceKm / rawDistanceKm) * targetPixels),
    };
  }, [scaleGeo, zoom]);

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

  const featurePositions = useMemo(() => {
    return data.features.map((feature, idx) => {
      const props = (feature.properties ?? {}) as Record<string, unknown>;
      const codId = String(props.COD_ID ?? props.id_tecnico ?? "");
      const coordinate = (longitude: unknown, latitude: unknown) =>
        typeof longitude === "number" && Number.isFinite(longitude) &&
        typeof latitude === "number" && Number.isFinite(latitude)
          ? project([longitude, latitude])
          : null;
      const fallback = calculateCentroid(feature.geometry as Geometry | undefined, project);
      return {
        codId,
        sitePoint: coordinate(props.SITE_LON, props.SITE_LAT),
        labelPoint: coordinate(props.LABEL_LON, props.LABEL_LAT) ?? fallback,
        idx,
      };
    });
  }, [data, project]);

  // View Mode Presets
  const setFlat2DMode = () => {
    setPitch(0);
    setBearing(0);
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
  };

  const setTactical3DMode = () => {
    setPitch(45);
    setBearing(-15);
    setZoom(1.1);
  };

  // Reset View handler
  const handleResetView = () => {
    setFlat2DMode();
    setHoveredId(null);
  };

  // Zoom handlers
  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 0.35, 4.5));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 0.35, 0.75));

  // Rotation handlers
  const handleRotateLeft = () => setBearing((prev) => (prev - 30) % 360);
  const handleRotateRight = () => setBearing((prev) => (prev + 30) % 360);

  // Native non-passive wheel event listener: confines zoom strictly to the map and completely prevents page scrolling
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;

    const handleNativeWheel = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();

      const delta = e.deltaY < 0 ? 0.18 : -0.18;
      setZoom((prev) => Math.max(0.75, Math.min(4.5, parseFloat((prev + delta).toFixed(2)))));
    };

    el.addEventListener("wheel", handleNativeWheel, { passive: false });
    return () => {
      el.removeEventListener("wheel", handleNativeWheel);
    };
  }, []);

  // Mouse drag handlers for fluid panning or 3D orbiting
  const handleMouseDown = (e: React.MouseEvent) => {
    const isRightClick = e.button === 2;
    const isShiftKey = e.shiftKey;
    const shouldOrbit = isRightClick || isShiftKey || dragMode === "orbit";

    setIsDragging(true);
    setDragType(shouldOrbit ? "orbit" : "pan");
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      const deltaX = e.clientX - dragStart.x;
      const deltaY = e.clientY - dragStart.y;

      if (dragType === "orbit") {
        // Orbit: Horizontal moves bearing, vertical moves pitch
        setBearing((prev) => Math.round((prev + deltaX * 0.4) % 360));
        setPitch((prev) => Math.max(0, Math.min(65, Math.round(prev - deltaY * 0.35))));
        setDragStart({ x: e.clientX, y: e.clientY });
      } else {
        // Pan
        setPan((prev) => ({
          x: prev.x + deltaX,
          y: prev.y + deltaY,
        }));
        setDragStart({ x: e.clientX, y: e.clientY });
      }
    }

    const rect = e.currentTarget.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;

    // Approximate Lat/Lon under cursor
    const scaleFactorX = rect.width > 0 ? rect.width / svgWidth : 1;
    const scaleFactorY = rect.height > 0 ? rect.height / svgHeight : 1;
    const rawSvgX = clientX / scaleFactorX;
    const rawSvgY = clientY / scaleFactorY;
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

  const isFlat2D = pitch === 0 && bearing === 0;
  const labelFontSize = Math.max(3.5, Math.min(8.5, 8.5 / Math.max(zoom, 0.75)));
  const showMapLabels = showLabels && zoom >= 0.85;
  const activeSubstation = hoveredId ? subMap.get(hoveredId) : (selectedId ? subMap.get(selectedId) : null);

  const handleToggleExpand = () => {
    if (isModalView) {
      onCloseModal?.();
    } else if (onOpenModal) {
      onOpenModal();
    } else {
      setInternalModalOpen(true);
    }
  };

  if (!positions.length) {
    return (
      <div className="flex h-64 items-center justify-center rounded-2xl border border-grid-graphite-light bg-grid-surface text-sm text-grid-gray">
        Nenhuma geometria válida disponível na carga atual.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`relative overflow-hidden transition-all ${
        isModalView
          ? "h-full w-full flex flex-col rounded-none border-0 bg-transparent"
          : "rounded-3xl border border-grid-graphite-light bg-grid-surface double-bezel"
      }`}
    >
      {/* HUD Header Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-grid-border-subtle bg-grid-surface/95 px-4 py-3 text-xs backdrop-blur-md">
        {/* Left: Title & Mode Toggle */}
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="h-2 w-2 rounded-full bg-grid-yellow energy-glow" />
          <strong className="font-display font-semibold text-white tracking-wide uppercase text-xs">
            Mapeamento Territorial Geoespacial
          </strong>

          {/* Perspective Preset Switcher: 2D Plano (Default) vs 3D Tático */}
          <div className="flex items-center gap-1 rounded-xl border border-grid-surface-border bg-grid-surface-elevated p-0.5 font-mono text-[0.68rem] ml-2">
            <button
              type="button"
              onClick={setFlat2DMode}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 transition-all ${
                isFlat2D
                  ? "bg-grid-yellow font-bold text-black energy-glow"
                  : "text-grid-gray hover:text-white"
              }`}
              title="Visão 2D Ortogonal Plana (Padrão Geográfico)"
            >
              <GlobeHemisphereWest size={13} />
              <span>2D Plano (Padrão)</span>
            </button>

            <button
              type="button"
              onClick={setTactical3DMode}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 transition-all ${
                !isFlat2D
                  ? "bg-grid-yellow font-bold text-black energy-glow"
                  : "text-grid-gray hover:text-white"
              }`}
              title="Inclinar Mapa em Perspectiva 3D Tática"
            >
              <Cube size={13} />
              <span>3D Tático</span>
            </button>
          </div>

          {/* Drag Mode Selector: Pan vs Orbit */}
          <button
            type="button"
            onClick={() => setDragMode(dragMode === "pan" ? "orbit" : "pan")}
            className={`flex items-center gap-1.5 rounded-lg border px-2 py-1 font-mono text-[0.66rem] transition-colors ${
              dragMode === "orbit"
                ? "border-grid-yellow/50 bg-grid-yellow/15 text-grid-yellow"
                : "border-grid-surface-border bg-grid-surface-elevated text-grid-gray hover:text-white"
            }`}
            title="Alternar função do clique principal entre Mover (Pan) ou Rotacionar/Inclinar (Órbita 3D)"
          >
            {dragMode === "orbit" ? <Repeat size={13} /> : <HandGrabbing size={13} />}
            <span>Modo: {dragMode === "orbit" ? "Órbita 3D" : "Mover (Pan)"}</span>
          </button>
        </div>

        {/* Center: Theme Selector Pills */}
        <div className="flex items-center gap-1 rounded-xl border border-grid-graphite-light bg-grid-surface-raised p-1 font-mono text-[0.66rem]">
          <button
            type="button"
            onClick={() => setThemeMode("criticality")}
            className={`rounded-lg px-2 py-1 transition-all ${
              themeMode === "criticality"
                ? "bg-grid-yellow font-bold text-black energy-glow"
                : "text-grid-gray hover:text-white"
            }`}
          >
            Criticidade
          </button>
          <button
            type="button"
            onClick={() => setThemeMode("gd_power")}
            className={`rounded-lg px-2 py-1 transition-all ${
              themeMode === "gd_power"
                ? "bg-grid-yellow font-bold text-black energy-glow"
                : "text-grid-gray hover:text-white"
            }`}
          >
            Calor GD (kW)
          </button>
          <button
            type="button"
            onClick={() => setThemeMode("consumption")}
            className={`rounded-lg px-2 py-1 transition-all ${
              themeMode === "consumption"
                ? "bg-grid-yellow font-bold text-black energy-glow"
                : "text-grid-gray hover:text-white"
            }`}
          >
            Consumo (MWh)
          </button>
          <button
            type="button"
            onClick={() => setThemeMode("clients")}
            className={`rounded-lg px-2 py-1 transition-all ${
              themeMode === "clients"
                ? "bg-grid-yellow font-bold text-black energy-glow"
                : "text-grid-gray hover:text-white"
            }`}
          >
            Clientes
          </button>
        </div>

        {/* Right: Zoom & Perspective Navigation Tools */}
        <div className="flex items-center gap-2">
          {/* Quick Search Input */}
          <div className="relative">
            <MagnifyingGlass size={13} className="pointer-events-none absolute left-2.5 top-2 text-grid-gray-muted" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Localizar zona..."
              className="w-28 sm:w-36 rounded-lg border border-grid-border bg-grid-surface-elevated py-1 pl-7 pr-2 font-mono text-[0.7rem] text-white placeholder:text-grid-gray-dim outline-none focus:border-grid-yellow"
            />
          </div>

          {/* Toggle Labels */}
          <button
            type="button"
            onClick={() => setShowLabels(!showLabels)}
            className={`flex items-center gap-1 rounded-lg border px-2 py-1 font-mono text-[0.68rem] transition-colors ${
              showLabels
                ? "border-grid-yellow/40 bg-grid-yellow/10 text-grid-yellow"
                : "border-grid-surface-border bg-grid-surface-elevated text-grid-gray"
            }`}
            title="Alternar Rótulos de Nomes"
          >
            {showLabels ? <Eye size={13} /> : <EyeSlash size={13} />}
            <span>Rótulos</span>
          </button>

          {/* 3D Rotation Controls */}
          <div className="flex items-center rounded-lg border border-grid-surface-border bg-grid-surface-elevated p-0.5">
            <button
              type="button"
              onClick={handleRotateLeft}
              className="px-1.5 py-1 text-grid-gray hover:text-white transition-colors font-mono text-[0.68rem]"
              title="Girar 30° para a Esquerda"
            >
              ↺
            </button>
            <button
              type="button"
              onClick={handleRotateRight}
              className="px-1.5 py-1 text-grid-gray hover:text-white transition-colors font-mono text-[0.68rem] border-l border-grid-surface-border"
              title="Girar 30° para a Direita"
            >
              ↻
            </button>
          </div>

          {/* Zoom Controls */}
          <div className="flex items-center rounded-lg border border-grid-surface-border bg-grid-surface-elevated p-0.5">
            <button
              type="button"
              onClick={handleZoomIn}
              className="p-1 text-grid-gray hover:text-white transition-colors"
              title="Aproximar Zoom (+)"
            >
              <MagnifyingGlassPlus size={15} />
            </button>
            <button
              type="button"
              onClick={handleZoomOut}
              className="p-1 text-grid-gray hover:text-white transition-colors"
              title="Afastar Zoom (-)"
            >
              <MagnifyingGlassMinus size={15} />
            </button>
            <button
              type="button"
              onClick={handleResetView}
              className="p-1 text-grid-gray hover:text-grid-yellow transition-colors border-l border-grid-surface-border"
              title="Redefinir Visão (2D Plano, Centro)"
            >
              <ArrowsCounterClockwise size={14} />
            </button>
          </div>

          {/* Modal / Fullscreen Expand Button */}
          <button
            type="button"
            onClick={handleToggleExpand}
            className="flex h-7 w-7 items-center justify-center rounded-lg border border-grid-surface-border bg-grid-surface-elevated text-grid-gray hover:border-grid-yellow hover:text-grid-yellow transition-colors"
            title={isModalView ? "Fechar Vista Expandida" : "Expandir Mapa em Tela Cheia (Modal)"}
          >
            {isModalView ? <ArrowsIn size={15} /> : <ArrowsOut size={15} />}
          </button>
        </div>
      </div>

      {/* 3D Perspective Viewport (Hardware Accelerated) */}
      <div
        ref={viewportRef}
        className={`relative select-none overflow-hidden overscroll-contain ${
          isModalView ? "flex-1 min-h-0 w-full" : "h-[480px] md:h-[560px]"
        } ${isDragging ? (dragType === "orbit" ? "cursor-grab" : "cursor-grabbing") : "cursor-crosshair"}`}
        style={{
          perspective: "1200px",
          perspectiveOrigin: "50% 50%",
          overscrollBehavior: "contain",
          touchAction: "none",
        }}
        onContextMenu={(e) => e.preventDefault()}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => {
          handleMouseUp();
          setHoveredId(null);
          setCursorGeo(null);
        }}
      >
        {/* 3D Atmospheric Horizon Fog Vignette (Softens the horizon into deep black in 3D mode) */}
        {!isFlat2D && (
          <div
            className="pointer-events-none absolute inset-x-0 top-0 h-32 z-10 transition-opacity duration-500"
            style={{
              background:
                "linear-gradient(to bottom, rgba(5, 5, 5, 1) 0%, rgba(5, 5, 5, 0.85) 35%, rgba(5, 5, 5, 0.4) 65%, rgba(5, 5, 5, 0) 100%)",
            }}
          />
        )}

        {/* Tactical HUD Overlay (Fixed 2D layer, never tilted by 3D transforms) */}
        <div className="pointer-events-none absolute inset-0 z-20">
          {/* Tactical Corner Reticles: ONLY shown in 2D mode so 3D mode stays visually infinite without box borders */}
          {isFlat2D && (
            <>
              <svg className="absolute top-3.5 left-3.5 h-5 w-5 text-grid-yellow" viewBox="0 0 20 20" fill="none">
                <path d="M 0 16 L 0 0 L 16 0" stroke="currentColor" strokeWidth="2.5" />
              </svg>
              <svg className="absolute top-3.5 right-3.5 h-5 w-5 text-grid-yellow" viewBox="0 0 20 20" fill="none">
                <path d="M 20 16 L 20 0 L 4 0" stroke="currentColor" strokeWidth="2.5" />
              </svg>
              <svg className="absolute bottom-3.5 left-3.5 h-5 w-5 text-grid-yellow" viewBox="0 0 20 20" fill="none">
                <path d="M 0 4 L 0 20 L 16 20" stroke="currentColor" strokeWidth="2.5" />
              </svg>
              <svg className="absolute bottom-3.5 right-3.5 h-5 w-5 text-grid-yellow" viewBox="0 0 20 20" fill="none">
                <path d="M 20 4 L 20 20 L 4 20" stroke="currentColor" strokeWidth="2.5" />
              </svg>
            </>
          )}

          {/* Compass Rose / North Indicator - Always crisp 2D HUD widget pointing to North */}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setFlat2DMode();
            }}
            className="pointer-events-auto absolute top-3.5 right-3.5 flex h-9 w-9 items-center justify-center rounded-full border border-grid-border-card bg-grid-surface/90 shadow-xl backdrop-blur-md transition-all hover:border-grid-yellow hover:scale-105 active:scale-95"
            title="Clique para alinhar ao Norte e retornar ao modo 2D Plano"
          >
            <div
              className="relative flex items-center justify-center transition-transform duration-300"
              style={{ transform: `rotate(${-bearing}deg)` }}
            >
              <svg width="24" height="24" viewBox="-12 -12 24 24">
                <polygon points="0,-10 3,0 0,2.5 -3,0" fill={THEME_COLORS.brand.yellow} />
                <polygon points="0,10 3,0 0,-2.5 -3,0" fill={THEME_COLORS.text.placeholder} />
                <text x="0" y="-10.5" textAnchor="middle" fill={THEME_COLORS.brand.yellow} className="font-mono text-[6.5px] font-bold">
                  N
                </text>
              </svg>
            </div>
          </button>

          {/* Graphic Scale Bar in HUD */}
          <div
            className="absolute bottom-3.5 left-4 flex flex-col gap-0.5 font-mono text-[9px] text-grid-gray"
            aria-label={`Escala aproximada: ${formatDistanceKm(scaleBar.distanceKm)}`}
            style={{ width: scaleBar.pixels }}
          >
            <div className="flex w-full items-center justify-between text-[8px]">
              <span>0</span>
              <span>{formatDistanceKm(scaleBar.distanceKm / 2)}</span>
              <span>{formatDistanceKm(scaleBar.distanceKm)}</span>
            </div>
            <div className="flex h-1.5 w-full border border-grid-border-strong bg-grid-surface-raised/90">
              <div className="w-1/2 bg-grid-yellow/50 border-r border-grid-border-strong" />
              <div className="w-1/2 bg-transparent" />
            </div>
          </div>
        </div>

        {/* Transforming 3D / 2D Canvas Wrapper */}
        <div
          className="w-full h-full"
          style={{
            transform: `rotateX(${pitch}deg) rotateZ(${bearing}deg)`,
            transformStyle: "preserve-3d",
            overflow: "visible",
            transition: isDragging ? "none" : "transform 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
          }}
        >
          <svg
            aria-label="Mapa territorial geoespacial interativo"
            className="h-full w-full select-none block overflow-visible"
            style={{ overflow: "visible" }}
            preserveAspectRatio="none"
            role="img"
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          >
            <defs>
              {/* Tone-Preserving Glow Filters */}
              <filter id="glowNormal" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor={THEME_COLORS.status.success} floodOpacity="0.65" />
              </filter>
              <filter id="glowAttention" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor={THEME_COLORS.status.warning} floodOpacity="0.70" />
              </filter>
              <filter id="glowCritical" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow dx="0" dy="0" stdDeviation="6" floodColor={THEME_COLORS.status.danger} floodOpacity="0.80" />
              </filter>
              <filter id="glowInfo" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor={THEME_COLORS.status.info} floodOpacity="0.65" />
              </filter>
              <filter id="glowYellow" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor={THEME_COLORS.brand.yellow} floodOpacity="0.65" />
              </filter>
              <filter id="territoryGlow" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor={THEME_COLORS.brand.yellow} floodOpacity="0.6" />
              </filter>

              {/* Infinite World Tactical Ground Grid Pattern */}
              {/* Anchored to world coordinates (patternUnits="userSpaceOnUse") so it stays fixed to the map */}
              <pattern
                id="worldTacticalGrid"
                width="60"
                height="60"
                patternUnits="userSpaceOnUse"
              >
                {/* Secondary sub-grid lines 20px */}
                <path
                  d="M 20 0 L 20 60 M 40 0 L 40 60 M 0 20 L 60 20 M 0 40 L 60 40"
                  stroke={THEME_COLORS.surface.elevatedAlt}
                  strokeWidth="0.8"
                  fill="none"
                />
                {/* Primary grid lines 60px */}
                <path
                  d="M 60 0 L 0 0 0 60"
                  stroke={THEME_COLORS.border.default}
                  strokeWidth="1.2"
                  fill="none"
                />
                {/* CAD-style corner tick at intersections */}
                <path
                  d="M -3 0 L 3 0 M 0 -3 L 0 3"
                  stroke={THEME_COLORS.brand.yellow}
                  strokeOpacity="0.28"
                  strokeWidth="1.2"
                />
              </pattern>

              {/* Radial Horizon Distance Fade for Infinite Ground Plane */}
              {/* Centered at camera optical focal center (camWorldX, camWorldY) */}
              <radialGradient
                id="groundHorizonFade"
                cx={camWorldX}
                cy={camWorldY}
                r={groundRadius * 0.7}
                gradientUnits="userSpaceOnUse"
              >
                <stop offset="0%" stopColor={THEME_COLORS.text.white} stopOpacity="0.95" />
                <stop offset="25%" stopColor={THEME_COLORS.text.white} stopOpacity="0.85" />
                <stop offset="50%" stopColor={THEME_COLORS.text.white} stopOpacity="0.5" />
                <stop offset="70%" stopColor={THEME_COLORS.text.white} stopOpacity="0.2" />
                <stop offset="88%" stopColor={THEME_COLORS.text.white} stopOpacity="0.04" />
                <stop offset="100%" stopColor={THEME_COLORS.surface.black} stopOpacity="0" />
              </radialGradient>

              {/* Mask for Infinite Ground Plane Fade */}
              <mask id="groundHorizonFadeMask" maskUnits="userSpaceOnUse">
                <rect
                  x={groundX}
                  y={groundY}
                  width={groundSize}
                  height={groundSize}
                  fill="url(#groundHorizonFade)"
                />
              </mask>
            </defs>

            {/* Interactive Zoom/Pan Transform Group */}
            <g
              transform={`translate(${svgWidth / 2 + pan.x}, ${svgHeight / 2 + pan.y}) scale(${zoom}) translate(${-svgWidth / 2}, ${-svgHeight / 2})`}
              className="transition-transform duration-75 ease-out"
            >
              {/* Infinite Ground Floor Surface (Subtle dark surface fading into horizon) */}
              <rect
                x={groundX}
                y={groundY}
                width={groundSize}
                height={groundSize}
                fill={THEME_COLORS.surface.surfaceModal}
                mask="url(#groundHorizonFadeMask)"
              />

              {/* Infinite Tactical CAD/GIS Ground Grid (Orthogonal perspective grid anchored to world coordinates) */}
              <rect
                x={groundX}
                y={groundY}
                width={groundSize}
                height={groundSize}
                fill="url(#worldTacticalGrid)"
                mask="url(#groundHorizonFadeMask)"
              />
              {/* Voronoi Territory Polygons */}
              {data.features.map((feature, index) => {
                const props = (feature.properties ?? {}) as Record<string, unknown>;
                const codId = String(props.COD_ID ?? props.id_tecnico ?? "");
                const name = String(props.NOM ?? props.NOME ?? `Zona ${index + 1}`);
                const path = geometryPath(feature.geometry as Geometry | undefined, project);
                if (!path) return null;

                const sub = subMap.get(codId);
                const hasMetrics = Boolean(sub);
                const critStr = sub?.metricas_rede.nivel_criticidade_gd.toUpperCase() ?? "";
                const isCritical = critStr.includes("CRÍT") || critStr.includes("CRIT");
                const isAttention = critStr.includes("ATEN") || critStr.includes("MÉD") || critStr.includes("MED");
                const isNormal = hasMetrics && !isCritical && !isAttention;
                const isHovered = hoveredId === codId;
                const isSelected = selectedId === codId;

                // Filter out if statusFilter doesn't match
                if (statusFilter === "normal" && !isNormal) return null;
                if (statusFilter === "attention" && !isAttention) return null;
                if (statusFilter === "critical" && !isCritical) return null;

                // Search query highlight
                const matchesSearch =
                  searchQuery.trim().length > 0 &&
                  (name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                    codId.includes(searchQuery));

                // Compute Theme Fill & Stroke with Tone-Preserving Interaction Highlights
                let fill: string = THEME_COLORS.surface.raised;
                let stroke: string = THEME_COLORS.border.surface;
                let strokeWidth = 1.0 / zoom;
                let strokeDasharray: string | undefined;
                let glowFilterId: string | undefined;

                if (!hasMetrics) {
                  strokeDasharray = `${4 / zoom} ${3 / zoom}`;
                  if (isSelected) {
                    fill = "rgba(148, 163, 184, 0.32)";
                    stroke = "#CBD5E1";
                    strokeWidth = 2.4 / zoom;
                  } else if (isHovered) {
                    fill = "rgba(148, 163, 184, 0.22)";
                    stroke = "rgba(148, 163, 184, 0.85)";
                    strokeWidth = 2.0 / zoom;
                  } else {
                    fill = "rgba(148, 163, 184, 0.08)";
                    stroke = "rgba(148, 163, 184, 0.48)";
                  }
                } else if (themeMode === "criticality") {
                  if (isCritical) {
                    if (isSelected) {
                      glowFilterId = "glowCritical";
                      fill = "rgba(239, 68, 68, 0.48)";
                      stroke = THEME_COLORS.status.danger;
                      strokeWidth = 2.8 / zoom;
                    } else if (isHovered) {
                      glowFilterId = "glowCritical";
                      fill = "rgba(239, 68, 68, 0.38)";
                      stroke = THEME_COLORS.status.danger;
                      strokeWidth = 2.4 / zoom;
                    } else if (matchesSearch) {
                      fill = "rgba(239, 68, 68, 0.40)";
                      stroke = THEME_COLORS.status.danger;
                      strokeWidth = 2.2 / zoom;
                    } else {
                      fill = "rgba(239, 68, 68, 0.25)";
                      stroke = THEME_COLORS.status.danger;
                      strokeWidth = 1.6 / zoom;
                    }
                  } else if (isAttention) {
                    if (isSelected) {
                      glowFilterId = "glowAttention";
                      fill = "rgba(245, 158, 11, 0.46)";
                      stroke = THEME_COLORS.status.warning;
                      strokeWidth = 2.6 / zoom;
                    } else if (isHovered) {
                      glowFilterId = "glowAttention";
                      fill = "rgba(245, 158, 11, 0.36)";
                      stroke = THEME_COLORS.status.warning;
                      strokeWidth = 2.3 / zoom;
                    } else if (matchesSearch) {
                      fill = "rgba(245, 158, 11, 0.38)";
                      stroke = THEME_COLORS.status.warning;
                      strokeWidth = 2.0 / zoom;
                    } else {
                      fill = "rgba(245, 158, 11, 0.22)";
                      stroke = THEME_COLORS.status.warning;
                      strokeWidth = 1.3 / zoom;
                    }
                  } else {
                    // Normal: intensifica o tom verde na interação
                    if (isSelected) {
                      glowFilterId = "glowNormal";
                      fill = "rgba(34, 197, 94, 0.40)";
                      stroke = THEME_COLORS.status.success;
                      strokeWidth = 2.6 / zoom;
                    } else if (isHovered) {
                      glowFilterId = "glowNormal";
                      fill = "rgba(34, 197, 94, 0.28)";
                      stroke = THEME_COLORS.status.success;
                      strokeWidth = 2.2 / zoom;
                    } else if (matchesSearch) {
                      fill = "rgba(34, 197, 94, 0.30)";
                      stroke = THEME_COLORS.status.success;
                      strokeWidth = 2.0 / zoom;
                    } else {
                      fill = "rgba(34, 197, 94, 0.09)";
                      stroke = "rgba(34, 197, 94, 0.40)";
                      strokeWidth = 1.0 / zoom;
                    }
                  }
                } else if (themeMode === "gd_power") {
                  const gdVal = sub?.geracao_distribuida.potencia_total_kw ?? 0;
                  const ratio = Math.min(1.0, gdVal / maxGdPower);
                  if (isSelected) {
                    glowFilterId = "glowYellow";
                    fill = "rgba(255, 212, 0, 0.50)";
                    stroke = THEME_COLORS.brand.yellow;
                    strokeWidth = 2.8 / zoom;
                  } else if (isHovered) {
                    glowFilterId = "glowYellow";
                    fill = "rgba(255, 212, 0, 0.40)";
                    stroke = THEME_COLORS.brand.yellow;
                    strokeWidth = 2.4 / zoom;
                  } else if (matchesSearch) {
                    fill = "rgba(255, 212, 0, 0.42)";
                    stroke = THEME_COLORS.brand.yellow;
                    strokeWidth = 2.2 / zoom;
                  } else {
                    const alpha = (0.06 + ratio * 0.45).toFixed(2);
                    fill = `rgba(255, 212, 0, ${alpha})`;
                    stroke = ratio > 0.4 ? THEME_COLORS.brand.yellow : "rgba(255, 212, 0, 0.35)";
                  }
                } else if (themeMode === "consumption") {
                  const consVal = sub?.metricas_rede.consumo_anual_mwh ?? 0;
                  const ratio = Math.min(1.0, consVal / maxConsumption);
                  if (isSelected) {
                    glowFilterId = "glowInfo";
                    fill = "rgba(59, 130, 246, 0.48)";
                    stroke = THEME_COLORS.status.info;
                    strokeWidth = 2.8 / zoom;
                  } else if (isHovered) {
                    glowFilterId = "glowInfo";
                    fill = "rgba(59, 130, 246, 0.38)";
                    stroke = THEME_COLORS.status.info;
                    strokeWidth = 2.4 / zoom;
                  } else if (matchesSearch) {
                    fill = "rgba(59, 130, 246, 0.40)";
                    stroke = THEME_COLORS.status.info;
                    strokeWidth = 2.2 / zoom;
                  } else {
                    const alpha = (0.06 + ratio * 0.40).toFixed(2);
                    fill = `rgba(59, 130, 246, ${alpha})`;
                    stroke = ratio > 0.4 ? THEME_COLORS.status.info : "rgba(59, 130, 246, 0.35)";
                  }
                } else if (themeMode === "clients") {
                  const cliVal = sub?.metricas_rede.total_clientes ?? 0;
                  const ratio = Math.min(1.0, cliVal / maxClients);
                  if (isSelected) {
                    glowFilterId = "glowNormal";
                    fill = "rgba(34, 197, 94, 0.48)";
                    stroke = THEME_COLORS.status.success;
                    strokeWidth = 2.8 / zoom;
                  } else if (isHovered) {
                    glowFilterId = "glowNormal";
                    fill = "rgba(34, 197, 94, 0.38)";
                    stroke = THEME_COLORS.status.success;
                    strokeWidth = 2.4 / zoom;
                  } else if (matchesSearch) {
                    fill = "rgba(34, 197, 94, 0.40)";
                    stroke = THEME_COLORS.status.success;
                    strokeWidth = 2.2 / zoom;
                  } else {
                    const alpha = (0.06 + ratio * 0.40).toFixed(2);
                    fill = `rgba(34, 197, 94, ${alpha})`;
                    stroke = ratio > 0.4 ? THEME_COLORS.status.success : "rgba(34, 197, 94, 0.35)";
                  }
                }

                return (
                  <g key={codId || `${name}-${index}`}>
                    <path
                      d={path}
                      fillRule="evenodd"
                      clipRule="evenodd"
                      fill={fill}
                      stroke={stroke}
                      strokeWidth={strokeWidth}
                      strokeDasharray={strokeDasharray}
                      strokeLinejoin="round"
                      className="transition-colors duration-150 cursor-pointer"
                      onMouseEnter={() => setHoveredId(codId)}
                      onClick={() => {
                        if (onSelectSubstation && codId) onSelectSubstation(codId);
                      }}
                      filter={glowFilterId ? `url(#${glowFilterId})` : undefined}
                    >
                      <title>{`${name} (ID: ${codId})${hasMetrics ? "" : " — sem métricas neste município"}`}</title>
                    </path>
                  </g>
                );
              })}

              {/* Physical substation pins & territory labels overlay */}
              {data.features.map((feature, index) => {
                const props = (feature.properties ?? {}) as Record<string, unknown>;
                const codId = String(props.COD_ID ?? props.id_tecnico ?? "");
                const name = String(props.NOM ?? props.NOME ?? `Zona ${index + 1}`).replace("SUBESTACAO", "SE");
                const { sitePoint, labelPoint } = featurePositions[index] ?? {};
                if (!sitePoint && !labelPoint) return null;

                const sub = subMap.get(codId);
                const critStr = sub?.metricas_rede.nivel_criticidade_gd.toUpperCase() ?? "";
                const isCritical = critStr.includes("CRÍT") || critStr.includes("CRIT");
                const isAttention = critStr.includes("ATEN") || critStr.includes("MÉD") || critStr.includes("MED");
                const isHovered = hoveredId === codId;
                const isSelected = selectedId === codId;

                // Determine tone-specific color for pins & labels that intensifies on interaction
                let pinColor: string = THEME_COLORS.text.placeholder;
                let labelHighlightColor: string = THEME_COLORS.text.white;

                if (themeMode === "criticality") {
                  if (isCritical) {
                    pinColor = isHovered || isSelected ? "#F87171" : THEME_COLORS.status.danger;
                    labelHighlightColor = "#F87171";
                  } else if (isAttention) {
                    pinColor = isHovered || isSelected ? "#FBBF24" : THEME_COLORS.status.warning;
                    labelHighlightColor = "#FBBF24";
                  } else if (sub) {
                    pinColor = isHovered || isSelected ? "#4ADE80" : THEME_COLORS.status.success;
                    labelHighlightColor = "#4ADE80";
                  }
                } else if (themeMode === "consumption") {
                  pinColor = isHovered || isSelected ? "#60A5FA" : THEME_COLORS.status.info;
                  labelHighlightColor = "#60A5FA";
                } else if (themeMode === "clients") {
                  pinColor = isHovered || isSelected ? "#4ADE80" : THEME_COLORS.status.success;
                  labelHighlightColor = "#4ADE80";
                } else if (themeMode === "gd_power") {
                  pinColor = isHovered || isSelected ? "#FFE033" : THEME_COLORS.brand.yellow;
                  labelHighlightColor = THEME_COLORS.brand.yellow;
                } else if (sub) {
                  pinColor = THEME_COLORS.text.white;
                  labelHighlightColor = THEME_COLORS.text.white;
                }

                return (
                  <g
                    key={`pin-${codId}-${index}`}
                    className="pointer-events-none"
                  >
                    {showNodes && sitePoint && (
                      <g transform={`translate(${sitePoint[0]}, ${sitePoint[1]})`}>
                        {/* Pulse Ring when Active */}
                        {(isHovered || isSelected || isCritical || isAttention) && (
                          <circle
                            r={(isHovered || isSelected ? 11 : isCritical ? 10 : 8) / Math.sqrt(zoom)}
                            fill="none"
                            stroke={pinColor}
                            strokeWidth={1.5 / zoom}
                            opacity={isHovered || isSelected ? 0.95 : isCritical ? 0.85 : 0.65}
                          />
                        )}
                        {/* Core Dot */}
                        <circle
                          r={(isHovered || isSelected ? 5.2 : 3.8) / Math.sqrt(zoom)}
                          fill={pinColor}
                          stroke={THEME_COLORS.surface.black}
                          strokeWidth={1.2 / zoom}
                        />
                      </g>
                    )}

                    {/* Clean Map Label */}
                    {showMapLabels && labelPoint && (
                      <g transform={`translate(${labelPoint[0]}, ${labelPoint[1]})`}>
                        <text
                          textAnchor="middle"
                          className="select-none font-mono font-bold tracking-tight"
                          style={{
                            fontSize: `${labelFontSize}px`,
                            fill: isHovered || isSelected ? labelHighlightColor : THEME_COLORS.text.subtle,
                            textShadow: "0 1px 3px rgba(0,0,0,0.95)",
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

          </svg>
        </div>

        {/* Floating Active Substation HUD Card */}
        {activeSubstation && (() => {
          const actCrit = activeSubstation.metricas_rede.nivel_criticidade_gd.toUpperCase();
          const isActCrit = actCrit.includes("CRÍT") || actCrit.includes("CRIT");
          const isActAttn = actCrit.includes("ATEN") || actCrit.includes("MÉD") || actCrit.includes("MED");

          const hudBorder = isActCrit
            ? "border-status-danger/50 shadow-[0_0_25px_rgba(239,68,68,0.22)]"
            : isActAttn
              ? "border-status-warning/50 shadow-[0_0_25px_rgba(245,158,11,0.22)]"
              : "border-status-success/50 shadow-[0_0_25px_rgba(34,197,94,0.18)]";

          const hudIdColor = isActCrit
            ? "text-status-danger"
            : isActAttn
              ? "text-status-warning"
              : "text-status-success";

          return (
            <div
              className={`absolute bottom-4 right-4 z-30 min-w-[280px] max-w-[340px] rounded-2xl border ${hudBorder} bg-grid-surface/95 p-4 shadow-2xl backdrop-blur-xl animate-in fade-in slide-in-from-bottom-2 duration-200`}
            >
              <div className="flex items-start justify-between gap-2 border-b border-grid-graphite-light pb-2 mb-2.5">
                <div>
                  <span className="font-mono text-[0.65rem] text-grid-gray block">
                    SUBESTAÇÃO DETECTADA
                  </span>
                  <strong className="font-display text-sm font-bold text-white block">
                    {activeSubstation.subestacao.split(" (ID:")[0]}
                  </strong>
                  <span className={`font-mono text-[0.68rem] ${hudIdColor}`}>
                    ID Técnico: {activeSubstation.id_tecnico}
                  </span>
                </div>
                <StatusPill
                  label={activeSubstation.metricas_rede.nivel_criticidade_gd}
                  size="sm"
                />
              </div>

            <div className="grid grid-cols-3 gap-2 font-mono text-center">
              <div className="rounded-lg border border-grid-border-subtle bg-grid-surface-raised p-1.5">
                <span className="block text-[0.62rem] text-grid-gray">POTÊNCIA GD</span>
                <strong className="block text-xs font-bold text-grid-yellow mt-0.5">
                  {activeSubstation.geracao_distribuida.potencia_total_kw.toLocaleString("pt-BR", {
                    maximumFractionDigits: 1,
                  })}{" "}
                  <span className="text-[0.6rem] font-normal text-grid-gray">kW</span>
                </strong>
              </div>

              <div className="rounded-lg border border-grid-border-subtle bg-grid-surface-raised p-1.5">
                <span className="block text-[0.62rem] text-grid-gray">CONSUMO</span>
                <strong className="block text-xs font-bold text-white mt-0.5">
                  {activeSubstation.metricas_rede.consumo_anual_mwh.toLocaleString("pt-BR", {
                    maximumFractionDigits: 0,
                  })}{" "}
                  <span className="text-[0.6rem] font-normal text-grid-gray">MWh</span>
                </strong>
              </div>

              <div className="rounded-lg border border-grid-border-subtle bg-grid-surface-raised p-1.5">
                <span className="block text-[0.62rem] text-grid-gray">CLIENTES</span>
                <strong className="block text-xs font-bold text-white mt-0.5">
                  {activeSubstation.metricas_rede.total_clientes.toLocaleString("pt-BR")}
                </strong>
              </div>
            </div>

            {/* Quick Inspection Action */}
            <button
              type="button"
              onClick={() => onSelectSubstation && onSelectSubstation(activeSubstation.id_tecnico)}
              className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-xl border border-grid-yellow/40 bg-grid-yellow/10 py-2 font-mono text-xs font-bold text-grid-yellow transition-colors hover:bg-grid-yellow/20"
            >
              <span>Abrir Telemetria do Ativo</span>
              <ArrowSquareOut size={14} />
            </button>
          </div>
        );
      })()}
    </div>

      {/* Footer Status Bar with Live Coordinates & Legend */}
      <div className="flex flex-wrap items-center justify-between border-t border-grid-border-subtle bg-grid-surface px-4 py-2.5 text-[0.7rem] font-mono text-grid-gray">
        {/* Live Coordinate Crosshair Readout */}
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1 text-grid-gray-subtle">
            <Compass size={14} className="text-grid-yellow" />
            <span>
              {cursorGeo
                ? `LAT: ${cursorGeo.lat.toFixed(4)}° | LON: ${cursorGeo.lon.toFixed(4)}°`
                : "POSICIONE O CURSOR SOBRE O MAPA"}
            </span>
          </span>
          <span className="text-grid-border-strong">|</span>
          <span className="text-grid-gray-muted">
            {isFlat2D ? "2D Plano (Ortogonal)" : `3D Tático (${pitch}° inclinação · ${bearing}° azimute)`} · Zoom: {(zoom * 100).toFixed(0)}%
          </span>
        </div>

        {/* Dynamic Legend based on active Theme */}
        <div className="flex items-center gap-4">
          {themeMode === "criticality" && (
            <>
              <button
                type="button"
                onClick={() => setStatusFilter((prev) => (prev === "normal" ? "all" : "normal"))}
                className={`flex items-center gap-1.5 rounded px-1.5 py-0.5 font-mono text-[0.68rem] transition-colors ${
                  statusFilter === "normal"
                    ? "bg-status-success/20 text-status-success ring-1 ring-status-success"
                    : "text-status-success/90 hover:text-status-success"
                }`}
                title="Filtrar por Normal"
              >
                <span className="h-2 w-3 rounded-sm border border-status-success/70 bg-status-success/25" />
                Normal
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter((prev) => (prev === "attention" ? "all" : "attention"))}
                className={`flex items-center gap-1.5 rounded px-1.5 py-0.5 font-mono text-[0.68rem] transition-colors ${
                  statusFilter === "attention"
                    ? "bg-status-warning/20 text-status-warning ring-1 ring-status-warning"
                    : "text-status-warning/90 hover:text-status-warning"
                }`}
                title="Filtrar por Médio / Atenção"
              >
                <span className="h-2 w-3 rounded-sm border border-status-warning bg-status-warning/30" />
                Médio
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter((prev) => (prev === "critical" ? "all" : "critical"))}
                className={`flex items-center gap-1.5 rounded px-1.5 py-0.5 font-mono text-[0.68rem] transition-colors ${
                  statusFilter === "critical"
                    ? "bg-status-danger/20 text-status-danger ring-1 ring-status-danger"
                    : "text-status-danger/90 hover:text-status-danger"
                }`}
                title="Filtrar por Crítico"
              >
                <span className="h-2 w-3 rounded-sm border border-status-danger bg-status-danger/30" />
                Crítico
              </button>
              <span className="flex items-center gap-1.5 text-grid-gray text-[0.68rem]">
                <span className="h-2 w-3 rounded-sm border border-dashed border-grid-gray/50 bg-grid-gray/10" />
                Sem métricas
              </span>
              {statusFilter !== "all" && (
                <button
                  type="button"
                  onClick={() => setStatusFilter("all")}
                  className="rounded bg-grid-surface-elevated border border-grid-border px-1.5 py-0.5 text-[0.65rem] text-grid-yellow hover:text-white"
                  title="Limpar filtro de criticidade"
                >
                  Exibir Todas
                </button>
              )}
            </>
          )}

          {themeMode === "gd_power" && (
            <div className="flex items-center gap-2">
              <span>0 kW</span>
              <div className="h-2 w-20 rounded-full bg-gradient-to-r from-grid-surface-elevated via-grid-yellow/40 to-grid-yellow" />
              <span className="text-grid-yellow font-bold">
                {maxGdPower.toLocaleString("pt-BR", { maximumFractionDigits: 0 })} kW
              </span>
            </div>
          )}

          {themeMode === "consumption" && (
            <div className="flex items-center gap-2">
              <span>0 MWh</span>
              <div className="h-2 w-20 rounded-full bg-gradient-to-r from-grid-surface-elevated via-status-info/40 to-status-info" />
              <span className="text-status-info font-bold">
                {maxConsumption.toLocaleString("pt-BR", { maximumFractionDigits: 0 })} MWh
              </span>
            </div>
          )}

          {themeMode === "clients" && (
            <div className="flex items-center gap-2">
              <span>0 UCs</span>
              <div className="h-2 w-20 rounded-full bg-gradient-to-r from-grid-surface-elevated via-status-success/40 to-status-success" />
              <span className="text-status-success font-bold">
                {maxClients.toLocaleString("pt-BR")} UCs
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Dedicated Fullscreen Map Modal */}
      {!isModalView && (
        <TerritoryMapModal
          isOpen={internalModalOpen}
          onClose={() => setInternalModalOpen(false)}
          data={data}
          substations={substations}
          selectedId={selectedId}
          onSelectSubstation={onSelectSubstation}
        />
      )}
    </div>
  );
};
