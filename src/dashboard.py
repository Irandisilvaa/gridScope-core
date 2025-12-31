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

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    layout="wide", 
    page_title="GridScope | Intelligence Dashboard",
    page_icon="⚡"
)

# --- CONFIGURAÇÃO DE CAMINHOS ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from utils import carregar_dados_cache
except ImportError:
    st.error("Erro: Arquivo 'utils.py' não encontrado na pasta src/. Verifique a estrutura de pastas.")
    st.stop()

# --- CONSTANTES E ESTILOS ---
CATEGORIAS_ALVO = ["Residencial", "Comercial", "Industrial", "Rural"]
CORES_MAPA = {
    "Residencial": "#007bff",
    "Comercial": "#ffc107",
    "Industrial": "#dc3545",
    "Rural": "#28a745"
}

# --- FUNÇÕES AUXILIARES ---
def formatar_br(valor):
    """Formata números para o padrão brasileiro (1.234,56)"""
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

@st.cache_data
def obter_dados_dashboard():
    """Carrega os dados do cache (GeoJSON e Mercado)"""
    try:
        gdf, dados_lista = carregar_dados_cache()
        if gdf is None or not dados_lista:
            return None, None
        return gdf, pd.DataFrame(dados_lista)
    except Exception as e:
        st.error(f"Erro ao processar dados de cache: {e}")
        return None, None

def consultar_simulacao(subestacao, data_escolhida):
    """Consulta a API de Geração Solar (Porta 8000)"""
    data_str = data_escolhida.strftime("%d-%m-%Y")
    url = f"http://127.0.0.1:8000/simulacao/{subestacao}?data={data_str}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        return None
    return None

def consultar_ia_predict(payload):
    """Consulta a API de Inteligência Artificial (Porta 8001)"""
    try:
        resp = requests.post(
            "http://127.0.0.1:8001/predict/duck-curve",
            json=payload,
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json(), None
        else:
            return None, f"Erro na API: {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return None, "Serviço de IA Offline (Porta 8001)"
    except Exception as e:
        return None, str(e)

# --- CARREGAMENTO INICIAL ---
gdf, df_mercado = obter_dados_dashboard()

if gdf is None or df_mercado is None:
    st.error("❌ Falha crítica: Não foi possível carregar os dados geográficos ou de mercado.")
    st.info("Certifique-se de que os arquivos .geojson e .json foram gerados pelo processo de ETL.")
    st.stop()

# --- SIDEBAR (FILTROS) ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2991/2991474.png", width=50) # Ícone decorativo
st.sidebar.title("GridScope Core")
st.sidebar.caption("Sistemas Elétricos & Analytics")
st.sidebar.divider()

lista_subs = sorted(df_mercado["subestacao"].unique())
escolha = st.sidebar.selectbox("Selecione a Subestação:", lista_subs)

data_analise = st.sidebar.date_input("Data da Análise:", date.today())
modo = "Auditoria (Histórico)" if data_analise < date.today() else "Operação (Tempo Real/Prev)"
st.sidebar.info(f"Modo Atual: {modo}")

# --- FILTRAGEM DE DADOS ---
area_sel = gdf[gdf["NOM"] == escolha]
# Garantir que temos os dados da subestação selecionada
try:
    dados_raw = df_mercado[df_mercado["subestacao"] == escolha].iloc[0]
except IndexError:
    st.error(f"Dados não encontrados para a subestação {escolha}")
    st.stop()

metricas = dados_raw.get("metricas_rede", {})
dados_gd = dados_raw.get("geracao_distribuida", {})
perfil = dados_raw.get("perfil_consumo", {})

# Coordenadas para o mapa
if not area_sel.empty:
    centroid = area_sel.geometry.centroid.iloc[0]
    lat_c, lon_c = centroid.y, centroid.x
else:
    lat_c, lon_c = -10.9472, -37.0731

# --- CONTEÚDO PRINCIPAL ---
st.title(f"Monitoramento: {escolha}")
st.markdown(f"**Localização:** Aracaju - SE | **Status:** Conectado")

# --- ROW 1: KEY PERFORMANCE INDICATORS (KPIs) ---
st.header("Infraestrutura de Rede")
k1, k2, k3, k4 = st.columns(4)

with k1:
    st.metric("Total de Clientes", f"{metricas.get('total_clientes', 0):,}".replace(",", "."))
with k2:
    st.metric("Consumo Anual", f"{formatar_br(metricas.get('consumo_anual_mwh', 0))} MWh")
with k3:
    st.metric("Usinas Ativas (GD)", f"{dados_gd.get('total_unidades', 0)}")
with k4:
    st.metric("Potência Solar", f"{formatar_br(dados_gd.get('potencia_total_kw', 0))} kW")

st.divider()

# --- ROW 2: GRÁFICO DE BARRAS E SIMULAÇÃO ---
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("📊 Potência Instalada por Classe")
    detalhe_gd = dados_gd.get("detalhe_por_classe", {})
    
    fig_barras = go.Figure(data=[
        go.Bar(
            x=list(detalhe_gd.keys()), 
            y=list(detalhe_gd.values()),
            marker_color='#1f77b4',
            text=[f"{v:.1f} kW" for v in detalhe_gd.values()],
            textposition='auto'
        )
    ])
    fig_barras.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10), yaxis_title="kW")
    st.plotly_chart(fig_barras, use_container_width=True)

with col_right:
    st.subheader(f"☀️ Simulação VPP: {data_analise.strftime('%d/%m/%y')}")
    dados_sim = consultar_simulacao(escolha, data_analise)
    
    if dados_sim:
        sc1, sc2 = st.columns(2)
        sc1.write(f"**Clima:** {dados_sim.get('condicao_tempo')}")
        sc1.write(f"**Irradiação:** {dados_sim.get('irradiacao_solar_kwh_m2')} kWh/m²")
        sc2.write(f"**Temp. Máx:** {dados_sim.get('temperatura_max_c')}°C")
        sc2.write(f"**Perda Térmica:** {dados_sim.get('fator_perda_termica')}%")
        
        impacto = dados_sim.get("impacto_na_rede", "NORMAL")
        if "CRITICO" in impacto.upper() or "ALTA" in impacto.upper():
            st.error(f"Alerta: {impacto}")
        else:
            st.success(f"Status: {impacto}")
    else:
        st.warning("⚠️ Serviço de Simulação Solar Offline.")

st.divider()

# --- ROW 3: INTELIGÊNCIA ARTIFICIAL (DUCK CURVE) ---
st.header("🧠 Análise Preditiva (AI Duck Curve)")
st.markdown("Cálculo de carga líquida e probabilidade de fluxo reverso.")

# Estado da sessão para manter o resultado da IA
if 'resultado_ia' not in st.session_state:
    st.session_state.resultado_ia = None

c_ia1, c_ia2 = st.columns([1, 3])
data_ia = c_ia1.date_input("Data do Forecast:", date.today() + timedelta(days=1))

if c_ia2.button("Executar Predição de IA", use_container_width=True):
    with st.spinner("IA processando modelos meteorológicos e carga..."):
        payload = {
            "data_alvo": str(data_ia),
            "potencia_gd_kw": float(dados_gd.get("potencia_total_kw", 0)),
            "lat": float(lat_c),
            "lon": float(lon_c)
        }
        res, erro = consultar_ia_predict(payload)
        if res:
            st.session_state.resultado_ia = res
        else:
            st.error(erro)

if st.session_state.resultado_ia:
    res = st.session_state.resultado_ia
    
    # Alerta visual
    cor_alerta = "#dc3545" if res['alerta'] else "#28a745"
    st.markdown(f"""
        <div style='background-color:{cor_alerta}; color:white; padding:10px; border-radius:5px; text-align:center;'>
            <b>ANÁLISE IA: {res['analise']}</b>
        </div>
    """, unsafe_allow_html=True)

    # Gráfico da Curva do Pato
    fig_duck = go.Figure()
    fig_duck.add_trace(go.Scatter(x=res['timeline'], y=res['consumo_mwh'], name="Consumo Estimado", line=dict(color='#3498db', width=3)))
    fig_duck.add_trace(go.Scatter(x=res['timeline'], y=res['geracao_mwh'], name="Geração Solar", line=dict(color='#f1c40f', width=3)))
    fig_duck.add_trace(go.Scatter(x=res['timeline'], y=res['carga_liquida_mwh'], name="Carga Líquida", fill='tozeroy', line=dict(color='white', dash='dot')))
    
    fig_duck.add_hline(y=0, line_dash="dash", line_color="red")
    fig_duck.update_layout(height=400, title="Projeção de Carga Líquida (MWh)", hovermode="x unified")
    st.plotly_chart(fig_duck, use_container_width=True)

st.divider()

# --- ROW 4: PERFIL E GEOLOCALIZAÇÃO ---
col_pie, col_map = st.columns([1, 2])

with col_pie:
    st.subheader("Segmentação de Clientes")
    dados_pie = [{"Segmento": k, "Qtd": v["qtd_clientes"]} for k, v in perfil.items() if k in CATEGORIAS_ALVO]
    df_pie = pd.DataFrame(dados_pie)
    
    if not df_pie.empty:
        fig_pie = px.pie(df_pie, values="Qtd", names="Segmento", hole=0.4, color="Segmento", color_discrete_map=CORES_MAPA)
        fig_pie.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=350)
        st.plotly_chart(fig_pie, use_container_width=True)

with col_map:
    st.subheader("Território de Atendimento")
    m = folium.Map(location=[lat_c, lon_c], zoom_start=13)

    def style_fn(feature):
        nome = feature['properties']['NOM']
        is_selected = (nome == escolha)
        
        # Busca criticidade para a cor
        dado_s = df_mercado[df_mercado['subestacao'] == nome]
        criticidade = "BAIXO"
        if not dado_s.empty:
            criticidade = dado_s.iloc[0].get('metricas_rede', {}).get('nivel_criticidade_gd', 'BAIXO')
        
        cor = {'BAIXO': '#2ecc71', 'MEDIO': '#f1c40f', 'ALTO': '#e74c3c'}.get(criticidade, '#2ecc71')
        
        return {
            'fillColor': cor,
            'color': 'white' if is_selected else 'gray',
            'weight': 3 if is_selected else 1,
            'fillOpacity': 0.7 if is_selected else 0.3
        }

    folium.GeoJson(
        gdf,
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(fields=["NOM"], aliases=["Subestação:"])
    ).add_to(m)

    st_folium(m, use_container_width=True, height=400)

# --- RODAPÉ ---
st.caption(f"GridScope v4.5 | Dados atualizados em: {date.today().strftime('%d/%m/%Y')}")