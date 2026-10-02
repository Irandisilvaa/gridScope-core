"""Carregamento versionado das malhas municipais do IBGE.

As malhas são usadas somente durante a geração dos derivados geográficos. A
API não consulta o serviço externo: depois de carregadas, elas são persistidas
no PostGIS junto com a publicação correspondente.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely import make_valid
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.ops import unary_union

try:
    from .municipalities import nome_municipio, normalizar_codigo_municipio
except ImportError:
    from municipalities import nome_municipio, normalizar_codigo_municipio


IBGE_MALHA_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/"
    "{codigo}?formato=application/vnd.geo+json&qualidade=intermediaria"
)
IBGE_MALHA_QUALIDADE = "intermediaria"
IBGE_MALHA_REVISAO = os.getenv("IBGE_MALHA_REVISAO", "").strip()
IBGE_MALHA_CACHE_DIR = Path(
    os.getenv("IBGE_MALHA_CACHE_DIR", "dados/malhas_ibge")
)


class LimitesMunicipaisError(RuntimeError):
    """Falha ao carregar ou validar uma malha municipal."""


def _somente_poligonos(geometry):
    if geometry is None or geometry.is_empty:
        return None
    geometry = make_valid(geometry)
    if isinstance(geometry, (Polygon, MultiPolygon)):
        return geometry
    if isinstance(geometry, GeometryCollection):
        partes = [
            parte
            for parte in geometry.geoms
            if isinstance(parte, (Polygon, MultiPolygon)) and not parte.is_empty
        ]
        return unary_union(partes) if partes else None
    return None


def _carregar_limite(codigo: str, session: requests.Session) -> gpd.GeoDataFrame:
    if not IBGE_MALHA_REVISAO:
        raise LimitesMunicipaisError(
            "IBGE_MALHA_REVISAO deve identificar explicitamente a edição oficial da malha"
        )
    url = IBGE_MALHA_URL.format(codigo=codigo)
    artifact_path = IBGE_MALHA_CACHE_DIR / IBGE_MALHA_REVISAO / f"{codigo}.geojson"
    if artifact_path.exists():
        content = artifact_path.read_bytes()
        obtained_at = datetime.fromtimestamp(
            artifact_path.stat().st_mtime, timezone.utc
        ).isoformat()
    else:
        try:
            resposta = session.get(url, timeout=60)
            resposta.raise_for_status()
            content = resposta.content
        except requests.RequestException as error:
            raise LimitesMunicipaisError(
                f"Falha ao carregar limite IBGE do município {codigo}"
            ) from error
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(content)
        obtained_at = datetime.now(timezone.utc).isoformat()

    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LimitesMunicipaisError(
            f"Artefato IBGE inválido para o município {codigo}"
        ) from error

    features = payload.get("features") if isinstance(payload, dict) else None
    if not features:
        raise LimitesMunicipaisError(f"IBGE não retornou geometria para {codigo}")

    codigos_retornados = set()
    for feature in features:
        propriedades = feature.get("properties", {}) if isinstance(feature, dict) else {}
        codigo_feature = None
        for chave in ("codarea", "codigo_municipio", "codigo", "id"):
            valor = normalizar_codigo_municipio(propriedades.get(chave))
            if valor:
                codigo_feature = valor
                break
        if not codigo_feature:
            raise LimitesMunicipaisError(
                f"IBGE retornou feature sem código municipal reconhecido para {codigo}"
            )
        codigos_retornados.add(codigo_feature)
    if codigos_retornados != {codigo}:
        raise LimitesMunicipaisError(
            f"IBGE retornou código(s) inesperado(s) para {codigo}: "
            f"{', '.join(sorted(codigos_retornados))}"
        )

    limite = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    if limite.empty or "geometry" not in limite:
        raise LimitesMunicipaisError(f"Geometria IBGE vazia para {codigo}")

    limite["geometry"] = limite.geometry.map(_somente_poligonos)
    limite = limite.dropna(subset=["geometry"])
    if limite.empty:
        raise LimitesMunicipaisError(f"Geometria poligonal inválida para {codigo}")

    limite = gpd.GeoDataFrame(
        {
            "municipio_codigo": [codigo],
            "nome": [nome_municipio(codigo)],
            "uf": [codigo[:2]],
            "fonte": ["IBGE malhas municipais"],
            "qualidade": [IBGE_MALHA_QUALIDADE],
            "revisao": [IBGE_MALHA_REVISAO],
            "fonte_url": [url],
            "checksum_sha256": [hashlib.sha256(content).hexdigest()],
            "obtido_em": [obtained_at],
        },
        geometry=[limite.geometry.union_all()],
        crs="EPSG:4326",
    )
    return limite


def carregar_limites_municipais(codigos: Iterable[object]) -> gpd.GeoDataFrame:
    """Baixa e valida os limites dos códigos IBGE informados."""

    normalizados = sorted(
        {
            codigo_normalizado
            for codigo in codigos
            if (codigo_normalizado := normalizar_codigo_municipio(codigo))
        }
    )
    if not normalizados:
        raise LimitesMunicipaisError("Nenhum código municipal válido para carregar")

    limites: list[gpd.GeoDataFrame] = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": "GridScope/1.0"})
        for codigo in normalizados:
            limite = _carregar_limite(codigo, session)
            limites.append(limite)

    resultado = gpd.GeoDataFrame(
        pd.concat(limites, ignore_index=True),
        geometry="geometry",
        crs="EPSG:4326",
    )
    resultado["geometry"] = resultado.geometry.map(_somente_poligonos)
    resultado = resultado.dropna(subset=["geometry"])
    resultado = resultado.dissolve(
        by=[
            "municipio_codigo",
            "nome",
            "uf",
            "fonte",
            "qualidade",
            "revisao",
            "fonte_url",
            "checksum_sha256",
            "obtido_em",
        ],
        as_index=False,
    )
    return resultado[
        [
            "municipio_codigo",
            "nome",
            "uf",
            "fonte",
            "qualidade",
            "revisao",
            "fonte_url",
            "checksum_sha256",
            "obtido_em",
            "geometry",
        ]
    ]
