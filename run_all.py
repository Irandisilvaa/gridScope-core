import subprocess
import sys
import time
import os
import logging
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

    processo = subprocess.Popen(
        [PYTHON_EXEC, "-m", "uvicorn", module_name, "--host", "0.0.0.0", "--port", str(port), "--workers", workers],
        cwd=DIR_RAIZ,
        env=env_vars,
        stdout=log_file,
        stderr=log_file
    )
    return processo


def verificar_banco_populado():
    from sqlalchemy import create_engine, text
    from src.config import DATABASE_URL
    
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            tabelas = ['subestacoes', 'consumidores', 'cache_mercado']
            
            for tabela in tabelas:
                try:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {tabela}"))
                    count = result.scalar()
                    
                    if count == 0:
                        return False  
                except:
                    return False  
            
            return True  
            
    except Exception as e:
        logger.warning(f"⚠️ Erro ao verificar banco: {e}")
        return False


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

    if TRAIN_MODEL_ON_STARTUP or not os.path.exists(CAMINHO_MODELO_PKL):
        logger.info("🧠 Treinando IA (Duck Curve)... Isso pode levar alguns segundos.")
        if not run_script(os.path.join(DIR_SRC, "ai", "train_model.py"), "Treinamento Modelo Random Forest"):
            sys.exit(1)
    else:
        logger.info("✅ Modelo de IA existente. Pulando treinamento no boot.")

if __name__ == "__main__":
    logger.info("--- ⚡ INICIANDO SISTEMA GRIDSCOPE (HACKATHON MODE) ⚡ ---")

    try:
        run_pipeline()

        logger.info("--- INICIANDO SERVIDORES ---")

        api_proc = start_api_process("src.api:app", 8000, "api_service.log", "API Principal")

        api_ai_proc = start_api_process("src.ai.ai_service:app", 8001, "api_ai.log", "API Inteligência Artificial")

        api_chat_proc = start_api_process("src.ai.chat_service:app", 8002, "api_chat.log", "API Chat IA (Gemini)")

        logger.info("⏳ Aguardando 12 segundos para carga completa dos modelos de IA...")
        time.sleep(12)

        logger.info("\n✅ APIs ONLINE — frontend Vite/PWA deve ser servido separadamente")
        logger.info("📝 Logs detalhados disponíveis na pasta /logs")
        logger.info("Press Ctrl+C para encerrar tudo.\n")

        while True:
            time.sleep(2)
            if api_proc.poll() is not None:
                logger.error("⚠️ CRITICAL: API Principal (8000) morreu! Verifique logs/api_service.log")
                break
            if api_ai_proc.poll() is not None:
                logger.error(
                    "⚠️ CRITICAL: API IA (8001) morreu! O Duck Curve não vai funcionar. Verifique logs/api_ai.log")
                break
            if api_chat_proc.poll() is not None:
                logger.warning("⚠️ API Chat (8002) morreu! O Chat IA não vai funcionar. Verifique logs/api_chat.log")
                break
    except KeyboardInterrupt:
        logger.info("\n🛑 Encerrando serviços...")
        try:
            api_proc.terminate()
            api_ai_proc.terminate()
            api_chat_proc.terminate()
        except:
            pass
        logger.info("GridScope encerrado com sucesso.")
