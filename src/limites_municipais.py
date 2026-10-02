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
import logging
import os
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely import make_valid
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.ops import unary_union

logger = logging.getLogger(__name__)

try:
    from .municipalities import nome_municipio, normalizar_codigo_municipio
except ImportError:
    from municipalities import nome_municipio, normalizar_codigo_municipio


IBGE_MALHA_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/"
    "{codigo}?formato=application/vnd.geo+json&qualidade={qualidade}"
)
IBGE_MALHA_ESTADO_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados/"
    "{uf}?intrarregiao=municipio&formato=application/vnd.geo+json&qualidade={qualidade}"
)
IBGE_MUNICIPIOS_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
IBGE_MALHA_QUALIDADE = os.getenv("IBGE_MALHA_QUALIDADE", "maxima").strip().casefold()
IBGE_MALHA_REVISAO = os.getenv("IBGE_MALHA_REVISAO", "").strip()
IBGE_MALHA_CACHE_DIR = Path(
    os.getenv("IBGE_MALHA_CACHE_DIR", "dados/malhas_ibge")
)
QUALIDADES_VALIDAS = {"maxima", "intermediaria", "minima"}


class LimitesMunicipaisError(RuntimeError):
    """Falha ao carregar ou validar uma malha municipal."""


def _validar_configuracao() -> None:
    """Falha cedo e com mensagem explícita em vez de no meio da publicação."""

    if not IBGE_MALHA_REVISAO:
        raise LimitesMunicipaisError(
            "IBGE_MALHA_REVISAO deve identificar explicitamente a edição oficial da malha"
        )
    if IBGE_MALHA_QUALIDADE not in QUALIDADES_VALIDAS:
        raise LimitesMunicipaisError(
            "IBGE_MALHA_QUALIDADE deve ser maxima, intermediaria ou minima"
        )


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
    _validar_configuracao()
    url = IBGE_MALHA_URL.format(codigo=codigo, qualidade=IBGE_MALHA_QUALIDADE)
    # A qualidade integra a identidade do artefato: não reutilize uma malha
    # simplificada quando a publicação exige a máxima resolução disponível.
    artifact_path = (
        IBGE_MALHA_CACHE_DIR / IBGE_MALHA_REVISAO / IBGE_MALHA_QUALIDADE / f"{codigo}.geojson"
    )
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


def _catalogo_nomes(session: requests.Session) -> dict[str, str]:
    """Nomes oficiais de todos os municípios; best effort, sem bloquear a malha."""

    artifact_path = (
        IBGE_MALHA_CACHE_DIR / IBGE_MALHA_REVISAO / "municipios_localidades.json"
    )
    if artifact_path.exists():
        raw = artifact_path.read_bytes()
    else:
        try:
            resposta = session.get(IBGE_MUNICIPIOS_URL, timeout=180)
            resposta.raise_for_status()
            raw = resposta.content
        except requests.RequestException as error:
            logger.warning("[MALHAS] Catálogo de nomes indisponível no IBGE: %s", error)
            return {}
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(raw)
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("[MALHAS] Catálogo de nomes do IBGE ilegível; usando nomes locais")
        return {}
    if not isinstance(payload, list):
        return {}
    nomes: dict[str, str] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        codigo = normalizar_codigo_municipio(item.get("id"))
        nome = item.get("nome")
        if codigo and isinstance(nome, str) and nome.strip():
            nomes[codigo] = nome.strip()
    return nomes


def _codigos_das_features(features, uf: str) -> list[str]:
    codigos: list[str] = []
    for feature in features:
        propriedades = feature.get("properties", {}) if isinstance(feature, dict) else {}
        codigo_feature = None
        for chave in ("codarea", "codigo_municipio", "codigo", "id"):
            codigo_feature = normalizar_codigo_municipio(propriedades.get(chave))
            if codigo_feature:
                break
        if not codigo_feature:
            raise LimitesMunicipaisError(
                f"IBGE retornou feature sem código municipal reconhecido no estado {uf}"
            )
        if codigo_feature[:2] != uf:
            raise LimitesMunicipaisError(
                f"IBGE retornou o município {codigo_feature} na malha do estado {uf}"
            )
        codigos.append(codigo_feature)
    return codigos


def _carregar_limite_uf(
    uf: str,
    session: requests.Session,
    nomes: dict[str, str],
) -> gpd.GeoDataFrame:
    """Baixa a malha municipal completa de uma UF em uma única requisição."""

    _validar_configuracao()
    url = IBGE_MALHA_ESTADO_URL.format(uf=uf, qualidade=IBGE_MALHA_QUALIDADE)
    artifact_path = (
        IBGE_MALHA_CACHE_DIR / IBGE_MALHA_REVISAO / IBGE_MALHA_QUALIDADE / f"uf_{uf}.geojson"
    )
    if artifact_path.exists():
        content = artifact_path.read_bytes()
        obtained_at = datetime.fromtimestamp(
            artifact_path.stat().st_mtime, timezone.utc
        ).isoformat()
    else:
        try:
            resposta = session.get(url, timeout=180)
            resposta.raise_for_status()
            content = resposta.content
        except requests.RequestException as error:
            raise LimitesMunicipaisError(
                f"Falha ao carregar as malhas municipais do estado {uf}"
            ) from error
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(content)
        obtained_at = datetime.now(timezone.utc).isoformat()

    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LimitesMunicipaisError(
            f"Artefato IBGE inválido para o estado {uf}"
        ) from error

    features = payload.get("features") if isinstance(payload, dict) else None
    if not features:
        raise LimitesMunicipaisError(f"IBGE não retornou geometrias municipais para o estado {uf}")
    codigos = _codigos_das_features(features, uf)

    limite = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    if limite.empty or "geometry" not in limite:
        raise LimitesMunicipaisError(f"Geometria IBGE vazia para o estado {uf}")
    limite["municipio_codigo"] = codigos
    limite["geometry"] = limite.geometry.map(_somente_poligonos)
    limite = limite.dropna(subset=["geometry"])
    if limite.empty:
        raise LimitesMunicipaisError(f"Geometria poligonal inválida para o estado {uf}")

    return gpd.GeoDataFrame(
        {
            "municipio_codigo": limite["municipio_codigo"],
            "nome": limite["municipio_codigo"].map(
                lambda codigo: nomes.get(codigo) or nome_municipio(codigo)
            ),
            "uf": [uf] * len(limite),
            "fonte": ["IBGE malhas municipais"] * len(limite),
            "qualidade": [IBGE_MALHA_QUALIDADE] * len(limite),
            "revisao": [IBGE_MALHA_REVISAO] * len(limite),
            "fonte_url": [url] * len(limite),
            "checksum_sha256": [hashlib.sha256(content).hexdigest()] * len(limite),
            "obtido_em": [obtained_at] * len(limite),
            "geometry": list(limite.geometry),
        },
        geometry="geometry",
        crs="EPSG:4326",
    )


def _dissolver(resultado: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
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


def carregar_limites_municipais_ufs(
    ufs: Iterable[object],
    codigos_declarados: Iterable[object] = (),
    *,
    session: requests.Session | None = None,
) -> gpd.GeoDataFrame:
    """Carrega todos os municípios das UFs informadas em poucas requisições.

    ``session`` existe para permitir teste sem rede: a função não deve abrir
    conexão própria quando o chamador já tem uma.
    """

    ufs_normalizados = sorted(
        {uf.strip().upper() for uf in ufs if uf is not None and str(uf).strip()}
    )
    if not ufs_normalizados:
        raise LimitesMunicipaisError("Nenhuma UF válida para carregar")
    declarados = {
        codigo
        for codigo in (
            normalizar_codigo_municipio(codigo) for codigo in codigos_declarados
        )
        if codigo
    }
    if session is not None:
        return _montar_limites_ufs(session, ufs_normalizados, declarados)
    with requests.Session() as propria:
        propria.headers.update({"User-Agent": "GridScope/1.0"})
        return _montar_limites_ufs(propria, ufs_normalizados, declarados)


def _montar_limites_ufs(
    session: requests.Session,
    ufs: list[str],
    declarados: set[str],
) -> gpd.GeoDataFrame:
    nomes = _catalogo_nomes(session)
    partes = [_carregar_limite_uf(uf, session, nomes) for uf in ufs]

    resultado = gpd.GeoDataFrame(
        pd.concat(partes, ignore_index=True), geometry="geometry", crs="EPSG:4326"
    )
    resultado = _dissolver(resultado)
    faltando = declarados - set(resultado["municipio_codigo"])
    if faltando:
        raise LimitesMunicipaisError(
            "Malha estadual não cobre os municípios declarados na entrega: "
            f"{', '.join(sorted(faltando))}"
        )
    logger.info(
        "[MALHAS] %s limites municipais validados nas UFs %s",
        len(resultado),
        ", ".join(ufs),
    )
    return resultado


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
        total = len(normalizados)
        logger.info("[MALHAS] Carregando %s municípios oficiais...", total)
        for index, codigo in enumerate(normalizados, start=1):
            logger.info("[MALHAS %s/%s] Município %s", index, total, codigo)
            limite = _carregar_limite(codigo, session)
            limites.append(limite)

    resultado = gpd.GeoDataFrame(
        pd.concat(limites, ignore_index=True),
        geometry="geometry",
        crs="EPSG:4326",
    )
    resultado = _dissolver(resultado)
    logger.info("[MALHAS] %s limites municipais validados", len(resultado))
    return resultado


def carregar_limites_para_territorio(codigos: Iterable[object]) -> gpd.GeoDataFrame:
    """Malha de validação: todos os municípios das UFs presentes em ``MUN``.

    O atributo ``MUN`` é declarado pelo distribuidor e não é fonte confiável de
    território. Na entrega Light auditada, 1,31% das sementes com ``MUN`` válido
    caem espacialmente em outro município do próprio estado; validar a
    coordenada apenas contra os municípios declarados transformaria erro de
    atribuição em erro de coordenada e bloquearia a entrega sem evidência real.
    Como a malha de validação define o que é "fora do escopo", ela não pode ser
    derivada do atributo que ela mesma deveria auditar.
    """

    declarados = sorted(
        {
            codigo_normalizado
            for codigo in codigos
            if (codigo_normalizado := normalizar_codigo_municipio(codigo))
        }
    )
    if not declarados:
        raise LimitesMunicipaisError("Nenhum código municipal válido para carregar")
    return carregar_limites_municipais_ufs(
        sorted({codigo[:2] for codigo in declarados}), declarados
    )
