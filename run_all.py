import subprocess
import sys
import time
import os
import logging
import urllib.error
import urllib.request
import platform
from datetime import datetime

DIR_RAIZ = os.path.dirname(os.path.abspath(__file__))
DIR_SRC = os.path.join(DIR_RAIZ, "src")
DIR_LOGS = os.path.join(DIR_RAIZ, "logs")
DIR_FRONTEND = os.path.join(DIR_RAIZ, "frontend")

CAMINHO_MODELO_PKL = os.path.join(DIR_SRC, "ai", "modelo_consumo.pkl")

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

PYTHON_EXEC = sys.executable

API_STARTUP_ENDPOINTS = {
    "API Principal": "http://127.0.0.1:8000/ready",
    "API Inteligência Artificial": "http://127.0.0.1:8001/health",
    "API Chat IA": "http://127.0.0.1:8002/ready",
}

FRONTEND_DEV_URL = "http://localhost:5173"

os.makedirs(DIR_LOGS, exist_ok=True)

nome_arquivo_log = f"{datetime.now().strftime('%Y-%m-%d')}_sistema.log"
caminho_log = os.path.join(DIR_LOGS, nome_arquivo_log)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(caminho_log, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("GridScope")


def modelo_artefato_compativel() -> bool:
    try:
        import joblib
        from src.ai.model_contract import model_is_compatible

        return model_is_compatible(joblib.load(CAMINHO_MODELO_PKL))
    except Exception as error:
        logger.warning("⚠️ Artefato ML indisponível ou incompatível: %s", error)
        return False


def get_env_with_src():
    env = os.environ.copy()
    original_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{DIR_SRC}{os.pathsep}{original_path}"
    env["PYTHONIOENCODING"] = "utf-8"
    env["NODE_ENV"] = env.get("NODE_ENV", "development")
    return env


def run_script(script_path, description):
    if not os.path.exists(script_path):
        logger.error(f"❌ ARQUIVO NÃO ENCONTRADO: {script_path}")
        return False

    inicio = time.time()
    logger.info(f"▶️ INICIANDO: {description}")

    resultado = subprocess.run([PYTHON_EXEC, script_path], env=get_env_with_src())

    duracao = round(time.time() - inicio, 2)
    if resultado.returncode == 0:
        logger.info(f"✅ SUCESSO: {description} ({duracao}s)")
        return True
    logger.error(f"❌ FALHA: {description} (Código {resultado.returncode})")
    return False


def run_module(module_name, description):
    """Executa um job Python empacotado com o mesmo ambiente do sistema."""

    inicio = time.time()
    logger.info(f"▶️ INICIANDO: {description}")
    resultado = subprocess.run(
        [PYTHON_EXEC, "-m", module_name],
        cwd=DIR_RAIZ,
        env=get_env_with_src(),
    )
    duracao = round(time.time() - inicio, 2)
    if resultado.returncode == 0:
        logger.info(f"✅ SUCESSO: {description} ({duracao}s)")
        return True
    logger.error(f"❌ FALHA: {description} (Código {resultado.returncode})")
    return False


def start_api_process(module_name, port, log_filename, description):
    logger.info(f"🚀 SUBINDO {description} na porta {port}...")

    log_path = os.path.join(DIR_LOGS, log_filename)
    log_file = open(log_path, "w", encoding="utf-8")

    workers = os.getenv("UVICORN_WORKERS", "1")

    env_vars = get_env_with_src()
    env_vars["PYTHONIOENCODING"] = "utf-8"

    try:
        return subprocess.Popen(
            [
                PYTHON_EXEC,
                "-m",
                "uvicorn",
                module_name,
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
                "--workers",
                workers,
            ],
            cwd=DIR_RAIZ,
            env=env_vars,
            stdout=log_file,
            stderr=log_file,
        )
    finally:
        log_file.close()


def start_frontend_process(log_filename="frontend_dev.log", description="Frontend (Vite)"):
    logger.info(f"🚀 SUBINDO {description} em http://localhost:5173...")

    if not os.path.exists(DIR_FRONTEND):
        raise FileNotFoundError(f"Pasta frontend não encontrada: {DIR_FRONTEND}")

    log_path = os.path.join(DIR_LOGS, log_filename)
    log_file = open(log_path, "w", encoding="utf-8")

    npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"

    env_vars = os.environ.copy()
    env_vars["NODE_ENV"] = env_vars.get("NODE_ENV", "development")
    env_vars["VITE_HOST"] = env_vars.get("VITE_HOST", "0.0.0.0")

    try:
        return subprocess.Popen(
            [npm_cmd, "run", "dev", "--", "--host", "0.0.0.0"],
            cwd=DIR_FRONTEND,
            env=env_vars,
            stdout=log_file,
            stderr=log_file,
        )
    finally:
        log_file.close()


def _stop_api_processes(processes):
    for description, process in processes:
        if process.poll() is None:
            logger.info("🛑 Encerrando %s...", description)
            try:
                process.terminate()
            except Exception:
                pass

    for description, process in processes:
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            logger.warning("⚠️ %s não encerrou no prazo; forçando parada", description)
            try:
                process.kill()
                process.wait(timeout=5)
            except Exception:
                pass


def aguardar_servicos(
    processes,
    endpoints,
    timeout_seconds=90,
    interval_seconds=1,
    request_timeout_seconds=10,
):
    """Aguarda healthchecks HTTP em vez de usar um atraso fixo no startup."""

    deadline = time.monotonic() + timeout_seconds
    pendentes = dict(endpoints)
    ultimos_erros = {}
    while pendentes and time.monotonic() < deadline:
        for description, process in processes:
            if process.poll() is not None:
                raise RuntimeError(f"{description} encerrou durante o startup")

        for description, url in tuple(pendentes.items()):
            try:
                with urllib.request.urlopen(url, timeout=request_timeout_seconds) as response:
                    if response.status == 200:
                        logger.info("✅ Healthcheck aprovado: %s", description)
                        del pendentes[description]
            except urllib.error.HTTPError as error:
                try:
                    detalhe = error.read().decode("utf-8", errors="replace")
                except OSError:
                    detalhe = str(error)
                ultimos_erros[description] = f"HTTP {error.code}: {detalhe}"
            except (urllib.error.URLError, TimeoutError, ConnectionRefusedError, OSError) as error:
                ultimos_erros[description] = str(error)

        if pendentes:
            time.sleep(interval_seconds)

    if pendentes:
        diagnosticos = "; ".join(
            f"{description}: {ultimos_erros.get(description, 'sem resposta')}"
            for description in pendentes
        )
        raise RuntimeError(f"Serviços não ficaram prontos: {diagnosticos}")


def aguardar_frontend(processes, url=FRONTEND_DEV_URL, timeout_seconds=120, interval_seconds=1.5):
    """Aguarda o Vite subir o dev server no localhost."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        for description, process in processes:
            if process.poll() is not None:
                raise RuntimeError(f"{description} encerrou durante o startup")

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GridScope-Startup"})
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status < 500:
                    logger.info("✅ Frontend (Vite) respondendo em %s", url)
                    return True
        except (urllib.error.URLError, TimeoutError, ConnectionRefusedError, OSError):
            pass

        time.sleep(interval_seconds)

    logger.warning("⚠️ Frontend não respondeu dentro do timeout (%ss). Pode estar ainda compilando - veja logs/frontend_dev.log", timeout_seconds)
    return False


def verificar_banco_populado():
    from sqlalchemy import text
    from src.database import get_engine

    engine = None
    try:
        engine = get_engine()

        with engine.connect() as conn:
            tabelas = ['subestacoes', 'consumidores', 'cache_mercado']

            for tabela in tabelas:
                try:
                    result = conn.execute(text(f'SELECT COUNT(*) FROM "{tabela}"'))
                    count = result.scalar()

                    if count == 0:
                        return False
                except Exception as error:
                    logger.warning("Falha ao verificar tabela %s: %s", tabela, error)
                    return False

            return True

    except Exception as error:
        logger.warning("⚠️ Erro ao verificar banco: %s", error)
        return False
    finally:
        if engine is not None:
            engine.dispose()


def run_pipeline():
    from src.config import DATA_INGEST_ON_STARTUP, TRAIN_MODEL_ON_STARTUP

    banco_populado = verificar_banco_populado()

    precisa_ingestao = DATA_INGEST_ON_STARTUP or not banco_populado
    if precisa_ingestao:
        logger.info("📦 Executando ingestão da fonte de dados configurada...")
        if not run_module("src.etl.pipeline", "Ingestão e publicação do snapshot"):
            logger.error("🛑 Falha crítica na ingestão. Abortando inicialização.")
            sys.exit(1)
    else:
        logger.info("✅ Banco de dados já populado. Pulando ingestão no boot.")

    if TRAIN_MODEL_ON_STARTUP or not modelo_artefato_compativel():
        logger.info("🧠 Treinando IA (Duck Curve)... Isso pode levar alguns segundos.")
        if not run_script(os.path.join(DIR_SRC, "ai", "train_model.py"), "Treinamento Modelo Random Forest"):
            sys.exit(1)
    else:
        logger.info("✅ Modelo de IA existente. Pulando treinamento no boot.")


if __name__ == "__main__":
    logger.info("--- ⚡ INICIANDO SISTEMA GRIDSCOPE⚡ ---")
    services = []

    try:
        run_pipeline()

        logger.info("--- INICIANDO SERVIÇOS ---")

        services.append(
            ("API Principal", start_api_process("src.api:app", 8000, "api_service.log", "API Principal"))
        )
        services.append(
            ("API Inteligência Artificial", start_api_process("src.ai.ai_service:app", 8001, "api_ai.log", "API Inteligência Artificial"))
        )
        services.append(
            ("API Chat IA (Gemini)", start_api_process("src.ai.chat_service:app", 8002, "api_chat.log", "API Chat IA (Gemini)"))
        )
        services.append(
            ("Frontend (Vite)", start_frontend_process("frontend_dev.log", "Frontend (Vite)"))
        )

        aguardar_servicos(
            services,
            API_STARTUP_ENDPOINTS,
            timeout_seconds=150,
        )

        aguardar_frontend(services, timeout_seconds=120)

        logger.info("\n✅ SISTEMA COMPLETO ONLINE!")
        logger.info("🌐 Frontend: http://localhost:5173")
        logger.info("🔌 API Principal: http://localhost:8000/docs")
        logger.info("🧠 API IA: http://localhost:8001/docs")
        logger.info("💬 API Chat: http://localhost:8002/docs")
        logger.info("📝 Logs detalhados disponíveis na pasta /logs")
        logger.info("Press Ctrl+C para encerrar tudo.\n")

        while True:
            time.sleep(2)
            encerrado = next(
                ((description, process) for description, process in services if process.poll() is not None),
                None,
            )
            if encerrado:
                logger.error("⚠️ %s encerrou inesperadamente; consulte o log do serviço", encerrado[0])
                break
    except KeyboardInterrupt:
        logger.info("\n🛑 Encerrando serviços...")
    finally:
        _stop_api_processes(services)
        logger.info("GridScope encerrado com sucesso.")
