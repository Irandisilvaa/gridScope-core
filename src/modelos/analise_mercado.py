import geopandas as gpd
import pandas as pd
import os
import json
import warnings
import sys
import gc
from shapely.geometry import mapping

warnings.filterwarnings('ignore')

# garante que os módulos do projeto sejam encontrados
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import (
    carregar_voronoi,
    carregar_transformadores,
    carregar_consumidores,
    carregar_geracao_gd,
    salvar_cache_mercado,
)

NOME_ARQUIVO_VORONOI = "subestacoes_logicas.geojson"
NOME_ARQUIVO_SAIDA = "perfil_mercado.json"

MAPA_CLASSES = {
    'RE': 'Residencial', 'RESIDENCIAL': 'Residencial', 'B1': 'Residencial',
    'CO': 'Comercial', 'COMERCIAL': 'Comercial', 'B3': 'Comercial',
    'IN': 'Industrial', 'INDUSTRIAL': 'Industrial', 'A4': 'Industrial',
    'RU': 'Rural', 'RURAL': 'Rural', 'B2': 'Rural',
    'PP': 'Poder Público', 'SP': 'Poder Público', 'PO': 'Poder Público'
}

def limpar_id(valor):
    """
    Normaliza IDs removendo decimais (.0), espaços e garantindo string.
    Essencial para garantir o 'match' entre tabelas.
    """
    if pd.isna(valor) or valor == '':
        return None
    s = str(valor).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return s

def calcular_consumo_real(df):
    """Soma ENE_01 a ENE_12 convertendo erros para 0."""
    cols_energia = [f'ENE_{i:02d}' for i in range(1, 13)]
    cols_existentes = [c for c in cols_energia if c in df.columns]
    
    if not cols_existentes:
        df['CONSUMO_ANUAL'] = 0.0
        return df

    # Converte para numérico e preenche NaN com 0
    df[cols_existentes] = df[cols_existentes].apply(pd.to_numeric, errors='coerce').fillna(0.0)
    
    df['CONSUMO_ANUAL'] = df[cols_existentes].sum(axis=1)
    return df

def analisar_mercado():
    print("INICIANDO ANALISE DETALHADA E LIMPEZA DE DADOS...")
    
    dir_script = os.path.dirname(os.path.abspath(__file__))
    dir_raiz = os.path.dirname(os.path.dirname(dir_script))
    
    path_saida = os.path.join(dir_raiz, NOME_ARQUIVO_SAIDA)
    print("1. Carregando e Normalizando Territórios...")
    try:
        gdf_voronoi = carregar_voronoi()
        # Reprojeção para metros para cálculos se necessário, mas aqui vamos manter controle
        gdf_voronoi = gdf_voronoi.to_crs(epsg=31984) 

        if 'COD_ID' not in gdf_voronoi.columns:
            print("ERRO CRÍTICO: Voronoi sem coluna COD_ID.")
            return

        # Normalização de Nomes
        if 'NOM' not in gdf_voronoi.columns and 'NOME' in gdf_voronoi.columns:
            gdf_voronoi = gdf_voronoi.rename(columns={'NOME': 'NOM'})
        
        # LIMPEZA PROFUNDA DO ID
        gdf_voronoi['COD_ID_CLEAN'] = gdf_voronoi['COD_ID'].apply(limpar_id)
        
        # Remove Voronois sem ID válido
        gdf_voronoi = gdf_voronoi.dropna(subset=['COD_ID_CLEAN'])
        
        print(f"   -> {len(gdf_voronoi)} territórios válidos carregados.")
    except Exception as e:
        print(f"Erro Voronoi: {e}")
        return
    print("2. Mapeando Transformadores (Spatial Join)...")
    try:
        gdf_trafos = carregar_transformadores().to_crs(epsg=31984)

        # Join Espacial: Trafo -> Voronoi
        trafos_join = gpd.sjoin(
            gdf_trafos, 
            gdf_voronoi[['NOM', 'COD_ID_CLEAN', 'geometry']], 
            predicate="intersects", 
            how="inner"
        )

        # Identificação das colunas corretas após o join
        col_id_sub = 'COD_ID_CLEAN' # Coluna que veio do Voronoi (já limpa)
        if 'COD_ID_CLEAN_right' in trafos_join.columns:
            col_id_sub = 'COD_ID_CLEAN_right'
            
        # Coluna do ID do Trafo (geralmente COD_ID ou COD_ID_left)
        col_id_trafo = 'COD_ID'
        if 'COD_ID_left' in trafos_join.columns:
            col_id_trafo = 'COD_ID_left'

        # Cria tabela de referência limpa
        ref_trafos = pd.DataFrame()
        ref_trafos['ID_TRAFO'] = trafos_join[col_id_trafo].apply(limpar_id)
        ref_trafos['ID_SUBESTACAO'] = trafos_join[col_id_sub].apply(limpar_id) # Já deve vir limpo, mas garante
        
        # Remove duplicatas (trafo na borda pode pegar 2 voronois, pegamos o primeiro)
        ref_trafos = ref_trafos.drop_duplicates(subset=['ID_TRAFO'])
        
        print(f"   -> {len(ref_trafos)} transformadores vinculados a subestações.")
    except Exception as e:
        print(f"Erro Crítico em Transformadores: {e}")
        return
    print("3. Processando Consumidores (Vínculo Rigoroso)...")
    df_cons_final = pd.DataFrame()
    mapa_pn_classe = {}
    
    try:
        cols_ene = [f'ENE_{i:02d}' for i in range(1, 13)]
        cols_leitura = ['UNI_TR_MT', 'CLAS_SUB', 'PN_CON'] + cols_ene
        
        # Ignora geometria para economizar memória e evitar erros
        df_uc = carregar_consumidores(colunas=cols_leitura, ignore_geometry=True)

        if df_uc is None or df_uc.empty:
            print("   ⚠️ Aviso: Tabela de consumidores vazia.")
        else:
            df_uc = calcular_consumo_real(df_uc)
            
            # LIMPEZA DO ID DE LIGAÇÃO
            df_uc['TRAFO_LINK'] = df_uc['UNI_TR_MT'].apply(limpar_id)
            
            # MERGE: Consumidor -> Trafo (que já tem a Subestação)
            df_cons_final = pd.merge(
                df_uc, 
                ref_trafos, 
                left_on='TRAFO_LINK', 
                right_on='ID_TRAFO', 
                how='inner'
            )
            
            # Mapeamento de Classes
            df_cons_final['TIPO'] = df_cons_final['CLAS_SUB'].astype(str).str[:2].map(MAPA_CLASSES).fillna('Outros')

            # Cache para usar na GD
            if 'PN_CON' in df_cons_final.columns:
                mapa_pn_classe = df_cons_final[['PN_CON', 'TIPO']].drop_duplicates(subset='PN_CON').set_index('PN_CON')['TIPO']
            
            total_ucs = len(df_uc)
            total_match = len(df_cons_final)
            print(f"   -> {total_match} consumidores vinculados (de um total de {total_ucs}).")
            if total_match == 0:
                print("   ❌ ATENÇÃO: Nenhum consumidor foi vinculado. Verifique se os IDs dos transformadores batem com 'UNI_TR_MT'.")

            del df_uc
            gc.collect()

    except Exception as e:
        print(f"Erro Consumidores: {e}")
    print("4. Processando GD...")
    df_gd_final = pd.DataFrame()
    try:
        df_gd = carregar_geracao_gd(colunas=['UNI_TR_MT', 'POT_INST', 'PN_CON'], ignore_geometry=True)
        
        if df_gd is not None and not df_gd.empty:
            df_gd['POT_INST'] = pd.to_numeric(df_gd['POT_INST'], errors='coerce').fillna(0.0)
            
            # LIMPEZA ID
            df_gd['TRAFO_LINK'] = df_gd['UNI_TR_MT'].apply(limpar_id)

            # MERGE
            df_gd_final = pd.merge(
                df_gd, 
                ref_trafos, 
                left_on='TRAFO_LINK', 
                right_on='ID_TRAFO', 
                how='inner'
            )
            
            if not mapa_pn_classe.empty:
                df_gd_final['TIPO'] = df_gd_final['PN_CON'].map(mapa_pn_classe).fillna('Outros')
            else:
                df_gd_final['TIPO'] = 'Outros'

            print(f"   -> {len(df_gd_final)} unidades de GD vinculadas.")
            del df_gd
            gc.collect()
    except Exception as e:
        print(f"Aviso GD: {e}")

    print("5. Construindo JSON de saída...")
    relatorio = []

    # Prepara geometria WGS84 para exportação
    try:
        gdf_voronoi_wgs = gdf_voronoi.to_crs(epsg=4326)
    except:
        gdf_voronoi_wgs = gdf_voronoi.copy()

    # Otimização: Agrupar dados antes do loop
    print("   -> Agrupando dados para preenchimento rápido...")
    
    # Agrupamento Consumidores
    grouped_cons = pd.DataFrame()
    if not df_cons_final.empty:
        # Por Subestação (Total)
        cons_por_sub = df_cons_final.groupby('ID_SUBESTACAO').agg(
            qtd=('TRAFO_LINK', 'count'),
            consumo=('CONSUMO_ANUAL', 'sum')
        )
        # Por Subestação e Classe (Detalhe)
        cons_por_sub_classe = df_cons_final.groupby(['ID_SUBESTACAO', 'TIPO']).agg(
            qtd=('TRAFO_LINK', 'count'),
            consumo=('CONSUMO_ANUAL', 'sum')
        ).reset_index()
    
    # Agrupamento GD
    grouped_gd = pd.DataFrame()
    if not df_gd_final.empty:
        gd_por_sub = df_gd_final.groupby('ID_SUBESTACAO').agg(
            qtd=('TRAFO_LINK', 'count'),
            potencia=('POT_INST', 'sum')
        )
        gd_por_sub_classe = df_gd_final.groupby(['ID_SUBESTACAO', 'TIPO'])['POT_INST'].sum().reset_index()

    # Loop Principal
    for idx, row in gdf_voronoi.iterrows():
        # Usa o ID Limpo
        sub_id = row['COD_ID_CLEAN']
        nome = row.get('NOM', f'Subestação {sub_id}')

        # 1. Recupera Dados Totais
        total_cli = 0
        total_cons = 0.0
        if not df_cons_final.empty and sub_id in cons_por_sub.index:
            total_cli = int(cons_por_sub.loc[sub_id, 'qtd'])
            total_cons = float(cons_por_sub.loc[sub_id, 'consumo'])

        total_gd_qtd = 0
        total_gd_pot = 0.0
        if not df_gd_final.empty and sub_id in gd_por_sub.index:
            total_gd_qtd = int(gd_por_sub.loc[sub_id, 'qtd'])
            total_gd_pot = float(gd_por_sub.loc[sub_id, 'potencia'])

        # 2. Recupera Geometria Segura
        geom_dict = None
        try:
            geom_wgs = gdf_voronoi_wgs.loc[idx, 'geometry']
            if geom_wgs and not geom_wgs.is_empty:
                geom_dict = mapping(geom_wgs)
        except: pass

        # 3. Definição Nível
        nivel = "BAIXO"
        if total_gd_pot > 1000: nivel = "MEDIO"
        if total_gd_pot > 5000: nivel = "ALTO"

        # 4. Estrutura Base
        stats = {
            "subestacao": f"{nome} (ID: {sub_id})",
            "id_tecnico": str(sub_id),
            "metricas_rede": {
                "total_clientes": total_cli,
                "consumo_anual_mwh": float(round(total_cons/1000, 2)),
                "nivel_criticidade_gd": nivel
            },
            "geracao_distribuida": {
                "total_unidades": total_gd_qtd,
                "potencia_total_kw": float(round(total_gd_pot, 2)),
                "detalhe_por_classe": {}
            },
            "perfil_consumo": {},
            "geometry": geom_dict
        }
        
        # 5. Preenche Perfil Detalhado (Usando os dados agrupados)
        classes_interesse = ['Residencial', 'Comercial', 'Industrial', 'Rural', 'Poder Público']
        
        if total_cli > 0 and not df_cons_final.empty:
            # Filtra o dataframe agrupado (muito mais rápido que filtrar o dataframe gigante)
            dados_cls = cons_por_sub_classe[cons_por_sub_classe['ID_SUBESTACAO'] == sub_id]
            
            for cls in classes_interesse:
                # Busca segura
                linha_cls = dados_cls[dados_cls['TIPO'] == cls]
                
                qtd_cls = 0
                cons_cls = 0.0
                
                if not linha_cls.empty:
                    qtd_cls = int(linha_cls['qtd'].values[0])
                    cons_cls = float(linha_cls['consumo'].values[0])
                
                pct = round((cons_cls/total_cons*100), 1) if total_cons > 0 else 0
                
                stats["perfil_consumo"][cls] = {
                    "qtd_clientes": qtd_cls,
                    "pct": pct,
                    "consumo_anual_mwh": float(round(cons_cls/1000, 2))
                }

        # 6. Preenche GD Detalhada
        if total_gd_pot > 0 and not df_gd_final.empty:
             dados_gd_cls = gd_por_sub_classe[gd_por_sub_classe['ID_SUBESTACAO'] == sub_id]
             for cls in classes_interesse:
                 linha_gd = dados_gd_cls[dados_gd_cls['TIPO'] == cls]
                 if not linha_gd.empty:
                     pot_cls = float(linha_gd['POT_INST'].values[0])
                     if pot_cls > 0:
                        stats["geracao_distribuida"]["detalhe_por_classe"][cls] = float(round(pot_cls, 2))
        
        relatorio.append(stats)

    print("6. Salvando resultados...")
    try:
        with open(path_saida, 'w', encoding='utf-8') as f:
            json.dump(relatorio, f, indent=4, ensure_ascii=False)
        print(f"✅ Arquivo JSON salvo em {path_saida}")
    except Exception as e:
        print(f"Erro ao salvar JSON local: {e}")

    try:
        salvar_cache_mercado(relatorio)
        print("✅ Cache salvo no banco de dados PostgreSQL")
    except Exception as e:
        print(f"⚠️ Aviso: Não foi possível salvar cache no banco: {e}")

def garantir_mercado_atualizado():
    dir_script = os.path.dirname(os.path.abspath(__file__))
    dir_raiz = os.path.dirname(os.path.dirname(dir_script))
    path_saida = os.path.join(dir_raiz, NOME_ARQUIVO_SAIDA)

    if not os.path.exists(path_saida):
        analisar_mercado()
    return path_saida

if __name__ == "__main__":
    analisar_mercado()