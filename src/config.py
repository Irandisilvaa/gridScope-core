import os
from dotenv import load_dotenv

DIR_SRC = os.path.dirname(os.path.abspath(__file__))
DIR_RAIZ = os.path.dirname(DIR_SRC)

DIR_DADOS = os.path.join(DIR_RAIZ, "dados")

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

CIDADE_ALVO = os.getenv("CIDADE_ALVO", "Aracaju, Sergipe, Brazil")
CRS_PROJETADO = "EPSG:31984"

ANEEL_API_HUB_URL = os.getenv("ANEEL_API_HUB_URL", "https://hub.arcgis.com/api/search/v1/collections/all/items")
DISTRIBUIDORA_ALVO = os.getenv("DISTRIBUIDORA_ALVO", "Energisa SE")

CHAT_API_KEY = os.getenv("GEMINI_API_KEY")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-3-flash-preview")
