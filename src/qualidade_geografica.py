"""Validação auditável da cobertura municipal das sementes de Voronoi."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd

try:
    from .geospatial import crs_projetado_bdgd
    from .municipalities import normalizar_codigo_municipio
except ImportError:
    from geospatial import crs_projetado_bdgd
    from municipalities import normalizar_codigo_municipio


class GeospatialCoverageError(RuntimeError):
    """Há sementes BDGD fora da área oficial de publicação."""

    def __init__(self, report: dict, occurrences: gpd.GeoDataFrame) -> None:
        self.report = report
        self.occurrences = occurrences
        if report.get("mesh_manifest_mismatch"):
            message = "As malhas municipais mudaram entre o preflight e o Voronoi"
        elif report["outside_above_tolerance_count"]:
            message = (
                f"{report['outside_above_tolerance_count']} transformadores estão além da "
                f"tolerância de {report['tolerance_m']:.0f} m dos limites municipais"
            )
        else:
            message = (
                f"{report['invalid_or_ineligible_count']} transformadores não são sementes "
                "geográficas válidas" if report["invalid_or_ineligible_count"]
                else "Nenhum transformador elegível foi encontrado para gerar sementes"
            )
        super().__init__(message)


def _geometria_representavel(geometry) -> bool:
    return (
        geometry is not None
        and not geometry.is_empty
        and geometry.is_valid
        and all(math.isfinite(value) for value in geometry.bounds)
    )


def _invalidos_no_crs_de_analise(
    records: gpd.GeoDataFrame,
    analysis_crs,
) -> gpd.GeoDataFrame:
    """Move somente geometrias finitas ao CRS de análise; as demais viram nulas."""

    if records.empty:
        empty = records.copy()
        empty["geometry"] = None
        return empty.set_crs(analysis_crs, allow_override=True)

    representable = records.geometry.map(_geometria_representavel)
    projected = records.loc[representable].to_crs(analysis_crs)
    non_representable = records.loc[~representable].copy()
    if not non_representable.empty:
        non_representable["geometry"] = None
        non_representable = non_representable.set_crs(analysis_crs, allow_override=True)
    if projected.empty:
        return non_representable
    if non_representable.empty:
        return projected
    combined = pd.concat([projected, non_representable], ignore_index=True)
    return gpd.GeoDataFrame(combined, geometry="geometry", crs=analysis_crs)


def preparar_transformadores_eligiveis(
    transformadores: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, dict[str, int]]:
    """Aplica a mesma elegibilidade na publicação e no diagnóstico isolado."""

    required = {"COD_ID", "SUB", "MUN", "geometry"}
    missing = required - set(transformadores.columns)
    if missing:
        raise ValueError(f"Transformadores sem colunas geográficas: {', '.join(sorted(missing))}")
    if transformadores.crs is None:
        raise ValueError("Transformadores precisam ter CRS")

    prepared = transformadores.copy()
    # Estes campos precisam existir também nas linhas rejeitadas para que o CSV
    # identifique a origem do bloqueio, e não apenas as sementes válidas.
    prepared["transformador_id"] = prepared["COD_ID"].astype("string").str.strip()
    prepared["subestacao_id"] = prepared["SUB"].astype("string").str.strip()
    prepared["municipio_original"] = prepared["MUN"]
    prepared["municipio_codigo"] = prepared["MUN"].map(normalizar_codigo_municipio)
    missing_identifier = prepared["COD_ID"].isna() | prepared["COD_ID"].astype("string").str.strip().eq("")
    blank_substation = prepared["SUB"].astype("string").str.strip().eq("")
    missing_substation = prepared["SUB"].isna() | blank_substation
    invalid_geometry = prepared.geometry.isna() | prepared.geometry.is_empty
    invalid_geometry |= ~prepared.geometry.geom_type.eq("Point")
    invalid_municipality = prepared["municipio_codigo"].isna()
    invalid = ~missing_substation & (
        missing_identifier | invalid_geometry | invalid_municipality
    )
    eligible = prepared.loc[~(missing_substation | invalid)].copy()
    invalid_records = prepared.loc[invalid].copy()
    invalid_records["classification"] = "invalid_geometry_or_identifier"
    invalid_records.loc[invalid_municipality & ~missing_substation, "classification"] = "invalid_municipality"
    return eligible, invalid_records, {
        "discarded_missing_substation_count": int(missing_substation.sum()),
        "missing_identifier_count": int(missing_identifier.sum()),
        "missing_empty_or_non_point_geometry_count": int(invalid_geometry.sum()),
        "missing_or_invalid_municipality_count": int(invalid_municipality.sum()),
    }


def relatorio_sem_transformadores_elegiveis(
    transformadores: gpd.GeoDataFrame,
    rejected: dict[str, int],
    invalid_records: gpd.GeoDataFrame,
    *,
    tolerancia_metros: float = 250,
) -> tuple[dict, gpd.GeoDataFrame]:
    """Cria diagnóstico bloqueante quando não há nenhuma semente utilizável."""

    count = len(transformadores)
    report = {
        "schema_version": 1,
        "status": "blocked",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tolerance_m": tolerancia_metros,
        "source_crs": str(transformadores.crs),
        "analysis_crs": None,
        "transformer_record_count": count,
        "eligible_transformer_count": 0,
        "unique_seed_count": 0,
        "invalid_or_ineligible_count": len(invalid_records),
        "ineligible_counts": rejected,
        "municipality_count": 0,
        "inside_count": 0,
        "outside_within_tolerance_count": 0,
        "outside_above_tolerance_count": 0,
        "distance_statistics_m": {"max": 0, "median": 0, "p95": 0},
        "counts_by_declared_municipality": {},
        "counts_by_substation": {},
        "boundary_provenance": [],
    }
    return report, invalid_records


def analisar_cobertura_geografica(
    transformadores: gpd.GeoDataFrame,
    limites: gpd.GeoDataFrame,
    *,
    tolerancia_metros: float = 250,
) -> tuple[dict, gpd.GeoDataFrame]:
    """Classifica cada transformador contra a união das malhas oficiais."""

    if limites.crs is None:
        raise ValueError("Limites precisam ter CRS")

    original_count = len(transformadores)
    if not math.isfinite(tolerancia_metros) or tolerancia_metros < 0:
        raise ValueError("Tolerância geográfica deve ser um número finito não negativo")
    valid, invalid_records, rejected = preparar_transformadores_eligiveis(transformadores)
    if valid.empty:
        return relatorio_sem_transformadores_elegiveis(
            transformadores, rejected, invalid_records, tolerancia_metros=tolerancia_metros
        )
    projected_crs = crs_projetado_bdgd(limites)
    invalid_records = _invalidos_no_crs_de_analise(invalid_records, projected_crs)
    source_finite = valid.geometry.map(
        lambda geometry: math.isfinite(geometry.x) and math.isfinite(geometry.y)
    )
    source_non_finite = valid.loc[~source_finite].copy()
    if not source_non_finite.empty:
        source_non_finite["classification"] = "non_finite_coordinate"
        source_non_finite["geometry"] = None
        source_non_finite = source_non_finite.set_crs(projected_crs, allow_override=True)
        invalid_records = gpd.GeoDataFrame(
            pd.concat([invalid_records, source_non_finite], ignore_index=True),
            geometry="geometry", crs=projected_crs,
        )
    valid = valid.loc[source_finite].to_crs(projected_crs)
    finite_coordinates = valid.geometry.map(
        lambda geometry: math.isfinite(geometry.x) and math.isfinite(geometry.y)
    )
    non_finite = valid.loc[~finite_coordinates].copy()
    if not non_finite.empty:
        non_finite["classification"] = "non_finite_coordinate"
        non_finite["geometry"] = None
        invalid_records = pd.concat([invalid_records, non_finite], ignore_index=True)
        invalid_records = gpd.GeoDataFrame(invalid_records, geometry="geometry", crs=valid.crs)
    rejected["non_finite_coordinate_count"] = int((~source_finite).sum() + (~finite_coordinates).sum())
    valid = valid.loc[finite_coordinates].copy()
    limites = limites.to_crs(projected_crs)
    boundary = limites.geometry.union_all()
    valid["distance_to_study_boundary_m"] = valid.geometry.distance(boundary)
    municipal_boundaries = dict(zip(limites["municipio_codigo"], limites.geometry))
    valid["distance_to_declared_municipality_m"] = pd.Series(
        float("nan"), index=valid.index, dtype="float64"
    )
    for municipio_codigo, geometry in municipal_boundaries.items():
        mask = valid["municipio_codigo"].eq(municipio_codigo)
        valid.loc[mask, "distance_to_declared_municipality_m"] = valid.loc[mask].geometry.distance(geometry)
    valid["inside_official_boundary"] = valid.geometry.map(boundary.covers)
    valid["classification"] = "inside"
    outside = ~valid["inside_official_boundary"]
    valid.loc[outside & (valid["distance_to_study_boundary_m"] <= tolerancia_metros), "classification"] = "outside_within_tolerance"
    valid.loc[outside & (valid["distance_to_study_boundary_m"] > tolerancia_metros), "classification"] = "outside_above_tolerance"
    occurrences = pd.concat([valid.loc[outside], invalid_records], ignore_index=True)
    occurrences = gpd.GeoDataFrame(occurrences, geometry="geometry", crs=projected_crs)
    point_occurrences = occurrences.geometry.map(
        lambda geometry: geometry is not None
        and geometry.geom_type == "Point"
        and _geometria_representavel(geometry)
    )
    wgs84 = occurrences.loc[point_occurrences].to_crs(4326)
    wgs84_finite = wgs84.geometry.map(_geometria_representavel)
    coordinate_indexes = wgs84.index[wgs84_finite]
    occurrences["longitude"] = None
    occurrences["latitude"] = None
    occurrences.loc[coordinate_indexes, "longitude"] = wgs84.loc[coordinate_indexes].geometry.x
    occurrences.loc[coordinate_indexes, "latitude"] = wgs84.loc[coordinate_indexes].geometry.y
    occurrences["analysis_x"] = None
    occurrences["analysis_y"] = None
    occurrences.loc[coordinate_indexes, "analysis_x"] = occurrences.loc[coordinate_indexes].geometry.x
    occurrences.loc[coordinate_indexes, "analysis_y"] = occurrences.loc[coordinate_indexes].geometry.y
    if "distance_to_declared_municipality_m" not in occurrences:
        occurrences["distance_to_declared_municipality_m"] = None

    distances = valid.loc[outside, "distance_to_study_boundary_m"]
    blocking = valid["classification"].eq("outside_above_tolerance")
    within_tolerance = valid["classification"].eq("outside_within_tolerance")
    unique_seed_count = valid.geometry.map(lambda geometry: geometry.wkb).nunique()
    invalid_count = len(invalid_records)
    report = {
        "schema_version": 1,
        "status": "blocked" if bool(blocking.any()) or invalid_count or valid.empty else "approved",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tolerance_m": tolerancia_metros,
        "source_crs": str(transformadores.crs),
        "analysis_crs": str(projected_crs),
        "transformer_record_count": original_count,
        "eligible_transformer_count": len(valid),
        "unique_seed_count": int(unique_seed_count),
        "duplicate_seed_record_count": int(len(valid) - unique_seed_count),
        "invalid_or_ineligible_count": invalid_count,
        "ineligible_counts": rejected,
        "municipality_count": len(limites),
        "inside_count": int((~outside).sum()),
        "outside_within_tolerance_count": int(valid["classification"].eq("outside_within_tolerance").sum()),
        "outside_within_tolerance_unique_seed_count": int(
            valid.loc[within_tolerance].geometry.map(lambda geometry: geometry.wkb).nunique()
        ),
        "outside_above_tolerance_count": int(blocking.sum()),
        "outside_above_tolerance_unique_seed_count": int(
            valid.loc[blocking].geometry.map(lambda geometry: geometry.wkb).nunique()
        ),
        "distance_statistics_m": {
            "max": round(float(distances.max()), 3) if not distances.empty else 0,
            "median": round(float(distances.median()), 3) if not distances.empty else 0,
            "p95": round(float(distances.quantile(0.95)), 3) if not distances.empty else 0,
        },
        "counts_by_declared_municipality": {
            str(key): int(value)
            for key, value in valid.loc[blocking, "municipio_codigo"].fillna("invalid_or_missing").value_counts().items()
        },
        "counts_by_substation": {
            str(key): int(value)
            for key, value in valid.loc[blocking, "subestacao_id"].value_counts().items()
        },
        "declared_municipality_distance_statistics_m": {
            "min": round(float(valid["distance_to_declared_municipality_m"].min()), 3)
            if not valid.empty else 0,
            "max": round(float(valid["distance_to_declared_municipality_m"].max()), 3)
            if not valid.empty else 0,
            "median": round(float(valid["distance_to_declared_municipality_m"].median()), 3)
            if not valid.empty else 0,
        },
        "boundary_provenance": [
            {
                key: str(row[key])
                for key in ("municipio_codigo", "fonte", "qualidade", "revisao", "fonte_url", "checksum_sha256")
                if key in limites.columns and pd.notna(row[key])
            }
            for _, row in limites.iterrows()
        ],
    }
    return report, occurrences


def persistir_diagnostico_geografico(
    directory: Path,
    report: dict,
    occurrences: gpd.GeoDataFrame,
) -> Path:
    """Persiste artefatos fora do staging para sobreviver a uma publicação bloqueada."""

    directory.mkdir(parents=True, exist_ok=True)
    (directory / "resumo.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    columns = [
        "transformador_id", "subestacao_id", "municipio_original", "municipio_codigo",
        "classification", "distance_to_study_boundary_m", "longitude", "latitude",
        "analysis_x", "analysis_y", "distance_to_declared_municipality_m",
    ]
    available = [column for column in columns if column in occurrences.columns]
    occurrences[available].to_csv(directory / "transformadores_fora.csv", index=False)
    geojson_path = directory / "transformadores_fora.geojson"
    exportable = occurrences.loc[occurrences.geometry.map(_geometria_representavel)]
    if exportable.empty:
        geojson_path.write_text(
            '{"type":"FeatureCollection","features":[]}', encoding="utf-8"
        )
    else:
        exportable_wgs84 = exportable.to_crs(4326)
        exportable_wgs84 = exportable_wgs84.loc[
            exportable_wgs84.geometry.map(_geometria_representavel)
        ]
        if exportable_wgs84.empty:
            geojson_path.write_text(
                '{"type":"FeatureCollection","features":[]}', encoding="utf-8"
            )
        else:
            exportable_wgs84[available + ["geometry"]].to_file(
                geojson_path, driver="GeoJSON"
            )
    return directory
