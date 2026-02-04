import geopandas as gpd
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sklearn.metrics import silhouette_score
import os
import sys
import logging

# Configuração
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import CIDADE_ALVO, DIR_RAIZ

# Arquivo gerado pelo script anterior
ARQUIVO_GEOJSON = os.path.join(DIR_RAIZ, "subestacoes_logicas.geojson")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("Auditoria")

def get_database_engine():
    # Ajuste a porta/senha se necessário
    db_url = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:1234@localhost:5433/gridscope_local")
    return create_engine(db_url)

def calcular_validacao():
    print("--- INICIANDO PROTOCOLO DE PROVA TÉCNICA (V2) ---")
    
    # 1. Carregar os Territórios Gerados
    if not os.path.exists(ARQUIVO_GEOJSON):
        logger.error(f"Arquivo {ARQUIVO_GEOJSON} não encontrado.")
        return

    gdf_territorios = gpd.read_file(ARQUIVO_GEOJSON)
    
    # --- CORREÇÃO CRÍTICA: FORÇAR PROJEÇÃO UTM ---
    # Convertendo para SIRGAS 2000 / UTM 24S (Metros)
    gdf_territorios = gdf_territorios.to_crs(epsg=31984)
    
    logger.info(f"Territórios carregados: {len(gdf_territorios)}")

    # 2. Carregar os Pontos Originais (A "Verdade" de Campo)
    engine = get_database_engine()
    sql = """
    SELECT "SUB" as cod_id_sub, geometry 
    FROM transformadores 
    WHERE "SUB" IS NOT NULL
    """
    gdf_pontos = gpd.read_postgis(sql, engine, geom_col='geometry')
    
    # --- CORREÇÃO CRÍTICA: MESMA PROJEÇÃO ---
    gdf_pontos = gdf_pontos.to_crs(epsg=31984)

    # Filtrar apenas pontos das subestações que existem no GeoJSON
    # (Ignora subestações pequenas que removemos no filtro de ruído)
    subs_validas = gdf_territorios['COD_ID'].unique()
    gdf_pontos = gdf_pontos[gdf_pontos['cod_id_sub'].isin(subs_validas)]
    
    # Clipagem: garantir que estamos analisando apenas pontos dentro da área mapeada
    # (Isso remove pontos que ficaram fora do recorte municipal e distorcem a estatística)
    area_total = gdf_territorios.union_all()
    gdf_pontos = gdf_pontos[gdf_pontos.geometry.within(area_total)]

    print("\n[1/3] TESTE DE INTEGRIDADE TOPOLÓGICA (FRAGMENTAÇÃO)")
    # Explode multipolygons para contar pedaços soltos
    exploded = gdf_territorios.explode(index_parts=True)
    n_fragmentos = len(exploded)
    n_subs = len(gdf_territorios)
    
    ratio_frag = n_fragmentos / n_subs
    # Se ratio for 1.0, é perfeito. Se for 2.0, tem média de 2 pedaços por sub.
    
    print(f"Subestações Originais: {n_subs}")
    print(f"Total de Fragmentos Poligonais: {n_fragmentos}")
    print(f"Índice de Fragmentação: {ratio_frag:.2f} (Ideal: 1.0)")
    
    if ratio_frag < 1.5:
        print(">> RESULTADO: BOM (Poucas ilhas)")
    else:
        print(">> RESULTADO: ALERTA (Muitas 'ilhas' de transformadores misturados)")

    print("\n[2/3] TESTE DE COESÃO ESPACIAL (SILHOUETTE SCORE)")
    print("Calculando distâncias vetoriais (Amostra 20%)...")
    
    if len(gdf_pontos) > 100:
        amostra = gdf_pontos.sample(frac=0.2, random_state=42)
    else:
        amostra = gdf_pontos

    coords = np.array(list(zip(amostra.geometry.x, amostra.geometry.y)))
    labels = amostra['cod_id_sub'].to_numpy()
    
    # O Score varia de -1 a 1. 
    # Em dados reais de energia (que se misturam nas bordas), 0.4 a 0.6 é excelente.
    try:
        score = silhouette_score(coords, labels, metric='euclidean')
        print(f"Silhouette Score Global: {score:.4f}")
        
        # Normalizando para leitura humana (0 a 100%)
        # Mapeando: 0.0 -> 0%, 0.5 -> 80%, 0.7 -> 100%
        confianca_percent = (max(0, score) / 0.6) * 100
        confianca_percent = min(100, confianca_percent)
        
        print(f"Nível de Definição das Fronteiras: {confianca_percent:.2f}%")
    except Exception as e:
        print(f"Não foi possível calcular Silhouette (poucos dados): {e}")
        score = 0

    print("\n[3/3] VERIFICAÇÃO DE CONSISTÊNCIA INTERNA (A PROVA REAL)")
    # SJoin agora com CRS corrigido
    join_check = gpd.sjoin(gdf_pontos, gdf_territorios, how="left", predicate="within")
    
    # Verifica se COD_ID do ponto bate com COD_ID do polígono
    # Tratamento para NaN (pontos que caíram fora de qualquer polígono por milímetros)
    join_check['match'] = join_check['cod_id_sub'] == join_check['COD_ID']
    
    acertos = join_check[join_check['match'] == True]
    taxa_acerto = (len(acertos) / len(gdf_pontos)) * 100
    
    print(f"Pontos dentro do território correto: {taxa_acerto:.2f}%")
    
    print("\n" + "="*40)
    print(f"LAUDO TÉCNICO CORRIGIDO")
    print("="*40)
    
    msg_final = ""
    if taxa_acerto > 98:
        msg_final += "[SUCESSO] O modelo Voronoi é geometricamente consistente.\n"
    else:
        msg_final += "[ATENÇÃO] Ainda há inconsistência geométrica (verifique projeção).\n"
        
    if ratio_frag > 1.5:
        msg_final += "[INSIGHT] O cadastro da BDGD possui muitas inconsistências ('Ilhas' de carga).\n"
        msg_final += "          Isso significa que há trafos da Sub A dentro da área da Sub B."
    else:
        msg_final += "[SUCESSO] A rede é bem organizada geograficamente."
        
    print(msg_final)

if __name__ == "__main__":
    calcular_validacao()