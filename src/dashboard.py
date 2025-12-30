import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import requests
import os
import sys
from datetime import date, timedelta

# ==================================================
# CONFIGURAÇÃO INICIAL E IMPORTAÇÃO DE UTILS
# ==================================================
st.set_page_config(layout="wide", page_title="GridScope")

# Adiciona o diretório atual ao path para importar o utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from utils import carregar_dados_cache
except ImportError:
    st.error("Erro: Arquivo 'utils.py' não encontrado na pasta src/.")
    st.stop()

# ==================================================
# CONSTANTES E ESTILOS
# ==================================================
CATEGORIAS_ALVO = ["Residencial", "Comercial", "Industrial"]
CORES_MAPA = {
    "Residencial": "#007bff",
    "Comercial": "#ffc107",
    "Industrial": "#dc3545"
}

# ==================================================
# FUNÇÕES DE CARREGAMENTO E API
# ==================================================
@st.cache_data
def obter_dados_dashboard():
    """
    Carrega os dados geoespaciais e de mercado do cache local.
    """
    try:
        gdf, dados_lista = carregar_dados_cache()
        return gdf, pd.DataFrame(dados_lista)
    except Exception as e:
        raise Exception(f"Erro ao carregar dados base: {e}")

def consultar_simulacao(subestacao, data_escolhida):
    """
    Consulta a API VPP (Porta 8000) para dados meteorológicos e geração estimada.
    """
    data_str = data_escolhida.strftime("%d-%m-%Y")
    url = f"http://127.0.0.1:8000/simulacao/{subestacao}?data={data_str}"
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException:
        return None
    return None

def consultar_ia_predict(payload):
    """
    Consulta a API de Inteligência Artificial (Porta 8001) para Duck Curve.
    """
    try:
        resp = requests.post(
            "http://127.0.0.1:8001/predict/duck-curve",
            json=payload,
            timeout=8
        )
        if resp.status_code == 200:
            return resp.json(), None
        else:
            return None, f"Erro na API: {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return None, "Serviço de IA Offline (Porta 8001)"
    except Exception as e:
        return None, str(e)

# ==================================================
# EXECUÇÃO PRINCIPAL: CARGA DE DADOS
# ==================================================
try:
    gdf, df_mercado = obter_dados_dashboard()
except Exception as e:
    st.error(f"Erro Crítico ao iniciar dashboard: {e}")
    st.stop()

# ==================================================
# BARRA LATERAL (SIDEBAR)
# ==================================================
st.sidebar.title("GridScope")
st.sidebar.caption("Centro de Operações Integrado")

# Filtros
lista_subs = sorted(gdf["NOM"].unique())
escolha = st.sidebar.selectbox("Selecione a Subestação:", lista_subs)

data_analise = st.sidebar.date_input("Data da Análise:", date.today(), format="DD/MM/YYYY")

# Lógica de Modo
modo = "Auditoria (Passado)" if data_analise < date.today() else "Previsão (Futuro)"
st.sidebar.info(f"Modo: {modo}")

# ==================================================
# PREPARAÇÃO DOS DADOS DA SELEÇÃO
# ==================================================
area_sel = gdf[gdf["NOM"] == escolha]
dados_raw = df_mercado[df_mercado["subestacao"] == escolha].iloc[0]

# Extração segura de dados usando .get para evitar erros
metricas = dados_raw.get("metricas_rede", {})
dados_gd = dados_raw.get("geracao_distribuida", {})
perfil = dados_raw.get("perfil_consumo", {})
detalhe_gd = dados_gd.get("detalhe_por_classe", {})

# Coordenadas Centrais
if not area_sel.empty:
    lat_c = area_sel.geometry.centroid.y.values[0]
    lon_c = area_sel.geometry.centroid.x.values[0]
else:
    lat_c, lon_c = -10.9472, -37.0731

# ==================================================
# LAYOUT PRINCIPAL - INÍCIO
# ==================================================
st.title(f"Subestação: {escolha}")

# --- 1. Infraestrutura Instalada ---
st.header("Infraestrutura Instalada")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Clientes", f"{metricas.get('total_clientes', 0):,}".replace(",", "."))
c2.metric("Carga Anual (MWh)", f"{metricas.get('consumo_anual_mwh', 0):,.0f}")
c3.metric("Usinas Solares", dados_gd.get("total_unidades", 0))
c4.metric("Potência Instalada (kW)", f"{dados_gd.get('potencia_total_kw', 0):,.0f}")

st.divider()

# --- 2. Simulação VPP (Monitoramento) ---
st.header(f"Simulação VPP: {data_analise.strftime('%d/%m/%Y')}")

dados_simulacao = consultar_simulacao(escolha, data_analise)

if dados_simulacao:
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Condição do Tempo", dados_simulacao.get("condicao_tempo", "-"))
    sc2.metric("Irradiação (kWh/m²)", dados_simulacao.get("irradiacao_solar_kwh_m2", 0))
    sc3.metric("Temperatura Máx (°C)", dados_simulacao.get("temperatura_max_c", 0))
    
    perda = dados_simulacao.get("fator_perda_termica", 0)
    sc4.metric("Perda Térmica", f"-{perda}%")

    # Alertas de Impacto
    impacto = dados_simulacao.get("impacto_na_rede", "NORMAL")
    if "ALTA" in impacto or "CRITICO" in impacto:
        st.error(f"Status da Rede: {impacto}")
    elif "BAIXA" in impacto:
        st.warning(f"Status da Rede: {impacto}")
    else:
        st.success(f"Status da Rede: {impacto}")
else:
    st.warning("⚠️ API de Simulação Offline (Porta 8000). Verifique o servidor.")

st.divider()

# --- 3. Módulo de IA (Duck Curve) ---
st.header("🤖 Análise Preditiva (AI Duck Curve)")
st.markdown("Previsão de Fluxo Reverso usando Inteligência Artificial e Meteo-Analytics.")

# Inicializa o estado da sessão para os resultados da IA não sumirem
if 'resultado_ia' not in st.session_state:
    st.session_state.resultado_ia = None

col_ia_in, col_ia_act = st.columns([1, 4])
data_ia = col_ia_in.date_input("Data para Previsão IA:", date.today() + timedelta(days=1), key="input_data_ia")

# Botão de Execução
if col_ia_act.button("🚀 Rodar Análise de IA", use_container_width=True):
    with st.spinner("Conectando à API de IA (Porta 8001)..."):
        payload = {
            "data_alvo": str(data_ia),
            "potencia_gd_kw": float(dados_gd.get("potencia_total_kw", 0)),
            "lat": float(lat_c),
            "lon": float(lon_c)
        }
        
        # Chama a função e guarda o resultado na sessão do Streamlit
        res, erro = consultar_ia_predict(payload)
        if res:
            st.session_state.resultado_ia = res
        else:
            st.error(f"Falha na requisição: {erro}")
            st.session_state.resultado_ia = None

# EXIBIÇÃO DOS RESULTADOS (FORA DO IF DO BOTÃO)
# Isso garante que o gráfico não suma quando você mexer em outra coisa
if st.session_state.resultado_ia:
    res = st.session_state.resultado_ia
    
    # Exibe Banner de Alerta
    cor_box = "#dc3545" if res['alerta'] else "#28a745"
    icone = "⚠️" if res['alerta'] else "✅"
    
    st.markdown(f"""
    <div style='background-color:{cor_box}; color:white; padding:15px; border-radius:8px; text-align:center; margin-bottom:15px;'>
        <b style='font-size:20px;'>{icone} {res['analise']}</b>
    </div>
    """, unsafe_allow_html=True)

    # Gráfico Duck Curve
    fig_duck = go.Figure()
    
    # 1. Linha de Consumo
    fig_duck.add_trace(go.Scatter(
        x=res['timeline'], y=res['consumo_mwh'], 
        name="Consumo (Carga)", line=dict(color='#1f77b4', width=3)
    ))
    
    # 2. Linha de Geração
    fig_duck.add_trace(go.Scatter(
        x=res['timeline'], y=res['geracao_mwh'], 
        name="Geração Solar", line=dict(color='#ff7f0e', width=3)
    ))
    
    # 3. Área de Carga Líquida
    fig_duck.add_trace(go.Scatter(
        x=res['timeline'], y=res['carga_liquida_mwh'], 
        name="Carga Líquida", fill='tozeroy', 
        line=dict(color='white', dash='dot'),
        fillcolor='rgba(128, 128, 128, 0.3)'
    ))
    
    # Linha Crítica de Zero
    fig_duck.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Injeção na Rede (Fluxo Reverso)")
    
    fig_duck.update_layout(
        title=f"Curva de Carga Prevista para {data_ia.strftime('%d/%m/%Y')}",
        xaxis_title="Hora do Dia",
        yaxis_title="Potência (MWh)",
        hovermode="x unified",
        height=450
    )
    
    st.plotly_chart(fig_duck, use_container_width=True)

st.divider()

# --- 4. Visualizações Finais (Gráficos e Mapa) ---
col_graf, col_map = st.columns([1.5, 2])

# Coluna da Esquerda: Gráfico de Pizza
with col_graf:
    st.subheader("Perfil de Consumo")
    dados_pie = [{"Segmento": k, "Clientes": v["qtd_clientes"]} for k, v in perfil.items() if k in CATEGORIAS_ALVO]
    df_cons = pd.DataFrame(dados_pie)

    if not df_cons.empty:
        fig_pie = px.pie(
            df_cons, 
            values="Clientes", 
            names="Segmento", 
            hole=0.4, 
            color="Segmento", 
            color_discrete_map=CORES_MAPA
        )
        fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Sem dados de perfil disponíveis.")

# Coluna da Direita: Mapa
with col_map:
    st.subheader("Geolocalização")
    if not area_sel.empty:
        m = folium.Map(location=[lat_c, lon_c], zoom_start=13, tiles="OpenStreetMap")

        # Estilo Dinâmico do Mapa
        def style_function(feature):
            nome = feature['properties']['NOM']
            cor = '#007bff'
            # Tenta achar risco na base de mercado
            dado_sub = df_mercado[df_mercado['subestacao'] == nome]
            if not dado_sub.empty:
                risco = dado_sub.iloc[0].get('metricas_rede', {}).get('nivel_criticidade_gd', 'BAIXO')
                cor = {'BAIXO': '#2ecc71', 'MEDIO': '#f1c40f', 'ALTO': '#e74c3c'}.get(risco, '#2ecc71')
            
            weight = 3 if nome == escolha else 1
            fill_op = 0.6 if nome == escolha else 0.2
            return {'fillColor': cor, 'color': 'black', 'weight': weight, 'fillOpacity': fill_op}

        folium.GeoJson(
            gdf,
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(fields=["NOM"], aliases=["Subestação:"])
        ).add_to(m)

        st_folium(m, use_container_width=True, height=500)