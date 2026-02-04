# utils.py
import json
import os
import sys
import math
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import mapping
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Utils")


def _force_scalar(val):
    if val is None:
        return None
    try:
        if isinstance(val, (pd.Series, pd.Index)):
            if val.empty:
                return None
            return _force_scalar(val.iloc[0])
        if isinstance(val, np.ndarray):
            if val.size == 0:
                return None
            if val.size == 1:
                return _force_scalar(val.item())
            return _force_scalar(val[0])
        if isinstance(val, list):
            if not val:
                return None
            if len(val) == 1:
                return _force_scalar(val[0])
        return val
    except Exception:
        return val


def sanitizar_dados(dado):
    try:
        if pd.isna(dado):
            return None

        if isinstance(dado, (pd.Series, pd.Index, np.ndarray, list)):
            if len(dado) == 0:
                return []
            if isinstance(dado, (pd.Series, np.ndarray)) and dado.size == 1:
                return sanitizar_dados(_force_scalar(dado))
            return [sanitizar_dados(x) for x in dado]

        if isinstance(dado, dict):
            return {str(k): sanitizar_dados(v) for k, v in dado.items()}

        if isinstance(dado, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(dado)
        if isinstance(dado, (np.floating, np.float64, np.float32)):
            return float(dado)
        if isinstance(dado, np.bool_):
            return bool(dado)

        if hasattr(dado, "geom_type"):
            return mapping(dado)

        if isinstance(dado, (pd.Timestamp, pd.Timedelta)):
            return str(dado)

        return dado
    except Exception as e:
        logger.warning(f"Erro ao sanitizar dado {type(dado)}: {e}")
        return str(dado)


def limpar_float(val):
    val = _force_scalar(val)
    if val is None or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip()
    try:
        if "," in val_str and "." in val_str:
            val_str = val_str.replace(".", "").replace(",", ".")
        elif "," in val_str:
            val_str = val_str.replace(",", ".")
        val_str = val_str.replace("R$", "").replace("%", "").replace(" ", "")
        return float(val_str)
    except ValueError:
        return 0.0


def carregar_dados_cache():
    try:
        from database import carregar_voronoi, carregar_subestacoes, carregar_cache_mercado

        gdf = carregar_voronoi()
        dados_mercado = carregar_cache_mercado()

        try:
            gdf_subs = carregar_subestacoes()
            if gdf is not None and not gdf.empty and gdf_subs is not None and not gdf_subs.empty:
                if "COD_ID" in gdf.columns and "COD_ID" in gdf_subs.columns:
                    gdf["COD_ID"] = gdf["COD_ID"].astype(str)
                    gdf_subs["COD_ID"] = gdf_subs["COD_ID"].astype(str)
                    merged = gdf.merge(
                        gdf_subs[["COD_ID", "NOME"]].drop_duplicates("COD_ID"),
                        on="COD_ID",
                        how="left"
                    )
                    if "NOME" in merged.columns:
                        merged["NOM"] = merged["NOME"].fillna(merged.get("NOM", ""))
                    gdf = merged
        except Exception as e:
            logger.warning(f"Aviso no merge de nomes (não fatal): {e}")

        return gdf, dados_mercado

    except ImportError as ie:
        logger.error(f"Módulo database não encontrado: {ie}")
        return gpd.GeoDataFrame(), []
    except Exception as e:
        logger.error(f"Erro crítico ao carregar dados: {e}")
        return gpd.GeoDataFrame(), []


def fundir_dados_geo_mercado(gdf, dados_mercado):
    try:
        geo_map = {}
        if gdf is not None and not gdf.empty:
            for _, row in gdf.iterrows():
                geom = row.get("geometry")
                chaves_possiveis = []
                for k in ("NOM", "NOME", "nome", "subestacao", "COD_ID"):
                    try:
                        chaves_possiveis.append(row.get(k))
                    except Exception:
                        chaves_possiveis.append(None)
                for chave in chaves_possiveis:
                    val = _force_scalar(chave)
                    if val:
                        k = str(val).strip().upper()
                        geo_map[k] = geom

        if isinstance(dados_mercado, pd.DataFrame):
            lista_mercado = dados_mercado.to_dict("records")
        elif isinstance(dados_mercado, list):
            lista_mercado = dados_mercado
        else:
            return []

        dados_finais = []
        for item in lista_mercado:
            if not isinstance(item, dict):
                continue
            novo_item = item.copy()
            raw_nome = _force_scalar(novo_item.get("subestacao") or novo_item.get("nome"))
            raw_id = _force_scalar(novo_item.get("id_tecnico") or novo_item.get("id") or novo_item.get("COD_ID"))
            geom_encontrada = None
            if raw_nome:
                nome_limpo = str(raw_nome).split(" (ID")[0].strip().upper()
                geom_encontrada = geo_map.get(nome_limpo)
            if not geom_encontrada and raw_id:
                id_limpo = str(raw_id).strip().upper()
                geom_encontrada = geo_map.get(id_limpo)
            novo_item["geometry"] = geom_encontrada
            dados_finais.append(novo_item)

        return sanitizar_dados(dados_finais)

    except Exception as e:
        logger.error(f"Erro fatal em fundir_dados_geo_mercado: {e}")
        return []
