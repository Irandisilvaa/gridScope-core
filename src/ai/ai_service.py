import pandas as pd
import numpy as np
import joblib
import uvicorn
import traceback
import sys
import os
import requests
import holidays
import calendar   
import geopandas as gpd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from shapely.geometry import Point
from scipy.ndimage import gaussian_filter1d

# Tentativa de importação do módulo de banco de dados
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from src.database import get_engine 
except ImportError:
    pass

app = FastAPI(title="GridScope AI - Enterprise Full", version="7.0 Final-Fix")

DIR_ATUAL = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(DIR_ATUAL, "modelo_consumo.pkl")

# Carregar modelo ML se existir
model_rf = None
if os.path.exists(MODEL_PATH):
    try: 
        model_rf = joblib.load(MODEL_PATH)
        print("✅ Modelo de Consumo ML carregado.")
    except Exception as e: 
        print(f"⚠️ Erro ao carregar modelo ML: {e}")

# Carregar GeoDataFrame de Subestações (Global)
gdf_subs = None
try:
    from database import carregar_subestacoes
    # Carrega apenas o necessário para evitar peso na memória
    gdf_subs = carregar_subestacoes(colunas=['COD_ID', 'NOME', 'geometry'])
except Exception as e:
    print(f"⚠️ Falha ao carregar subestações do banco: {e}")

class DuckCurveRequest(BaseModel):
    data_alvo: str
    potencia_gd_kw: float
    consumo_mes_alvo_mwh: float 
    lat: float
    lon: float
    dna_perfil: dict | None = None 

def normalizar_id(valor):
    if pd.isna(valor): return ""
    s = str(valor).strip().replace('.0', '')
    return s

def buscar_dados_reais_interno(nome_subestacao, mes_alvo):
    """Busca o consumo real no banco de dados para calibrar a simulação."""
    if not nome_subestacao or nome_subestacao == "Desconhecida":
        return None
        
    try:
        from database import carregar_subestacoes, get_engine
        
        # Se o gdf global não estiver carregado, tenta carregar local
        local_gdf = gdf_subs if gdf_subs is not None else carregar_subestacoes()
        if local_gdf is None or local_gdf.empty:
            return None

        filtro = local_gdf['NOME'].astype(str).str.upper().str.contains(str(nome_subestacao).strip().upper(), na=False)
        
        if filtro.sum() == 0: 
            return None

        id_alvo = normalizar_id(local_gdf[filtro].iloc[0]['COD_ID'])
        
        engine = get_engine()
        col_mes = f"ENE_{int(mes_alvo):02d}"
        
        # Query segura
        sql = f"""
            SELECT SUM(c."{col_mes}") as total_kwh
            FROM consumidores c
            JOIN transformadores t ON c."UNI_TR_MT" = t."COD_ID"
            WHERE t."SUB" = '{id_alvo}'
        """
        
        result = pd.read_sql(sql, engine)
        engine.dispose()
        
        if not result.empty and pd.notna(result['total_kwh'].iloc[0]):
            # IMPORTANTE: Converter para float nativo do Python para evitar erro de Série
            val = float(result['total_kwh'].iloc[0])
            return val
        
        return None

    except Exception as e:
        print(f"❌ Erro ETL Banco: {e}")
        return None

def resolver_subestacao(lat, lon):
    if gdf_subs is None or gdf_subs.empty: return "Desconhecida"
    try:
        ponto = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326")
        gdf_alvo = gdf_subs.to_crs("EPSG:4326")
        
        join = gpd.sjoin(ponto, gdf_alvo, how="left", predicate="within")
        if not join.empty:
            # Retorna o primeiro match encontrado
            return str(join.iloc[0].get('NOME', join.iloc[0].get('NOM', 'Subestação')))
    except: 
        pass
    return "Não Mapeada"

def obter_clima(lat, lon, data_str):
    """Obtém dados da API Open-Meteo ou gera dados sintéticos em caso de falha."""
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat, "longitude": lon, 
            "start_date": data_str, "end_date": data_str, 
            "hourly": ["shortwave_radiation", "temperature_2m"], 
            "timezone": "America/Sao_Paulo"
        }
        r = requests.get(url, params=params, timeout=3)
        if r.status_code == 200:
            d = r.json()
            r_api = np.array(d["hourly"]["shortwave_radiation"], dtype=float)
            t_api = np.array(d["hourly"]["temperature_2m"], dtype=float)
            
            # Garantir 24 horas
            if len(r_api) >= 24:
                return r_api[:24], t_api[:24]
    except:
        pass
    
    # Fallback sintético
    horas = np.arange(24)
    rad = 1000 * np.exp(-((horas - 12) ** 2) / (2 * 3.5 ** 2))
    rad[(horas < 6) | (horas > 18)] = 0
    temp = 25 + 5 * np.sin((horas - 14) * np.pi / 12)
    
    return rad, temp

def prever_curva_ml(data_alvo, dna):
    """Gera o shape da curva de consumo usando ML ou heurística."""
    if not dna: dna = {"residencial": 0.4, "comercial": 0.3, "industrial": 0.3, "rural": 0.0}
    
    if model_rf:
        try:
            br_holidays = holidays.Brazil()
            eh_feriado = int(data_alvo.date() in br_holidays)
            eh_fds = int(data_alvo.weekday() >= 5)
            
            features = []
            for h in range(24):
                features.append({
                    "hora": h, "mes": data_alvo.month, "dia_semana": data_alvo.weekday(),
                    "eh_feriado": eh_feriado, "eh_fim_semana": eh_fds,
                    "pct_residencial": float(dna.get('residencial',0)),
                    "pct_comercial": float(dna.get('comercial',0)),
                    "pct_industrial": float(dna.get('industrial',0)),
                    "pct_rural": float(dna.get('rural',0))
                })
            
            predicao = model_rf.predict(pd.DataFrame(features))
            return np.array(predicao, dtype=float)
        except: 
            pass
    
    # Fallback Senoidal
    t = np.linspace(0, 24, 24)
    return np.maximum(10 + 5 * np.sin((t - 10) * np.pi / 12), 0.1)

@app.post("/predict/duck-curve")
def calcular_curva_inteligente(payload: DuckCurveRequest):
    try:
        # 1. Resolver Local e Data
        sub_nome = resolver_subestacao(payload.lat, payload.lon)
        try:
            dt = datetime.strptime(payload.data_alvo, "%Y-%m-%d")
        except:
            dt = datetime.now()

        # 2. Definir Consumo Base (Real vs Estimado)
        consumo_real = buscar_dados_reais_interno(sub_nome, dt.month)
        
        # Garantia de float nativo
        if consumo_real is not None and float(consumo_real) > 0:
            consumo_mes_final_kwh = float(consumo_real)
            origem = "GDB (Real)"
        else:
            val = float(payload.consumo_mes_alvo_mwh)
            # Se vier em MWh e for muito pequeno, assume erro de unidade, senão converte
            consumo_mes_final_kwh = val * 1000.0 if val < 50000 else val
            origem = "Estimado"

        # 3. Preparar Potência GD
        pot_gd_input = float(payload.potencia_gd_kw)
        # Verificação simples de unidade (W vs kW)
        razao = pot_gd_input / consumo_mes_final_kwh if consumo_mes_final_kwh != 0 else 0
        if razao > 0.5 and pot_gd_input > 10000: 
            pot_gd_final_kw = pot_gd_input / 1000.0
        else:
            pot_gd_final_kw = pot_gd_input

        # 4. Calcular Carga Média
        _, dias_no_mes = calendar.monthrange(dt.year, dt.month)
        media_diaria_kwh = consumo_mes_final_kwh / dias_no_mes if dias_no_mes > 0 else consumo_mes_final_kwh

        # 5. Gerar Shape da Curva
        curva_shape = prever_curva_ml(dt, payload.dna_perfil)

        # Normalização do shape
        max_val = np.max(curva_shape)
        if max_val > 0:
            curva_shape = curva_shape / max_val 
        else:
            curva_shape = np.ones(24) * 0.5  
            
        perfil_tipico = np.array([
            0.3, 0.25, 0.2, 0.18, 0.2, 0.3, 0.5, 
            0.8, 0.9, 0.85, 0.8, 0.75, 0.7,       
            0.8, 0.9, 1.0, 0.95, 0.9, 0.85,       
            0.7, 0.6, 0.5, 0.4, 0.35              
        ])
        
        # Mescla shape ML com típico para suavizar
        curva_combinada = 0.7 * curva_shape + 0.3 * perfil_tipico
        
        soma_shape = curva_combinada.sum()
        if soma_shape == 0: soma_shape = 1
            
        # 6. Processar DNA (Perfil de Carga)
        dna = payload.dna_perfil or {}
        try:
            dna_res = float(dna.get('residencial', 0) or 0)
            dna_com = float(dna.get('comercial', 0) or 0)
            dna_ind = float(dna.get('industrial', 0) or 0)
            dna_rur = float(dna.get('rural', 0) or 0)
        except:
            dna_res, dna_com, dna_ind, dna_rur = 0.4, 0.3, 0.3, 0.0

        soma_dna = dna_res + dna_com + dna_ind + dna_rur
        if soma_dna <= 0:
            dna_res, dna_com, dna_ind, dna_rur = 0.4, 0.3, 0.3, 0.0
            soma_dna = 1.0

        # Renormaliza DNA
        dna_res /= soma_dna; dna_com /= soma_dna; dna_ind /= soma_dna; dna_rur /= soma_dna
        dna_usado = {"residencial": dna_res, "comercial": dna_com, "industrial": dna_ind, "rural": dna_rur}

        # Ajuste de escala por perfil
        fator_escala = 1.0
        if dna_ind > 0.5: fator_escala = 1.2
        elif dna_res > 0.7: fator_escala = 0.8
            
        # CURVA CONSUMO FINAL (array)
        curve_consumo = curva_combinada * (media_diaria_kwh / soma_shape) * fator_escala
        
        # 7. Calcular Geração Solar
        rad, temp = obter_clima(payload.lat, payload.lon, payload.data_alvo)
        eficiencia_temp = 1.0 - np.clip((temp - 25.0) * 0.004, 0.0, 0.2)
        
        horas = np.arange(24)
        fator_diurno = np.exp(-((horas - 12) ** 2) / (2 * 4 ** 2))
        fator_diurno[(horas < 6) | (horas > 19)] = 0
        
        # CURVA GERAÇÃO FINAL (array)
        curve_geracao = pot_gd_final_kw * (rad / 1000.0) * 0.85 * eficiencia_temp * fator_diurno
        
        if len(curve_geracao) > 0:
            curve_geracao = gaussian_filter1d(curve_geracao, sigma=1.0)
        
        # CURVA LÍQUIDA
        curve_liquida = curve_consumo - curve_geracao
        
        # Garantir valor mínimo visual para gráficos
        min_visivel_val = float(np.min(curve_consumo)) * 0.1
        min_visivel = max(min_visivel_val, 1.0)
        curve_consumo = np.maximum(curve_consumo, min_visivel)

        # 8. Preparar Resposta (JSON Safe)
        # Importante: usar .tolist() para arrays numpy e float() para escalares
        consumo_res_kwh = np.round(curve_consumo * dna_res, 3).tolist()
        consumo_com_kwh = np.round(curve_consumo * dna_com, 3).tolist()
        consumo_ind_kwh = np.round(curve_consumo * dna_ind, 3).tolist()

        consumo_mensal_por_classe = {
            str(int(dt.month)): {
                "residencial": float(consumo_mes_final_kwh * dna_res),
                "comercial": float(consumo_mes_final_kwh * dna_com),
                "industrial": float(consumo_mes_final_kwh * dna_ind),
                "rural": float(consumo_mes_final_kwh * dna_rur)
            }
        }

        return {
            "subestacao": sub_nome,
            "timeline": [f"{h:02d}:00" for h in range(24)],
            "consumo_kwh": np.round(curve_consumo, 3).tolist(),
            "geracao_kwh": np.round(curve_geracao, 3).tolist(),
            "carga_liquida_kwh": np.round(curve_liquida, 3).tolist(),
            "consumo_res_kwh": consumo_res_kwh,
            "consumo_com_kwh": consumo_com_kwh,
            "consumo_ind_kwh": consumo_ind_kwh,
            "consumo_mes_alvo_kwh": float(consumo_mes_final_kwh),
            "origem_consumo": origem,
            "pot_gd_final_kw": float(pot_gd_final_kw),
            "dna_perfil_usado": dna_usado,
            "consumo_mensal_por_classe": consumo_mensal_por_classe,
            "alerta": bool(np.min(curve_liquida) < 0),
            "analise": f"Carga Média: {media_diaria_kwh/24:.0f} kW | GD: {pot_gd_final_kw:.0f} kWp"
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)