import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error
import joblib
import os
import sys
import holidays

# --- 1. CONFIGURAÇÃO DE CAMINHOS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

# Adiciona o caminho 'src' e 'src/etl' para o Python encontrar seu ETL
sys.path.append(os.path.join(project_root, "src"))
sys.path.append(os.path.join(project_root, "src", "etl"))

# Caminho para salvar o modelo
MODEL_PATH = os.path.join(current_dir, "modelo_consumo_real.pkl")

# --- 2. IMPORTAÇÃO DO SEU ETL ---
try:
    from etl.etl_ai_consumo import buscar_dados_reais_para_ia
    print("✅ Módulo ETL importado com sucesso da pasta src/etl!")
except ImportError as e:
    print(f"❌ Erro crítico: Não foi possível importar o ETL. Verifique se 'etl_ai_consumo.py' está em 'src/etl'.")
    print(f"Detalhe do erro: {e}")
    sys.exit(1)

# --- 3. FUNÇÃO DE CONVERSÃO (Mensal Real -> Horário Treino) ---
def gerar_dataset_baseado_no_real(dados_reais, anos_treino=[2022, 2023, 2024]):
    """
    Pega o volume MENSAL real do BDGD e distribui nas HORAS
    usando o perfil de carga (Pato) para a IA treinar.
    """
    perfil_mensal = dados_reais['consumo_mensal'] # Ex: {1: 50000.0, 2: 48000.0...}
    
    lista_dados = []
    br_holidays = holidays.Brazil()
    
    print(f"⏳ Processando dados de {len(anos_treino)} anos baseados no volume real...")

    for ano in anos_treino:
        # Gera todas as horas do ano
        datas = pd.date_range(f"{ano}-01-01", f"{ano}-12-31 23:00", freq="h")
        
        for data in datas:
            mes = data.month
            hora = data.hour
            dia_sem = data.dayofweek
            eh_feriado = data.date() in br_holidays
            eh_fim_semana = dia_sem >= 5
            
            # 1. VOLUME REAL (A Verdade do BDGD)
            # Pega o total do mês (MWh) e descobre a média por hora (kWh)
            vol_mes_mwh = perfil_mensal.get(mes, 100.0)
            carga_media_hora = (vol_mes_mwh * 1000) / (30 * 24) # MWh -> kWh
            
            # 2. PERFIL DE CONSUMO (A Curva Horária)
            fator = 1.0
            
            # Picos Diários
            fator += 0.4 * np.exp(-(hora - 11)**2 / 10) # Pico Manhã
            fator += 0.7 * np.exp(-(hora - 19)**2 / 6)  # Pico Noite (Mais forte)
            
            # Vales
            if hora < 6: fator *= 0.5 # Madrugada baixa
                
            # Fim de Semana/Feriado (Redução)
            if eh_fim_semana or eh_feriado:
                fator *= 0.85
                if hora > 18: fator *= 0.9
            
            # Tendência Anual (Pequeno crescimento entre os anos simulados)
            fator *= (1.03 ** (ano - anos_treino[0]))

            # Ruído pequeno (para a IA não decorar)
            ruido = np.random.normal(1.0, 0.05)
            
            consumo_final = carga_media_hora * fator * ruido
            
            lista_dados.append({
                "consumo": consumo_final,
                "hora": hora,
                "mes": mes,
                "dia_semana": dia_sem,
                "dia_ano": data.dayofyear,
                "ano": ano,
                "eh_feriado": int(eh_feriado),
                "eh_fim_semana": int(eh_fim_semana)
            })
            
    return pd.DataFrame(lista_dados)

# --- 4. FLUXO PRINCIPAL ---
def treinar_agora():
    print("\n--- 🚀 INICIANDO TREINAMENTO COM DADOS REAIS (BDGD) ---")
    
    # A. Busca dados no seu GDB
    # Mude para o nome exato da sua subestação no GDB se for diferente
    dados_bdgd = buscar_dados_reais_para_ia("SUBESTA9")
    
    if "erro" in dados_bdgd or dados_bdgd.get("consumo_anual_mwh", 0) == 0:
        print("❌ Falha: O ETL não retornou dados válidos. Verifique o GDB.")
        return

    print(f"✅ Dados Recebidos: {dados_bdgd['consumo_anual_mwh']:.2f} MWh totais.")

    # B. Gera o Dataset Horário para a IA
    df = gerar_dataset_baseado_no_real(dados_bdgd, anos_treino=[2023, 2024, 2025])
    print(f"📊 Dataset Horário Gerado: {len(df)} registros.")

    # C. Treinamento
    features = ["hora", "mes", "dia_semana", "dia_ano", "ano", "eh_feriado", "eh_fim_semana"]
    X = df[features]
    y = df["consumo"]

    # Separa 20% para prova final
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    print("\n🤖 Treinando a IA (Random Forest)...")
    modelo = RandomForestRegressor(
        n_estimators=150,
        min_samples_split=5,
        n_jobs=-1,
        random_state=42
    )
    modelo.fit(X_train, y_train)

    # D. Validação
    score = modelo.score(X_test, y_test)
    mae = mean_absolute_error(y_test, modelo.predict(X_test))
    
    print("-" * 30)
    print(f"🏆 RESULTADO DO TREINO:")
    print(f"📈 Precisão (R²): {score:.4f}")
    print(f"📉 Erro Médio: {mae:.2f} kWh")
    
    if score > 0.90:
        print("🌟 EXCELENTE: A IA aprendeu o padrão real da sua subestação!")
    else:
        print("⚠️ ALERTA: O modelo pode precisar de mais ajustes.")

    # E. Salvar
    joblib.dump(modelo, MODEL_PATH)
    print(f"\n💾 Modelo salvo e pronto para uso em:\n   -> {MODEL_PATH}")

if __name__ == "__main__":
    treinar_agora()