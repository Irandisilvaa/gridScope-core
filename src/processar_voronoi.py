import geopandas as gpd
import matplotlib.pyplot as plt
import osmnx as ox
import numpy as np
import os
import sys
from scipy.spatial import Voronoi
from shapely.geometry import Polygon
from shapely.ops import unary_union

# Importa o nosso carregador de dados
import etl_bdgd 

# --- CONFIGURAÇÕES ---
CIDADE_ALVO = "Aracaju, Sergipe, Brazil"
CRS_PROJETADO = "EPSG:31984" # SIRGAS 2000 / UTM zone 24S

def voronoi_finite_polygons_2d(vor, radius=None):
    """
    Versão compatível com NumPy 2.0+
    """
    if vor.points.shape[1] != 2:
        raise ValueError("Requires 2D input")
    
    new_regions = []
    new_vertices = vor.vertices.tolist()
    center = vor.points.mean(axis=0)
    
    if radius is None:
        radius = np.ptp(vor.points).max() * 2
    
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
    
    # 1. CARREGAR DADOS
    subs_raw = etl_bdgd.carregar_subestacoes()
    
    # 2. CARREGAR LIMITES
    print(f"📍 Baixando limites territoriais de: {CIDADE_ALVO}...")
    try:
        limite_cidade = ox.geocode_to_gdf(CIDADE_ALVO)
    except Exception as e:
        print(f"❌ Erro ao baixar dados do OSM: {e}")
        return

    # 3. PREPARAR CRS
    if subs_raw.crs is None:
        subs_raw.set_crs(epsg=4674, inplace=True)
    
    limite_cidade = limite_cidade.to_crs(subs_raw.crs)

    # 4. FILTRAR
    print("✂️  Recortando subestações da área de interesse...")
    subs_cidade = gpd.clip(subs_raw, limite_cidade)
    print(f"⚡ Subestações na área urbana: {len(subs_cidade)}")
    
    if len(subs_cidade) < 2:
        print("⚠️  ERRO: Preciso de pelo menos 2 subestações.")
        return

    # 5. PONTOS
    subs_proj = subs_cidade.to_crs(CRS_PROJETADO)
    pontos_proj = subs_proj.copy()
    pontos_proj['geometry'] = subs_proj.geometry.centroid
    limite_proj = limite_cidade.to_crs(CRS_PROJETADO)

    # 6. VORONOI
    print("🧮 Calculando diagrama matemático...")
    coords = np.array([(p.x, p.y) for p in pontos_proj.geometry])
    vor = Voronoi(coords)
    regions, vertices = voronoi_finite_polygons_2d(vor)
    
    polygons_list = []
    for region in regions:
        polygons_list.append(Polygon(vertices[region]))
    
    voronoi_gdf = gpd.GeoDataFrame(geometry=polygons_list, crs=CRS_PROJETADO)

    # 7. INTERSEÇÃO
    print("🗺️  Aplicando máscara da cidade...")
    subs_logicas = gpd.overlay(voronoi_gdf, limite_proj, how='intersection')

    # 8. JOIN FINAL (RECUPERAR DADOS)
    subs_logicas_finais = gpd.sjoin(subs_logicas, pontos_proj, how="inner", predicate="contains")
    
    # --- CORREÇÃO DO ERRO DE NOME ---
    # Detecta qual coluna de nome está disponível (NOM ou NOME)
    coluna_nome_real = 'NOM' if 'NOM' in subs_logicas_finais.columns else 'NOME'
    print(f"🎯 Usando coluna '{coluna_nome_real}' para visualização.")

    # 9. SALVAR
    arquivo_saida = "subestacoes_logicas_aracaju.geojson"
    caminho_saida = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", arquivo_saida)
    subs_logicas_finais.to_crs(epsg=4326).to_file(caminho_saida, driver='GeoJSON')
    print(f"✅ SUCESSO! Arquivo gerado em: {arquivo_saida}")

    # 10. PLOTAR
    print("🎨 Gerando visualização...")
    fig, ax = plt.subplots(figsize=(12, 12))
    
    # Fundo
    limite_proj.plot(ax=ax, color='#f0f0f0', edgecolor='#444444')
    
    # Polígonos Voronoi
    subs_logicas_finais.plot(ax=ax, column=coluna_nome_real, cmap='tab20', alpha=0.6, edgecolor='white')
    
    # Pontos e Rótulos (Usando a coluna detectada dinamicamente)
    pontos_proj.plot(ax=ax, color='black', markersize=25, zorder=5)
    
    for x, y, label in zip(pontos_proj.geometry.x, pontos_proj.geometry.y, pontos_proj[coluna_nome_real]):
        ax.text(x, y+150, str(label), fontsize=8, ha='center', fontweight='bold')

    plt.title(f"Subestações Lógicas - {CIDADE_ALVO}", fontsize=16)
    plt.axis('off')
    plt.show()

if __name__ == "__main__":
    main()