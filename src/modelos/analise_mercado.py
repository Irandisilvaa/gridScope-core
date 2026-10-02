import geopandas as gpd
import pandas as pd
import os
import json
import warnings
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
import gc
from shapely.geometry import mapping

warnings.filterwarnings('ignore')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import (
    carregar_voronoi,
    carregar_transformadores,
    carregar_consumidores,
    carregar_geracao_gd,
    salvar_cache_mercado,
)
from config import DIR_DADOS
from municipalities import ESCOPO_TODA_BASE, normalizar_codigo_municipio

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
    if not s:
        return None
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

    df[cols_existentes] = df[cols_existentes].apply(pd.to_numeric, errors='coerce').fillna(0.0)
    
    df['CONSUMO_ANUAL'] = df[cols_existentes].sum(axis=1)
    return df


def _classificar_geracao_por_classe(
    df_geracao: pd.DataFrame, mapa_pn_classe: pd.Series
) -> pd.DataFrame:
    if mapa_pn_classe.empty:
        df_geracao['TIPO'] = 'Outros'
    else:
        df_geracao['TIPO'] = df_geracao['PN_CON'].map(mapa_pn_classe).fillna('Outros')
    return df_geracao


def _construir_relatorio_escopo(
    gdf_voronoi: gpd.GeoDataFrame,
    gdf_voronoi_wgs: gpd.GeoDataFrame,
    df_cons_final: pd.DataFrame,
    df_gd_final: pd.DataFrame,
    municipio_codigo: str,
    subestacoes_permitidas: set[str] | None = None,
) -> list[dict]:
    """Agrega o mesmo modelo para a base inteira ou para um município."""

    if municipio_codigo == ESCOPO_TODA_BASE:
        consumidores = df_cons_final
        geracao = df_gd_final
    else:
        consumidores = df_cons_final[
            df_cons_final["MUNICIPIO_CODIGO"] == municipio_codigo
        ] if not df_cons_final.empty else df_cons_final
        geracao = df_gd_final[
            df_gd_final["MUNICIPIO_CODIGO"] == municipio_codigo
        ] if not df_gd_final.empty else df_gd_final

    cons_por_sub = pd.DataFrame(columns=["qtd", "consumo"])
    cons_por_sub_classe = pd.DataFrame(columns=["ID_SUBESTACAO", "TIPO", "qtd", "consumo"])
    if not consumidores.empty:
        cons_por_sub = consumidores.groupby("ID_SUBESTACAO").agg(
            qtd=("TRAFO_LINK", "count"),
            consumo=("CONSUMO_ANUAL", "sum"),
        )
        cons_por_sub_classe = consumidores.groupby(["ID_SUBESTACAO", "TIPO"]).agg(
            qtd=("TRAFO_LINK", "count"),
            consumo=("CONSUMO_ANUAL", "sum"),
        ).reset_index()

    gd_por_sub = pd.DataFrame(columns=["qtd", "potencia"])
    gd_por_sub_classe = pd.DataFrame(columns=["ID_SUBESTACAO", "TIPO", "qtd", "potencia"])
    if not geracao.empty:
        gd_por_sub = geracao.groupby("ID_SUBESTACAO").agg(
            qtd=("TRAFO_LINK", "count"),
            potencia=("POT_INST", "sum"),
        )
        gd_por_sub_classe = geracao.groupby(["ID_SUBESTACAO", "TIPO"]).agg(
            qtd=("TRAFO_LINK", "count"),
            potencia=("POT_INST", "sum"),
        ).reset_index()

    df_temporal_sub: dict[str, dict | list] = {}
    if not consumidores.empty and "ANO_MES" in consumidores.columns:
        df_validos = consumidores.dropna(subset=["ANO_MES"])
        if not df_validos.empty:
            cons_tempo = df_validos.groupby(["ID_SUBESTACAO", "ANO_MES"]).size().reset_index(name="novos_clientes")
            cons_tempo = cons_tempo.sort_values(["ID_SUBESTACAO", "ANO_MES"])
            cons_tempo["clientes_cumulativo"] = cons_tempo.groupby("ID_SUBESTACAO")["novos_clientes"].cumsum()
            for sub, group in cons_tempo.groupby("ID_SUBESTACAO"):
                df_temporal_sub.setdefault(str(sub), {})["clientes"] = (
                    group[["ANO_MES", "clientes_cumulativo"]]
                    .set_index("ANO_MES")
                    .to_dict()["clientes_cumulativo"]
                )

    if not geracao.empty and "ANO_MES" in geracao.columns:
        df_validos = geracao.dropna(subset=["ANO_MES"])
        if not df_validos.empty:
            gd_tempo = df_validos.groupby(["ID_SUBESTACAO", "ANO_MES"]).agg(
                novas_unidades=("TRAFO_LINK", "count"),
                nova_potencia=("POT_INST", "sum"),
            ).reset_index()
            gd_tempo = gd_tempo.sort_values(["ID_SUBESTACAO", "ANO_MES"])
            gd_tempo["mmgd_cumulativo"] = gd_tempo.groupby("ID_SUBESTACAO")["novas_unidades"].cumsum()
            gd_tempo["potencia_cumulativa"] = gd_tempo.groupby("ID_SUBESTACAO")["nova_potencia"].cumsum()
            for sub, group in gd_tempo.groupby("ID_SUBESTACAO"):
                temporal = df_temporal_sub.setdefault(str(sub), {})
                temporal["mmgd"] = (
                    group[["ANO_MES", "mmgd_cumulativo"]]
                    .set_index("ANO_MES")
                    .to_dict()["mmgd_cumulativo"]
                )
                temporal["potencia"] = (
                    group[["ANO_MES", "potencia_cumulativa"]]
                    .set_index("ANO_MES")
                    .to_dict()["potencia_cumulativa"]
                )

    for sub, mod_data in list(df_temporal_sub.items()):
        todos_meses: set[str] = set()
        for dict_mes in mod_data.values():
            todos_meses.update(dict_mes.keys())
        last_cli = 0
        last_mmgd = 0
        last_pot = 0.0
        consolidado = []
        for mes in sorted(todos_meses):
            last_cli = mod_data.get("clientes", {}).get(mes, last_cli)
            last_mmgd = mod_data.get("mmgd", {}).get(mes, last_mmgd)
            last_pot = mod_data.get("potencia", {}).get(mes, last_pot)
            consolidado.append({
                "mes": mes,
                "clientes": last_cli,
                "unidades_mmgd": last_mmgd,
                "potencia_kw": float(round(last_pot, 2)),
            })
        df_temporal_sub[sub] = consolidado

    relatorio: list[dict] = []
    gdf_voronoi_unicos = gdf_voronoi.drop_duplicates(subset=["COD_ID_CLEAN"]).copy()
    for idx, row in gdf_voronoi_unicos.iterrows():
        sub_id = row["COD_ID_CLEAN"]
        if subestacoes_permitidas is not None and sub_id not in subestacoes_permitidas:
            continue
        nome = row.get("NOM", f"Subestação {sub_id}")

        total_cli = 0
        total_cons = 0.0
        if sub_id in cons_por_sub.index:
            total_cli = int(cons_por_sub.loc[sub_id, "qtd"])
            total_cons = float(cons_por_sub.loc[sub_id, "consumo"])

        total_gd_qtd = 0
        total_gd_pot = 0.0
        if sub_id in gd_por_sub.index:
            total_gd_qtd = int(gd_por_sub.loc[sub_id, "qtd"])
            total_gd_pot = float(gd_por_sub.loc[sub_id, "potencia"])

        geom_dict = None
        try:
            geom_wgs = gdf_voronoi_wgs.loc[idx, "geometry"]
            if geom_wgs is not None and not geom_wgs.is_empty:
                geom_dict = mapping(geom_wgs)
        except Exception:
            pass

        consumo_anual_mwh = total_cons / 1000
        demanda_media_kw = (consumo_anual_mwh * 1000) / 8760 if consumo_anual_mwh > 0 else 0
        razao_r = total_gd_pot / demanda_media_kw if demanda_media_kw > 0 else 0
        nivel = "NORMAL" if razao_r < 0.4 else "MÉDIO" if razao_r <= 1.0 else "CRÍTICO"

        stats = {
            "municipio_codigo": municipio_codigo,
            "subestacao": f"{nome} (ID: {sub_id})",
            "id_tecnico": str(sub_id),
            "metricas_rede": {
                "total_clientes": total_cli,
                "consumo_anual_mwh": float(round(total_cons / 1000, 2)),
                "nivel_criticidade_gd": nivel,
            },
            "geracao_distribuida": {
                "total_unidades": total_gd_qtd,
                "potencia_total_kw": float(round(total_gd_pot, 2)),
                "detalhe_por_classe": {},
            },
            "perfil_consumo": {},
            "evolucao_temporal": df_temporal_sub.get(str(sub_id), []),
            "geometry": geom_dict,
        }

        classes_interesse = ["Residencial", "Comercial", "Industrial", "Rural", "Poder Público"]
        if total_cli > 0:
            dados_cls = cons_por_sub_classe[cons_por_sub_classe["ID_SUBESTACAO"] == sub_id]
            for classe in classes_interesse:
                linha_cls = dados_cls[dados_cls["TIPO"] == classe]
                qtd_cls = int(linha_cls["qtd"].values[0]) if not linha_cls.empty else 0
                cons_cls = float(linha_cls["consumo"].values[0]) if not linha_cls.empty else 0.0
                stats["perfil_consumo"][classe] = {
                    "qtd_clientes": qtd_cls,
                    "pct": round((cons_cls / total_cons * 100), 1) if total_cons > 0 else 0,
                    "consumo_anual_mwh": float(round(cons_cls / 1000, 2)),
                }

            dados_gd_cls = gd_por_sub_classe[gd_por_sub_classe["ID_SUBESTACAO"] == sub_id]
            for classe in classes_interesse:
                linha_gd = dados_gd_cls[dados_gd_cls["TIPO"] == classe]
                if not linha_gd.empty:
                    potencia = float(linha_gd["potencia"].values[0])
                    quantidade = int(linha_gd["qtd"].values[0])
                    if potencia > 0 or quantidade > 0:
                        stats["geracao_distribuida"]["detalhe_por_classe"][classe] = {
                            "potencia_kw": float(round(potencia, 2)),
                            "qtd": quantidade,
                        }

        relatorio.append(stats)
    return relatorio

def analisar_mercado():
    print("INICIANDO ANALISE DETALHADA E LIMPEZA DE DADOS...")
    
    dir_script = os.path.dirname(os.path.abspath(__file__))
    dir_raiz = os.path.dirname(os.path.dirname(dir_script))
    
    path_saida = os.path.join(dir_raiz, NOME_ARQUIVO_SAIDA)
    print("1. Carregando e Normalizando Territórios...")
    try:
        gdf_voronoi = carregar_voronoi()
        gdf_voronoi = gdf_voronoi.to_crs(epsg=31984) 

        if 'COD_ID' not in gdf_voronoi.columns:
            raise RuntimeError("Voronoi sem coluna COD_ID")

        if 'NOM' not in gdf_voronoi.columns and 'NOME' in gdf_voronoi.columns:
            gdf_voronoi = gdf_voronoi.rename(columns={'NOME': 'NOM'})
        
        gdf_voronoi['COD_ID_CLEAN'] = gdf_voronoi['COD_ID'].apply(limpar_id)
        
        gdf_voronoi = gdf_voronoi.dropna(subset=['COD_ID_CLEAN'])
        
        print(f"   -> {len(gdf_voronoi)} territórios válidos carregados.")
    except Exception as e:
        print(f"Erro Voronoi: {e}")
        raise RuntimeError("Falha ao carregar territórios Voronoi") from e
    print("2. Mapeando Transformadores (Spatial Join)...")
    try:
        gdf_trafos = carregar_transformadores().to_crs(epsg=31984)

        gdf_voronoi['COD_ID_CLEAN'] = gdf_voronoi['COD_ID'].apply(limpar_id)
        gdf_voronoi = gdf_voronoi.dropna(subset=['COD_ID_CLEAN'])

        if 'SUB' in gdf_trafos.columns and gdf_trafos['SUB'].notna().any():
            ref_trafos = pd.DataFrame()
            ref_trafos['ID_TRAFO'] = gdf_trafos['COD_ID'].apply(limpar_id)
            ref_trafos['ID_SUBESTACAO'] = gdf_trafos['SUB'].apply(limpar_id)
            if 'MUN' in gdf_trafos.columns:
                ref_trafos['MUNICIPIO_CODIGO'] = gdf_trafos['MUN'].apply(normalizar_codigo_municipio)
            else:
                ref_trafos['MUNICIPIO_CODIGO'] = None
        else:
            trafos_join = gpd.sjoin(
                gdf_trafos,
                gdf_voronoi[['NOM', 'COD_ID_CLEAN', 'geometry']],
                predicate="intersects",
                how="inner"
            )

            col_id_sub = 'COD_ID_CLEAN'
            if 'COD_ID_CLEAN_right' in trafos_join.columns:
                col_id_sub = 'COD_ID_CLEAN_right'

            col_id_trafo = 'COD_ID'
            if 'COD_ID_left' in trafos_join.columns:
                col_id_trafo = 'COD_ID_left'

            ref_trafos = pd.DataFrame()
            ref_trafos['ID_TRAFO'] = trafos_join[col_id_trafo].apply(limpar_id)
            ref_trafos['ID_SUBESTACAO'] = trafos_join[col_id_sub].apply(limpar_id)
            coluna_municipio = next(
                (coluna for coluna in ('MUN', 'MUN_left') if coluna in trafos_join.columns),
                None,
            )
            if coluna_municipio:
                ref_trafos['MUNICIPIO_CODIGO'] = trafos_join[coluna_municipio].apply(normalizar_codigo_municipio)
            else:
                ref_trafos['MUNICIPIO_CODIGO'] = None

        ref_trafos = ref_trafos.dropna(subset=['ID_TRAFO', 'ID_SUBESTACAO'])
        ambiguos = ref_trafos[ref_trafos['ID_TRAFO'].duplicated(keep=False)]
        if not ambiguos.empty:
            raise RuntimeError("Transformador vinculado a mais de um território")

        print(f"   -> {len(ref_trafos)} transformadores vinculados a subestações.")
    except Exception as e:
        print(f"Erro Crítico em Transformadores: {e}")
        raise RuntimeError("Falha ao vincular transformadores aos territórios") from e
    print("3. Processando Consumidores (Vínculo Rigoroso)...")
    df_cons_final = pd.DataFrame()
    mapa_pn_classe = pd.Series(dtype='object')
    
    try:
        cols_ene = [f'ENE_{i:02d}' for i in range(1, 13)]
        cols_leitura = ['UNI_TR_MT', 'CLAS_SUB', 'PN_CON', 'DAT_CON', 'MUN'] + cols_ene
        
        df_uc = carregar_consumidores(colunas=cols_leitura, ignore_geometry=True)

        if df_uc is None or df_uc.empty:
            raise RuntimeError("Tabela de consumidores vazia; análise não publicada")
        else:
            df_uc = calcular_consumo_real(df_uc)
            
            df_uc['TRAFO_LINK'] = df_uc['UNI_TR_MT'].apply(limpar_id)
            
            df_cons_final = pd.merge(
                df_uc, 
                ref_trafos, 
                left_on='TRAFO_LINK', 
                right_on='ID_TRAFO', 
                how='inner'
            )
            municipio_trafo = df_cons_final.get('MUNICIPIO_CODIGO')
            if 'MUN' in df_cons_final.columns:
                municipio_consumidor = df_cons_final['MUN'].apply(normalizar_codigo_municipio)
            else:
                municipio_consumidor = pd.Series(None, index=df_cons_final.index, dtype='object')
            df_cons_final['MUNICIPIO_CODIGO'] = municipio_consumidor
            if municipio_trafo is not None:
                df_cons_final['MUNICIPIO_CODIGO'] = df_cons_final['MUNICIPIO_CODIGO'].fillna(municipio_trafo)
            
            df_cons_final['TIPO'] = df_cons_final['CLAS_SUB'].astype(str).str[:2].map(MAPA_CLASSES).fillna('Outros')

            if 'PN_CON' in df_cons_final.columns:
                mapa_pn_classe = df_cons_final[['PN_CON', 'TIPO']].drop_duplicates(subset='PN_CON').set_index('PN_CON')['TIPO']

            # Tratamento de Data para Série Temporal
            if 'DAT_CON' in df_cons_final.columns:
                # Converte para datetime e extrai YYYY-MM
                df_cons_final['DATA_CONEXAO'] = pd.to_datetime(df_cons_final['DAT_CON'], errors='coerce', dayfirst=True)
                df_cons_final['ANO_MES'] = df_cons_final['DATA_CONEXAO'].dt.to_period('M').astype(str)
                # Remove nulos caso a data seja inválida para a série temporal
                df_cons_final['ANO_MES'] = df_cons_final['ANO_MES'].replace('NaT', None)
            
            total_ucs = len(df_uc)
            total_match = len(df_cons_final)
            print(f"   -> {total_match} consumidores vinculados (de um total de {total_ucs}).")
            if total_match == 0:
                print("   ❌ ATENÇÃO: Nenhum consumidor foi vinculado. Verifique se os IDs dos transformadores batem com 'UNI_TR_MT'.")

            del df_uc
            gc.collect()

    except Exception as e:
        print(f"Erro Consumidores: {e}")
        raise RuntimeError("Falha ao processar consumidores; análise não publicada") from e
    print("4. Processando GD...")
    df_gd_final = pd.DataFrame()
    try:
        df_gd = carregar_geracao_gd(
            colunas=['UNI_TR_MT', 'POT_INST', 'PN_CON', 'DAT_CON', 'MUN'],
            ignore_geometry=True,
        )
        
        if df_gd is not None and not df_gd.empty:
            df_gd['POT_INST'] = pd.to_numeric(df_gd['POT_INST'], errors='coerce').fillna(0.0)
            
            df_gd['TRAFO_LINK'] = df_gd['UNI_TR_MT'].apply(limpar_id)

            df_gd_final = pd.merge(
                df_gd, 
                ref_trafos, 
                left_on='TRAFO_LINK', 
                right_on='ID_TRAFO', 
                how='inner'
            )
            municipio_trafo = df_gd_final.get('MUNICIPIO_CODIGO')
            if 'MUN' in df_gd_final.columns:
                municipio_gd = df_gd_final['MUN'].apply(normalizar_codigo_municipio)
            else:
                municipio_gd = pd.Series(None, index=df_gd_final.index, dtype='object')
            df_gd_final['MUNICIPIO_CODIGO'] = municipio_gd
            if municipio_trafo is not None:
                df_gd_final['MUNICIPIO_CODIGO'] = df_gd_final['MUNICIPIO_CODIGO'].fillna(municipio_trafo)
            
            df_gd_final = _classificar_geracao_por_classe(df_gd_final, mapa_pn_classe)

            # Tratamento de Data para Série Temporal
            if 'DAT_CON' in df_gd_final.columns:
                df_gd_final['DATA_CONEXAO'] = pd.to_datetime(df_gd_final['DAT_CON'], errors='coerce', dayfirst=True)
                df_gd_final['ANO_MES'] = df_gd_final['DATA_CONEXAO'].dt.to_period('M').astype(str)
                df_gd_final['ANO_MES'] = df_gd_final['ANO_MES'].replace('NaT', None)

            print(f"   -> {len(df_gd_final)} unidades de GD vinculadas.")
            del df_gd
            gc.collect()
    except Exception as e:
        print(f"Aviso GD: {e}")
        raise RuntimeError("Falha ao processar geração distribuída; análise não publicada") from e

    print("5. Construindo JSON de saída...")
    try:
        gdf_voronoi_wgs = gdf_voronoi.to_crs(epsg=4326)
    except Exception:
        gdf_voronoi_wgs = gdf_voronoi.copy()

    print("   -> Gerando escopos de base inteira e municípios...")
    subestacoes_por_municipio: dict[str, set[str]] = {}
    for municipio, grupo in ref_trafos.dropna(subset=["MUNICIPIO_CODIGO"]).groupby("MUNICIPIO_CODIGO"):
        subestacoes_por_municipio[str(municipio)] = set(grupo["ID_SUBESTACAO"].dropna().astype(str))

    codigos_municipios = set(subestacoes_por_municipio)
    for dataframe in (df_cons_final, df_gd_final):
        if not dataframe.empty and "MUNICIPIO_CODIGO" in dataframe.columns:
            codigos_municipios.update(dataframe["MUNICIPIO_CODIGO"].dropna().unique())

    relatorio_toda_base = _construir_relatorio_escopo(
        gdf_voronoi,
        gdf_voronoi_wgs,
        df_cons_final,
        df_gd_final,
        ESCOPO_TODA_BASE,
    )
    relatorio = list(relatorio_toda_base)
    for municipio in sorted(str(codigo) for codigo in codigos_municipios if codigo):
        relatorio.extend(
            _construir_relatorio_escopo(
                gdf_voronoi,
                gdf_voronoi_wgs,
                df_cons_final,
                df_gd_final,
                municipio,
                subestacoes_por_municipio.get(municipio, set()),
            )
        )

    print("6. Salvando resultados...")
    if os.getenv("GRIDSCOPE_DERIVED_STAGING") == "1":
        print("Staging ativo: arquivos derivados locais não serão publicados.")
    else:
        try:
            with open(path_saida, 'w', encoding='utf-8') as f:
                json.dump(relatorio_toda_base, f, indent=4, ensure_ascii=False)
            print(f"✅ Arquivo JSON salvo em {path_saida}")

            path_global_json = os.path.join(DIR_DADOS, "cache_mercado_toda_base.json")
            with open(path_global_json, 'w', encoding='utf-8') as f:
                json.dump(relatorio_toda_base, f, indent=4, ensure_ascii=False)
            print(f"✅ Cache de mercado global salvo em {path_global_json}")
        except Exception as e:
            print(f"Erro ao salvar JSON local: {e}")

    try:
        salvar_cache_mercado(relatorio)
        print("✅ Cache salvo no banco de dados PostgreSQL")
    except Exception as e:
        print(f"⚠️ Aviso: Não foi possível salvar cache no banco: {e}")
        raise RuntimeError("Falha ao persistir cache de mercado; análise não publicada") from e

def garantir_mercado_atualizado():
    dir_script = os.path.dirname(os.path.abspath(__file__))
    dir_raiz = os.path.dirname(os.path.dirname(dir_script))
    path_saida = os.path.join(dir_raiz, NOME_ARQUIVO_SAIDA)

    if not os.path.exists(path_saida):
        analisar_mercado()
    return path_saida

if __name__ == "__main__":
    analisar_mercado()
