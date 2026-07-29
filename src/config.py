import os
from dotenv import load_dotenv

DIR_SRC = os.path.dirname(os.path.abspath(__file__))
DIR_RAIZ = os.path.dirname(DIR_SRC)

DIR_DADOS = os.path.join(DIR_RAIZ, "dados")
os.makedirs(DIR_DADOS, exist_ok=True)

path_env = os.path.join(DIR_RAIZ, '.env')
load_dotenv(path_env)

_http_proxy = os.getenv("HTTP_PROXY")
_https_proxy = os.getenv("HTTPS_PROXY")
if _http_proxy:
    os.environ["HTTP_PROXY"] = _http_proxy
    os.environ["http_proxy"] = _http_proxy
if _https_proxy:
    os.environ["HTTPS_PROXY"] = _https_proxy
    os.environ["https_proxy"] = _https_proxy

# Bypass de proxy para comunicação local (API FastAPI, etc)
os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
os.environ["no_proxy"] = "localhost,127.0.0.1,::1"

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:1234@localhost:5435/gridscope_local")

import re

CIDADE_ALVO = os.getenv("CIDADE_ALVO", "Aracaju, Sergipe, Brazil")

def get_city_slug(cidade: str) -> str:
    s = str(cidade).lower().strip()
    s = re.sub(r'[^a-z0-9]', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    return s or "cidade"

def get_cidade_alvo():
    return os.getenv("CIDADE_ALVO", CIDADE_ALVO)

def atualizar_cidade_alvo(nova_cidade):
    global CIDADE_ALVO
    CIDADE_ALVO = nova_cidade
    os.environ["CIDADE_ALVO"] = nova_cidade
    
    path_env = os.path.join(DIR_RAIZ, '.env')
    if os.path.exists(path_env):
        try:
            with open(path_env, 'r', encoding='utf-8') as f:
                linhas = f.readlines()
            with open(path_env, 'w', encoding='utf-8') as f:
                cidade_escrita = False
                for linha in linhas:
                    if linha.startswith("CIDADE_ALVO="):
                        f.write(f"CIDADE_ALVO={nova_cidade}\n")
                        cidade_escrita = True
                    else:
                        f.write(linha)
                if not cidade_escrita:
                    f.write(f"CIDADE_ALVO={nova_cidade}\n")
        except Exception:
            pass
CRS_PROJETADO = "EPSG:31984"

ANEEL_API_HUB_URL = os.getenv("ANEEL_API_HUB_URL", "https://hub.arcgis.com/api/search/v1/collections/all/items")
DISTRIBUIDORA_ALVO = os.getenv("DISTRIBUIDORA_ALVO", "Energisa SE")

CHAT_API_KEY = os.getenv("GEMINI_API_KEY")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-3-flash-preview")
