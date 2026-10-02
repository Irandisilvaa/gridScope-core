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

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres@localhost:5435/gridscope_local")
DATABASE_SCHEMA = os.getenv("DATABASE_SCHEMA", "public").strip()

# Alimentação de dados. Em desenvolvimento, o adaptador local mantém a execução
# com um GDB já disponível. Em operação, configurar um adaptador da distribuidora
# somente após o contrato de acesso e formato ser confirmado.
DATA_SOURCE = os.getenv("DATA_SOURCE", "local_file").strip().lower()
FILE_GDB = os.getenv(
    "FILE_GDB",
    "Energisa_SE_6587_2024-12-31_V11_20250902-1412.gdb",
)
DISTRIBUTOR_SOURCE_URL = os.getenv("DISTRIBUTOR_SOURCE_URL")
DISTRIBUTOR_API_TOKEN = os.getenv("DISTRIBUTOR_API_TOKEN")
DATA_SOURCE_TIMEOUT_SECONDS = int(os.getenv("DATA_SOURCE_TIMEOUT_SECONDS", "120"))
DATA_MAX_DOWNLOAD_BYTES = int(os.getenv("DATA_MAX_DOWNLOAD_BYTES", str(2 * 1024 * 1024 * 1024)))
DATA_MAX_ARCHIVE_ENTRIES = int(os.getenv("DATA_MAX_ARCHIVE_ENTRIES", "100000"))
DATA_INGEST_ON_STARTUP = os.getenv("DATA_INGEST_ON_STARTUP", "false").lower() in {"1", "true", "yes"}
TRAIN_MODEL_ON_STARTUP = os.getenv("TRAIN_MODEL_ON_STARTUP", "false").lower() in {"1", "true", "yes"}
ALLOW_FILE_CACHE = os.getenv("ALLOW_FILE_CACHE", "true").lower() in {"1", "true", "yes"}
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
AUTH_SESSION_TTL_SECONDS = int(os.getenv("AUTH_SESSION_TTL_SECONDS", str(8 * 60 * 60)))
AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "gridscope_session")
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
AUTH_LOGIN_RATE_LIMIT = int(os.getenv("AUTH_LOGIN_RATE_LIMIT", "8"))
AUTH_LOGIN_RATE_WINDOW_SECONDS = int(os.getenv("AUTH_LOGIN_RATE_WINDOW_SECONDS", "900"))
AUTH_CHAT_RATE_LIMIT = int(os.getenv("AUTH_CHAT_RATE_LIMIT", "20"))
AUTH_CHAT_RATE_WINDOW_SECONDS = int(os.getenv("AUTH_CHAT_RATE_WINDOW_SECONDS", "60"))
AUTH_ADMIN_RATE_LIMIT = int(os.getenv("AUTH_ADMIN_RATE_LIMIT", "30"))
AUTH_ADMIN_RATE_WINDOW_SECONDS = int(os.getenv("AUTH_ADMIN_RATE_WINDOW_SECONDS", "60"))

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
