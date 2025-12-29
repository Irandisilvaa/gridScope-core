import geopandas as gpd
import matplotlib.pyplot as plt
import osmnx as ox
import numpy as np
import os
from scipy.spatial import Voronoi
from shapely.geometry import Polygon
from shapely.ops import unary_union

# Importa o nosso carregador de dados (o arquivo anterior)
import etl_bdgd 

# --- CONFIGURAÇÕES ---
CIDADE_ALVO = "Aracaju, Sergipe, Brazil"
# Sistema de Coordenadas Projetado (UTM) para cálculo de distância em Metros
# EPSG:31984 = SIRGAS 2000 / UTM zone 24S (Correto para Sergipe)
CRS_PROJETADO = "EPSG:31984"

def voronoi_finite_polygons_2d(vor, radius=None):
    """
    Função matemática auxiliar para converter o diagrama de Voronoi (infinito)
    em polígonos finitos que podemos desenhar no mapa.
    """
    if vor.points.shape[1] != 2:
        raise ValueError("Requires 2D input")
    new_regions = []
    new_vertices = vor.vertices.tolist()
    center = vor.points.mean(axis=0)
    if radius is None:
        radius = vor.points.ptp().max() * 2
    # Constrói regiões finitas
    all_ridges = {}
    for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
        all_ridges.setdefault(p1, []).append((p2, v1, v2))
        all_ridges.setdefault(p2, []).append((p1, v1, v2))
    for p1, region in enumerate(vor.point_region):
        vertices = vor.regions[region]
        if all(v >= 0 for v in vertices):
            new_regions.append(vertices)
            continue
        ridges = all_ridges[p1]
        new_region = [v for v in vertices if v >= 0]
        for p2, v1, v2 in ridges:
            if v2 < 0: v1, v2 = v2, v1
            if v1 >= 0: continue
            t = vor.points[p2] - vor.points[p1] # tangent
            t /= np.linalg.norm(t)
            n = np.array([-t[1], t[0]])  # normal
            midpoint = vor.points[[p1, p2]].mean(axis=0)
            direction = np.sign(np.dot(midpoint - center, n)) * n
            far_point = vor.vertices[v2] + direction * radius
            new_region.append(len(new_vertices))
            new_vertices.append(far_point.tolist())
        vs = np.asarray([new_vertices[v] for v in new_region])
        c = vs.mean(axis=0)
        angles = np.arctan2(vs[:,1] - c[1], vs[:,0] - c[0])
        new_region = np.array(new_region)[np.argsort(angles)]
        new_regions.append(new_region.tolist())
    return new_regions, np.asarray(new_vertices)

def main():
    print("🚀 INICIANDO GERAÇÃO DE SUBESTAÇÕES LÓGICAS (VORONOI)")
    
    # 1. CARREGAR DADOS (Via ETL)
    subs_raw = etl_bdgd.carregar_subestacoes()
    
    # 2. CARREGAR LIMITES DA CIDADE (OSMnx)
    print(f"📍 Baixando limites territoriais de: {CIDADE_ALVO}...")
    try:
        limite_cidade = ox.geocode_to_gdf(CIDADE_ALVO)
    except Exception as e:
        print(f"❌ Erro ao baixar dados do OSM: {e}")
        return

    # 3. PREPARAR SISTEMAS DE COORDENADAS (Unificar tudo)
    # Converter BDGD e Limite para o CRS da BDGD primeiro para garantir o clip
    if subs_raw.crs is None:
        # Assume SIRGAS 2000 (padrão ANEEL) se não tiver
        subs_raw.set_crs(epsg=4674, inplace=True)
    
    limite_cidade = limite_cidade.to_crs(subs_raw.crs)

    # 4. FILTRAR: Manter apenas subestações DENTRO da cidade
    # (O arquivo da Energisa tem o estado todo)
    print("✂️  Recortando subestações da área de interesse...")
    subs_cidade = gpd.clip(subs_raw, limite_cidade)
    
    print(f"⚡ Subestações na área urbana: {len(subs_cidade)}")
    if len(subs_cidade) < 2:
        print("⚠️  ERRO: Preciso de pelo menos 2 subestações para gerar Voronoi.")
        return

    # 5. CONVERTER PARA PONTOS E PROJETAR (METROS)
    # A BDGD traz polígonos (terrenos). O Voronoi precisa de pontos (centróides).
    pontos_geo = subs_cidade.copy()
    pontos_geo['geometry'] = subs_cidade.geometry.centroid
    
    # Projetar para UTM (Metros)
    pontos_proj = pontos_geo.to_crs(CRS_PROJETADO)
    limite_proj = limite_cidade.to_crs(CRS_PROJETADO)

    # 6. ALGORITMO DE VORONOI
    print("🧮 Calculando diagrama matemático...")
    coords = np.array([(p.x, p.y) for p in pontos_proj.geometry])
    vor = Voronoi(coords)
    
    regions, vertices = voronoi_finite_polygons_2d(vor)
    
    # Criar GeoDataFrame dos polígonos brutos
    polygons_list = []
    for region in regions:
        polygons_list.append(Polygon(vertices[region]))
    
    voronoi_gdf = gpd.GeoDataFrame(geometry=polygons_list, crs=CRS_PROJETADO)

    # 7. INTERSEÇÃO FINAL (O "Pulo do Gato")
    # Corta os polígonos infinitos no formato exato da cidade
    print("🗺️  Aplicando máscara da cidade...")
    subs_logicas = gpd.overlay(voronoi_gdf, limite_proj, how='intersection')

    # 8. RECUPERAR OS DADOS (Join Espacial)
    # Atribui o Nome e ID da subestação original para a nova área lógica
    # "Qual ponto está dentro de qual polígono?"
    subs_logicas_finais = gpd.sjoin(subs_logicas, pontos_proj, how="inner", predicate="contains")
    
    # Limpar colunas duplicadas do join
    colunas_finais = ['NOM', 'COD_ID', 'geometry']
    subs_logicas_finais = subs_logicas_finais[colunas_finais]

    # 9. SALVAR RESULTADO
    arquivo_saida = "subestacoes_logicas_aracaju.geojson"
    # Salvar na raiz do projeto (voltar um nível do src)
    caminho_saida = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", arquivo_saida)
    
    # Converter de volta para Lat/Long (Padrão Web/Mapbox)
    subs_logicas_finais = subs_logicas_finais.to_crs(epsg=4326)
    subs_logicas_finais.to_file(caminho_saida, driver='GeoJSON')
    
    print(f"✅ SUCESSO! Arquivo gerado em: {arquivo_saida}")

    # 10. PLOTAR PARA VISUALIZAÇÃO
    fig, ax = plt.subplots(figsize=(10, 10))
    limite_proj.plot(ax=ax, color='#eeeeee', edgecolor='black', linewidth=2)
    subs_logicas_finais.to_crs(CRS_PROJETADO).plot(ax=ax, column='NOM', cmap='tab20', alpha=0.6, edgecolor='white')
    pontos_proj.plot(ax=ax, color='black', markersize=15, label='Subestações Reais')
    
    # Colocar rótulos
    for x, y, label in zip(pontos_proj.geometry.x, pontos_proj.geometry.y, pontos_proj['NOM']):
        ax.text(x, y, str(label), fontsize=6, ha='center')

    plt.title(f"Subestações Lógicas - {CIDADE_ALVO}", fontsize=15)
    plt.axis('off')
    plt.show()

if __name__ == "__main__":
    main()