from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import csv
import io
import json
import logging
import math
import os
import re
import sys
import requests
import urllib.parse 
import uuid
from datetime import datetime, date
from typing import Dict, Optional, List, Any, Literal
from uuid import UUID
from shapely.geometry import mapping
from sqlalchemy.exc import IntegrityError

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from utils import DataCacheError, carregar_dados_cache, fundir_dados_geo_mercado
    from cache_redis import cache_json, is_redis_available
    from config import DATA_SOURCE, DIR_DADOS, get_cidade_alvo
    from database import carregar_cobertura_municipios, carregar_publication_metadata, get_engine
    from municipalities import (
        ESCOPO_TODA_BASE,
        nome_municipio,
        normalizar_escopo,
        uf_municipio,
    )
    from auth.dependencies import (
        admin_user,
        clear_auth_cookies,
        current_user,
        request_identity,
        require_csrf,
        set_auth_cookies,
    )
    from auth.rate_limit import RateLimitExceeded, RateLimitUnavailable, enforce_rate_limit
    from auth.store import (
        UserRecord,
        authenticate_user,
        count_active_admins,
        create_session,
        create_user,
        ensure_auth_tables,
        get_user_by_id,
        list_users,
        mark_login,
        reset_password,
        revoke_session,
        update_user,
    )
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
auth_storage_ready = False


def _initialize_auth_storage() -> None:
    global auth_storage_ready
    try:
        ensure_auth_tables()
        auth_storage_ready = True
    except Exception:
        auth_storage_ready = False
        logger.exception("Falha ao inicializar armazenamento de autenticação")


app.add_event_handler("startup", _initialize_auth_storage)
logger = logging.getLogger(__name__)


@app.middleware("http")
async def request_id_middleware(request, call_next):
    requested_id = request.headers.get("X-Request-ID", "")
    request_id = requested_id if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", requested_id) else uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_id=%s method=%s path=%s status=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
    )
    return response


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
    municipio_codigo: Optional[str] = None
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
    publication_id: Optional[str] = None
    delivery_id: Optional[str] = None
    reference_period: Optional[str] = None
    city_target: Optional[str] = None
    published_at: Optional[str] = None
    row_counts: Dict[str, int] = Field(default_factory=dict)
    quality_report: Dict[str, Any] = Field(default_factory=dict)


class MunicipalityCoverage(BaseModel):
    codigo: str
    nome: str
    uf: str
    consumidores: int = 0
    transformadores: int = 0
    subestacoes: int = 0
    unidades_gd: int = 0


class ReadinessResponse(BaseModel):
    status: str
    checks: Dict[str, str]


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=12, max_length=128)


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    role: Literal["admin", "user"]
    is_active: bool
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None


class AuthResponse(BaseModel):
    user: UserResponse


class CreateUserRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    name: str = Field(..., min_length=1, max_length=160)
    password: str = Field(..., min_length=12, max_length=128)
    role: Literal["admin", "user"] = "user"


class UpdateUserRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    role: Optional[Literal["admin", "user"]] = None
    is_active: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    password: str = Field(..., min_length=12, max_length=128)


def _user_response(user: UserRecord) -> UserResponse:
    return UserResponse.model_validate(user.public_dict())


def _ensure_auth_ready() -> None:
    if not auth_storage_ready:
        _initialize_auth_storage()
    if not auth_storage_ready:
        raise HTTPException(status_code=503, detail="Autenticação indisponível")


def _enforce_auth_rate_limit(request: Request, email: str) -> None:
    try:
        from config import AUTH_LOGIN_RATE_LIMIT, AUTH_LOGIN_RATE_WINDOW_SECONDS

        enforce_rate_limit(
            "login-ip",
            request_identity(request),
            AUTH_LOGIN_RATE_LIMIT,
            AUTH_LOGIN_RATE_WINDOW_SECONDS,
        )
        enforce_rate_limit(
            "login-email",
            email.strip().casefold(),
            AUTH_LOGIN_RATE_LIMIT,
            AUTH_LOGIN_RATE_WINDOW_SECONDS,
        )
    except RateLimitExceeded as error:
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas de login; tente novamente mais tarde",
            headers={"Retry-After": str(error.retry_after)},
        ) from error
    except RateLimitUnavailable as error:
        raise HTTPException(status_code=503, detail="Controle de tentativas indisponível") from error


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


def _normalizar_escopo_api(value: Optional[str]) -> str:
    escopo = normalizar_escopo(value)
    if not escopo:
        raise HTTPException(status_code=400, detail="Município inválido; use um código IBGE de 7 dígitos")
    return escopo


def _carregar_alvo_simulacao(
    *,
    id_tecnico: Optional[str] = None,
    nome_subestacao: Optional[str] = None,
    municipio: str = ESCOPO_TODA_BASE,
) -> Dict[str, Any]:
    gdf, dados_mercado = carregar_dados_cache(municipio_codigo=municipio)
    dados_fundidos = fundir_dados_geo_mercado(gdf, dados_mercado)
    if not dados_fundidos:
        raise HTTPException(status_code=503, detail="Dados de mercado indisponíveis")

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


def _extrair_coordenadas_simulacao(alvo: Dict[str, Any]) -> tuple[float, float]:
    geom = alvo.get("geometry")
    if not isinstance(geom, dict):
        geom = getattr(geom, "__geo_interface__", None)
    coordenadas = geom.get("coordinates") if isinstance(geom, dict) else None

    def primeiro_par(valor: Any) -> tuple[float, float] | None:
        if isinstance(valor, (list, tuple)):
            if (
                len(valor) == 2
                and all(isinstance(parte, (int, float)) and not isinstance(parte, bool) for parte in valor)
            ):
                return float(valor[0]), float(valor[1])
            for item in valor:
                par = primeiro_par(item)
                if par is not None:
                    return par
        return None

    par = primeiro_par(coordenadas)
    if par is None:
        raise HTTPException(
            status_code=503,
            detail="Localização da subestação indisponível para simulação",
        )

    lon, lat = par
    if not (
        math.isfinite(lat)
        and math.isfinite(lon)
        and -90 <= lat <= 90
        and -180 <= lon <= 180
    ):
        raise HTTPException(
            status_code=503,
            detail="Localização da subestação inválida para simulação",
        )
    return lat, lon


def _gerar_simulacao(alvo: Dict[str, Any], data_obj: date) -> Dict[str, Any]:
    lat, lon = _extrair_coordenadas_simulacao(alvo)

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

    if not auth_storage_ready:
        _initialize_auth_storage()
    checks["auth"] = "ok" if auth_storage_ready else "unavailable"
    checks["redis"] = "ok" if is_redis_available() else "unavailable"
    if all(value == "ok" for value in checks.values()):
        return {"status": "ready", "checks": checks}

    raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})


@app.post("/auth/login", response_model=AuthResponse, tags=["Auth"])
def login(payload: LoginRequest, request: Request, response: Response):
    _ensure_auth_ready()
    _enforce_auth_rate_limit(request, payload.email)
    try:
        user = authenticate_user(payload.email, payload.password)
    except ValueError:
        user = None
    if user is None:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

    from config import AUTH_SESSION_TTL_SECONDS

    token = create_session(user.id, AUTH_SESSION_TTL_SECONDS)
    mark_login(user.id)
    set_auth_cookies(response, token)
    return {"user": _user_response(user)}


@app.post("/auth/logout", status_code=204, tags=["Auth"])
def logout(
    request: Request,
    response: Response,
    _user: UserRecord = Depends(current_user),
    _csrf: None = Depends(require_csrf),
):
    from config import AUTH_COOKIE_NAME

    revoke_session(request.cookies.get(AUTH_COOKIE_NAME, ""))
    clear_auth_cookies(response)


@app.get("/auth/me", response_model=AuthResponse, tags=["Auth"])
def me(user: UserRecord = Depends(current_user)):
    return {"user": _user_response(user)}


def _enforce_admin_rate_limit(user: UserRecord) -> None:
    try:
        from config import AUTH_ADMIN_RATE_LIMIT, AUTH_ADMIN_RATE_WINDOW_SECONDS

        enforce_rate_limit(
            "admin-users",
            str(user.id),
            AUTH_ADMIN_RATE_LIMIT,
            AUTH_ADMIN_RATE_WINDOW_SECONDS,
        )
    except RateLimitExceeded as error:
        raise HTTPException(
            status_code=429,
            detail="Muitas operações administrativas; tente novamente mais tarde",
            headers={"Retry-After": str(error.retry_after)},
        ) from error
    except RateLimitUnavailable as error:
        raise HTTPException(status_code=503, detail="Controle de tentativas indisponível") from error


@app.get("/auth/admin/users", response_model=list[UserResponse], tags=["Auth Admin"])
def admin_list_users(admin: UserRecord = Depends(admin_user)):
    _ensure_auth_ready()
    _enforce_admin_rate_limit(admin)
    return [_user_response(user) for user in list_users()]


@app.post("/auth/admin/users", response_model=UserResponse, status_code=201, tags=["Auth Admin"])
def admin_create_user(
    payload: CreateUserRequest,
    admin: UserRecord = Depends(admin_user),
    _csrf: None = Depends(require_csrf),
):
    _ensure_auth_ready()
    _enforce_admin_rate_limit(admin)
    try:
        user = create_user(payload.email, payload.name, payload.password, payload.role)
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="Já existe um usuário com este e-mail") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _user_response(user)


@app.patch("/auth/admin/users/{user_id}", response_model=UserResponse, tags=["Auth Admin"])
def admin_update_user(
    user_id: UUID,
    payload: UpdateUserRequest,
    admin: UserRecord = Depends(admin_user),
    _csrf: None = Depends(require_csrf),
):
    _ensure_auth_ready()
    _enforce_admin_rate_limit(admin)
    target = get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if target.id == admin.id and (payload.is_active is False or payload.role == "user"):
        raise HTTPException(status_code=400, detail="Não é possível remover os próprios privilégios administrativos")
    if target.role == "admin" and (
        payload.is_active is False or payload.role == "user"
    ) and count_active_admins() <= 1:
        raise HTTPException(status_code=400, detail="O sistema precisa manter um administrador ativo")
    try:
        updated = update_user(
            user_id,
            name=payload.name,
            role=payload.role,
            is_active=payload.is_active,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if updated is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return _user_response(updated)


@app.post("/auth/admin/users/{user_id}/reset-password", status_code=204, tags=["Auth Admin"])
def admin_reset_password(
    user_id: UUID,
    payload: ResetPasswordRequest,
    admin: UserRecord = Depends(admin_user),
    _csrf: None = Depends(require_csrf),
):
    _ensure_auth_ready()
    _enforce_admin_rate_limit(admin)
    if get_user_by_id(user_id) is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    try:
        reset_password(user_id, payload.password)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/data/status", response_model=DataStatus, tags=["Status"], dependencies=[Depends(current_user)])
def data_status():
    """Expõe a proveniência da carga publicada sem devolver dados do arquivo."""

    database_metadata = carregar_publication_metadata()
    if database_metadata is not None:
        if not database_metadata.get("city_target"):
            database_metadata["city_target"] = get_cidade_alvo()
        return database_metadata

    metadata_path = os.path.join(DIR_DADOS, "metadata_carga_atual.json")
    if not os.path.exists(metadata_path):
        return {
            "status": "unavailable",
            "source": DATA_SOURCE,
            "publication_id": None,
            "delivery_id": "GS-PROD-2026",
            "city_target": get_cidade_alvo(),
            "reference_period": None,
            "published_at": None,
            "row_counts": {},
            "quality_report": {},
        }

    try:
        with open(metadata_path, "r", encoding="utf-8") as metadata_file:
            metadata = json.load(metadata_file)
        return {
            "status": metadata.get("status", "unknown"),
            "source": metadata.get("source", DATA_SOURCE),
            "publication_id": metadata.get("publication_id"),
            "delivery_id": metadata.get("delivery_id", "GS-PROD-2026"),
            "reference_period": metadata.get("reference_period"),
            "city_target": metadata.get("city_target") or get_cidade_alvo(),
            "published_at": metadata.get("published_at"),
            "row_counts": metadata.get("row_counts", {}),
            "quality_report": metadata.get("quality_report", {}),
        }
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Metadados da carga indisponíveis") from exc


@app.get(
    "/coverage/municipalities",
    response_model=List[MunicipalityCoverage],
    tags=["Cobertura"],
    dependencies=[Depends(current_user)],
)
@cache_json(ttl_seconds=3600, key_prefix="coverage_cache")
def municipalities_coverage():
    """Lista os municípios efetivamente presentes nas tabelas da carga."""

    coverage_by_code: dict[str, MunicipalityCoverage] = {}
    for row in carregar_cobertura_municipios():
        codigo = normalizar_escopo(row.get("codigo"))
        if not codigo or codigo == ESCOPO_TODA_BASE:
            continue
        coverage_by_code[codigo] = MunicipalityCoverage(
            codigo=codigo,
            nome=nome_municipio(codigo),
            uf=uf_municipio(codigo),
            consumidores=int(row.get("consumidores", 0) or 0),
            transformadores=int(row.get("transformadores", 0) or 0),
            subestacoes=int(row.get("subestacoes", 0) or 0),
            unidades_gd=int(row.get("unidades_gd", 0) or 0),
        )
    return [
        item.model_dump()
        for item in sorted(coverage_by_code.values(), key=lambda item: (item.nome.casefold(), item.codigo))
    ]


@app.get("/mercado/ranking", response_model=List[SubestacaoData], tags=["Core"], dependencies=[Depends(current_user)])
@cache_json(ttl_seconds=300)
def obter_dados_completos(municipio: str = ESCOPO_TODA_BASE):
    try:
        escopo = _normalizar_escopo_api(municipio)
        gdf, dados_mercado = carregar_dados_cache(municipio_codigo=escopo)
        dados_fundidos = fundir_dados_geo_mercado(gdf, dados_mercado)
        if not dados_fundidos:
            raise HTTPException(status_code=503, detail="Dados de mercado indisponíveis")
        
        for item in dados_fundidos:
            # sanitizar_dados já converte a geometria; mapping() não é idempotente.
            geometria = item.get('geometry')
            if geometria is not None and hasattr(geometria, 'geom_type'):
                item['geometry'] = mapping(geometria)
            
            if 'metricas_rede' in item:
                m = item['metricas_rede']
                if 'consumo_anual_mwh' in m:
                    m['consumo_anual_mwh'] = limpar_float(m['consumo_anual_mwh'])

            if 'perfil_consumo' in item:
                for classe, valores in item['perfil_consumo'].items():
                    raw_consumo = valores.get('consumo_anual_mwh', valores.get('consumo', 0))
                    valores['consumo_anual_mwh'] = limpar_float(raw_consumo)

        return dados_fundidos
    except HTTPException:
        raise
    except DataCacheError as error:
        raise HTTPException(status_code=503, detail="Dados de mercado indisponíveis") from error
    except Exception as e:
        logger.exception("Falha ao carregar ranking")
        raise HTTPException(status_code=500, detail="Erro interno ao carregar o ranking") from e


@app.get("/mercado/ranking.csv", tags=["Exportações"], dependencies=[Depends(current_user)])
def exportar_ranking_csv(
    busca: Optional[str] = Query(None, description="Filtra por nome ou ID técnico"),
    situacao: str = Query("all", description="all, normal ou attention"),
    municipio: str = Query(ESCOPO_TODA_BASE, description="Código IBGE ou all"),
):
    """Exporta o ranking atual sem incluir geometria ou dados pessoais."""

    if situacao not in {"all", "normal", "attention"}:
        raise HTTPException(status_code=400, detail="Situacao invalida. Use all, normal ou attention")

    try:
        rows = obter_dados_completos(_normalizar_escopo_api(municipio))
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

@app.get("/mercado/geojson", tags=["Core"], dependencies=[Depends(current_user)])
@cache_json(ttl_seconds=3600)
def obter_apenas_geojson(municipio: str = ESCOPO_TODA_BASE):
    """Retorna apenas o GeoJSON dos territórios Voronoi do banco PostgreSQL"""
    try:
        escopo = _normalizar_escopo_api(municipio)
        gdf, dados_mercado = carregar_dados_cache(municipio_codigo=escopo)
        if gdf is None or gdf.empty:
            # Escopo válido sem territórios é um resultado vazio; falhas de
            # leitura continuam sendo convertidas em 503 pelos except abaixo.
            return {"type": "FeatureCollection", "features": []}
        return json.loads(gdf.to_json())
    except HTTPException:
        raise
    except DataCacheError as error:
        raise HTTPException(status_code=503, detail="GeoJSON indisponível") from error
    except Exception as e:
        logger.exception("Falha ao carregar GeoJSON")
        raise HTTPException(status_code=503, detail="GeoJSON indisponível") from e

@app.get("/simulacao/id/{id_tecnico}", response_model=SimulacaoSolar, tags=["Simulacao"], dependencies=[Depends(current_user)])
def simular_geracao_por_id(
    id_tecnico: str,
    data: Optional[str] = Query(None, description="Data: AAAA-MM-DD ou DD/MM/AAAA"),
    municipio: str = Query(ESCOPO_TODA_BASE, description="Código IBGE ou all"),
):
    data_obj = _parse_data_simulacao(data)
    try:
        alvo = _carregar_alvo_simulacao(
            id_tecnico=id_tecnico,
            municipio=_normalizar_escopo_api(municipio),
        )
        return _gerar_simulacao(alvo, data_obj)
    except HTTPException:
        raise
    except DataCacheError as error:
        raise HTTPException(status_code=503, detail="Dados de mercado indisponíveis") from error
    except Exception as error:
        logger.exception("Falha ao gerar simulação por ID")
        raise HTTPException(status_code=500, detail="Erro interno ao gerar a simulação") from error


@app.get("/simulacao/{nome_subestacao}", response_model=SimulacaoSolar, tags=["Simulacao"], dependencies=[Depends(current_user)])
def simular_geracao(
    nome_subestacao: str,
    data: Optional[str] = Query(None, description="Data: DD-MM-AAAA ou DD/MM/AAAA"),
    municipio: str = Query(ESCOPO_TODA_BASE, description="Código IBGE ou all"),
):
    data_obj = _parse_data_simulacao(data)
    try:
        alvo = _carregar_alvo_simulacao(
            nome_subestacao=nome_subestacao,
            municipio=_normalizar_escopo_api(municipio),
        )
        return _gerar_simulacao(alvo, data_obj)
    except HTTPException:
        raise
    except DataCacheError as error:
        raise HTTPException(status_code=503, detail="Dados de mercado indisponíveis") from error
    except Exception as error:
        logger.exception("Falha ao gerar simulação por nome")
        raise HTTPException(status_code=500, detail="Erro interno ao gerar a simulação") from error
