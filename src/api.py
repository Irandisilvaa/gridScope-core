from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import csv
import io
import json
import logging
import os
import sys
import requests
import urllib.parse 
from datetime import datetime, date
from typing import Dict, Optional, List, Any
from shapely.geometry import mapping

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from utils import carregar_dados_cache, fundir_dados_geo_mercado
    from cache_redis import cache_json, is_redis_available
    from config import DATA_SOURCE, DIR_DADOS
    from database import get_engine
except ImportError as e:
    print(f"CRITICAL API ERROR: {e}")
    sys.exit(1)

app = FastAPI(
    title="GridScope API",
    description="API Avançada de Monitoramento de Rede",
    version="4.7" 
)

def limpar_float(valor):
    """Converte strings BR (1.000,00) ou sujas para float Python (1000.00)"""
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        try:
            limpo = valor.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
            return float(limpo)
        except ValueError:
            return 0.0
    return 0.0


CSV_COLUNAS_RANKING = (
    "id_tecnico",
    "subestacao",
    "total_clientes",
    "consumo_anual_mwh",
    "nivel_criticidade_gd",
    "total_unidades_gd",
    "potencia_total_kw_gd",
)
logger = logging.getLogger(__name__)


def proteger_celula_csv(valor: object) -> object:
    """Evita que planilhas interpretem texto exportado como fórmula."""

    if isinstance(valor, str) and valor.startswith(("=", "+", "-", "@")):
        return f"'{valor}"
    return valor

class MetricasRede(BaseModel):
    total_clientes: int
    consumo_anual_mwh: float
    nivel_criticidade_gd: str

class PerfilClasse(BaseModel):
    qtd_clientes: int
    pct: float
    consumo_anual_mwh: Optional[float] = 0.0 


class DetalheGeracao(BaseModel):
    potencia_kw: float
    qtd: int


class GeracaoDistribuida(BaseModel):
    total_unidades: int
    potencia_total_kw: float
    detalhe_por_classe: Dict[str, DetalheGeracao]


class EvolucaoTemporal(BaseModel):
    mes: str
    clientes: int
    unidades_mmgd: int
    potencia_kw: float

class SubestacaoData(BaseModel):
    subestacao: str
    id_tecnico: str
    metricas_rede: MetricasRede
    geracao_distribuida: GeracaoDistribuida
    perfil_consumo: Dict[str, PerfilClasse]
    evolucao_temporal: List[EvolucaoTemporal] = Field(default_factory=list)
    geometry: Optional[Dict[str, Any]] = None

class SimulacaoSolar(BaseModel):
    subestacao: str
    data_referencia: str
    fonte_dados: str
    condicao_tempo: str
    irradiacao_solar_kwh_m2: float
    temperatura_max_c: float
    fator_perda_termica: float
    potencia_instalada_kw: float
    geracao_estimada_mwh: float
    impacto_na_rede: str


class DataStatus(BaseModel):
    status: str
    source: str
    delivery_id: Optional[str] = None
    reference_period: Optional[str] = None
    published_at: Optional[str] = None
    row_counts: Dict[str, int] = Field(default_factory=dict)


class ReadinessResponse(BaseModel):
    status: str
    checks: Dict[str, str]


def obter_clima_avancado(lat: float, lon: float, data_alvo: date):
    hoje = date.today()
    
    if data_alvo < hoje:
        url = "https://archive-api.open-meteo.com/v1/archive"
        fonte = "Historico Real"
    else:
        url = "https://api.open-meteo.com/v1/forecast"
        fonte = "Previsao Numerica"

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": data_alvo.isoformat(),
        "end_date": data_alvo.isoformat(),
        "daily": ["shortwave_radiation_sum", "temperature_2m_max", "weather_code"],
        "timezone": "America/Sao_Paulo"
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        dados = response.json()
        
        daily = dados.get('daily', {})
        
        irradiacao_mj = daily['shortwave_radiation_sum'][0]
        if irradiacao_mj is None: irradiacao_mj = 0
        irradiacao_kwh = irradiacao_mj / 3.6
        
        temp_max = daily['temperature_2m_max'][0]
        if temp_max is None: temp_max = 30.0
        
        code = daily['weather_code'][0]
        tempo_desc = "Ceu Limpo"
        if code > 3: tempo_desc = "Nublado"
        if code > 50: tempo_desc = "Chuvoso"

        return irradiacao_kwh, temp_max, tempo_desc, fonte
        
    except Exception as e:
        logger.warning("Falha ao consultar clima: %s", e)
        return 5.0, 30.0, "Dados Offline", "Estimativa Padrao"


def _parse_data_simulacao(data: Optional[str]) -> date:
    if not data:
        return date.today()

    data_clean = data.replace("/", "-").replace(" ", "-")
    for formato in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(data_clean, formato).date()
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail="Formato invalido. Use DD-MM-AAAA")


def _carregar_alvo_simulacao(
    *,
    id_tecnico: Optional[str] = None,
    nome_subestacao: Optional[str] = None,
) -> Dict[str, Any]:
    gdf, dados_mercado = carregar_dados_cache()
    dados_fundidos = fundir_dados_geo_mercado(gdf, dados_mercado)

    if id_tecnico is not None:
        id_buscado = urllib.parse.unquote(id_tecnico).strip().upper()
        matches = [
            item
            for item in dados_fundidos
            if str(item.get("id_tecnico", "")).strip().upper() == id_buscado
        ]
        if not matches:
            raise HTTPException(status_code=404, detail=f"ID técnico '{id_buscado}' não encontrado")
        if len(matches) > 1:
            raise HTTPException(status_code=409, detail=f"ID técnico '{id_buscado}' ambíguo")
        return matches[0]

    nome_buscado = urllib.parse.unquote(nome_subestacao or "").strip().upper()
    exact_matches = [
        item
        for item in dados_fundidos
        if str(item.get("subestacao", "")).strip().upper() == nome_buscado
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        raise HTTPException(status_code=409, detail=f"Subestacao '{nome_buscado}' ambigua")

    partial_matches = [
        item
        for item in dados_fundidos
        if nome_buscado
        and (
            nome_buscado in str(item.get("subestacao", "")).strip().upper()
            or str(item.get("subestacao", "")).strip().upper() in nome_buscado
        )
    ]
    if len(partial_matches) == 1:
        return partial_matches[0]
    if len(partial_matches) > 1:
        raise HTTPException(status_code=409, detail=f"Subestacao '{nome_buscado}' ambigua")

    raise HTTPException(status_code=404, detail=f"Subestacao '{nome_buscado}' nao encontrada")


def _gerar_simulacao(alvo: Dict[str, Any], data_obj: date) -> Dict[str, Any]:
    lat, lon = -10.9472, -37.0731
    try:
        geom = alvo.get("geometry")
        if isinstance(geom, dict) and "coordinates" in geom:
            coords = geom["coordinates"]
            if isinstance(coords[0], float):
                lon, lat = coords[0], coords[1]
            else:
                lon, lat = coords[0][0][0], coords[0][0][1]
    except (IndexError, KeyError, TypeError):
        pass

    irradiacao, temp_max, desc_tempo, fonte = obter_clima_avancado(lat, lon, data_obj)

    perda_termica = 0.0
    if temp_max > 25:
        perda_termica = (temp_max - 25) * 0.004

    fator_performance_real = 0.75 * (1 - perda_termica)
    potencia = limpar_float(alvo["geracao_distribuida"]["potencia_total_kw"])
    geracao_mwh = potencia * irradiacao * fator_performance_real / 1000

    impacto = "Normal"
    if irradiacao > 5.5 and temp_max < 30:
        impacto = "CRITICO: Sol forte e Temp amena. Pico de injecao!"
    elif irradiacao > 5.0:
        impacto = "ALTA INJECAO: Atencao ao fluxo reverso."
    elif irradiacao < 2.0:
        impacto = "BAIXA GERACAO: Rede suportara carga maxima."

    return {
        "subestacao": alvo["subestacao"],
        "data_referencia": data_obj.strftime("%d/%m/%Y"),
        "fonte_dados": fonte,
        "condicao_tempo": desc_tempo,
        "irradiacao_solar_kwh_m2": round(irradiacao, 2),
        "temperatura_max_c": round(temp_max, 1),
        "fator_perda_termica": round(perda_termica * 100, 2),
        "potencia_instalada_kw": potencia,
        "geracao_estimada_mwh": round(geracao_mwh, 2),
        "impacto_na_rede": impacto,
    }

@app.get("/", tags=["Status"])
def home():
    return {"status": "online", "system": "GridScope Core 4.7"}


@app.get("/health", tags=["Status"])
def health():
    """Liveness: o processo HTTP está executando."""

    return {"status": "ok", "service": "gridscope-api", "version": app.version}


@app.get("/ready", response_model=ReadinessResponse, tags=["Status"])
def readiness():
    """Readiness: dependências necessárias para servir dados estão disponíveis."""

    checks: Dict[str, str] = {}
    engine = None
    try:
        engine = get_engine()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
    finally:
        if engine is not None:
            engine.dispose()

    checks["redis"] = "ok" if is_redis_available() else "unavailable"
    if all(value == "ok" for value in checks.values()):
        return {"status": "ready", "checks": checks}

    raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})


@app.get("/data/status", response_model=DataStatus, tags=["Status"])
def data_status():
    """Expõe a proveniência da carga publicada sem devolver dados do arquivo."""

    metadata_path = os.path.join(DIR_DADOS, "metadata_carga_atual.json")
    if not os.path.exists(metadata_path):
        return {"status": "unavailable", "source": DATA_SOURCE, "row_counts": {}}

    try:
        with open(metadata_path, "r", encoding="utf-8") as metadata_file:
            metadata = json.load(metadata_file)
        return {
            "status": metadata.get("status", "unknown"),
            "source": metadata.get("source", DATA_SOURCE),
            "delivery_id": metadata.get("delivery_id"),
            "reference_period": metadata.get("reference_period"),
            "published_at": metadata.get("published_at"),
            "row_counts": metadata.get("row_counts", {}),
        }
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Metadados da carga indisponíveis") from exc

@app.get("/mercado/ranking", response_model=List[SubestacaoData], tags=["Core"])
@cache_json(ttl_seconds=300)
def obter_dados_completos():
    try:
        gdf, dados_mercado = carregar_dados_cache()
        dados_fundidos = fundir_dados_geo_mercado(gdf, dados_mercado)
        
        for item in dados_fundidos:
            if item.get('geometry'):
                item['geometry'] = mapping(item['geometry'])
            
            if 'metricas_rede' in item:
                m = item['metricas_rede']
                if 'consumo_anual_mwh' in m:
                    m['consumo_anual_mwh'] = limpar_float(m['consumo_anual_mwh'])

            if 'perfil_consumo' in item:
                for classe, valores in item['perfil_consumo'].items():
                    raw_consumo = valores.get('consumo_anual_mwh', valores.get('consumo', 0))
                    valores['consumo_anual_mwh'] = limpar_float(raw_consumo)

        return dados_fundidos
    except Exception as e:
        logger.exception("Falha ao carregar ranking")
        raise HTTPException(status_code=500, detail="Erro interno ao carregar o ranking") from e


@app.get("/mercado/ranking.csv", tags=["Exportações"])
def exportar_ranking_csv(
    busca: Optional[str] = Query(None, description="Filtra por nome ou ID técnico"),
    situacao: str = Query("all", description="all, normal ou attention"),
):
    """Exporta o ranking atual sem incluir geometria ou dados pessoais."""

    if situacao not in {"all", "normal", "attention"}:
        raise HTTPException(status_code=400, detail="Situacao invalida. Use all, normal ou attention")

    try:
        rows = obter_dados_completos()
        termo = (busca or "").strip().casefold()
        if termo:
            rows = [
                row
                for row in rows
                if termo in f"{row.get('id_tecnico', '')} {row.get('subestacao', '')}".casefold()
            ]
        if situacao != "all":
            rows = [
                row
                for row in rows
                if (str(row.get("metricas_rede", {}).get("nivel_criticidade_gd", "")).upper() == "NORMAL")
                == (situacao == "normal")
            ]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=CSV_COLUNAS_RANKING, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            metricas = row.get("metricas_rede", {})
            geracao = row.get("geracao_distribuida", {})
            writer.writerow(
                {
                    "id_tecnico": proteger_celula_csv(row.get("id_tecnico", "")),
                    "subestacao": proteger_celula_csv(row.get("subestacao", "")),
                    "total_clientes": metricas.get("total_clientes", 0),
                    "consumo_anual_mwh": metricas.get("consumo_anual_mwh", 0),
                    "nivel_criticidade_gd": proteger_celula_csv(metricas.get("nivel_criticidade_gd", "")),
                    "total_unidades_gd": geracao.get("total_unidades", 0),
                    "potencia_total_kw_gd": geracao.get("potencia_total_kw", 0),
                }
            )

        content = "\ufeff" + output.getvalue()
        return StreamingResponse(
            iter([content]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=gridscope-ranking.csv"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Exportação indisponível") from exc

@app.get("/mercado/geojson", tags=["Core"])
@cache_json(ttl_seconds=3600)
def obter_apenas_geojson():
    """Retorna apenas o GeoJSON dos territórios Voronoi do banco PostgreSQL"""
    try:
        gdf, _ = carregar_dados_cache()
        return json.loads(gdf.to_json())
    except Exception as e:
        logger.exception("Falha ao carregar GeoJSON")
        raise HTTPException(status_code=503, detail="GeoJSON indisponível") from e

@app.get("/simulacao/id/{id_tecnico}", response_model=SimulacaoSolar, tags=["Simulacao"])
def simular_geracao_por_id(
    id_tecnico: str,
    data: Optional[str] = Query(None, description="Data: AAAA-MM-DD ou DD/MM/AAAA"),
):
    data_obj = _parse_data_simulacao(data)
    try:
        alvo = _carregar_alvo_simulacao(id_tecnico=id_tecnico)
        return _gerar_simulacao(alvo, data_obj)
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Falha ao gerar simulação por ID")
        raise HTTPException(status_code=500, detail="Erro interno ao gerar a simulação") from error


@app.get("/simulacao/{nome_subestacao}", response_model=SimulacaoSolar, tags=["Simulacao"])
def simular_geracao(
    nome_subestacao: str,
    data: Optional[str] = Query(None, description="Data: DD-MM-AAAA ou DD/MM/AAAA"),
):
    data_obj = _parse_data_simulacao(data)
    try:
        alvo = _carregar_alvo_simulacao(nome_subestacao=nome_subestacao)
        return _gerar_simulacao(alvo, data_obj)
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Falha ao gerar simulação por nome")
        raise HTTPException(status_code=500, detail="Erro interno ao gerar a simulação") from error
