import json
import os
import geopandas as gpd
import pandas as pd
from config import PATH_GEOJSON, PATH_JSON_MERCADO

def carregar_dados_cache():
    """
    Carrega o GeoJSON (mapa) e o JSON (dados de mercado) de forma unificada.
    Retorna: (GeoDataFrame, List[Dict])
    """
    # Verifica se os arquivos existem antes de tentar ler
    if not os.path.exists(PATH_GEOJSON):
        raise FileNotFoundError(f"GeoJSON não encontrado em: {PATH_GEOJSON}")
    
    if not os.path.exists(PATH_JSON_MERCADO):
        raise FileNotFoundError(f"JSON de Mercado não encontrado em: {PATH_JSON_MERCADO}")

    try:
        # Carrega o mapa
        gdf = gpd.read_file(PATH_GEOJSON)
        
        # Carrega os dados estatísticos
        with open(PATH_JSON_MERCADO, 'r', encoding='utf-8') as f:
            dados_mercado = json.load(f)

        return gdf, dados_mercado
    except Exception as e:
        raise Exception(f"Erro ao ler arquivos de cache: {str(e)}")

def fundir_dados_geo_mercado(gdf, dados_mercado):
    """
    Cruza os dados do mapa (gdf) com os dados estatísticos (dados_mercado).
    Adiciona a geometria ao objeto JSON para uso na API.
    """
    # Cria um dicionário para busca rápida da geometria pelo nome da subestação
    # Ex: {'NORTISTA': <shapely.geometry.Polygon>, ...}
    geo_map = {
        row['NOM']: row['geometry'] 
        for _, row in gdf.iterrows() 
        if pd.notnull(row['NOM'])
    }

    dados_finais = []
    for item in dados_mercado:
        sub_nome = item['subestacao']
        # Adiciona a geometria ao item se ela existir no mapa
        item['geometry'] = geo_map.get(sub_nome)
        
        # Se for para API, às vezes precisamos converter a geometria para GeoJSON (dict)
        # Mas para uso interno (cálculos), manter o objeto Shapely é melhor.
        # Aqui deixamos o objeto original.
        dados_finais.append(item)
        
    return dados_finais