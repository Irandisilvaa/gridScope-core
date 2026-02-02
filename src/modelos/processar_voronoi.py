import geopandas as gpd
import matplotlib.pyplot as plt
import osmnx as ox
import os
import sys
import hashlib
import logging
import numpy as np
from shapely.ops import voronoi_diagram
from sqlalchemy import create_engine

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import CIDADE_ALVO, DIR_RAIZ
from database import salvar_voronoi 

NOME_IMAGEM_SAIDA = "territorios_voronoi.png"
NOME_JSON_SAIDA = "subestacoes_logicas.geojson"
MINIMO_TRAFOS_PARA_VALIDAR = 5

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("GeoProcessor")

def get_database_engine():
    db_url = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:1234@localhost:5433/gridscope_local")
    return create_engine(db_url, isolation_level="AUTOCOMMIT")

def gerar_cor_unica(texto_seed):
    hash_object = hashlib.md5(texto_seed.encode())
    hex_hash = hash_object.hexdigest()
    return '#' + hex_hash[:6]

def obter_limite_municipal(cidade_alvo):
    logger.info(f"Obtendo limites de {cidade_alvo}...")
    try:
        gdf_cidade = ox.geocode_to_gdf(cidade_alvo)
        gdf_cidade = gdf_cidade.to_crs(epsg=31984) 
        return gdf_cidade
    except Exception as e:
        logger.error(f"Erro ao baixar limite: {e}")
        sys.exit(1)

def limpar_geometrias_ruidosas(gdf):
    logger.info("Iniciando limpeza topológica (Remoção de Ilhas)...")
    
    gdf_exploded = gdf.explode(index_parts=False).reset_index(drop=True)
    gdf_exploded['area_m2'] = gdf_exploded.geometry.area
    
    gdf_main_components = gdf_exploded.sort_values('area_m2', ascending=False).drop_duplicates(subset=['COD_ID'])
    
    removidos = len(gdf_exploded) - len(gdf_main_components)
    logger.info(f"Fragmentos isolados removidos: {removidos}")
    
    return gdf_main_components

def gerar_territorios_robustos(gdf_limite):
    engine = get_database_engine()
    bbox = gdf_limite.to_crs(epsg=4326).total_bounds
    
    sql = f"""
    WITH contagem AS (
        SELECT "SUB", COUNT(*) as total FROM transformadores GROUP BY "SUB"
    )
    SELECT 
        t."SUB" AS cod_id_sub,
        COALESCE(s."NOME", 'SUB-' || t."SUB") AS nome_sub,
        t.geometry
    FROM transformadores t
    LEFT JOIN subestacoes s ON t."SUB" = s."COD_ID"
    JOIN contagem c ON t."SUB" = c."SUB"
    WHERE t."SUB" IS NOT NULL
    AND c.total >= {MINIMO_TRAFOS_PARA_VALIDAR}
    AND t.geometry && ST_MakeEnvelope({bbox[0]-0.05}, {bbox[1]-0.05}, {bbox[2]+0.05}, {bbox[3]+0.05}, 4326)
    """
    
    logger.info("Carregando ativos da rede...")
    gdf_pontos = gpd.read_postgis(sql, engine, geom_col='geometry')
    
    if gdf_pontos.empty:
        logger.error("Nenhum ativo válido encontrado.")
        sys.exit(1)

    gdf_pontos = gdf_pontos.to_crs(gdf_limite.crs)
    
    limite_expandido = gdf_limite.buffer(2000) 
    limite_unido = limite_expandido.union_all()
    
    gdf_pontos = gdf_pontos[gdf_pontos.geometry.within(limite_unido)]

    logger.info(f"Calculando Voronoi para {len(gdf_pontos)} transformadores...")
    
    pontos_uniao = gdf_pontos.union_all()
    voronoi_geom = voronoi_diagram(pontos_uniao, envelope=limite_unido)
    
    gdf_voronoi_cells = gpd.GeoDataFrame(geometry=list(voronoi_geom.geoms), crs=gdf_limite.crs)
    
    logger.info("Mapeando Rede...")
    gdf_cells_mapped = gpd.sjoin(gdf_voronoi_cells, gdf_pontos, how="inner", predicate="contains")
    
    logger.info("Consolidando Territórios...")
    gdf_territorios = gdf_cells_mapped.dissolve(by="cod_id_sub", aggfunc={"nome_sub": "first"}).reset_index()
    gdf_territorios = gdf_territorios.rename(columns={"cod_id_sub": "COD_ID", "nome_sub": "NOM"})
    
    # ETAPA DE CORREÇÃO DE ERROS (FILTRO DE ILHAS)
    gdf_territorios = limpar_geometrias_ruidosas(gdf_territorios)
    
    logger.info("Verificando subestações externas...")
    gdf_centroides = gdf_pontos.dissolve(by="cod_id_sub").centroid
    limite_oficial_uniao = gdf_limite.union_all()
    
    for idx, row in gdf_territorios.iterrows():
        cod_id = row['COD_ID']
        if cod_id in gdf_centroides.index:
            ponto_central = gdf_centroides.loc[cod_id]
            if not ponto_central.within(limite_oficial_uniao):
                if "EXTERNA" not in str(row['NOM']):
                    novo_nome = f"{row['NOM']} (EXTERNA)"
                    gdf_territorios.at[idx, 'NOM'] = novo_nome

    logger.info("Recorte Municipal Final...")
    gdf_final = gpd.clip(gdf_territorios, gdf_limite)
    gdf_final = gdf_final[gdf_final.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    
    return gdf_final

def main():
    print(f"PROCESSAMENTO DE TERRITÓRIOS - {CIDADE_ALVO}")
    
    limite = obter_limite_municipal(CIDADE_ALVO)
    territorios = gerar_territorios_robustos(limite)
    
    territorios_wgs84 = territorios.to_crs(epsg=4326)

    print("Salvando dados...")
    try:
        salvar_voronoi(territorios_wgs84)
        print("Dados salvos no banco.")
    except Exception as e:
        print(f"Erro banco: {e}")

    path_json = os.path.join(DIR_RAIZ, NOME_JSON_SAIDA)
    territorios_wgs84.to_file(path_json, driver="GeoJSON")
    print(f"GeoJSON salvo: {path_json}")

    print("Renderizando Mapa...")
    try:
        fig, ax = plt.subplots(figsize=(12, 12))
        
        limite.plot(ax=ax, facecolor='#ecf0f1', edgecolor='#7f8c8d', linewidth=2, zorder=1)
        
        for idx, row in territorios.iterrows():
            cor_unica = gerar_cor_unica(str(row['COD_ID']))
            
            gpd.GeoSeries(row.geometry).plot(
                ax=ax, 
                color=cor_unica, 
                alpha=0.6, 
                edgecolor='white', 
                linewidth=0.8,
                zorder=2
            )
            
            if row.geometry.area > 20000:
                centro = row.geometry.centroid
                ax.annotate(
                    text=row['NOM'],
                    xy=(centro.x, centro.y),
                    xytext=(0, 0),
                    textcoords="offset points",
                    ha='center', va='center',
                    fontsize=8, fontweight='bold', color='black',
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.8)
                )

        ax.set_title(f"Topologia Operacional Otimizada - {CIDADE_ALVO}", fontsize=14)
        ax.set_axis_off()
        
        path_img = os.path.join(DIR_RAIZ, NOME_IMAGEM_SAIDA)
        plt.savefig(path_img, dpi=150, bbox_inches='tight')
        print(f"Mapa salvo: {path_img}")
        
    except Exception as e:
        logger.error(f"Erro visualização: {e}")

if __name__ == "__main__":
    main()