import geopandas as gpd
import matplotlib.pyplot as plt
import osmnx as ox
import os
import sys
import hashlib
import json
import logging
import pandas as pd
from shapely import make_valid
from shapely.ops import voronoi_diagram
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.ops import unary_union

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from config import CIDADE_ALVO, DIR_RAIZ
    from database import (
        carregar_subestacoes,
        carregar_transformadores,
        get_engine,
        salvar_limites_municipais,
        salvar_voronoi,
        salvar_voronoi_municipal,
    )
    from limites_municipais import carregar_limites_municipais
    from municipalities import normalizar_codigo_municipio
except ImportError:
    CIDADE_ALVO = "Aracaju, Brazil"
    DIR_RAIZ = os.getcwd()
    def get_engine():
        raise RuntimeError("Camada de banco indisponível")
    def salvar_voronoi(gdf): pass
    def salvar_limites_municipais(gdf): pass
    def salvar_voronoi_municipal(gdf): pass
    def carregar_subestacoes(*args, **kwargs): raise RuntimeError("Camada de banco indisponível")
    def carregar_transformadores(*args, **kwargs): raise RuntimeError("Camada de banco indisponível")
    def carregar_limites_municipais(*args, **kwargs): raise RuntimeError("Camada de limites indisponível")
    def normalizar_codigo_municipio(value): return str(value).strip() if value else None

NOME_IMAGEM_SAIDA = "territorios_voronoi.png"
NOME_JSON_SAIDA = "subestacoes_logicas.geojson"
MARGEM_PONTOS_FORA_LIMITE_METROS = 250

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GeoProcessor")

def get_database_engine():
    """Conexão resiliente com o banco."""
    return get_engine()

def gerar_cor_unica(texto_seed):
    """Gera uma cor HEX consistente baseada no ID."""
    hash_object = hashlib.md5(str(texto_seed).encode())
    return '#' + hash_object.hexdigest()[:6]

def obter_limite_municipal(cidade_alvo):
    """Baixa e corrige a geometria da cidade."""
    logger.info(f"Obtendo limites oficiais de {cidade_alvo}...")
    try:
        gdf_cidade = ox.geocode_to_gdf(cidade_alvo)
        gdf_cidade = gdf_cidade.to_crs(epsg=31984)
        gdf_cidade['geometry'] = gdf_cidade.geometry.make_valid()
        return gdf_cidade
    except Exception as e:
        logger.error(f"Erro crítico ao baixar limite: {e}")
        sys.exit(1)

def carregar_trafos(gdf_limite):
    """Carrega transformadores garantindo margem de segurança."""
    engine = get_database_engine()
    
    bbox = gdf_limite.to_crs(epsg=4326).total_bounds
    
    sql = f"""
    SELECT 
        t."SUB" AS cod_id_sub,
        COALESCE(s."NOME", 'SUB-' || t."SUB") AS nome_sub,
        t.geometry
    FROM transformadores t
    LEFT JOIN subestacoes s ON t."SUB" = s."COD_ID"
    WHERE t."SUB" IS NOT NULL
    AND t.geometry && ST_MakeEnvelope({bbox[0]-0.05}, {bbox[1]-0.05}, {bbox[2]+0.05}, {bbox[3]+0.05}, 4326)
    """
    
    gdf_pontos = gpd.read_postgis(sql, engine, geom_col='geometry')
    
    if gdf_pontos.empty:
        logger.error("Nenhum transformador encontrado.")
        sys.exit(1)
        
    return gdf_pontos.to_crs(gdf_limite.crs)

def processar_voronoi_robusto(gdf_limite, gdf_pontos):
    """
    Gera Voronoi em 'Canvas Infinito' e recorta com 'Cortador de Biscoito'.
    Isso impede matematicamente a existência de buracos.
    """
    logger.info(f"Calculando topologia para {len(gdf_pontos)} pontos...")

    envelope_expandido = gdf_limite.envelope.buffer(20000).union_all()
    
    pontos_uniao = gdf_pontos.union_all()
    voronoi_bruto = voronoi_diagram(pontos_uniao, envelope=envelope_expandido)
    
    gdf_voronoi = gpd.GeoDataFrame(geometry=list(voronoi_bruto.geoms), crs=gdf_limite.crs)
    
    gdf_mapeado = gpd.sjoin(gdf_voronoi, gdf_pontos, how="inner", predicate="contains")
    
    gdf_territorios = gdf_mapeado.dissolve(by="cod_id_sub", aggfunc={"nome_sub": "first"}).reset_index()
    gdf_territorios = gdf_territorios.rename(columns={"cod_id_sub": "COD_ID", "nome_sub": "NOM"})
    
    logger.info("Aplicando recorte de precisão (Cookie Cutter)...")
    gdf_final = gpd.clip(gdf_territorios, gdf_limite)
    
    gdf_final = gdf_final[~gdf_final.is_empty]
    gdf_final = gdf_final.dissolve(by="COD_ID", aggfunc={"NOM": "first"}).reset_index()
    
    return gdf_final


def _normalizar_id(valor):
    if pd.isna(valor):
        return None
    codigo = str(valor).strip()
    if not codigo or codigo.casefold() in {"nan", "none"}:
        return None
    if codigo.endswith(".0"):
        codigo = codigo[:-2]
    return codigo


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


def _limite_estudo(transformadores: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if "MUN" not in transformadores.columns:
        raise RuntimeError("Transformadores sem MUN para determinar a área de estudo")
    codigos = {
        codigo
        for codigo in transformadores["MUN"].map(normalizar_codigo_municipio)
        if codigo
    }
    if not codigos:
        raise RuntimeError("Nenhum município válido nos transformadores")
    limites = carregar_limites_municipais(sorted(codigos)).to_crs(epsg=31984)
    if limites.empty:
        raise RuntimeError("Limites municipais vazios")
    return limites


def _validar_pontos_no_limite(
    sites: gpd.GeoDataFrame,
    limites: gpd.GeoDataFrame,
    tolerancia_metros: float = MARGEM_PONTOS_FORA_LIMITE_METROS,
) -> dict:
    limite = limites.geometry.union_all()
    distancias = sites.geometry.distance(limite)
    fora = ~sites.geometry.map(limite.covers)
    acima_tolerancia = fora & (distancias > tolerancia_metros)
    if bool(acima_tolerancia.any()):
        exemplos = sites.loc[acima_tolerancia, ["COD_ID", "geometry"]].head(5)
        detalhes = "; ".join(
            f"{row.COD_ID}@{row.geometry.x:.3f},{row.geometry.y:.3f}"
            for row in exemplos.itertuples()
        )
        raise RuntimeError(
            f"{int(acima_tolerancia.sum())} transformadores estão além da tolerância "
            f"de {tolerancia_metros:.0f} m dos limites municipais: {detalhes}"
        )
    excecoes = []
    if bool(fora.any()):
        logger.warning(
            "%s transformadores estão fora do limite oficial, mas dentro da tolerância de %s m",
            int(fora.sum()),
            tolerancia_metros,
        )
        for row in sites.loc[fora].itertuples():
            excecoes.append(
                {
                    "transformador_id": str(row.transformador_id),
                    "subestacao_id": str(row.COD_ID),
                    "municipio_codigo": normalizar_codigo_municipio(row.municipio_codigo),
                    "distance_m": round(float(row.geometry.distance(limite)), 3),
                    "action": "retained_as_seed_clipped_to_official_boundary",
                }
            )
    return {
        "policy": "official_clip_external_seeds",
        "outside_tolerance_m": tolerancia_metros,
        "outside_official_boundary_count": len(excecoes),
        "outside_official_boundary": excecoes,
    }


def _adicionar_ponto_rotulo(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Adiciona um ponto interno determinístico para o rótulo de cada geometria."""

    resultado = gdf.copy()
    pontos = resultado.geometry.map(
        lambda geometry: geometry.representative_point()
        if geometry is not None and not geometry.is_empty
        else None
    )
    pontos_wgs = gpd.GeoSeries(pontos, crs=resultado.crs).to_crs(epsg=4326)
    resultado["LABEL_LON"] = pontos_wgs.map(
        lambda ponto: float(ponto.x) if ponto is not None and not ponto.is_empty else None
    )
    resultado["LABEL_LAT"] = pontos_wgs.map(
        lambda ponto: float(ponto.y) if ponto is not None and not ponto.is_empty else None
    )
    return resultado


def gerar_territorios_por_transformadores(
    transformadores: gpd.GeoDataFrame,
    subestacoes: gpd.GeoDataFrame,
    limites: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Gera uma área por subestação a partir de todos os transformadores."""

    required = {"SUB", "geometry"}
    if not required.issubset(transformadores.columns):
        raise RuntimeError("Transformadores sem SUB/geometry para gerar Voronoi")

    trafos = transformadores.dropna(subset=["SUB", "geometry"]).copy()
    trafos = trafos[~trafos.geometry.is_empty]
    trafos["transformador_id"] = (
        trafos["COD_ID"].map(_normalizar_id)
        if "COD_ID" in trafos.columns
        else trafos.index.map(str)
    )
    trafos["municipio_codigo"] = (
        trafos["MUN"].map(normalizar_codigo_municipio)
        if "MUN" in trafos.columns
        else None
    )
    trafos["COD_ID"] = trafos["SUB"].map(_normalizar_id)
    trafos = trafos.dropna(subset=["COD_ID"])
    if trafos.empty:
        raise RuntimeError("Nenhum transformador elegível para gerar Voronoi")
    trafos = trafos.to_crs(epsg=31984).reset_index(drop=True)
    limites = limites.to_crs(epsg=31984)

    sites = trafos[["COD_ID", "transformador_id", "municipio_codigo", "geometry"]].copy()
    sites["_coordenada"] = sites.geometry.map(lambda geometry: geometry.wkb)
    conflitos = sites.groupby("_coordenada")["COD_ID"].nunique()
    if bool((conflitos > 1).any()):
        raise RuntimeError("Transformadores de SUBs diferentes compartilham coordenadas")
    sites = sites.drop_duplicates("_coordenada").drop(columns="_coordenada")
    relatorio_geografico = _validar_pontos_no_limite(sites, limites)

    nomes = {}
    localizacoes = {}
    if not subestacoes.empty and {"COD_ID", "NOME"}.issubset(subestacoes.columns):
        nomes = {
            codigo: str(nome).strip()
            for codigo, nome in zip(
                subestacoes["COD_ID"].map(_normalizar_id), subestacoes["NOME"]
            )
            if codigo and not pd.isna(nome)
        }
    if not subestacoes.empty and {"COD_ID", "geometry"}.issubset(subestacoes.columns):
        if subestacoes.crs is not None:
            subestacoes_wgs = subestacoes.to_crs(epsg=4326)
            for row in subestacoes_wgs.itertuples():
                codigo = _normalizar_id(getattr(row, "COD_ID", None))
                geometry = getattr(row, "geometry", None)
                if codigo and geometry is not None and not geometry.is_empty:
                    ponto = geometry.representative_point()
                    localizacoes[codigo] = (float(ponto.x), float(ponto.y))

    logger.info(
        "Calculando Voronoi para %s transformadores e %s subestações...",
        len(sites),
        sites["COD_ID"].nunique(),
    )
    # A tolerância acima é somente uma regra de qualidade para pontos do GDB.
    # O mapa publicado deve continuar limitado à união oficial das malhas.
    limite_estudo = limites.geometry.union_all()
    # O envelope numérico precisa conter sementes aceitas pela tolerância,
    # mas nunca é usado como área publicada: o recorte oficial vem depois.
    envelope = limite_estudo.envelope.union(sites.geometry.union_all()).envelope.buffer(1)
    bruto = voronoi_diagram(sites.geometry.union_all(), envelope=envelope)
    celulas = gpd.GeoDataFrame(
        {"geometry": list(bruto.geoms)}, geometry="geometry", crs=sites.crs
    )
    # Associe cada célula à semente antes do recorte. Isso mantém a identidade
    # da célula mesmo quando a semente está alguns metros fora da malha oficial.
    mapeado = gpd.sjoin(
        celulas,
        sites[["COD_ID", "geometry"]],
        how="inner",
        predicate="contains",
    )
    if len(mapeado) != len(celulas):
        raise RuntimeError(
            f"{len(celulas) - len(mapeado)} células Voronoi ficaram sem transformador"
        )

    mapeado = mapeado[["COD_ID", "geometry"]].copy()
    mapeado["geometry"] = mapeado.geometry.intersection(limite_estudo)
    mapeado = mapeado[~mapeado.geometry.is_empty]

    territorios = mapeado[["COD_ID", "geometry"]].dissolve(
        by="COD_ID", as_index=False
    )
    territorios["NOM"] = territorios["COD_ID"].map(nomes).fillna(
        "SUB-" + territorios["COD_ID"]
    )
    territorios["geometry"] = territorios.geometry.map(_somente_poligonos)
    territorios = territorios.dropna(subset=["geometry"])
    territorios = _adicionar_ponto_rotulo(territorios)
    territorios["SITE_LON"] = territorios["COD_ID"].map(
        lambda codigo: localizacoes.get(codigo, (None, None))[0]
    )
    territorios["SITE_LAT"] = territorios["COD_ID"].map(
        lambda codigo: localizacoes.get(codigo, (None, None))[1]
    )
    territorios = territorios[
        [
            "COD_ID",
            "NOM",
            "SITE_LON",
            "SITE_LAT",
            "LABEL_LON",
            "LABEL_LAT",
            "geometry",
        ]
    ]

    # Pontos aceitos apenas pela tolerância são registrados, mas não podem ser
    # usados para declarar que o território oficial foi expandido.
    sites_dentro_limite = sites[sites.geometry.map(limite_estudo.covers)]
    territorios_por_sub = territorios.set_index("COD_ID").geometry.to_dict()
    sem_territorio = []
    sub_incorreto = []
    for row in sites_dentro_limite.itertuples():
        territorio = territorios_por_sub.get(row.COD_ID)
        if territorio is None:
            sem_territorio.append(row.transformador_id)
        elif not territorio.covers(row.geometry):
            sub_incorreto.append(row.transformador_id)
    if sem_territorio:
        raise RuntimeError("Há transformadores sem território após o dissolve")
    if sub_incorreto:
        raise RuntimeError("Há transformadores atribuídos ao SUB errado")

    territorios.attrs["geospatial_quality_report"] = relatorio_geografico
    return territorios.to_crs(epsg=4326)


def gerar_recortes_municipais(
    territorios: gpd.GeoDataFrame, limites: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Recorta os territórios globais pelos limites oficiais dos municípios."""

    territorios_proj = territorios.to_crs(epsg=31984)
    limites_proj = limites.to_crs(epsg=31984)
    colunas_territorio = [
        coluna
        for coluna in (
            "COD_ID", "NOM", "SITE_LON", "SITE_LAT", "LABEL_LON", "LABEL_LAT", "geometry"
        )
        if coluna in territorios_proj.columns
    ]
    recortes = gpd.overlay(
        territorios_proj[colunas_territorio],
        limites_proj[["municipio_codigo", "geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    recortes["geometry"] = recortes.geometry.map(_somente_poligonos)
    recortes = recortes.dropna(subset=["geometry"])
    if recortes.empty:
        raise RuntimeError("Nenhum recorte municipal foi gerado")
    colunas_recorte = [
        coluna
        for coluna in (
            "municipio_codigo",
            "COD_ID",
            "NOM",
            "SITE_LON",
            "SITE_LAT",
            "LABEL_LON",
            "LABEL_LAT",
            "geometry",
        )
        if coluna in recortes.columns
    ]
    recortes = recortes[colunas_recorte]
    recortes = recortes.dissolve(
        by=["municipio_codigo", "COD_ID"],
        as_index=False,
        aggfunc={
            coluna: "first"
            for coluna in ("NOM", "SITE_LON", "SITE_LAT")
            if coluna in recortes.columns
        },
    )
    recortes["geometry"] = recortes.geometry.map(_somente_poligonos)
    recortes = recortes.dropna(subset=["geometry"])
    # O ponto global não serve para o recorte municipal; sempre recalcule.
    recortes = recortes.drop(columns=["LABEL_LON", "LABEL_LAT"], errors="ignore")
    recortes = _adicionar_ponto_rotulo(recortes)
    return recortes.to_crs(epsg=4326)


def processar_voronoi_toda_base():
    """Gera o Voronoi global e seus recortes municipais."""

    logger.info("Carregando transformadores para o Voronoi de toda a base...")
    transformadores = carregar_transformadores()
    limites = _limite_estudo(transformadores)
    subestacoes = carregar_subestacoes()
    territorios = gerar_territorios_por_transformadores(
        transformadores,
        subestacoes,
        limites,
    )
    recortes = gerar_recortes_municipais(territorios, limites)
    return (
        territorios,
        limites.to_crs(epsg=4326),
        recortes,
        territorios.attrs.get("geospatial_quality_report", {}),
    )

def main(cidade_alvo=None):
    escopo = os.getenv("GRIDSCOPE_VORONOI_SCOPE", "all").strip().casefold()
    cidade = cidade_alvo or os.getenv("CIDADE_ALVO", CIDADE_ALVO)
    limites_municipais = None
    recortes_municipais = None
    if escopo == "all":
        print("--- INICIANDO PROCESSAMENTO: TODA A BASE ---")
        territorios, limites_municipais, recortes_municipais, relatorio_geografico = processar_voronoi_toda_base()
    else:
        print(f"--- INICIANDO PROCESSAMENTO: {cidade} ---")
        limite = obter_limite_municipal(cidade)
        pontos = carregar_trafos(limite)
        territorios = processar_voronoi_robusto(limite, pontos)
    
    territorios_wgs84 = territorios.to_crs(epsg=4326)
    
    print("Salvando no Banco de Dados...")
    try:
        if callable(salvar_voronoi):
            salvar_voronoi(territorios_wgs84)
            if escopo == "all":
                salvar_limites_municipais(limites_municipais)
                salvar_voronoi_municipal(recortes_municipais)
            print("Sucesso: Dados persistidos.")
    except Exception as e:
        if os.getenv("GRIDSCOPE_DERIVED_STAGING") == "1":
            # Dentro do corte atômico, um Voronoi não persistido não pode virar
            # entrega publicada com derivados vazios.
            raise RuntimeError("Falha ao persistir territórios Voronoi") from e
        logger.warning(f"Banco inacessível: {e}")

    quality_report_path = os.getenv("GRIDSCOPE_GEOSPATIAL_QUALITY_REPORT")
    if escopo == "all" and quality_report_path:
        with open(quality_report_path, "w", encoding="utf-8") as report_file:
            json.dump(relatorio_geografico, report_file, ensure_ascii=False, indent=2)

    if os.getenv("GRIDSCOPE_DERIVED_STAGING") == "1":
        print("Staging ativo: arquivos derivados locais não serão publicados.")
        return

    path_json = os.path.join(DIR_RAIZ, NOME_JSON_SAIDA)
    territorios_wgs84.to_file(path_json, driver="GeoJSON")
    
    try:
        from config import DIR_DADOS, get_city_slug
        slug = "toda_base" if escopo == "all" else get_city_slug(cidade)
        path_escopo_json = os.path.join(DIR_DADOS, f"voronoi_{slug}.geojson")
        territorios_wgs84.to_file(path_escopo_json, driver="GeoJSON")
        print(f"GeoJSON salvo para o escopo: {path_escopo_json}")
    except Exception as err:
        logger.warning(f"Erro ao salvar GeoJSON específico da cidade: {err}")
        
    print(f"Arquivo GeoJSON gerado: {path_json}")

    if escopo == "all":
        print("Mapa de validação municipal ignorado no escopo Toda a base.")
        print("--- PROCESSO CONCLUÍDO COM SUCESSO ---")
        return

    print("Gerando Mapa de Validação...")
    try:
        fig, ax = plt.subplots(figsize=(14, 14))
        
        limite.plot(ax=ax, facecolor='none', edgecolor='black', linewidth=4, zorder=5)
        
        for _, row in territorios.iterrows():
            gpd.GeoSeries(row.geometry).plot(
                ax=ax,
                color=gerar_cor_unica(row['COD_ID']),
                alpha=0.7,
                edgecolor='white',
                linewidth=0.5,
                zorder=3
            )
            
            if row.geometry.area > 80000: 
                centro = row.geometry.centroid
                ax.annotate(
                    text=str(row['NOM']).replace("SUB-", ""),
                    xy=(centro.x, centro.y),
                    ha='center', va='center',
                    fontsize=8, fontweight='bold', color='#2c3e50',
                    bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none", alpha=0.6)
                )

        ax.set_title(f"Mapa de Calor de Responsabilidade - {CIDADE_ALVO}", fontsize=16)
        ax.set_axis_off()
        
        path_img = os.path.join(DIR_RAIZ, NOME_IMAGEM_SAIDA)
        plt.savefig(path_img, dpi=150, bbox_inches='tight', pad_inches=0.1)
        print(f"Imagem Salva: {path_img}")
        
    except Exception as e:
        logger.error(f"Erro na plotagem: {e}")

    print("--- PROCESSO CONCLUÍDO COM SUCESSO ---")

if __name__ == "__main__":
    main()
