import streamlit as st
import sys
import os

st.set_page_config(
    page_title="GridScope - Inteligência Energética",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from views import analise_subestacao, visao_geral, relatorios
except ImportError as e:
    st.error(f"Erro de importação no main.py: {e}")
    st.stop()

# --- CSS Personalizado ---
st.markdown("""
    <style>
        .stApp { background-color: #0e1117; }
        section[data-testid="stSidebar"] { background-color: #161b22; }
    </style>
""", unsafe_allow_html=True)

# --- Sidebar ---
st.sidebar.image("https://img.icons8.com/fluency/96/lightning-bolt.png", width=60)
st.sidebar.title("GridScope")
st.sidebar.markdown("---")

navegacao = st.sidebar.radio(
    "Navegue pelo Sistema:",
    ["🔍 Análise por Subestação (IA)", "📊 Visão Geral", "📄 Relatórios"]
)

st.sidebar.markdown("---")
st.sidebar.caption("Hackathon Edition v1.0")

# --- Roteamento ---
if navegacao == "🔍 Análise por Subestação (IA)":
    try:
        # Verifica se o módulo tem a função render_view
        if hasattr(analise_subestacao, 'render_view'):
            analise_subestacao.render_view()
        else:
            st.warning("Módulo 'analise_subestacao' carregado, mas sem função render_view().")
    except Exception as e:
        st.error(f"Erro ao carregar módulo de Análise: {e}")

elif navegacao == "📊 Visão Geral":
    try:
        if hasattr(visao_geral, 'render_view'):
            visao_geral.render_view()
        else:
            st.warning("Módulo 'visao_geral' carregado, mas sem função render_view().")
    except Exception as e:
        st.error(f"Erro ao carregar módulo de Visão Geral: {e}")

elif navegacao == "📄 Relatórios":
    try:
        if hasattr(relatorios, 'render_view'):
            relatorios.render_view()
        else:
            st.warning("Módulo 'relatorios' carregado, mas sem função render_view().")
    except Exception as e:
        st.error(f"Erro ao carregar módulo de Relatórios: {e}")