from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
from datetime import datetime

app = FastAPI(title="GridScope AI Service")

class DuckCurveRequest(BaseModel):
    data_alvo: str
    potencia_gd_kw: float
    lat: float
    lon: float

@app.post("/predict/duck-curve") 
def predict_duck_curve(req: DuckCurveRequest):
   
    horas = list(range(24))
    
    
    consumo = [
        25, 22, 20, 19, 20, 25, 40, 55, 65, 70, 75, 80, 
        82, 80, 75, 70, 65, 75, 95, 100, 90, 70, 45, 30
    ]
    
    
    geracao = []
    potencia_mw = req.potencia_gd_kw / 1000.0
    for h in horas:
        if 6 <= h <= 18:

            seno = np.sin(np.pi * (h - 6) / 12)
            geracao.append(round(seno * potencia_mw * 0.8, 2))
        else:
            geracao.append(0.0)
            

    carga_liquida = [round(c - g, 2) for c, g in zip(consumo, geracao)]
    
   
    min_liquida = min(carga_liquida)
    alerta = min_liquida < 10 
    
    if min_liquida < 0:
        msg = f"RISCO CRÍTICO: Fluxo reverso de {abs(min_liquida)} MW detectado!"
    elif min_liquida < 15:
        msg = "ATENÇÃO: Carga líquida muito baixa. Risco de instabilidade."
    else:
        msg = "Operação Estável. Geração distribuída absorvida pela carga."

    return {
        "timeline": horas,
        "consumo_mwh": consumo,
        "geracao_mwh": geracao,
        "carga_liquida_mwh": carga_liquida,
        "analise": msg,
        "alerta": alerta
    }