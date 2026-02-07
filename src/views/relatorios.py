"""
Página de Relatórios Personalizados - GridScope
Central de Exportação de Dados com filtros separados para CSV e PDF
"""
import streamlit as st
import pandas as pd
import os
import sys
import base64
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def render_view():
    """Renderiza a Central de Exportação de Dados."""
    
    try:
        from pdf_report import (
            CLASSES_DISPONIVEIS,
            METRICAS_DISPONIVEIS,
            get_bulk_data,
            filter_dataframe,
            generate_csv,
            generate_pdf
        )
    except ImportError as e:
        st.error(f"Erro ao importar módulo de relatórios: {e}")
        st.info("Verifique se o arquivo `pdf_report.py` existe na pasta `src/`")
        st.stop()
   
    st.markdown("""
    <style>
        /* Botões primários amarelos com texto preto */
        .stDownloadButton > button[kind="primary"],
        .stButton > button[kind="primary"] {
            background-color: #FFD700 !important;
            color: #000 !important;
            border: 1px solid #000 !important;
        }
        
        .stDownloadButton > button[kind="primary"]:hover,
        .stButton > button[kind="primary"]:hover {
            background-color: #E6C200 !important;
            color: #000 !important;
        }
        
        /* Botões secundários */
        .stButton > button[kind="secondary"] {
            background-color: #FFD700 !important;
            color: #000 !important;
            border: 1px solid #000 !important;
        }
        
        .stButton > button[kind="secondary"]:hover {
            background-color: #E6C200 !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # --- Header da Página ---
    st.markdown("# Central de Exportação de Dados")
    st.markdown("""
    **Gerencie e exporte dados do GridScope para análise externa ou documentação.**
    
    Esta central permite que você:
    - **Exporte datasets em CSV** para ferramentas como PowerBI, Excel ou Python
    - **Gere relatórios PDF** com visual profissional para apresentações e documentação
    - **Personalize filtros** escolhendo quais classes e métricas incluir
    """)
    
    st.divider()
    
    st.header("1. Dataset CSV")
    st.markdown("""
    **Ideal para análise de dados e dashboards.**
    
    Exporte os dados brutos em formato CSV (Comma-Separated Values) para:
    - **PowerBI/Tableau** - Crie dashboards interativos
    - **Excel** - Análises personalizadas e tabelas dinâmicas
    - **Python/R** - Análises estatísticas e machine learning
    
    *Os dados seguem o formato Tidy Data (cada linha = uma observação, cada coluna = uma variável).*
    """)
    
    col_csv1, col_csv2 = st.columns(2)
    
    with col_csv1:
        csv_classes = st.multiselect(
            "Classes de Consumo",
            options=CLASSES_DISPONIVEIS,
            default=["Residencial", "Comercial", "Industrial"],
            key="csv_classes"
        )
    
    with col_csv2:
        csv_metricas = st.multiselect(
            "Métricas",
            options=list(METRICAS_DISPONIVEIS.keys()),
            default=["clientes", "consumo_mwh"],
            format_func=lambda x: METRICAS_DISPONIVEIS[x],
            key="csv_metricas"
        )
    
    csv_tipo = st.radio(
        "Tipo de Valor",
        options=["absoluto", "percentual"],
        format_func=lambda x: "Valores Absolutos" if x == "absoluto" else "Percentual (%)",
        horizontal=True,
        key="csv_tipo"
    )
    
    if csv_classes and csv_metricas:
        with st.expander("Pré-visualização dos Dados", expanded=True):
            try:
                with st.spinner("Carregando dados..."):
                    df_raw = get_bulk_data()
                    df_preview = filter_dataframe(
                        df_raw, 
                        csv_classes, 
                        csv_metricas, 
                        csv_tipo
                    )
                    
                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                    with col_stat1:
                        st.metric("Subestações", len(df_preview))
                    with col_stat2:
                        st.metric("Colunas", len(df_preview.columns))
                    with col_stat3:
                        st.metric("Registros", len(df_preview))
                    
                    st.dataframe(
                        df_preview.head(10),
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    if len(df_preview) > 10:
                        st.caption(f"Mostrando 10 de {len(df_preview)} registros. Baixe o arquivo completo abaixo.")
                        
            except Exception as e:
                st.error(f"Erro ao carregar preview: {e}")
    
    if csv_classes and csv_metricas:
        try:
            csv_bytes = generate_csv(
                get_bulk_data(),
                csv_classes,
                csv_metricas,
                csv_tipo
            )
            
            data_atual = datetime.now().strftime("%Y%m%d_%H%M")
            st.download_button(
                label="Baixar Dataset CSV",
                data=csv_bytes,
                file_name=f"GridScope_Dataset_{data_atual}.csv",
                mime="text/csv",
                use_container_width=True,
                type="primary"
            )
        except Exception as e:
            st.error(f"Erro ao gerar CSV: {e}")
    else:
        st.button("Baixar Dataset CSV", disabled=True, use_container_width=True)
        st.caption("Selecione pelo menos uma classe e uma métrica.")
    
    st.divider()
    
    st.header("2. Relatório PDF")
    st.markdown("""
    **Ideal para documentação e apresentações.**
    
    Gere relatórios visuais prontos para impressão com:
    - **Análise por Subestação** - Foco em uma área específica
    - **Gráficos e tabelas** - Visualização clara dos indicadores
    - **Design GridScope** - Identidade visual profissional
    
    *Perfeito para reuniões, relatórios gerenciais e documentação técnica.*
    """)
    
    try:
        from utils import carregar_dados_cache
        gdf, dados_lista = carregar_dados_cache()
        df_mercado = pd.DataFrame(dados_lista) if dados_lista else pd.DataFrame()
        
        mapa_opcoes = {}
        if not df_mercado.empty and 'subestacao' in df_mercado.columns:
            for idx, row in df_mercado.iterrows():
                label = str(row.get('subestacao', ''))
                # Ignora subestações externas
                if '(EXTERNA)' in label:
                    continue
                id_tec = row.get('id_tecnico', idx)
                mapa_opcoes[label] = id_tec
    except Exception as e:
        st.error(f"Erro ao carregar subestações: {e}")
        mapa_opcoes = {}
    
    col_sub, col_data = st.columns(2)
    
    with col_sub:
        if mapa_opcoes:
            subestacao_selecionada = st.selectbox(
                "Subestação",
                options=sorted(mapa_opcoes.keys()),
                key="pdf_subestacao"
            )
            id_subestacao = mapa_opcoes.get(subestacao_selecionada)
        else:
            st.warning("Nenhuma subestação disponível")
            subestacao_selecionada = None
            id_subestacao = None
    
    with col_data:
        from datetime import date
        data_relatorio = st.date_input(
            "Data do Relatório",
            value=date.today(),
            key="pdf_data"
        )
    
    pdf_classes = st.multiselect(
        "Classes a incluir no relatório",
        options=CLASSES_DISPONIVEIS,
        default=["Residencial", "Comercial", "Industrial"],
        key="pdf_classes"
    )
    
    st.subheader("Seções do Relatório")
    col_sec1, col_sec2 = st.columns(2)
    
    with col_sec1:
        sec_consumo = st.checkbox("Consumo por Classe", value=True, key="sec_consumo")
        sec_gd = st.checkbox("Geração Distribuída por Classe", value=True, key="sec_gd")
    
    with col_sec2:
        sec_comparacao = st.checkbox("Comparação vs Total da Cidade", value=True, key="sec_comparacao")
        sec_ranking = st.checkbox("Ranking das Subestações", value=True, key="sec_ranking")
        sec_diagnostico = st.checkbox("Diagnóstico da Ferramenta (IA)", value=True, help="Gera análise automática com Inteligência Artificial (pode demorar alguns segundos)", key="sec_diagnostico")
    
    secoes_pdf = []
    if sec_consumo:
        secoes_pdf.append("consumo")
    if sec_gd:
        secoes_pdf.append("gd")
    if sec_comparacao:
        secoes_pdf.append("comparacao")
    if sec_ranking:
        secoes_pdf.append("ranking")
    if sec_diagnostico:
        secoes_pdf.append("diagnostico")
    
    if pdf_classes and secoes_pdf and subestacao_selecionada:
        try:
            if st.button("Gerar Relatório PDF", use_container_width=True, type="secondary"):
                with st.spinner("Gerando PDF..."):
                    pdf_bytes = generate_pdf(
                        classes_selecionadas=pdf_classes,
                        metricas_selecionadas=["clientes", "consumo_mwh", "potencia_gd_kw", "qtd_gd"],
                        tipo_valor="absoluto",
                        substation_id=str(id_subestacao),
                        secoes=secoes_pdf
                    )
                
                data_formatada = data_relatorio.strftime("%Y%m%d")
                nome_arquivo = f"Relatorio_GridScope_{subestacao_selecionada.replace(' ', '_')}_{data_formatada}.pdf"
                st.download_button(
                    label="Download PDF",
                    data=pdf_bytes,
                    file_name=nome_arquivo,
                    mime="application/pdf",
                    use_container_width=True
                )
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")
    else:
        st.button("Gerar Relatório PDF", disabled=True, use_container_width=True)
        if not subestacao_selecionada:
            st.caption("Selecione uma subestação.")
        if not pdf_classes:
            st.caption("Selecione pelo menos uma classe.")
        if not secoes_pdf:
            st.caption("Selecione pelo menos uma seção.")
    
    st.divider()
    
    with st.expander("Sobre os Dados"):
        st.markdown("""
        ### Estrutura do CSV (Tidy Data)
        
        O arquivo CSV segue o formato "Tidy Data" recomendado para análise de dados:
        
        | Subestação | ID | Região | Residencial_Clientes | Comercial_Clientes | ... |
        |------------|-----|--------|---------------------|-------------------|-----|
        | SE Farolândia | 12345 | Centro | 5000 | 200 | ... |
        
        ### Cálculo de Percentual
        
        Quando selecionado "Percentual do Total", cada valor é calculado como:
        
        ```
        Percentual = (Valor da Classe / Total da Subestação) × 100
        ```
        """)
    
    # Footer
    st.caption(f"GridScope Enterprise v5.0 | Central de Exportação | {datetime.now().strftime('%d/%m/%Y')}")
