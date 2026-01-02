import geopandas as gpd
import pandas as pd
import os
import json
import warnings

warnings.filterwarnings('ignore')

# --- CONFIGURAÇÕES ---
NOME_PASTA_GDB = "Energisa_SE_6587_2023-12-31_V11_20250701-0833.gdb"
NOME_ARQUIVO_VORONOI = "subestacoes_logicas_aracaju.geojson"
NOME_ARQUIVO_SAIDA = "perfil_mercado_aracaju.json"

# Correção: Mapa expandido para garantir que Rural e Poder Público sejam identificados
MAPA_CLASSES = {
    'RE': 'Residencial',
    'CO': 'Comercial',
    'IN': 'Industrial',
    'RU': 'Rural',
    'PP': 'Poder Público',
    'SP': 'Poder Público', # Serviço Público agrupado em Poder Público
    'PO': 'Poder Público'
}

def analisar_mercado():
    print("INICIANDO ANALISE DETALHADA (POR ID)...")
    
    dir_script = os.path.dirname(os.path.abspath(__file__))
    dir_raiz = os.path.dirname(os.path.dirname(dir_script))
    
    path_voronoi = os.path.join(dir_raiz, NOME_ARQUIVO_VORONOI)
    path_gdb = os.path.join(dir_raiz, "dados", NOME_PASTA_GDB)
    path_saida = os.path.join(dir_raiz, NOME_ARQUIVO_SAIDA)

    # Fallback para caso os arquivos estejam na mesma pasta (debug)
    if not os.path.exists(path_voronoi):
        path_voronoi = NOME_ARQUIVO_VORONOI
        path_gdb = NOME_PASTA_GDB
        path_saida = NOME_ARQUIVO_SAIDA

    if not os.path.exists(path_voronoi):
        print(f"Erro: Voronoi nao encontrado em {path_voronoi}")
        return

    print("1. Carregando territorios...")
    gdf_voronoi = gpd.read_file(path_voronoi).to_crs(epsg=31984)

    if 'COD_ID' not in gdf_voronoi.columns:
        print("ERRO CRÍTICO: O arquivo Voronoi não tem a coluna COD_ID.")
        return

    print("2. Mapeando Transformadores...")
    try:
        gdf_trafos = gpd.read_file(path_gdb, layer='UNTRMT', engine='pyogrio').to_crs(epsg=31984)
        
        # Join espacial para saber qual trafo pertence a qual polígono Voronoi
        trafos_join = gpd.sjoin(gdf_trafos, gdf_voronoi[['NOM', 'COD_ID', 'geometry']], predicate="intersects")
        
        # Mantemos COD_ID (da Subestação) e renomeamos para não confundir com o ID do Trafo
        trafos_join = trafos_join.rename(columns={'COD_ID_right': 'ID_SUBESTACAO', 'NOM': 'NOME_SUBESTACAO'})
        
        ref_trafos = trafos_join[['COD_ID', 'NOME_SUBESTACAO', 'ID_SUBESTACAO']].copy()
        
        # O COD_ID aqui é o do Trafo, usado para linkar com Consumidores
        ref_trafos['COD_ID'] = ref_trafos['COD_ID'].astype(str) 
        
    except Exception as e:
        print(f"Erro ao ler transformadores: {e}")
        return

    print("3. Processando Consumidores...")
    try:
        gdf_uc = gpd.read_file(path_gdb, layer='UCBT_tab', engine='pyogrio', columns=['UNI_TR_MT', 'CLAS_SUB', 'ENE_12', 'PN_CON'])
        df_uc = pd.DataFrame(gdf_uc).drop(columns='geometry', errors='ignore')
        
        # --- CORREÇÃO CRÍTICA: Converter Energia para Float ---
        # Se vier como string/object, a soma resultaria em erro ou concatenação
        df_uc['ENE_12'] = pd.to_numeric(df_uc['ENE_12'], errors='coerce').fillna(0.0)
        
        df_uc['UNI_TR_MT'] = df_uc['UNI_TR_MT'].astype(str)

        # Merge Consumidor -> Trafo (que agora tem o ID da Subestação correta)
        df_cons_final = pd.merge(df_uc, ref_trafos, left_on='UNI_TR_MT', right_on='COD_ID', how='inner')

        # Mapeia as classes usando o dicionário expandido
        df_cons_final['TIPO'] = df_cons_final['CLAS_SUB'].str[:2].map(MAPA_CLASSES).fillna('Outros')

        # Cria mapa auxiliar para classificar a GD (Paineis) baseado na classe do consumidor
        mapa_pn_classe = df_cons_final[['PN_CON', 'TIPO']].drop_duplicates(subset='PN_CON').set_index('PN_CON')['TIPO']
        
    except Exception as e:
        print(f"Erro consumidores: {e}")
        return

    print("4. Processando Paineis Solares e Classificando...")
    try:
        gdf_gd = gpd.read_file(path_gdb, layer='UGBT_tab', engine='pyogrio', columns=['UNI_TR_MT', 'POT_INST', 'PN_CON'])
        df_gd = pd.DataFrame(gdf_gd).drop(columns='geometry', errors='ignore')
        
        # --- CORREÇÃO CRÍTICA: Converter Potência para Float ---
        df_gd['POT_INST'] = pd.to_numeric(df_gd['POT_INST'], errors='coerce').fillna(0.0)
        
        df_gd['UNI_TR_MT'] = df_gd['UNI_TR_MT'].astype(str)
        
        df_gd_final = pd.merge(df_gd, ref_trafos, left_on='UNI_TR_MT', right_on='COD_ID', how='inner')
        
        df_gd_final['TIPO'] = df_gd_final['PN_CON'].map(mapa_pn_classe).fillna('Outros')
        
        print(f"   -> {len(df_gd_final)} usinas mapeadas e classificadas.")
        
    except Exception as e:
        print(f"Aviso GD: {e}")
        df_gd_final = pd.DataFrame(columns=['NOME_SUBESTACAO', 'ID_SUBESTACAO', 'POT_INST', 'TIPO'])

    print("5. Gerando JSON Detalhado (Agrupado por ID Único)...")
    relatorio = []
    
    # Pegamos todos os IDs únicos presentes nos consumidores e na GD
    ids_unicos = set(df_cons_final['ID_SUBESTACAO'].unique()) | set(df_gd_final['ID_SUBESTACAO'].unique())
    ids_unicos = sorted(list([x for x in ids_unicos if str(x) != 'nan']))

    for sub_id in ids_unicos:
        # Filtramos pelo ID, não pelo Nome
        dados_cons = df_cons_final[df_cons_final['ID_SUBESTACAO'] == sub_id]
        dados_gd = df_gd_final[df_gd_final['ID_SUBESTACAO'] == sub_id]
        
        # Recupera o nome (pega o primeiro nome encontrado para esse ID)
        if not dados_cons.empty:
            nome_original = dados_cons.iloc[0]['NOME_SUBESTACAO']
        elif not dados_gd.empty:
            nome_original = dados_gd.iloc[0]['NOME_SUBESTACAO']
        else:
            nome_original = f"Desconhecido ({sub_id})"

        # Cria um nome composto para diferenciar no Dashboard
        nome_display = f"{nome_original} (ID: {sub_id})"

        total_clientes = len(dados_cons)
        consumo_total = dados_cons['ENE_12'].sum() if not dados_cons.empty else 0
        qtd_gd_total = len(dados_gd)
        potencia_gd_total = dados_gd['POT_INST'].sum() if not dados_gd.empty else 0

        nivel_criticidade = "BAIXO"
        if potencia_gd_total > 1000: nivel_criticidade = "MEDIO"
        if potencia_gd_total > 5000: nivel_criticidade = "ALTO"
        
        # Tenta recuperar a geometria original do Voronoi para este ID
        geom_dict = None
        try:
            # Pega a linha do GeoDataFrame original
            geo_row = gdf_voronoi[gdf_voronoi['COD_ID'] == sub_id]
            if not geo_row.empty:
                # Converte a geometria shapely para string JSON e depois para dict
                geom_dict = json.loads(geo_row.iloc[0].geometry.json)
        except Exception:
            pass

        stats = {
            "subestacao": nome_display,
            "id_tecnico": str(sub_id),
            "metricas_rede": {
                "total_clientes": int(total_clientes),
                "consumo_anual_mwh": float(round(consumo_total/1000, 2)),
                "nivel_criticidade_gd": nivel_criticidade
            },
            "geracao_distribuida": {
                "total_unidades": int(qtd_gd_total),
                "potencia_total_kw": float(round(potencia_gd_total, 2)),
                "detalhe_por_classe": {}
            },
            "perfil_consumo": {},
            "geometry": geom_dict # Reintegrando geometria
        }
        
        for cls in ['Residencial', 'Comercial', 'Industrial']:
            # Filtra dados apenas desta classe
            df_classe = dados_cons[dados_cons['TIPO'] == cls]
            qtd_cli = int(df_classe.shape[0])
            
            # --- CORREÇÃO IMPORTANTE: CÁLCULO DO CONSUMO DA CLASSE ---
            # Se não houver clientes, zera tudo
            if qtd_cli > 0:
                consumo_classe = df_classe['ENE_12'].sum()
                pct_val = (qtd_cli/total_clientes)*100
                consumo_mwh = consumo_classe/1000
            else:
                consumo_classe = 0
                pct_val = 0
                consumo_mwh = 0

            # Preenche o objeto sempre (mesmo zerado) para o gráfico não quebrar
            stats["perfil_consumo"][cls] = {
                "qtd_clientes": qtd_cli,
                "pct": round(pct_val, 1),
                "consumo_anual_mwh": float(round(consumo_mwh, 2))
            }
            
            # GD por classe
            pot_classe = dados_gd[dados_gd['TIPO'] == cls]['POT_INST'].sum()
            if pot_classe > 0:
                stats["geracao_distribuida"]["detalhe_por_classe"][cls] = float(round(pot_classe, 2))
        
        relatorio.append(stats)

    with open(path_saida, 'w', encoding='utf-8') as f:
        json.dump(relatorio, f, indent=4, ensure_ascii=False)
        
    print(f"SUCESSO! Relatorio atualizado em: {path_saida}")

if __name__ == "__main__":
    analisar_mercado()