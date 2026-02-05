import streamlit as st
import sys
import os

# --- Configuração Inicial ---
st.set_page_config(
    page_title="GridScope - Inteligência Energética",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicialização do Estado
if 'pagina_atual' not in st.session_state:
    st.session_state['pagina_atual'] = "Visão Geral"

# Configuração de Caminho
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# --- Importação das Views com Tratamento de Erro ---
try:
    from views import analise_subestacao, visao_geral, tab_chat, relatorios
except ImportError as e:
    st.error(f"Aviso: {e}. Certifique-se que a pasta 'views' existe e contém os arquivos.")
    class MockView:
        def render_view(self): st.info("Funcionalidade em desenvolvimento ou arquivo não encontrado.")
    
    if 'analise_subestacao' not in locals(): analise_subestacao = MockView()
    if 'visao_geral' not in locals(): visao_geral = MockView()
    if 'tab_chat' not in locals(): tab_chat = MockView()
    if 'relatorios' not in locals(): relatorios = MockView()

# --- CSS Personalizado ---
st.markdown("""
    <style>
        .stApp { background-color: #0e1117; }
        section[data-testid="stSidebar"] { background-color: #161b22; }
        
        .profile-container {
            width: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding-top: 10px;
            padding-bottom: 10px; 
            margin-bottom: 10px;
        }
        
        .avatar-frame {
            width: 90px; /* Reduzi levemente para caber melhor embaixo */
            height: 90px;
            border-radius: 50%;
            padding: 3px; 
            background: linear-gradient(45deg, #f09433 0%, #e6683c 25%, #dc2743 50%, #cc2366 75%, #bc1888 100%); 
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 5px;
            transition: transform 0.3s ease;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            overflow: hidden; 
        }
        
        .avatar-frame:hover {
            transform: scale(1.05);
            cursor: pointer;
        }

        .avatar-img {
            width: 100%;
            height: 100%;
            border-radius: 50%;
            object-fit: cover; 
            object-position: center; 
            transform: scale(2.1);
            display: block;
            border: none;
        }
        
        .profile-name {
            color: #ffffff;
            font-weight: bold;
            font-size: 1.1rem;
            margin: 0;
            line-height: 1.2;
            text-align: center;
        }
        
        .profile-status {
            color: #00e676;
            font-size: 0.75rem;
            margin-top: 2px;
            margin-bottom: 0px;
            text-align: center;
            font-weight: 500;
            letter-spacing: 0.5px;
        }
        
        div.stButton > button {
            width: 100%;
            border-radius: 20px;
            background-color: #21262d;
            color: white;
            border: 1px solid #30363d;
            margin-top: 5px;
            font-weight: 600;
        }
        div.stButton > button:hover {
            border-color: #f09433;
            color: #f09433;
            background-color: #262c36;
        }
    </style>
""", unsafe_allow_html=True)

url_logo = "https://i.ibb.co/PzM7Kbs7/imagem-2026-02-04-150703728-removebg-preview.png" 
url_avatar = "https://i.ibb.co/8Lm3gSKk/Gemini-Generated-Image-dmdcrpdmdcrpdmdc.png"


st.sidebar.image(url_logo, use_container_width=True)
st.sidebar.markdown("<br>", unsafe_allow_html=True) 

opcoes_menu = ["🔍 Análise por Subestação", "📊 Visão Geral", "📄 Relatórios"]

# Callback para atualizar a página quando o radio muda
def on_radio_change():
    st.session_state['pagina_atual'] = st.session_state['nav_radio']

# Define o índice inicial do radio
# Se a página atual não estiver no menu (ex: Chat IA), mantemos o índice anterior ou 0
if 'nav_radio' not in st.session_state:
     st.session_state['nav_radio'] = opcoes_menu[0]

try:
    # Tenta sincronizar o radio com a página atual se ela estiver no menu
    if st.session_state['pagina_atual'] in opcoes_menu:
        index_atual = opcoes_menu.index(st.session_state['pagina_atual'])
    else:
        # Se estiver no Chat, mantemos o visual no último item ou 0, sem triggerar mudança
        index_atual = opcoes_menu.index(st.session_state.get('nav_radio', opcoes_menu[0]))
except (ValueError, KeyError):
    index_atual = 0

navegacao = st.sidebar.radio(
    "Ferramentas:",
    opcoes_menu,
    index=index_atual,
    key="nav_radio",
    on_change=on_radio_change
)

st.sidebar.markdown("---")
st.sidebar.markdown("**Assistente Inteligente**")

st.sidebar.markdown(f"""
    <div class="profile-container">
        <div class="avatar-frame">
            <img src="{url_avatar}" class="avatar-img">
        </div>
        <p class="profile-name">Helios AI</p>
        <p class="profile-status">● Online</p>
    </div>
""", unsafe_allow_html=True)

if st.sidebar.button("✨ Conversar com Helios"):
    st.session_state['pagina_atual'] = "Chat IA"
    st.rerun()

st.sidebar.caption("GridScope v4.9 Enterprise")

pagina = st.session_state['pagina_atual']

if pagina == "Chat IA":
    col_a, col_b = st.columns([1, 20])
    with col_a:
        st.markdown(f'<div style="width:60px; height:60px; border-radius:50%; overflow:hidden;"><img src="{url_avatar}" style="width:100%; height:100%; object-fit:cover; transform:scale(2.1);"></div>', unsafe_allow_html=True)
    with col_b:
        st.title("Helios AI Assistant")
        
    try:
        if hasattr(tab_chat, 'render_view'):
            tab_chat.render_view()
        else:
            st.info("Olá! Sou o Helios. O módulo de chat ainda não está conectado.")
    except Exception as e:
        st.error(f"Erro no Chat: {e}")

elif pagina == "🔍 Análise por Subestação":
    try:
        if hasattr(analise_subestacao, 'render_view'):
            analise_subestacao.render_view()
    except Exception as e:
        st.error(f"Erro ao carregar módulo de Análise: {e}")

elif pagina == "📊 Visão Geral":
    try:
        if hasattr(visao_geral, 'render_view'):
            visao_geral.render_view()
    except Exception as e:
        st.error(f"Erro ao carregar módulo de Visão Geral: {e}")

elif pagina == "📄 Relatórios":
    try:
        if hasattr(relatorios, 'render_view'):
            relatorios.render_view()
        else:
            st.warning("Módulo 'relatorios' carregado, mas sem função render_view().")
    except Exception as e:
        st.error(f"Erro ao carregar módulo de Relatórios: {e}")