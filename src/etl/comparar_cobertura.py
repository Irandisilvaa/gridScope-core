"""Compara ocorrências bloqueantes com uma malha municipal candidata local."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

from src.geospatial import crs_projetado_bdgd
from src.municipalities import normalizar_codigo_municipio


def _load_boundaries(path: Path, code_column: str, selected_codes: set[str]) -> gpd.GeoDataFrame:
    boundaries = gpd.read_file(path)
    if boundaries.crs is None or code_column not in boundaries.columns:
        raise ValueError("Malha candidata exige CRS e coluna de código IBGE informada")
    boundaries = boundaries.copy()
    boundaries["municipio_codigo"] = boundaries[code_column].map(normalizar_codigo_municipio)
    boundaries = boundaries[boundaries["municipio_codigo"].isin(selected_codes)]
    missing = selected_codes - set(boundaries["municipio_codigo"])
    if missing:
        raise ValueError(f"Malha candidata não contém municípios do manifesto: {', '.join(sorted(missing))}")
    return boundaries[["municipio_codigo", "geometry"]].dissolve(by="municipio_codigo", as_index=False)


def _download_ibge_reference(uf: str, destination: Path) -> tuple[Path, str]:
    """Baixa a referência municipal máxima estadual para classificar, não publicar."""

    url = (
        f"https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf.upper()}"
        "?intrarregiao=municipio&formato=application/vnd.geo+json&qualidade=maxima"
    )
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(response.content)
    return destination, "codarea"


def comparar(
    occurrences_path: Path,
    manifest_path: Path,
    candidate_path: Path | None,
    candidate_code_column: str,
    output_dir: Path,
    reference_path: Path | None = None,
    reference_code_column: str | None = None,
    reference_ibge_uf: str | None = None,
    candidate_ibge_uf: str | None = None,
) -> int:
    occurrences = pd.read_csv(occurrences_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected_codes = {entry["municipio_codigo"] for entry in manifest}
    points = gpd.GeoDataFrame(
        occurrences,
        geometry=gpd.points_from_xy(occurrences["longitude"], occurrences["latitude"]),
        crs="EPSG:4326",
    )
    if candidate_ibge_uf:
        if candidate_path:
            raise ValueError("Use apenas uma malha candidata")
        candidate_path, candidate_code_column = _download_ibge_reference(
            candidate_ibge_uf,
            output_dir / f"candidata_ibge_{candidate_ibge_uf.upper()}_maxima.geojson",
        )
    if candidate_path is None:
        raise ValueError("Informe uma malha candidata")
    candidate = _load_boundaries(candidate_path, candidate_code_column, selected_codes)
    analysis_crs = crs_projetado_bdgd(candidate)
    points = points.to_crs(analysis_crs)
    candidate = candidate.to_crs(analysis_crs)
    union = candidate.geometry.union_all()
    points["distancia_uniao_candidata_m"] = points.geometry.distance(union)
    inside = points.geometry.map(union.covers)
    points["classificacao_candidata"] = "outside_above_tolerance"
    points.loc[inside, "classificacao_candidata"] = "inside"
    points.loc[~inside & (points["distancia_uniao_candidata_m"] <= 250), "classificacao_candidata"] = "outside_within_tolerance"
    points["distancia_uniao_atual_m"] = points["distance_to_study_boundary_m"]
    points["classificacao_atual"] = points["classification"]

    if reference_ibge_uf:
        if reference_path:
            raise ValueError("Use apenas uma referência ampla")
        reference_path, reference_code_column = _download_ibge_reference(
            reference_ibge_uf,
            output_dir / f"referencia_ibge_{reference_ibge_uf.upper()}_maxima.geojson",
        )
    if reference_path:
        if not reference_code_column:
            raise ValueError("--coluna-codigo-referencia é obrigatória com --referencia-ampla")
        reference = gpd.read_file(reference_path)
        if reference.crs is None or reference_code_column not in reference.columns:
            raise ValueError("Referência ampla exige CRS e coluna de código IBGE")
        reference = reference[[reference_code_column, "geometry"]].copy().to_crs(analysis_crs)
        reference["municipio_espacial"] = reference[reference_code_column].map(normalizar_codigo_municipio)
        joined = gpd.sjoin(points[["geometry"]], reference[["municipio_espacial", "geometry"]], how="left", predicate="intersects")
        spatial = joined.groupby(level=0)["municipio_espacial"].agg(lambda values: sorted(set(values.dropna())))
        points["municipios_espaciais"] = points.index.map(lambda index: spatial.get(index, []))
        def classify_reference(row):
            codes = row.municipios_espaciais
            if not codes:
                return "outside_reference_coverage"
            if len(codes) > 1:
                return "municipal_boundary_ambiguity"
            if codes[0] not in selected_codes:
                return "covered_by_unselected_municipality"
            return (
                "declared_municipality_mismatch"
                if codes[0] != normalizar_codigo_municipio(row.municipio_codigo)
                else "covered_by_selected_municipality"
            )
        points["classificacao_referencia"] = points.apply(classify_reference, axis=1)

    output_dir.mkdir(parents=True, exist_ok=True)
    output = points.to_crs(4326)
    if "municipios_espaciais" in output:
        output["municipios_espaciais"] = output["municipios_espaciais"].map(json.dumps)
    output.drop(columns="geometry").to_csv(output_dir / "comparacao_transformadores.csv", index=False)
    output.to_file(output_dir / "comparacao_transformadores.geojson", driver="GeoJSON")
    summary = {
        "candidate_path": str(candidate_path),
        "candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        "analysis_crs": str(analysis_crs),
        "record_count": len(points),
        "unique_seed_count": int(points.geometry.map(lambda geometry: geometry.wkb).nunique()),
        "candidate_inside_count": int(points["classificacao_candidata"].eq("inside").sum()),
        "candidate_within_tolerance_count": int(points["classificacao_candidata"].eq("outside_within_tolerance").sum()),
        "candidate_blocking_count": int(points["classificacao_candidata"].eq("outside_above_tolerance").sum()),
        "by_declared_municipality": {
            str(municipio): {
                str(classification): int(count)
                for classification, count in group["classificacao_candidata"].value_counts().items()
            }
            for municipio, group in points.groupby("municipio_codigo")
        },
    }
    (output_dir / "comparacao_resumo.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocorrencias", required=True, type=Path)
    parser.add_argument("--manifesto-atual", required=True, type=Path)
    parser.add_argument("--malha-candidata", type=Path)
    parser.add_argument("--coluna-codigo", required=True)
    parser.add_argument("--saida", required=True, type=Path)
    parser.add_argument("--referencia-ampla", type=Path)
    parser.add_argument("--coluna-codigo-referencia")
    parser.add_argument("--referencia-ibge-uf", help="UF para baixar referência IBGE máxima")
    parser.add_argument("--malha-candidata-ibge-uf", help="UF para baixar malha candidata IBGE máxima")
    args = parser.parse_args(argv)
    return comparar(
        args.ocorrencias, args.manifesto_atual, args.malha_candidata,
        args.coluna_codigo, args.saida, args.referencia_ampla,
        args.coluna_codigo_referencia, args.referencia_ibge_uf,
        args.malha_candidata_ibge_uf,
    )


if __name__ == "__main__":
    raise SystemExit(main())
