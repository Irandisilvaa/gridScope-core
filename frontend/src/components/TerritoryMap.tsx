import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";
import type { StyleFunction } from "leaflet";
import type { GeoJsonObject } from "geojson";
import type { Territories } from "../lib/api";

type TerritoryMapProps = {
  data: Territories;
};

const territoryStyle: StyleFunction = (feature) => {
  const id = String(feature?.properties?.COD_ID ?? "");
  const hue = [...id].reduce((total, character) => total + character.charCodeAt(0), 0) % 360;
  return {
    color: "#6fe7d2",
    weight: 1,
    fillColor: `hsl(${hue}, 48%, 42%)`,
    fillOpacity: 0.36,
  };
};

export function TerritoryMap({ data }: TerritoryMapProps) {
  return (
    <div className="territory-map" aria-label="Mapa dos territórios das subestações">
      <MapContainer
        center={[-10.95, -37.07]}
        zoom={11}
        minZoom={8}
        maxZoom={16}
        scrollWheelZoom={false}
        className="territory-map__canvas"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <GeoJSON data={data as unknown as GeoJsonObject} style={territoryStyle} />
      </MapContainer>
    </div>
  );
}
