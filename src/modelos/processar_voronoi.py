import geopandas as gpd
import matplotlib.pyplot as plt
import osmnx as ox
import os
import sys
import hashlib
import logging
import numpy as np
from shapely.ops import voronoi_diagram
from shapely.geometry import box
from sqlalchemy import create_engine

# --- CONFIGURAÇÃO INICIAL ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from config import CIDADE_ALVO, DIR_RAIZ
    from database import salvar_voronoi 
except ImportError:
    CIDADE_ALVO = "Aracaju, Brazil"
    DIR_RAIZ = os.getcwd()
    def salvar_voronoi(gdf): pass

NOME_IMAGEM_SAIDA = "territorios_voronoi.png"
NOME_JSON_SAIDA = "subestacoes_logicas.geojson"

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GeoProcessor")

def get_database_engine():
    """Conexão resiliente com o banco."""
    db_url = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:1234@localhost:5433/gridscope_local")
    return create_engine(db_url, isolation_level="AUTOCOMMIT")

def gerar_cor_unica(texto_seed):
    """Gera uma cor HEX consistente baseada no ID."""
    hash_object = hashlib.md5(str(texto_seed).encode())
    return '#' + hash_object.hexdigest()[:6]

def obter_limite_municipal(cidade_alvo):
    """Baixa e corrige a geometria da cidade."""
    logger.info(f"Obtendo limites oficiais de {cidade_alvo}...")
    try:
        gdf_cidade = ox.geocode_to_gdf(cidade_alvo)
        # Projeção UTM (Sirgas 2000 / UTM zone 24S) para precisão métrica
        gdf_cidade = gdf_cidade.to_crs(epsg=31984)
        
        # CORREÇÃO TÉCNICA: Garante que a geometria não tenha nós cruzados
        gdf_cidade['geometry'] = gdf_cidade.geometry.make_valid()
        return gdf_cidade
    except Exception as e:
        logger.error(f"Erro crítico ao baixar limite: {e}")
        sys.exit(1)

def carregar_trafos(gdf_limite):
    """Carrega transformadores garantindo margem de segurança."""
    engine = get_database_engine()
    
    # Pega bounds em WGS84 para a query SQL
    bbox = gdf_limite.to_crs(epsg=4326).total_bounds
    
    # Query otimizada: Pega trafos numa área levemente maior que a cidade
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

    # 1. ENVELOPE INFINITO: Cria uma área de trabalho gigante (20km de borda)
    # Isso garante que as células das bordas não "fechem" antes do limite da cidade
    envelope_expandido = gdf_limite.envelope.buffer(20000).union_all()
    
    # 2. GERAÇÃO DO VORONOI
    # Usamos todos os pontos disponíveis no buffer
    pontos_uniao = gdf_pontos.union_all()
    voronoi_bruto = voronoi_diagram(pontos_uniao, envelope=envelope_expandido)
    
    gdf_voronoi = gpd.GeoDataFrame(geometry=list(voronoi_bruto.geoms), crs=gdf_limite.crs)
    
    # 3. SPATIAL JOIN (Atribuição)
    # Associa cada polígono gigante ao seu transformador dono
    gdf_mapeado = gpd.sjoin(gdf_voronoi, gdf_pontos, how="inner", predicate="contains")
    
    # 4. DISSOLVE (Fusão)
    # Junta os pedaços da mesma subestação
    gdf_territorios = gdf_mapeado.dissolve(by="cod_id_sub", aggfunc={"nome_sub": "first"}).reset_index()
    gdf_territorios = gdf_territorios.rename(columns={"cod_id_sub": "COD_ID", "nome_sub": "NOM"})
    
    # 5. RECORTE BOOLEANO (O Segredo da Cobertura Total)
    # Cortamos os territórios "infinitos" exatamente no formato da cidade
    logger.info("Aplicando recorte de precisão (Cookie Cutter)...")
    gdf_final = gpd.clip(gdf_territorios, gdf_limite)
    
    # Limpezas finais
    gdf_final = gdf_final[~gdf_final.is_empty]
    # Explode multipartes para garantir que ilhas sejam polígonos válidos, mas mantém o mesmo ID
    gdf_final = gdf_final.explode(index_parts=False).reset_index(drop=True)
    
    return gdf_final

def main():
    print(f"--- INICIANDO PROCESSAMENTO: {CIDADE_ALVO} ---")
    
    # 1. Obter e Preparar Limites
    limite = obter_limite_municipal(CIDADE_ALVO)
    
    # 2. Carregar Dados
    pontos = carregar_trafos(limite)
    
    # 3. Processamento Core
    territorios = processar_voronoi_robusto(limite, pontos)
    
    # 4. Exportação
    territorios_wgs84 = territorios.to_crs(epsg=4326)
    
    print("Salvando no Banco de Dados...")
    try:
        if callable(salvar_voronoi):
            salvar_voronoi(territorios_wgs84)
            print("Sucesso: Dados persistidos.")
    except Exception as e:
        logger.warning(f"Banco inacessível: {e}")

    path_json = os.path.join(DIR_RAIZ, NOME_JSON_SAIDA)
    territorios_wgs84.to_file(path_json, driver="GeoJSON")
    print(f"Arquivo GeoJSON gerado: {path_json}")

    # 5. Validação Visual
    print("Gerando Mapa de Validação...")
    try:
        fig, ax = plt.subplots(figsize=(14, 14))
        
        # Fundo: Limite oficial em preto grosso (para ver se sobra algo fora)
        limite.plot(ax=ax, facecolor='none', edgecolor='black', linewidth=4, zorder=5)
        
        # Territórios
        for _, row in territorios.iterrows():
            gpd.GeoSeries(row.geometry).plot(
                ax=ax,
                color=gerar_cor_unica(row['COD_ID']),
                alpha=0.7,
                edgecolor='white',
                linewidth=0.5,
                zorder=3
            )
            
            # Label inteligente: Só coloca nome se o pedaço for grande
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