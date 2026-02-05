import streamlit as st
import sys
import os
import base64
from pathlib import Path

# --- Configuração Inicial (DEVE ser a primeira linha do Streamlit) ---
st.set_page_config(
    page_title="GridScope - Inteligência Energética",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Gerenciamento de Caminhos Robusto (Fix para Docker/Linux) ---
# Pega o diretório onde ESTE arquivo está localizado
CURRENT_FILE_DIR = Path(__file__).parent.absolute()

# Se este arquivo estiver na raiz, o BASE_DIR é ele mesmo.
# Se estiver dentro de src, ajustamos.
BASE_DIR = CURRENT_FILE_DIR

# Adiciona ao path do sistema para importações funcionarem
sys.path.append(str(BASE_DIR))

# --- Definição dos Caminhos de Recursos ---
# Usando Pathlib para garantir compatibilidade de barras (/ ou \)
# IMPORTANTE: Verifique se no Linux as pastas estão exatamente como "src", "icons" (tudo minúsculo)
path_logo = BASE_DIR / "src" / "icons" / "logoGridScope.png"
path_avatar = BASE_DIR / "src" / "icons" / "helio.png"

# Debug nos logs da AWS (para você ver se o caminho está certo com 'docker logs')
print(f"--- DEBUG PATHS ---")
print(f"Base Dir: {BASE_DIR}")
print(f"Logo Path: {path_logo} | Existe? {path_logo.exists()}")
print(f"Avatar Path: {path_avatar} | Existe? {path_avatar.exists()}")
print(f"-------------------")

if 'pagina_atual' not in st.session_state:
    st.session_state['pagina_atual'] = "Visão Geral"

# --- Função Auxiliar: Imagem para Base64 ---
def get_img_as_base64(file_path):
    try:
        if not file_path.exists():
            return ""
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception as e:
        print(f"Erro ao carregar imagem {file_path}: {e}")
        return ""

# Carregamento prévio para HTML
avatar_b64 = get_img_as_base64(path_avatar)
img_avatar_src = f"data:image/png;base64,{avatar_b64}" if avatar_b64 else ""

# --- Importação das Views ---
try:
    # Tenta importar dos módulos locais
    from src.views import analise_subestacao, visao_geral, tab_chat, relatorios
except ImportError:
    try:
        # Tenta importar direto se o PYTHONPATH já incluir src
        from views import analise_subestacao, visao_geral, tab_chat, relatorios
    except ImportError as e:
        st.error(f"Erro de Importação das Views: {e}")
        # Classes Mock para não quebrar a UI
        class MockView:
            def render_view(self): st.info("Módulo em manutenção ou não encontrado.")
        
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
            transform: scale(1.1); /* Ajustado escala para não cortar demais */
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
    st.sidebar.warning(f"Logo não encontrado em: {path_logo}")

st.sidebar.markdown("<br>", unsafe_allow_html=True) 

opcoes_menu = ["🔍 Análise por Subestação", "📊 Visão Geral", "📄 Relatórios"]

try:
    if st.session_state['pagina_atual'] in opcoes_menu:
        index_atual = opcoes_menu.index(st.session_state['pagina_atual'])
    else:
        index_atual = 0 
except ValueError:
    index_atual = 0 

navegacao = st.sidebar.radio(
    "Ferramentas:",
    opcoes_menu,
    index=index_atual,
    key="nav_radio"
)

if navegacao != st.session_state['pagina_atual'] and navegacao in opcoes_menu:
    st.session_state['pagina_atual'] = navegacao
    st.rerun()

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

if st.sidebar.button("✨ Conversar com Helios"):
    st.session_state['pagina_atual'] = "Chat IA"
    st.rerun()

st.sidebar.caption("GridScope v4.9 Enterprise")

# --- Roteamento de Páginas ---
pagina = st.session_state['pagina_atual']

if pagina == "Chat IA":
    col_a, col_b = st.columns([1, 20])
    with col_a:
        # Ajuste no HTML do avatar pequeno
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