import streamlit as st
import sys
import os
import base64
from pathlib import Path

st.set_page_config(
    page_title="GridScope - Inteligência Energética",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

CURRENT_FILE_DIR = Path(__file__).parent.absolute()

if CURRENT_FILE_DIR.name == 'src':
    BASE_DIR = CURRENT_FILE_DIR.parent  
else:
    BASE_DIR = CURRENT_FILE_DIR       

if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

path_logo = BASE_DIR / "src" / "icons" / "logoGridScope.png"
path_avatar = BASE_DIR / "src" / "icons" / "helio.png"

print(f"--- DEBUG PATHS ---")
print(f"Diretório Atual do Arquivo: {CURRENT_FILE_DIR}")
print(f"Raiz do Projeto Definida (BASE_DIR): {BASE_DIR}")
print(f"Procurando Logo em: {path_logo}")
print(f"Existe? {path_logo.exists()}")
print(f"-------------------")

if 'pagina_atual' not in st.session_state:
    st.session_state['pagina_atual'] = "📊 Visão Geral"

def get_img_as_base64(file_path):
    if not file_path.exists():
        return ""
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception as e:
        print(f"Erro ao ler imagem {file_path}: {e}")
        return ""

avatar_b64 = get_img_as_base64(path_avatar)
img_avatar_src = f"data:image/png;base64,{avatar_b64}" if avatar_b64 else ""

try:
    from src.views import analise_subestacao, visao_geral, tab_chat, relatorios
except ImportError:
    try:
        from views import analise_subestacao, visao_geral, tab_chat, relatorios
    except ImportError as e:
        st.error(f"Erro de Importação: {e}")
        class MockView:
            def render_view(self): st.info("Módulo não encontrado.")
        
        if 'analise_subestacao' not in locals(): analise_subestacao = MockView()
        if 'visao_geral' not in locals(): visao_geral = MockView()
        if 'tab_chat' not in locals(): tab_chat = MockView()
        if 'relatorios' not in locals(): relatorios = MockView()

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
            padding: 10px 0; 
            margin-bottom: 10px;
        }
        
        .avatar-frame {
            width: 90px;
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
            transform: scale();
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

# --- Construção da Sidebar ---
if path_logo.exists():
    st.sidebar.image(str(path_logo), use_container_width=True)
else:
    # Mostra um aviso amigável se não achar
    st.sidebar.warning(f"Logo não encontrado.")

st.sidebar.markdown("<br>", unsafe_allow_html=True) 

opcoes_menu = ["🔍 Análise por Subestação", "📊 Visão Geral", "📄 Relatórios"]

# --- Função de Navegação Centralizada ---
def set_page(page_name=None):
    if page_name is None:
        page_name = st.session_state.get('nav_radio')
    
    st.session_state['pagina_atual'] = page_name
    
    # Se a página não estiver no menu (ex: Chat), limpa a seleção do radio
    if page_name not in opcoes_menu and 'nav_radio' in st.session_state:
        st.session_state['nav_radio'] = None

# Callback para o radio button
def update_nav():
    set_page(st.session_state['nav_radio'])

try:
    if st.session_state['pagina_atual'] in opcoes_menu:
        index_atual = opcoes_menu.index(st.session_state['pagina_atual'])
    else:
        index_atual = None 
except ValueError:
    index_atual = None 

navegacao = st.sidebar.radio(
    "Ferramentas:",
    opcoes_menu,
    index=index_atual,
    key="nav_radio",
    on_change=update_nav
)

st.sidebar.markdown("---")
st.sidebar.markdown("**Assistente Inteligente**")

# Renderiza Avatar HTML apenas se a imagem foi carregada
avatar_html = f"""
    <div class="profile-container">
        <div class="avatar-frame">
            <img src="{img_avatar_src}" class="avatar-img">
        </div>
        <p class="profile-name">Helios AI</p>
        <p class="profile-status">● Online</p>
    </div>
"""
st.sidebar.markdown(avatar_html, unsafe_allow_html=True)

st.sidebar.button("✨ Conversar com Helios", on_click=set_page, args=("Chat IA",))


st.sidebar.caption("GridScope v4.9 Enterprise")

# --- Roteamento de Páginas ---
pagina = st.session_state['pagina_atual']

if pagina == "Chat IA":
    col_a, col_b = st.columns([1, 20])
    with col_a:
        st.markdown(f'<div style="width:60px; height:60px; border-radius:50%; overflow:hidden;"><img src="{img_avatar_src}" style="width:100%; height:100%; object-fit:cover;"></div>', unsafe_allow_html=True)
    with col_b:
        st.title("Helios AI Assistant")
        
    try:
        if hasattr(tab_chat, 'render_view'):
            tab_chat.render_view()
        else:
            st.info("Módulo de chat desconectado.")
    except Exception as e:
        st.error(f"Erro no Chat: {e}")

elif pagina == "🔍 Análise por Subestação":
    try:
        if hasattr(analise_subestacao, 'render_view'):
            analise_subestacao.render_view()
    except Exception as e:
        st.error(f"Erro em Análise: {e}")

elif pagina == "📊 Visão Geral":
    try:
        if hasattr(visao_geral, 'render_view'):
            visao_geral.render_view()
    except Exception as e:
        st.error(f"Erro em Visão Geral: {e}")

elif pagina == "📄 Relatórios":
    try:
        if hasattr(relatorios, 'render_view'):
            relatorios.render_view()
    except Exception as e:
        st.error(f"Erro em Relatórios: {e}")