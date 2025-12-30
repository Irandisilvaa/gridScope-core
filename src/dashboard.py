import streamlit as st
import geopandas as gpd
import pandas as pd
import json
import plotly.express as px
import folium
from streamlit_folium import st_folium
import os
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="GridScope")

CATEGORIAS_ALVO = ['Residencial', 'Comercial', 'Industrial']

CORES_MAPA = {
    'Residencial': '#007bff', 
    'Comercial': '#ffc107', 
    'Industrial': '#dc3545'
}

@st.cache_data
def carregar_dados_base():
    if os.path.exists("subestacoes_logicas_aracaju.geojson"):
        caminho_geo = "subestacoes_logicas_aracaju.geojson"
        caminho_json = "perfil_mercado_aracaju.json"
    else:
        caminho_geo = "../subestacoes_logicas_aracaju.geojson"
        caminho_json = "../perfil_mercado_aracaju.json"

    gdf = gpd.read_file(caminho_geo)
    with open(caminho_json, 'r', encoding='utf-8') as f:
        dados_mercado = json.load(f)
    return gdf, pd.DataFrame(dados_mercado)

def consultar_simulacao(subestacao, data_escolhida):
    data_str = data_escolhida.strftime("%d-%m-%Y")
    url = f"http://127.0.0.1:8000/simulacao/{subestacao}?data={data_str}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        return None
    return None

try:
    gdf, df_mercado = carregar_dados_base()
except Exception as e:
    st.error(f"Erro ao carregar arquivos: {e}")
    st.stop()

st.sidebar.title("GridScope")
st.sidebar.write("Centro de Operacoes")

lista_subs = sorted(gdf['NOM'].unique())
escolha = st.sidebar.selectbox("Selecione a Subestacao:", lista_subs)

data_analise = st.sidebar.date_input("Data da Analise:", date.today(), format="DD/MM/YYYY")

modo = "Auditoria (Passado)" if data_analise < date.today() else "Previsao (Futuro)"
st.sidebar.info(f"Modo: {modo}")

area_sel = gdf[gdf['NOM'] == escolha]
dados_raw = df_mercado[df_mercado['subestacao'] == escolha].iloc[0]

metricas = dados_raw.get('metricas_rede', {})
dados_gd = dados_raw.get('geracao_distribuida', {})
perfil = dados_raw.get('perfil_consumo', {})
detalhe_gd = dados_gd.get('detalhe_por_classe', {})

st.title(f"Subestacao: {escolha}")

st.header("Infraestrutura Instalada")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Clientes", f"{metricas.get('total_clientes', 0):,}".replace(",", "."))
c2.metric("Carga Anual (MWh)", f"{metricas.get('consumo_anual_mwh', 0):,.0f}")
c3.metric("Usinas Solares", dados_gd.get('total_unidades', 0))
c4.metric("Potencia Instalada (kW)", f"{dados_gd.get('potencia_total_kw', 0):,.0f}")

st.divider()

st.header(f"Simulacao VPP: {data_analise.strftime('%d/%m/%Y')}")

dados_simulacao = consultar_simulacao(escolha, data_analise)

if dados_simulacao:
    sc1, sc2, sc3, sc4 = st.columns(4)
    
    sc1.metric("Condicao do Tempo", dados_simulacao['condicao_tempo'])
    sc2.metric("Irradiacao (kWh/m2)", dados_simulacao['irradiacao_solar_kwh_m2'])
    sc3.metric("Temperatura Max (C)", dados_simulacao['temperatura_max_c'])
    
    perda = dados_simulacao['fator_perda_termica']
    sc4.metric("Perda Termica", f"-{perda}%")
    
    res1, res2 = st.columns([1, 2])
    
    geracao = dados_simulacao.get('geracao_estimada_hoje_mwh', dados_simulacao.get('geracao_estimada_mwh'))
    
    delta_cor = "normal"
    if geracao > 100: delta_cor = "inverse"
    
    res1.metric("Geracao Estimada (MWh)", f"{geracao}", delta_color=delta_cor)
    
    msg_impacto = dados_simulacao['impacto_na_rede']
    
    if "ALTA" in msg_impacto or "CRITICO" in msg_impacto:
        st.error(msg_impacto)
    elif "BAIXA" in msg_impacto:
        st.warning(msg_impacto)
    else:
        st.success(msg_impacto)
        
else:
    st.warning("API Offline ou Inacessivel.")

st.divider()

col_graf, col_map = st.columns([1.5, 2])

with col_graf:
    st.subheader("Perfil de Consumo")
    df_cons = pd.DataFrame([{"Segmento": k, "Clientes": v["qtd_clientes"]} for k,v in perfil.items() if k in CATEGORIAS_ALVO])
    if not df_cons.empty:
        fig_cons = px.pie(df_cons, values='Clientes', names='Segmento', hole=0.4, color='Segmento', color_discrete_map=CORES_MAPA)
        fig_cons.update_layout(height=250, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig_cons, use_container_width=True)
    
    st.subheader("Potencia por Classe (kW)")
    if detalhe_gd:
        df_gd_class = pd.DataFrame([{"Segmento": k, "Potencia_kW": v} for k,v in detalhe_gd.items() if k in CATEGORIAS_ALVO and v > 0])
        if not df_gd_class.empty:
            fig_gd = px.bar(df_gd_class, x='Segmento', y='Potencia_kW', color='Segmento', text_auto='.2s', color_discrete_map=CORES_MAPA)
            fig_gd.update_layout(height=300, showlegend=False)
            st.plotly_chart(fig_gd, use_container_width=True)
        else:
            st.info("Sem GD nessas categorias.")

with col_map:
    st.subheader("Mapa da Area")
    centro_lat = area_sel.geometry.centroid.y.values[0]
    centro_lon = area_sel.geometry.centroid.x.values[0]
    m = folium.Map(location=[centro_lat, centro_lon], zoom_start=13, tiles="OpenStreetMap")
    
    def style_function(feature):
        nome = feature['properties']['NOM']
        dado = next((x for x in df_mercado.to_dict('records') if x['subestacao'] == nome), None)
        risco = dado.get('metricas_rede', {}).get('nivel_criticidade_gd', 'BAIXO') if dado else 'BAIXO'
        cor = {'BAIXO': '#2ecc71', 'MÉDIO': '#f1c40f', 'ALTO': '#e74c3c'}.get(risco, '#2ecc71')
        opac = 0.6 if nome == escolha else 0.2
        return {'fillColor': cor, 'color': 'black', 'weight': 2, 'fillOpacity': opac}

    folium.GeoJson(gdf, style_function=style_function, tooltip=folium.GeoJsonTooltip(fields=['NOM'])).add_to(m)
    st_folium(m, use_container_width=True, height=600)