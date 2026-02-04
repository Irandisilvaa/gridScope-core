import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine
import os
import sys

# Setup de caminhos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import CIDADE_ALVO

def get_engine():
    # Ajuste a senha/porta se necessário, conforme seu .env ou configuração local
    db_url = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:1234@localhost:5433/gridscope_local")
    return create_engine(db_url)

def auditar_subestacoes():
    print(f"🕵️ INICIANDO AUDITORIA FORENSE DE SUBESTAÇÕES - {CIDADE_ALVO}")
    engine = get_engine()

    # --- CORREÇÃO AQUI ---
    # Adicionamos o JOIN com a tabela subestacoes para pegar o nome correto
    sql = """
    SELECT 
        t."SUB" as cod_id,
        COALESCE(s."NOME", 'SUB-' || t."SUB") as nome_original,
        ST_Centroid(ST_Collect(t.geometry)) as centro_geom,
        COUNT(*) as qtd_trafos
    FROM transformadores t
    LEFT JOIN subestacoes s ON t."SUB" = s."COD_ID"
    WHERE t."SUB" IS NOT NULL
    GROUP BY t."SUB", s."NOME"
    """
    
    try:
        gdf_subs = gpd.read_postgis(sql, engine, geom_col='centro_geom')
    except Exception as e:
        print(f"❌ Erro ao ler banco de dados: {e}")
        return

    if gdf_subs.empty:
        print("⚠️ Nenhum dado retornado. Verifique se há transformadores com 'SUB' preenchido.")
        return
    
    # Normalizamos o nome para comparação (remove espaços, tudo maiúsculo)
    # Converte para string primeiro para evitar erro se houver None
    gdf_subs['nome_normalizado'] = gdf_subs['nome_original'].astype(str).str.strip().str.upper()
    
    # Convertemos para UTM para medir distâncias em METROS
    gdf_subs = gdf_subs.to_crs(epsg=31984)

    # 2. Agrupamos pelo NOME para ver quem está duplicado
    agrupado = gdf_subs.groupby('nome_normalizado')

    print("\n--- RELATÓRIO DE CONFLITOS DE IDENTIDADE ---\n")
    
    problemas_encontrados = False

    for nome, grupo in agrupado:
        if len(grupo) > 1: # Se tem mais de 1 ID para o mesmo nome
            problemas_encontrados = True
            ids = grupo['cod_id'].tolist()
            trafos = grupo['qtd_trafos'].tolist()
            
            # Calcula a distância máxima entre os centroides desses IDs
            pontos = grupo.geometry.unary_union # (Pode dar aviso de deprecation, mas funciona para audit)
            
            distancia_max = 0
            if pontos.geom_type == 'MultiPoint':
                geoms = list(pontos.geoms)
                # Compara todos contra todos nesse grupo
                for p1 in geoms:
                    for p2 in geoms:
                        d = p1.distance(p2)
                        if d > distancia_max:
                            distancia_max = d
            
            print(f"🚨 NOME: '{nome}'")
            print(f"   IDs Encontrados: {ids}")
            print(f"   Trafos por ID:   {trafos}")
            print(f"   Distância entre eles: {distancia_max:.2f} metros")
            
            if distancia_max < 300:
                print("   ✅ CONCLUSÃO: Mesma subestação (Bancos de transformadores distintos no mesmo pátio).")
                print("      -> AÇÃO: O script de Voronoi vai unir corretamente.")
            else:
                print("   ❌ CONCLUSÃO: Locais fisicamente distintos!")
                print("      -> AÇÃO: Perigo de agrupar coisas distantes.")
            print("-" * 50)

    if not problemas_encontrados:
        print("✅ Nenhuma duplicação de nome encontrada. O mapa reflete IDs únicos.")
    else:
        print("\n⚠️ Análise concluída.")

if __name__ == "__main__":
    auditar_subestacoes()