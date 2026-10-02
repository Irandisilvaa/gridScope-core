"""Política de projeção métrica para dados geográficos brasileiros."""

from __future__ import annotations

import math

import geopandas as gpd
from pyproj import CRS


class GeospatialCrsError(ValueError):
    """Não foi possível selecionar uma projeção métrica para a extensão."""


def _utm_zone(longitude: float) -> int:
    return max(1, min(60, math.floor((longitude + 180) / 6) + 1))


def crs_projetado_bdgd(
    referencia: gpd.GeoDataFrame | gpd.GeoSeries,
) -> CRS:
    """Seleciona SIRGAS 2000 / UTM para uma extensão compacta no Brasil."""

    if referencia.crs is None:
        raise GeospatialCrsError("Geometria sem CRS; não é possível selecionar UTM")
    geometrias = referencia.geometry if isinstance(referencia, gpd.GeoDataFrame) else referencia
    geometrias = geometrias[geometrias.notna() & ~geometrias.is_empty]
    if geometrias.empty:
        raise GeospatialCrsError("Geometria vazia; não é possível selecionar UTM")

    wgs84 = gpd.GeoSeries(geometrias, crs=referencia.crs).to_crs(4326)
    min_lon, min_lat, max_lon, max_lat = wgs84.total_bounds
    # Uma margem numérica evita classificar como multizona um limite que apenas
    # encosta na linha meridiana por arredondamento do arquivo.
    epsilon = 1e-9
    zones = {_utm_zone(min_lon + epsilon), _utm_zone(max_lon - epsilon)}
    if len(zones) != 1 or min_lat < 0 < max_lat:
        # Projeção oficial de abrangência nacional. Evita aplicar uma única UTM
        # fora de sua zona em concessões extensas ou que cruzam o Equador.
        return CRS.from_epsg(5880)

    zone = zones.pop()
    epsg = (31960 + zone) if max_lat <= 0 else (31954 + zone)
    crs = CRS.from_epsg(epsg)
    if not crs.is_projected or any(axis.unit_name != "metre" for axis in crs.axis_info):
        raise GeospatialCrsError(f"CRS métrico inválido selecionado: EPSG:{epsg}")
    return crs
