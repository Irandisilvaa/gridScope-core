import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import joblib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "modelo_consumo.pkl")

dates = pd.date_range("2023-01-01", "2023-12-31", freq="H")
df = pd.DataFrame({"t": dates})

df["hora"] = df["t"].dt.hour
df["mes"] = df["t"].dt.month
df["dia_semana"] = df["t"].dt.dayofweek
df["eh_fim_de_semana"] = df["dia_semana"] >= 5

def perfil(r):
    h = r["hora"]
    base = 1.8 if 18 <= h <= 22 else 1.0
    return 10 * base + np.random.normal(0, 0.3)

df["consumo"] = df.apply(perfil, axis=1)

modelo = RandomForestRegressor(n_estimators=50, random_state=42)
modelo.fit(df[["hora", "mes", "dia_semana", "eh_fim_de_semana"]], df["consumo"])

joblib.dump(modelo, MODEL_PATH)
print("✅ Modelo treinado e salvo")
