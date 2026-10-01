import subprocess
import sys
import time
import os
import logging
import urllib.error
import urllib.request
from datetime import datetime

DIR_RAIZ = os.path.dirname(os.path.abspath(__file__))
DIR_SRC = os.path.join(DIR_RAIZ, "src")
DIR_LOGS = os.path.join(DIR_RAIZ, "logs")

CAMINHO_MODELO_PKL = os.path.join(DIR_SRC, "ai", "modelo_consumo.pkl")

import sys
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

    log_file = open(os.path.join(DIR_LOGS, log_filename), "w", encoding="utf-8")

    import platform
    workers = "1" if platform.system() == "Windows" else "4"

    env_vars = get_env_with_src()
    env_vars["PYTHONIOENCODING"] = "utf-8"

    try:
        return subprocess.Popen(
            [PYTHON_EXEC, "-m", "uvicorn", module_name, "--host", "0.0.0.0", "--port", str(port), "--workers", workers],
            cwd=DIR_RAIZ,
            env=env_vars,
            stdout=log_file,
            stderr=log_file
        )
    finally:
        log_file.close()


def _stop_api_processes(processes):
    for description, process in processes:
        if process.poll() is None:
            logger.info("🛑 Encerrando %s...", description)
            process.terminate()

    for description, process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("⚠️ %s não encerrou no prazo; forçando parada", description)
            process.kill()
            process.wait(timeout=5)


def aguardar_servicos(processes, endpoints, timeout_seconds=60, interval_seconds=1):
    """Aguarda healthchecks HTTP em vez de usar um atraso fixo no startup."""

    deadline = time.monotonic() + timeout_seconds
    pendentes = dict(endpoints)
    while pendentes and time.monotonic() < deadline:
        for description, process in processes:
            if process.poll() is not None:
                raise RuntimeError(f"{description} encerrou durante o startup")

        for description, url in tuple(pendentes.items()):
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    if response.status == 200:
                        logger.info("✅ Healthcheck aprovado: %s", description)
                        del pendentes[description]
            except urllib.error.URLError:
                continue

        if pendentes:
            time.sleep(interval_seconds)

    if pendentes:
        raise RuntimeError(f"Serviços não ficaram prontos: {', '.join(pendentes)}")


def verificar_banco_populado():
    from sqlalchemy import text
    from src.database import get_engine

    engine = None
    try:
        # Reutiliza o search_path/schema validado pela DAL; a engine anterior
        # sempre consultava public, mesmo quando DATABASE_SCHEMA era outro.
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
    logger.info("--- ⚡ INICIANDO SISTEMA GRIDSCOPE (HACKATHON MODE) ⚡ ---")
    api_processes = []

    try:
        run_pipeline()

        logger.info("--- INICIANDO SERVIDORES ---")

        api_processes.append(
            ("API Principal", start_api_process("src.api:app", 8000, "api_service.log", "API Principal"))
        )
        api_processes.append(
            ("API Inteligência Artificial", start_api_process("src.ai.ai_service:app", 8001, "api_ai.log", "API Inteligência Artificial"))
        )
        api_processes.append(
            ("API Chat IA (Gemini)", start_api_process("src.ai.chat_service:app", 8002, "api_chat.log", "API Chat IA (Gemini)"))
        )

        aguardar_servicos(
            api_processes,
            API_STARTUP_ENDPOINTS,
        )

        logger.info("\n✅ APIs ONLINE — frontend Vite/PWA deve ser servido separadamente")
        logger.info("📝 Logs detalhados disponíveis na pasta /logs")
        logger.info("Press Ctrl+C para encerrar tudo.\n")

        while True:
            time.sleep(2)
            encerrado = next(
                ((description, process) for description, process in api_processes if process.poll() is not None),
                None,
            )
            if encerrado:
                logger.error("⚠️ %s encerrou inesperadamente; consulte o log do serviço", encerrado[0])
                break
    except KeyboardInterrupt:
        logger.info("\n🛑 Encerrando serviços...")
    finally:
        _stop_api_processes(api_processes)
        logger.info("GridScope encerrado com sucesso.")
