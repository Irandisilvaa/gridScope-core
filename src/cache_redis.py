
import redis
import json
import logging
from functools import wraps
from typing import Optional, Any
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from config import REDIS_HOST, REDIS_PORT, REDIS_DB
except ImportError:
    REDIS_HOST = "redis"
    REDIS_PORT = 6379
    REDIS_DB = 0

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
PUBLICATION_VERSION_KEY = "grid_scope:publication_version"

try:
    redis_client = redis.Redis(
        host=REDIS_HOST, 
        port=REDIS_PORT, 
        db=REDIS_DB, 
        decode_responses=True,
        socket_connect_timeout=2
    )
except Exception as e:
    logger.warning(f"⚠️ Redis não configurado corretamente: {e}")
    redis_client = None

_VERSAO_RECUPERADA: Optional[str] = None


def is_redis_available():
    if not redis_client: return False
    try:
        return redis_client.ping()
    except redis.RedisError:
        return False

def _recuperar_versao_publicada() -> str:
    """Usa o registro transacional do banco quando o Redis perde a chave de versão."""

    global _VERSAO_RECUPERADA
    if _VERSAO_RECUPERADA:
        return _VERSAO_RECUPERADA

    try:
        from database import carregar_publication_metadata

        metadata = carregar_publication_metadata()
    except Exception as error:
        logger.warning(f"Falha ao recuperar a versão publicada no banco: {error}")
        return "unpublished"

    if not isinstance(metadata, dict):
        return "unpublished"

    versao = str(metadata.get("publication_id") or "unpublished")
    definir_versao_publicacao(versao)
    _VERSAO_RECUPERADA = versao
    return versao


def _publication_version() -> str:
    """Retorna a versão publicada para impedir cache de snapshots antigos."""

    if not is_redis_available():
        return "unpublished"

    try:
        redis_version = redis_client.get(PUBLICATION_VERSION_KEY)
    except redis.RedisError as error:
        logger.warning(f"Falha ao ler a versão publicada no Redis: {error}")
        return "unpublished"
    if redis_version:
        return str(redis_version)

    return _recuperar_versao_publicada()


def definir_versao_publicacao(publication_id: str) -> bool:
    """Registra no Redis o corte publicado usado como namespace de cache."""

    global _VERSAO_RECUPERADA

    if not is_redis_available():
        return False
    try:
        redis_client.set(PUBLICATION_VERSION_KEY, str(publication_id))
        _VERSAO_RECUPERADA = None
        return True
    except Exception:
        logger.exception("Falha ao registrar versão publicada no Redis")
        return False

def cache_json(ttl_seconds: int = 300, key_prefix: str = "api_cache"):
    """
    Decorator para cachear respostas JSON de endpoints.
    Chave do cache: prefixo + nome_funcao + argumentos

    Os testes de contrato podem desabilitar o backend operacional com
    ``GRIDSCOPE_DISABLE_RUNTIME_CACHE=1``. Isso evita que fixtures sejam
    persistidas no Redis usado pelo dashboard.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if os.getenv("GRIDSCOPE_DISABLE_RUNTIME_CACHE") == "1":
                return func(*args, **kwargs)
            if not is_redis_available():
                return func(*args, **kwargs)

            key_parts = [key_prefix, f"publication={_publication_version()}", func.__name__]
            if args: key_parts.extend([str(a) for a in args])
            if kwargs: key_parts.extend([f"{k}={v}" for k, v in kwargs.items()])
            
            cache_key = ":".join(key_parts)
            
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    logger.info(f"⚡ Cache HIT: {cache_key}")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Erro ao ler Redis: {e}")

            result = func(*args, **kwargs)

            try:
                # Não permita que uma resposta iniciada no corte anterior seja
                # gravada no namespace que deixou de ser autoritativo.
                if _publication_version() != key_parts[1].split("=", 1)[1]:
                    return result
                if hasattr(result, 'to_json'):
                    to_save = result.to_json()
                elif hasattr(result, 'dict'):
                    to_save = json.dumps(result.dict())
                else:
                    to_save = json.dumps(result)
                
                redis_client.setex(cache_key, ttl_seconds, to_save)
                logger.info(f"💾 Cache SET: {cache_key} (TTL: {ttl_seconds}s)")
            except Exception as e:
                logger.warning(f"Erro ao salvar Redis: {e}")
            
            return result
        return wrapper
    return decorator

def limpar_cache(padrao: str = "api_cache:*"):
    if not is_redis_available(): return 0
    keys = list(redis_client.scan_iter(match=padrao))
    if keys:
        return redis_client.delete(*keys)
    return 0
