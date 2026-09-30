import os
import joblib
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import r2_score, mean_absolute_error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "validacao")
os.makedirs(OUT_DIR, exist_ok=True)

try:
    from .model_contract import FEATURE_COLUMNS, TARGET_COLUMN, model_is_compatible
    from .train_model import gerar_dados_treino_inteligente
except ImportError:
    from model_contract import FEATURE_COLUMNS, TARGET_COLUMN, model_is_compatible
    from train_model import gerar_dados_treino_inteligente

def validar_modelo(model_path):
    nome = os.path.basename(model_path).replace("modelo_", "").replace(".pkl", "")
    print(f"\n📊 Validando: {nome}")

    modelo = joblib.load(model_path)
    if not model_is_compatible(modelo):
        raise ValueError("Artefato incompatível com o contrato atual de features")

    df = gerar_dados_treino_inteligente(seed=123)
    df["data"] = pd.date_range("2023-01-01", periods=len(df), freq="h")
    feature_columns = FEATURE_COLUMNS
    missing = set(feature_columns) - set(df.columns)
    if missing:
        raise ValueError(f"Features ausentes no dataset de validação: {sorted(missing)}")

    X = df.loc[:, list(feature_columns)]

    print("🤖 Rodando inferência...")
    y_pred = modelo.predict(X)

    y_ref = df[TARGET_COLUMN].to_numpy()

    r2 = r2_score(y_ref, y_pred)
    mae = mean_absolute_error(y_ref, y_pred)

    ini = 24 * 7 * 8
    fim = ini + 24 * 7

    plt.figure(figsize=(14, 6))
    plt.plot(df["data"].iloc[ini:fim], y_ref[ini:fim], "--", label="Comportamento Esperado")
    plt.plot(df["data"].iloc[ini:fim], y_pred[ini:fim], label="Predição IA")
    plt.title(f"{nome} | R² = {r2:.3f}")
    plt.xlabel("Data")
    plt.ylabel("Consumo (MWh)")
    plt.legend()
    plt.grid(alpha=0.2)
    plt.xticks(rotation=45)

    img_path = os.path.join(OUT_DIR, f"{nome}.png")
    plt.tight_layout()
    plt.savefig(img_path)
    plt.close()

    return nome, round(r2, 4), round(mae, 2), img_path

if __name__ == "__main__":

    print("\n📊 VALIDAÇÃO FORMAL DA IA")

    resultados = []

    for arq in sorted(os.listdir(BASE_DIR)):
        if not arq.startswith("modelo_") or not arq.endswith(".pkl"):
            continue

        nome = arq.replace("modelo_", "").replace(".pkl", "")

        res = validar_modelo(os.path.join(BASE_DIR, arq))
        resultados.append(res)

    df_res = pd.DataFrame(
        resultados,
        columns=["Subestacao", "R2", "MAE_MWh", "Imagem"]
    )

    csv_path = os.path.join(OUT_DIR, "relatorio_validacao.csv")
    df_res.to_csv(csv_path, index=False)

    print("\n✅ Validação concluída")
    print(df_res)
    print(f"\n📁 Relatório salvo em: {csv_path}")
