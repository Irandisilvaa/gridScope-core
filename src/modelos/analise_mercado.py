import geopandas as gpd
import pandas as pd
import os
import json
import warnings
import sys
import fiona
import gc  # Garbage Collector para gerenciamento de memória
from sqlalchemy import create_engine
from shapely.geometry import mapping

# --- CONFIGURAÇÕES ---
warnings.filterwarnings('ignore')

# Adiciona o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Tenta pegar a URL do banco do config.py
try:
    from config import DATABASE_URL
except ImportError:
    DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/gridscope_db"

from database import (
    carregar_voronoi, 
    carregar_transformadores, 
    carregar_consumidores, 
    carregar_geracao_gd, 
    salvar_cache_mercado
)

# Nomes de arquivos
NOME_ARQUIVO_VORONOI = "subestacoes_logicas_aracaju.geojson"
NOME_ARQUIVO_SAIDA = "perfil_mercado_aracaju.json"
CACHE_FILE_TRAFOS = "cache_mapeamento_trafos.parquet"

# --- FUNÇÃO DE UTILIDADE: IMPORTAÇÃO INTELIGENTE ---
def importar_arquivo_imediato(nome_tabela, motivo, tem_geometria=False):
    """Pede um arquivo ao usuário, suporta CSV, SHP e GDB."""
    print(f"\n⚠️  PROBLEMA EM '{nome_tabela}': {motivo}")
    print(f"👉 Cole o CAMINHO COMPLETO do arquivo (CSV/SHP/GDB) para '{nome_tabela}'")
    path_arquivo = input("   (ou pressione ENTER para seguir sem esses dados): ").strip('"').strip("'")
    
    if not path_arquivo or not os.path.exists(path_arquivo):
        print("   ⏭️  Pulando importação...")
        return pd.DataFrame()

    print(f"   📂 Lendo: {os.path.basename(path_arquivo)}...")
    df = pd.DataFrame()

    try:
        if path_arquivo.lower().endswith('.gdb'):
            try:
                layers = fiona.listlayers(path_arquivo)
                sugestao = layers[0]
                if 'consumidor' in nome_tabela:
                    sugestao = next((l for l in layers if 'UCBT' in l or 'CONSUMIDOR' in l), layers[0])
                elif 'transformador' in nome_tabela:
                    sugestao = next((l for l in layers if 'UNTR' in l or 'TRAFO' in l), layers[0])
                
                print(f"   📂 Camadas: {layers}")
                layer_name = input(f"   👉 Nome da camada (Enter para '{sugestao}'): ").strip()
                if not layer_name: layer_name = sugestao
                df = gpd.read_file(path_arquivo, layer=layer_name)
            except Exception as e:
                print(f"   ❌ Erro GDB: {e}")
                return pd.DataFrame()
        elif path_arquivo.lower().endswith('.csv'):
            try:
                df = pd.read_csv(path_arquivo, encoding='utf-8', sep=';')
            except:
                df = pd.read_csv(path_arquivo, encoding='latin1', sep=';')
        else:
            df = gpd.read_file(path_arquivo)

        if not tem_geometria and hasattr(df, 'geometry'):
            df = pd.DataFrame(df.drop(columns=['geometry']))

        df.columns = [c.strip().upper() for c in df.columns]
        df = df.loc[:, ~df.columns.duplicated()]

        engine = create_engine(DATABASE_URL)
        print(f"   💾 Salvando '{nome_tabela}' no Banco de Dados...")
        if isinstance(df, gpd.GeoDataFrame) and tem_geometria:
            df.to_postgis(nome_tabela, engine, if_exists='replace', index=False)
        else:
            df.to_sql(nome_tabela, engine, if_exists='replace', index=False)
        
        print(f"   ✅ Importado: {len(df)} registros.")
        return df

    except Exception as e:
        print(f"   ❌ Erro ao importar: {e}")
        return pd.DataFrame()

# --- ALGORITMO OTIMIZADO: SOMA DE CONSUMO ---
def calcular_consumo_anual_otimizado(df):
    """
    Soma as colunas ENE_01 a ENE_12 de forma vetorizada.
    Se não encontrar, tenta CONSUMO ou ENE_FORN.
    """
    # Lista padrão de colunas de energia (ENE_01 ... ENE_12)
    cols_energia = [f'ENE_{i:02d}' for i in range(1, 13)]
    
    # Verifica quais dessas existem no DataFrame
    cols_existentes = [c for c in cols_energia if c in df.columns]
    
    if len(cols_existentes) > 0:
        print(f"   ⚡ Somando colunas mensais: {cols_existentes[0]} ... {cols_existentes[-1]}")
        # Converte para numérico (coerces errors to NaN) e preenche NaN com 0
        df_temp = df[cols_existentes].apply(pd.to_numeric, errors='coerce').fillna(0)
        return df_temp.sum(axis=1)
    
    # Se não tiver ENE_XX, tenta coluna única
    col_unica = next((c for c in ['CONSUMO', 'CONS_KWH', 'ENE_FORN', 'CONSUMO_ANUAL'] if c in df.columns), None)
    if col_unica:
        print(f"   ⚡ Usando coluna única de consumo: {col_unica}")
        return pd.to_numeric(df[col_unica], errors='coerce').fillna(0)
    
    return 0.0

# --- LOOP PRINCIPAL ---
def analisar_mercado():
    print("INICIANDO ANÁLISE DE MERCADO (MODO OTIMIZADO)...")
    
    dir_script = os.path.dirname(os.path.abspath(__file__))
    dir_raiz = os.path.dirname(os.path.dirname(dir_script))
    path_voronoi_file = os.path.join(dir_raiz, NOME_ARQUIVO_VORONOI)
    path_saida = os.path.join(dir_raiz, NOME_ARQUIVO_SAIDA)

    # =========================================================
    # 1. VORONOI (Territórios das Subestações)
    # =========================================================
    print("1. Carregando Territórios (Voronoi)...")
    gdf_voronoi = pd.DataFrame()
    try:
        gdf_voronoi = carregar_voronoi()
    except:
        pass 
    
    if gdf_voronoi.empty:
        if os.path.exists(path_voronoi_file):
            gdf_voronoi = gpd.read_file(path_voronoi_file)
        else:
            print(f"   ❌ ARQUIVO NÃO ENCONTRADO: {path_voronoi_file}")
            return

    if gdf_voronoi.crs is None:
        gdf_voronoi.set_crs("EPSG:4326", inplace=True)
    gdf_voronoi = gdf_voronoi.to_crs(epsg=31984)
    gdf_voronoi = gdf_voronoi.loc[:, ~gdf_voronoi.columns.duplicated()]

    # Padronização ID/Nome
    if 'COD_ID' not in gdf_voronoi.columns:
        gdf_voronoi['COD_ID'] = gdf_voronoi['ID'] if 'ID' in gdf_voronoi.columns else gdf_voronoi.index.astype(str)
    
    if 'NOM' not in gdf_voronoi.columns:
        col_nome = next((c for c in ['NOME', 'SUB', 'NO_SUB', 'NOM_SUB'] if c in gdf_voronoi.columns), None)
        gdf_voronoi['NOM'] = gdf_voronoi[col_nome] if col_nome else "Subestação " + gdf_voronoi['COD_ID'].astype(str)

    gdf_voronoi = gdf_voronoi[['COD_ID', 'NOM', 'geometry']]
    print(f"   > {len(gdf_voronoi)} territórios carregados.")

    # =========================================================
    # 2. TRANSFORMADORES E CRIAÇÃO DE HASH MAP
    # =========================================================
    print("2. Mapeando Transformadores...")
    ref_trafos = None

    # Tenta carregar cache
    if os.path.exists(CACHE_FILE_TRAFOS):
        print(f"   ⚡ Cache encontrado! Carregando '{CACHE_FILE_TRAFOS}'...")
        try:
            ref_trafos = pd.read_parquet(CACHE_FILE_TRAFOS)
            print(f"   > {len(ref_trafos)} transformadores carregados do cache.")
        except Exception as e:
            print(f"   ⚠️ Cache corrompido, refazendo... ({e})")
            os.remove(CACHE_FILE_TRAFOS)

    # Se não tem cache, calcula
    if ref_trafos is None:
        gdf_trafos = carregar_transformadores()
        if gdf_trafos.empty:
            gdf_trafos = importar_arquivo_imediato("transformadores", "Tabela vazia", tem_geometria=True)
            if gdf_trafos.empty: return

        gdf_trafos.columns = [c.upper().strip() for c in gdf_trafos.columns]
        
        # Geometria e Projeção
        col_geom = next((c for c in ['GEOMETRY', 'GEOM'] if c in gdf_trafos.columns), None)
        if col_geom: 
            gdf_trafos = gdf_trafos.set_geometry(col_geom)
            if gdf_trafos.crs is None: gdf_trafos.set_crs(gdf_voronoi.crs, allow_override=True)
            else: gdf_trafos = gdf_trafos.to_crs(gdf_voronoi.crs)
        else:
            print("   ❌ Erro: Transformadores sem geometria.")
            return

        # Cruzamento Espacial
        print("   ⚙️ Executando sjoin (cruzamento espacial)...")
        try:
            trafos_mapped = gpd.sjoin(
                gdf_trafos, 
                gdf_voronoi[['COD_ID', 'NOM', 'geometry']], 
                how="inner", predicate='intersects', lsuffix='_trafo', rsuffix='_sub'
            )
        except Exception as e:
            print(f"   ❌ Erro sjoin: {e}")
            return

        # Resolução de Colunas
        cols = trafos_mapped.columns.tolist()
        col_id_sub = next((c for c in ['COD_ID__sub', 'COD_ID_sub', 'COD_ID_right', 'COD_ID_SUB', 'COD_ID'] if c in cols), None)
        col_id_trafo = next((c for c in ['CTMT', 'COD_ID__trafo', 'COD_ID_trafo', 'UNI_TR_MT', 'TRANSF_ID', 'COD_ID'] if c in cols), None)
        
        if not col_id_trafo and 'COD_ID' in cols and col_id_sub != 'COD_ID': col_id_trafo = 'COD_ID'
        if not col_id_trafo:
            trafos_mapped['ID_GERADO_AUTO'] = trafos_mapped.index.astype(str)
            col_id_trafo = 'ID_GERADO_AUTO'

        if col_id_sub:
            ref_trafos = trafos_mapped[[col_id_trafo, col_id_sub]].copy()
            ref_trafos.columns = ['ID_TRAFO', 'ID_SUBESTACAO']
            # Limpeza e Remoção de Duplicatas (Essencial)
            ref_trafos['ID_TRAFO'] = ref_trafos['ID_TRAFO'].astype(str).str.replace(r'\.0$', '', regex=True)
            ref_trafos['ID_SUBESTACAO'] = ref_trafos['ID_SUBESTACAO'].astype(str).str.replace(r'\.0$', '', regex=True)
            
            # Remove duplicatas para garantir mapeamento 1:1
            ref_trafos = ref_trafos.drop_duplicates(subset=['ID_TRAFO'])
            
            print(f"   💾 Salvando cache para próxima vez...")
            ref_trafos.to_parquet(CACHE_FILE_TRAFOS)
        else:
            print("   ❌ Erro: Não foi possível identificar ID da Subestação.")
            return

    # --- CRIAÇÃO DO HASH MAP (DICIONÁRIO) ---
    # Isso é MUITO mais rápido e leve que um DataFrame merge
    print("   🗺️  Criando índice de mapeamento em memória (Hash Map)...")
    mapa_trafo_sub = pd.Series(
        ref_trafos.ID_SUBESTACAO.values, 
        index=ref_trafos.ID_TRAFO
    ).to_dict()
    
    # Libera memória do DataFrame antigo
    del ref_trafos
    gc.collect()

    # =========================================================
    # 3. CONSUMIDORES (ALGORITMO EFICIENTE)
    # =========================================================
    print("3. Processando Consumidores...")
    metrics_df = pd.DataFrame()
    
    if mapa_trafo_sub:
        gdf_ucs = carregar_consumidores()
        
        if not gdf_ucs.empty:
            # Descarta geometria
            if hasattr(gdf_ucs, 'geometry'):
                gdf_ucs = pd.DataFrame(gdf_ucs.drop(columns=['geometry']))
            
            gdf_ucs.columns = [c.upper().strip() for c in gdf_ucs.columns]
            
            # Identifica ID do Trafo
            col_trafo_uc = next((c for c in ['CTMT', 'UNI_TR_SD', 'UNI_TR_MT', 'TRANSF_ID', 'ID_TRAFO'] if c in gdf_ucs.columns), None)
            
            if col_trafo_uc:
                print("   ⚡ Calculando consumo anual e mapeando subestações...")
                
                # 1. Limpeza do ID do Trafo
                gdf_ucs['clean_trafo_id'] = gdf_ucs[col_trafo_uc].astype(str).str.replace(r'\.0$', '', regex=True)
                
                # 2. Mapeamento Direto (Lookup O(1)) - Sem Merge pesado
                # Cria coluna 'ID_SUBESTACAO' usando o dicionário
                gdf_ucs['ID_SUBESTACAO'] = gdf_ucs['clean_trafo_id'].map(mapa_trafo_sub)
                
                # Filtra apenas os que foram encontrados (Remove orfãos para economizar processamento)
                ucs_mapped = gdf_ucs.dropna(subset=['ID_SUBESTACAO'])
                print(f"   > {len(ucs_mapped)} clientes vinculados a subestações (de {len(gdf_ucs)} totais).")

                # 3. Cálculo do Consumo Anual (Soma ENE_01 a ENE_12)
                ucs_mapped['CONSUMO_TOTAL_ANO'] = calcular_consumo_anual_otimizado(ucs_mapped)
                
                # 4. Agregação Final
                metrics_df = ucs_mapped.groupby('ID_SUBESTACAO').agg(
                    total_clientes=('clean_trafo_id', 'count'),
                    consumo_anual_mwh=('CONSUMO_TOTAL_ANO', lambda x: x.sum() / 1000) # Soma KWh e vira MWh
                ).reset_index()

                # Limpeza
                del gdf_ucs, ucs_mapped
                gc.collect()
            else:
                print("   ⚠️ Coluna de vínculo com Trafo não encontrada nos consumidores.")

    # =========================================================
    # 4. GERAÇÃO DISTRIBUÍDA (GD)
    # =========================================================
    print("4. Processando GD...")
    gd_summary = pd.DataFrame()

    if mapa_trafo_sub:
        gdf_gd = carregar_geracao_gd()
        if not gdf_gd.empty:
            gdf_gd.columns = [c.upper().strip() for c in gdf_gd.columns]
            
            col_trafo_gd = next((c for c in ['CTMT', 'UNI_TR_MT', 'COD_ID_TRAFO'] if c in gdf_gd.columns), None)
            
            if col_trafo_gd:
                # Mesmo processo: Limpeza -> Map -> Agregação
                gdf_gd['clean_trafo_id'] = gdf_gd[col_trafo_gd].astype(str).str.replace(r'\.0$', '', regex=True)
                gdf_gd['ID_SUBESTACAO'] = gdf_gd['clean_trafo_id'].map(mapa_trafo_sub)
                
                gd_mapped = gdf_gd.dropna(subset=['ID_SUBESTACAO'])
                print(f"   > {len(gd_mapped)} usinas GD vinculadas.")

                col_pot = next((c for c in ['POT_KW', 'MDA_POT_INST', 'POTENCIA'] if c in gd_mapped.columns), None)
                gd_mapped['POT_CALC'] = pd.to_numeric(gd_mapped[col_pot], errors='coerce').fillna(0) if col_pot else 0

                gd_summary = gd_mapped.groupby('ID_SUBESTACAO').agg(
                    total_unidades=('clean_trafo_id', 'count'),
                    potencia_total_kw=('POT_CALC', 'sum')
                ).reset_index()
                
                del gdf_gd, gd_mapped
                gc.collect()

    # =========================================================
    # 5. GERAR RELATÓRIO JSON
    # =========================================================
    print("5. Gerando Relatório Final...")
    relatorio = []

    # Indexação para busca rápida
    if not metrics_df.empty:
        metrics_df.set_index('ID_SUBESTACAO', inplace=True)
    if not gd_summary.empty:
        gd_summary.set_index('ID_SUBESTACAO', inplace=True)

    for idx, row in gdf_voronoi.iterrows():
        sub_id = str(row['COD_ID']).replace('.0', '')
        nome = row.get('NOM', f'Subestação {sub_id}')

        # Busca dados (Lookup no índice é O(1))
        clientes = 0
        consumo = 0.0
        if sub_id in metrics_df.index:
            clientes = int(metrics_df.loc[sub_id, 'total_clientes'])
            consumo = float(metrics_df.loc[sub_id, 'consumo_anual_mwh'])

        gd_qtd = 0
        gd_pot = 0.0
        if sub_id in gd_summary.index:
            gd_qtd = int(gd_summary.loc[sub_id, 'total_unidades'])
            gd_pot = float(gd_summary.loc[sub_id, 'potencia_total_kw'])

        # Classificação
        nivel = "BAIXO"
        if gd_pot > 1000: nivel = "MEDIO"
        if gd_pot > 5000: nivel = "ALTO"

        geom_dict = None
        if hasattr(row, 'geometry') and row.geometry:
            try: geom_dict = mapping(row.geometry)
            except: pass

        stats = {
            "subestacao": f"{nome} (ID: {sub_id})",
            "id_tecnico": str(sub_id),
            "metricas_rede": {
                "total_clientes": clientes,
                "consumo_anual_mwh": round(consumo, 2),
                "nivel_criticidade_gd": nivel
            },
            "geracao_distribuida": {
                "total_unidades": gd_qtd,
                "potencia_total_kw": round(gd_pot, 2),
                "detalhe_por_classe": {}
            },
            "perfil_consumo": {},
            "geometry": geom_dict
        }
        relatorio.append(stats)

    # Salva
    try:
        with open(path_saida, 'w', encoding='utf-8') as f:
            json.dump(relatorio, f, indent=4, ensure_ascii=False)
        print(f"✅ Arquivo JSON gerado: {path_saida}")
        salvar_cache_mercado(relatorio)
        print("✅ Dados salvos no cache do banco.")
    except Exception as e:
        print(f"❌ Erro ao salvar final: {e}")

if __name__ == "__main__":
    analisar_mercado()