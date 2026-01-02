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
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from contextlib import asynccontextmanager

# --- CONFIGURAÇÃO ---
DIR_ATUAL = os.path.dirname(os.path.abspath(__file__))

# Nome do modelo padrão (O que você acabou de treinar e validou)
MODELO_PADRAO_NOME = "modelo_consumo_real.pkl"
MODELO_PADRAO_PATH = os.path.join(DIR_ATUAL, MODELO_PADRAO_NOME)

# Cache para não carregar o modelo do disco a cada request
cache_modelos = {}

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [AI_API] {msg}", flush=True)

# --- CICLO DE VIDA ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    log("Inicializando API GridScope AI...")
    
    # Carrega o modelo principal na memória ao iniciar
    if os.path.exists(MODELO_PADRAO_PATH):
        try:
            model = joblib.load(MODELO_PADRAO_PATH)
            cache_modelos["PADRAO"] = model
            log(f"Modelo Principal carregado: {MODELO_PADRAO_NOME}")
        except Exception as e:
            log(f"Erro ao carregar modelo padrão: {e}")
    else:
        log(f"Modelo padrão não encontrado em: {MODELO_PADRAO_PATH}")
    
    yield
    log("Encerrando API...")

app = FastAPI(title="GridScope AI Service", version="5.0", lifespan=lifespan)

# --- INPUT DA API (Agora com 'subestacao') ---
class DuckCurveRequest(BaseModel):
    subestacao: str            # <--- O NOME QUE VOCÊ QUER PASSAR
    data_alvo: str
    potencia_gd_kw: float
    consumo_mes_alvo_mwh: float # O volume real vem do seu Dashboard/BD
    lat: float
    lon: float

# --- FUNÇÃO DE CLIMA (Mantida igual) ---
def obter_clima(lat, lon, data_str):
    # (Mesmo código da sua versão anterior para Open-Meteo)
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {"latitude": lat, "longitude": lon, "start_date": data_str, "end_date": data_str, 
                  "hourly": ["shortwave_radiation", "temperature_2m"], "timezone": "America/Sao_Paulo"}
        r = requests.get(url, params=params, timeout=1.5)
        if r.status_code == 200:
            d = r.json()
            if 'hourly' in d:
                return np.array(d['hourly']['shortwave_radiation']), np.array(d['hourly']['temperature_2m'])
    except:
        pass
    # Fallback
    rad = np.array([0]*6 + [50,200,450,700,850,950,900,800,600,350,150,20] + [0]*6)
    if len(rad) != 24: rad = np.resize(rad, 24)
    return rad, np.array([25.0]*24)

# --- ENDPOINT INTELIGENTE ---
@app.post("/predict/duck-curve")
def prever_curva(payload: DuckCurveRequest):
    log(f"Request recebido: {payload.subestacao} | Data: {payload.data_alvo}")
    
    try:
        # 1. Tenta encontrar modelo específico, senão usa o Padrão
        # Isso permite que no futuro você treine "modelo_ITABAIANA.pkl" e a API ache ele.
        nome_modelo_especifico = f"modelo_{payload.subestacao.upper()}.pkl"
        path_especifico = os.path.join(DIR_ATUAL, nome_modelo_especifico)
        
        modelo_ativo = None
        
        # Lógica de Seleção de Modelo
        if nome_modelo_especifico in cache_modelos:
            modelo_ativo = cache_modelos[nome_modelo_especifico] # Já está na memória
        elif os.path.exists(path_especifico):
            log(f"Carregando modelo específico: {nome_modelo_especifico}")
            modelo_ativo = joblib.load(path_especifico)
            cache_modelos[nome_modelo_especifico] = modelo_ativo # Salva no cache
        else:
            # Usa o modelo genérico (Aracaju) que serve como base comportamental
            modelo_ativo = cache_modelos.get("PADRAO")

        # 2. Prepara Features
        try:
            dt = datetime.strptime(payload.data_alvo, "%Y-%m-%d")
        except:
            dt = datetime.now()
            
        br_holidays = holidays.Brazil()
        dias_mes = calendar.monthrange(dt.year, dt.month)[1]
        
        # Média diária baseada no volume que o usuário mandou
        if payload.consumo_mes_alvo_mwh <= 0: payload.consumo_mes_alvo_mwh = 100
        media_dia_mwh = payload.consumo_mes_alvo_mwh / dias_mes

        # 3. Inferência da IA (Forma da Curva)
        perfil_base = np.zeros(24)
        
        if modelo_ativo:
            df = pd.DataFrame({
                "hora": range(24),
                "mes": dt.month,
                "dia_semana": dt.weekday(),
                "dia_ano": dt.timetuple().tm_yday,
                "ano": dt.year,
                "eh_feriado": int(dt in br_holidays),
                "eh_fim_semana": int(dt.weekday() >= 5)
            })
            # Garante ordem das colunas
            cols = ["hora", "mes", "dia_semana", "dia_ano", "ano", "eh_feriado", "eh_fim_semana"]
            try:
                perfil_base = modelo_ativo.predict(df[cols])
            except Exception as e:
                log(f"Erro no predict: {e}. Usando fallback.")
        
        # Se a IA falhar ou modelo for None, usa fallback matemático
        if np.sum(perfil_base) == 0:
            perfil_base = 10 + 8 * np.exp(-(np.arange(24)-19)**2/8)

        # 4. NORMALIZAÇÃO E ESCALA (O Segredo!)
        # A IA diz: "Às 19h o consumo é o dobro das 04h".
        # A matemática diz: "O total do dia tem que dar X MWh".
        perfil_base = np.maximum(perfil_base, 0.1) # Evita negativos
        fator_forma = perfil_base / perfil_base.sum() # Transforma em % do dia
        
        # Aplica o volume que veio do payload
        consumo_final = fator_forma * media_dia_mwh
        
        # Ajuste fino para feriados se não capturado
        if dt in br_holidays: consumo_final *= 0.9

        # 5. Cálculo Solar e Net Load
        rad, temp = obter_clima(payload.lat, payload.lon, payload.data_alvo)
        gd_mw = payload.potencia_gd_kw / 1000.0
        perda = (temp - 25).clip(min=0) * 0.004
        geracao = gd_mw * (rad / 1000.0) * 0.85 * (1 - perda)
        
        carga_liquida = consumo_final - geracao

        # 6. Diagnóstico
        min_net = np.min(carga_liquida)
        status = "Operação Normal"
        alerta = False
        
        if min_net < 0:
            status = f"FLUXO REVERSO DETECTADO ({abs(min_net):.2f} MWh)"
            alerta = True
        elif min_net < (np.max(consumo_final) * 0.15):
             status = "Cuidado: Margem Baixa (Rampa)"
             alerta = True

        return {
            "subestacao": payload.subestacao,
            "modelo_usado": "Especifico" if nome_modelo_especifico in cache_modelos else "Generico (Base Regional)",
            "timeline": [f"{h:02d}:00" for h in range(24)],
            "consumo": np.round(consumo_final, 3).tolist(),
            "geracao": np.round(geracao, 3).tolist(),
            "carga_liquida": np.round(carga_liquida, 3).tolist(),
            "status": status,
            "alerta": alerta
        }

    except Exception as e:
        log(f"ERRO CRÍTICO: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)