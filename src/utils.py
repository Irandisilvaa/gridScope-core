import json
import os
import geopandas as gpd
import pandas as pd
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import PATH_GEOJSON, PATH_JSON_MERCADO

def carregar_dados_cache():
    """
    Carrega dados do PostgreSQL (sem fallback para arquivos locais)
    Retorna: (GeoDataFrame, List[Dict])
    """
    from database import carregar_voronoi, carregar_subestacoes, carregar_cache_mercado
    
    gdf = carregar_voronoi()
    
    gdf_subs = carregar_subestacoes()
    if 'NOME' in gdf_subs.columns and 'COD_ID' in gdf_subs.columns:
        gdf_subs_simple = gdf_subs[['COD_ID', 'NOME']].drop_duplicates(subset=['COD_ID']).copy()
        gdf_subs_simple['COD_ID'] = gdf_subs_simple['COD_ID'].astype(str)
        gdf['COD_ID'] = gdf['COD_ID'].astype(str)
        gdf = gdf.merge(gdf_subs_simple, on='COD_ID', how='left')
        gdf = gdf.rename(columns={'NOME': 'NOM'})
    
    dados_mercado = carregar_cache_mercado()
    
    return gdf, dados_mercado

def fundir_dados_geo_mercado(gdf, dados_mercado):
    """Cruza dados."""
    geo_map = {str(row['NOM']).strip().upper(): row['geometry'] for _, row in gdf.iterrows() if pd.notnull(row['NOM'])}
    dados_finais = []
    lista = dados_mercado if isinstance(dados_mercado, list) else dados_mercado.to_dict('records')

    for item in lista:
        sub_nome = str(item.get('subestacao', '')).split(' (ID')[0].strip().upper()
        item['geometry'] = geo_map.get(sub_nome)
        dados_finais.append(item)
        
    return dados_finais