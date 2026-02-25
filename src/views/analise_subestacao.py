import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import os
import sys
import ast
from datetime import date
import warnings

try:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import tab_ia
    
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    from config import CIDADE_ALVO
except ImportError:
    tab_ia = None 
    CIDADE_ALVO = "Cidade Desconhecida"

def render_view():
    warnings.filterwarnings("ignore", category=UserWarning)
    warnings.filterwarnings("ignore", message=".*use_container_width.*")

    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)

    try:
        from utils import carregar_dados_cache, limpar_float
    except ImportError as e:
        st.error(f"Erro de importação: {e}. Verifique se 'utils.py' existe na raiz.")
        st.stop()

    CATEGORIAS_ALVO = ["Residencial", "Comercial", "Industrial", "Rural", "Poder Público"]

    CORES_MAPA = {
        "Residencial": "#007bff",        
        "Comercial": "#ffc107",          
        "Industrial": "#dc3545",         
        "Rural": "#28a745",              
        "Poder Público": "#6f42c1",      
    }

    def formatar_br(valor):
        if isinstance(valor, str): return valor
        try:
            return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except (ValueError, TypeError):
            return str(valor)

    def converter_para_dict(dado):
        if isinstance(dado, dict):
            return dado
        if isinstance(dado, str):
            try:
                return ast.literal_eval(dado)
            except (ValueError, SyntaxError):
                return {}
        return {}

    @st.cache_data
    def obter_dados_dashboard():
        try:
            gdf, dados_lista = carregar_dados_cache()
            if gdf is None or not dados_lista:
                return None, None
            return gdf, pd.DataFrame(dados_lista)
        except Exception as e:
            st.error(f"Erro ao processar dados de cache: {e}")
            return None, None
        
    gdf, df_mercado = obter_dados_dashboard()

    if gdf is None or df_mercado is None:
        st.error("❌ Falha crítica: Dados não carregados. Verifique se o ETL rodou.")
        st.stop()
    gdf = gdf.loc[:, ~gdf.columns.duplicated()]


    mapa_opcoes = {}
    if 'subestacao' in df_mercado.columns:
        for idx, row in df_mercado.iterrows():
            id_tec = row.get('id_tecnico', idx)
            label = row['subestacao']
            mapa_opcoes[label] = id_tec

    if not mapa_opcoes:
        st.warning("Nenhuma subestação disponível nos dados de mercado.")
        st.stop()

    escolha_label = st.sidebar.selectbox("Selecione a Subestação:", sorted(mapa_opcoes.keys()))
    id_escolhido = mapa_opcoes[escolha_label]

    data_analise = st.sidebar.date_input("Data da Análise:", date.today())
    modo = "Auditoria (Histórico)" if data_analise < date.today() else "Operação (Tempo Real/Prev)"
    st.sidebar.info(f"Modo Atual: {modo}")

    area_sel = gdf[gdf["COD_ID"].astype(str) == str(id_escolhido)]

    centroid_existe = False
    lat_c, lon_c = -10.9472, -37.0731 

    if not area_sel.empty:
        centroid_existe = True
        try:
            c = area_sel.geometry.centroid.iloc[0]
            lat_c, lon_c = c.y, c.x
        except Exception:
            pass

    try:
        if 'id_tecnico' in df_mercado.columns:
            dados_filtrados = df_mercado[df_mercado["id_tecnico"].astype(str) == str(id_escolhido)]
        else:
            dados_filtrados = df_mercado[df_mercado["subestacao"] == escolha_label]

        if dados_filtrados.empty:
            dados_filtrados = df_mercado.iloc[[0]]

        dados_raw = dados_filtrados.iloc[0]
        nome_limpo_escolha = str(dados_raw["subestacao"]).split(' (ID:')[0]
        subestacao_obj = {
            "id": str(id_escolhido),
            "nome": nome_limpo_escolha
        }

    except Exception as e:
        st.error(f"Erro ao recuperar dados da tabela: {e}")
        st.stop()

    metricas = converter_para_dict(dados_raw.get("metricas_rede", {}))
    dados_gd = converter_para_dict(dados_raw.get("geracao_distribuida", {}))
    perfil = converter_para_dict(dados_raw.get("perfil_consumo", {}))

    potencia_kw_calc = limpar_float(dados_gd.get('potencia_total_kw', 0))
    consumo_mwh_calc = limpar_float(metricas.get('consumo_anual_mwh', 1))
    if consumo_mwh_calc == 0: consumo_mwh_calc = 1
    
    geracao_est_mwh_calc = (potencia_kw_calc * 4.5 * 365) / 1000
    penetracao_calc = (geracao_est_mwh_calc / consumo_mwh_calc) * 100

    st.title(f"Monitoramento: {subestacao_obj['nome']}")
    st.caption(f"ID Técnico: {id_escolhido}")
    
    if penetracao_calc > 25:
        st.error(f"🚨 **CRITICIDADE ALTA: RISCO DE INVERSÃO DE FLUXO** | Penetração GD: {penetracao_calc:.1f}%")
    elif penetracao_calc > 15:
        st.warning(f"⚠️ **ATENÇÃO: NÍVEL DE ALERTA** | Penetração GD: {penetracao_calc:.1f}%")
    else:
        st.success(f"✅ **OPERACIONAL: REDE ESTÁVEL** | Penetração GD: {penetracao_calc:.1f}%")

    st.markdown(f"**Localização:** {CIDADE_ALVO} | **Status:** Conectado")

    st.header("Infraestrutura de Rede")
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Total de Clientes", f"{metricas.get('total_clientes', 0):,}".replace(",", "."))
    with k2:
        st.metric("Consumo Anual (MWh)", f"{formatar_br(metricas.get('consumo_anual_mwh', 0))} ")
    with k3:
        st.metric("Unidades MMGD", f"{dados_gd.get('total_unidades', 0)}")
    with k4:
        st.metric("Potência Solar Instalada (kW)", f"{formatar_br(dados_gd.get('potencia_total_kw', 0))}")

    st.divider()

    tab_visao_geral, tab_ia_render = st.tabs(["📊 Visão Geral", "🧠 Simulação Duck Curve (IA)"])

    with tab_visao_geral:
        st.subheader("Área de Cobertura Geográfica")
        if centroid_existe:
            m = folium.Map(location=[lat_c, lon_c], zoom_start=13, scrollWheelZoom=False)

            def style_fn(feature):
                feature_id = feature['properties'].get('COD_ID')
                is_sel = (str(feature_id) == str(id_escolhido))
                cor = '#007bff' if is_sel else 'gray'
                return {'fillColor': cor, 'color': 'white' if is_sel else 'gray', 'weight': 3 if is_sel else 1,
                        'fillOpacity': 0.7 if is_sel else 0.3}

            folium.GeoJson(gdf, style_function=style_fn, tooltip=folium.GeoJsonTooltip(fields=["NOM", "COD_ID"],
                                                                                            aliases=["Subestação:",
                                                                                                     "ID:"])).add_to(m)
            st_folium(m, use_container_width=True, height=400)
        else:
            st.warning("Geometria não encontrada para este ID.")

        st.divider()

        st.subheader("Potência da GD Instalada por Classe")

        detalhe_raw = converter_para_dict(dados_gd.get("detalhe_por_classe", {}))
        
        detalhe_gd = {}
        for k, v in detalhe_raw.items():     
            potencia = 0
            if isinstance(v, dict):
                potencia = v.get('potencia_kw', 0)
            elif isinstance(v, (int, float)):
                potencia = float(v)
                
            if potencia > 0:
                detalhe_gd[k] = potencia

        if detalhe_gd:
            detalhe_gd = dict(sorted(detalhe_gd.items(), key=lambda item: item[1], reverse=True))
            lista_cores = [CORES_MAPA.get(k, '#6c757d') for k in detalhe_gd.keys()]

            fig_barras = go.Figure(data=[go.Bar(
                x=list(detalhe_gd.keys()),
                y=list(detalhe_gd.values()),
                marker_color=lista_cores, 
                text=[f"{v:,.2f} kW".replace(",", "X").replace(".", ",").replace("X", ".") for v in
                    detalhe_gd.values()],
                textposition='auto'
            )])
            
            fig_barras.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="kW")
            st.plotly_chart(fig_barras, use_container_width=True)
        else:
            st.info("Sem dados de GD para exibir.")

        st.subheader("Perfil de Carga")

        dados_perfil = []
        detalhe_raw = converter_para_dict(dados_gd.get("detalhe_por_classe", {}))
        for cls in CATEGORIAS_ALVO:
            perfil_cls = converter_para_dict(perfil.get(cls, {}))
            gd_cls = detalhe_raw.get(cls, {})
            if isinstance(gd_cls, (int, float)):
                pot_gd = float(gd_cls)
                qtd_gd = 0
            else:
                pot_gd = float(gd_cls.get('potencia_kw', 0)) if isinstance(gd_cls, dict) else 0
                qtd_gd = int(gd_cls.get('qtd', 0)) if isinstance(gd_cls, dict) else 0

            dados_perfil.append({
                "Classe": cls,
                "Clientes": perfil_cls.get("qtd_clientes", 0),
                "Consumo (MWh)": limpar_float(perfil_cls.get("consumo_anual_mwh", 0)),
                "Unidades MMGD": qtd_gd,
                "Potência GD (kW)": pot_gd
            })

        df_perfil = pd.DataFrame(dados_perfil)

        filtro_metrica = st.radio(
            "Visualizar por:",
            ["Consumo por Classe", "Clientes por Classe", "Unidades MMGD por Classe"],
            horizontal=True,
            key="filtro_perfil_carga"
        )

        if filtro_metrica == "Consumo por Classe":
            col_y = "Consumo (MWh)"
            titulo_y = "Consumo Anual (MWh)"
            sufixo = " MWh"
        elif filtro_metrica == "Clientes por Classe":
            col_y = "Clientes"
            titulo_y = "Nº de Clientes"
            sufixo = ""
        else:
            col_y = "Unidades MMGD"
            titulo_y = "Unidades MMGD"
            sufixo = ""

        df_plot = df_perfil[df_perfil[col_y] > 0].sort_values(by=col_y, ascending=False)

        if not df_plot.empty:
            if col_y in ["Clientes", "Unidades MMGD"]:
                text_labels = [f"{int(v)}{sufixo}" for v in df_plot[col_y]]
                hover_tmpl = '<b>%{x}</b><br>' + titulo_y + ': %{y}<extra></extra>'
            else:
                text_labels = [f"{formatar_br(v)}{sufixo}" for v in df_plot[col_y]]
                hover_tmpl = '<b>%{x}</b><br>' + titulo_y + ': %{y:,.2f}<extra></extra>'

            fig_perfil = go.Figure(data=[
                go.Bar(
                    x=df_plot["Classe"],
                    y=df_plot[col_y],
                    marker_color=[CORES_MAPA.get(c, '#6c757d') for c in df_plot["Classe"]],
                    text=text_labels,
                    textposition='auto',
                    hovertemplate=hover_tmpl
                )
            ])
            fig_perfil.update_layout(
                height=350,
                margin=dict(l=10, r=10, t=10, b=10),
                yaxis_title=titulo_y,
                showlegend=False,
                xaxis=dict(title=None)
            )
            st.plotly_chart(fig_perfil, use_container_width=True)
        else:
            st.info(f"Sem dados de {filtro_metrica.lower()} para exibir.")

        st.divider()

        st.subheader("Evolução Histórica (Série Temporal)")
        evolucao = dados_raw.get("evolucao_temporal", [])
        
        if evolucao:
            df_evolucao = pd.DataFrame(evolucao)
            df_evolucao['mes'] = pd.to_datetime(df_evolucao['mes'])
            
            filtro_hist = st.radio(
                "Métrica Histórica:",
                ["Crescimento de Clientes", "Crescimento de Unidades MMGD", "Evolução da Potência (kW)"],
                horizontal=True,
                key="filtro_historico"
            )
            
            if filtro_hist == "Crescimento de Clientes":
                col_hist = "clientes"
                titulo_h = "Total de Clientes Acumulados"
                sufixo_h = ""
            elif filtro_hist == "Crescimento de Unidades MMGD":
                col_hist = "unidades_mmgd"
                titulo_h = "Unidades MMGD Acumuladas"
                sufixo_h = ""
            else:
                col_hist = "potencia_kw"
                titulo_h = "Potência Instalada (kW)"
                sufixo_h = " kW"

            if col_hist in ["clientes", "unidades_mmgd"]:
                text_hist = [f"{int(v)}{sufixo_h}" for v in df_evolucao[col_hist]]
                hover_th = '<b>%{x|%b/%Y}</b><br>' + titulo_h + ': %{y}<extra></extra>'
            else:
                text_hist = [f"{formatar_br(v)}{sufixo_h}" for v in df_evolucao[col_hist]]
                hover_th = '<b>%{x|%b/%Y}</b><br>' + titulo_h + ': %{y:,.2f}<extra></extra>'

            fig_hist = go.Figure()
            fig_hist.add_trace(go.Scatter(
                x=df_evolucao['mes'],
                y=df_evolucao[col_hist],
                fill='tozeroy',
                mode='lines+markers',
                line=dict(color='#007bff', width=3),
                marker=dict(size=6, color='white', line=dict(width=2, color='#007bff')),
                hovertemplate=hover_th
            ))

            data_max = df_evolucao['mes'].max()
            data_min_default = data_max - pd.DateOffset(years=10)

            fig_hist.update_layout(
                height=350,
                margin=dict(l=10, r=10, t=20, b=10),
                yaxis_title=titulo_h,
                xaxis=dict(
                    title="Mês",
                    tickformat="%m/%Y",
                    range=[data_min_default, data_max],
                    rangeslider=dict(visible=True)
                ),
                showlegend=False
            )
            st.plotly_chart(fig_hist, use_container_width=True)
            
            st.caption("Nota: Gráfico de dados cumulativos desde a primeira conexão (mês a mês).")
            
        else:
            st.info("Nenhuma série temporal de crescimento registrada para esta Subestação.")

        st.divider()

        st.header("Relatório Técnico & Ações")
        col_table, col_actions = st.columns([2, 1])

        with col_table:
            st.subheader("Dados Consolidados")
            dados_consolidados = {
                "Parâmetro": ["Subestação", "ID", "Consumo Anual", "Potência GD", "Clientes"],
                "Valor": [
                    subestacao_obj['nome'], 
                    str(id_escolhido),
                    f"{formatar_br(metricas.get('consumo_anual_mwh', 0))} MWh",
                    f"{formatar_br(dados_gd.get('potencia_total_kw', 0))} kW",
                    str(metricas.get('total_clientes', 0))
                ]
            }
            st.dataframe(pd.DataFrame(dados_consolidados), use_container_width=True, hide_index=True)

        with col_actions:
            st.subheader("Diagnóstico")
            st.write(f"**Penetração GD:** {penetracao_calc:.1f}%")
            
            if penetracao_calc > 25:
                st.warning("⚠️ Risco de inversão de fluxo.")
            else:
                st.success("✅ **Rede Estável:** Capacidade disponível.")


                
    with tab_ia_render:
        if tab_ia:
            tab_ia.render_tab_ia(subestacao_obj, data_analise, dados_gd)
        else:
            st.error("Módulo de IA não carregado.")

    st.caption(f"GridScope v4.9 Enterprise | Dados atualizados em: {date.today().strftime('%d/%m/%Y')}")