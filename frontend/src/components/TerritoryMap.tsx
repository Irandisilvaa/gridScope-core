import type { Territories } from "../lib/api";

type TerritoryMapProps = {
  data: Territories;
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

function featureLabel(feature: Record<string, unknown>) {
  const properties = (feature.properties ?? {}) as Record<string, unknown>;
  return String(properties.NOM ?? properties.NOME ?? properties.COD_ID ?? "Território");
}

export function TerritoryMap({ data }: TerritoryMapProps) {
  const positions: Position[] = [];
  data.features.forEach((feature) => {
    const geometry = feature.geometry as Geometry | undefined;
    collectPositions(geometry?.coordinates, positions);
  });

  if (!positions.length) {
    return <p className="p-4 text-sm text-[#8ea4a7]">Nenhuma geometria válida na carga atual.</p>;
  }

  const longitudes = positions.map(([longitude]) => longitude);
  const latitudes = positions.map(([, latitude]) => latitude);
  const minLongitude = Math.min(...longitudes);
  const maxLongitude = Math.max(...longitudes);
  const minLatitude = Math.min(...latitudes);
  const maxLatitude = Math.max(...latitudes);
  const longitudeSpan = Math.max(maxLongitude - minLongitude, 0.001);
  const latitudeSpan = Math.max(maxLatitude - minLatitude, 0.001);
  const project: Project = ([longitude, latitude]) => [
    30 + ((longitude - minLongitude) / longitudeSpan) * 740,
    30 + ((maxLatitude - latitude) / latitudeSpan) * 360,
  ];

  return (
    <figure className="overflow-hidden rounded-lg border border-white/10 bg-[#102936]">
      <svg
        aria-label="Mapa dos territórios das subestações"
        className="h-[360px] w-full"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        viewBox="0 0 800 420"
      >
        <title>Territórios publicados por subestação</title>
        <rect className="fill-[#102936]" height="420" width="800" x="0" y="0" />
        {data.features.map((feature, index) => {
          const path = geometryPath(feature.geometry as Geometry | undefined, project);
          if (!path) return null;
          return (
            <path
              className="fill-[#6fe7d2]/20 stroke-[#6fe7d2]/70 transition-colors hover:fill-[#ffc857]/30"
              d={path}
              key={String(feature.id ?? `${featureLabel(feature)}-${index}`)}
              strokeWidth="1.4"
            >
              <title>{featureLabel(feature)}</title>
            </path>
          );
        })}
      </svg>
      <figcaption className="border-t border-white/10 px-3 py-2 text-xs text-[#8ea4a7]">
        Geometrias da carga publicada atual · {data.features.length} territórios
      </figcaption>
    </figure>
  );
}
