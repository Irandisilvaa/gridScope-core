from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
from datetime import datetime

app = FastAPI(title="GridScope AI Service")

# Payload que o Dashboard envia
class DuckCurveRequest(BaseModel):
    data_alvo: str
    potencia_gd_kw: float
    lat: float
    lon: float

@app.post("/predict/duck-curve") # Rota exata que o Dashboard procura
def predict_duck_curve(req: DuckCurveRequest):
    # 1. Simulação das 24 horas
    horas = list(range(24))
    
    # 2. Simulação de Carga (Consumo típico)
    # Madrugada baixa, pico ao meio dia e pico maior à noite
    consumo = [
        25, 22, 20, 19, 20, 25, 40, 55, 65, 70, 75, 80, 
        82, 80, 75, 70, 65, 75, 95, 100, 90, 70, 45, 30
    ]
    
    # 3. Simulação de Geração Solar (Baseada na potência enviada pelo Dash)
    # Geração ocorre entre 6h e 18h
    geracao = []
    potencia_mw = req.potencia_gd_kw / 1000.0
    for h in horas:
        if 6 <= h <= 18:
            # Curva em formato de sino
            seno = np.sin(np.pi * (h - 6) / 12)
            geracao.append(round(seno * potencia_mw * 0.8, 2))
        else:
            geracao.append(0.0)
            
    # 4. Cálculo da Carga Líquida (A Curva do Pato)
    carga_liquida = [round(c - g, 2) for c, g in zip(consumo, geracao)]
    
    # 5. Lógica de Alerta
    min_liquida = min(carga_liquida)
    alerta = min_liquida < 10 # Alerta se a sobra for pouca ou negativa
    
    if min_liquida < 0:
        msg = f"⚠️ RISCO CRÍTICO: Fluxo reverso de {abs(min_liquida)} MW detectado!"
    elif min_liquida < 15:
        msg = "⚠️ ATENÇÃO: Carga líquida muito baixa. Risco de instabilidade."
    else:
        msg = "✅ Operação Estável. Geração distribuída absorvida pela carga."

    return {
        "timeline": horas,
        "consumo_mwh": consumo,
        "geracao_mwh": geracao,
        "carga_liquida_mwh": carga_liquida,
        "analise": msg,
        "alerta": alerta
    }