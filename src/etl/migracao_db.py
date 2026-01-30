import os
import sys
import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text
import logging
from tqdm import tqdm
import time
import io
import csv

# Adiciona diretório pai
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- CONFIGURAÇÕES ---
NOME_GDB = os.getenv("FILE_GDB", "Energisa_SE_6587_2024-12-31_V11_20250902-1412.gdb")
DIR_DADOS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dados")
PATH_GDB = os.path.join(DIR_DADOS, NOME_GDB)

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MigracaoTurbo")

CAMADAS_ALVO = {
    'UNTRMT': 'transformadores',
    'UCBT_tab': 'consumidores',
    'UGBT_tab': 'geracao_gd',
    'SUB': 'subestacoes',
    'SSDMT': 'rede_mt'
}

def get_database_engine():
    # Use psycopg2 explicitamente
    db_url = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:1234@localhost:5433/gridscope_local")
    return create_engine(db_url, isolation_level="AUTOCOMMIT")

def limpar_dados_antigos(engine):
    logger.info("🧼 Iniciando limpeza de tabelas...")
    tabelas = list(CAMADAS_ALVO.values()) + ['territorios_voronoi', 'cache_mercado']
    
    with engine.connect() as conn:
        for tabela in tabelas:
            try:
                conn.execute(text(f"TRUNCATE TABLE {tabela} CASCADE"))
                logger.info(f"   🗑️  {tabela} limpa.")
            except Exception as e:
                if "does not exist" in str(e):
                    pass
                else:
                    logger.warning(f"   ⚠️  Erro ao limpar {tabela}: {e}")

def fast_pg_insert(df, table_name, engine):
    """
    Usa o comando COPY do PostgreSQL para inserir dados muito rápido (Bulk Insert)
    Ideal para tabelas grandes (> 100k linhas) sem geometria.
    """
    # 1. Cria a tabela vazia (para garantir que o schema exista com os tipos certos)
    df.head(0).to_sql(table_name, engine, if_exists='replace', index=False)

    # 2. Conecta via driver bruto (psycopg2)
    raw_conn = engine.raw_connection()
    cur = raw_conn.cursor()
    
    # 3. Prepara o buffer em memória (CSV virtual)
    output = io.StringIO()
    # Exporta para CSV separado por '|' (menos comum que vírgula em dados de texto)
    # quoting=csv.QUOTE_MINIMAL garante que strings com '|' sejam tratadas
    df.to_csv(output, sep='|', header=False, index=False, quoting=csv.QUOTE_MINIMAL)
    output.seek(0)

    # 4. Executa o COPY FROM STDIN
    try:
        columns = ', '.join([f'"{c}"' for c in df.columns])
        # copy_expert permite usar sintaxe SQL completa do COPY
        sql = f"COPY {table_name} ({columns}) FROM STDIN WITH (FORMAT CSV, DELIMITER '|', NULL '')"
        cur.copy_expert(sql, output)
        raw_conn.commit()
    except Exception as e:
        raw_conn.rollback()
        raise e
    finally:
        cur.close()
        raw_conn.close()

def processar_camada(engine, layer_gdb, nome_tabela):
    start_time = time.time()
    
    try:
        # 1. LEITURA OTIMIZADA
        logger.info(f"📖 Lendo {layer_gdb} via Pyogrio...")
        
        try:
            gdf = gpd.read_file(
                PATH_GDB, 
                layer=layer_gdb, 
                engine="pyogrio", 
                use_arrow=True
            )
        except Exception as e_ogrio:
            logger.warning(f"⚠️ Falha Pyogrio ({e_ogrio}). Fallback lento...")
            gdf = gpd.read_file(PATH_GDB, layer=layer_gdb)

        if gdf.empty:
            logger.warning(f"⚠️ Camada {layer_gdb} vazia.")
            return

        total_rows = len(gdf)
        logger.info(f"   ↳ Carregado {total_rows} registros em {time.time() - start_time:.2f}s")

        # 2. PROCESSAMENTO E GRAVAÇÃO
        e_espacial = 'geometry' in gdf.columns and gdf.geometry.notnull().any()

        if e_espacial:
            # --- FLUXO ESPACIAL (PostGIS) ---
            if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
            
            logger.info(f"   🗺️  Gravando MAPA em '{nome_tabela}' (PostGIS)...")
            
            # PostGIS ainda usa insert normal, mas com chunk ajustado
            gdf.to_postgis(
                nome_tabela, 
                engine, 
                if_exists='replace', 
                index=False, 
                chunksize=5000
            )
        else:
            # --- FLUXO TABULAR (Alta Performance) ---
            if 'geometry' in gdf.columns:
                gdf = gdf.drop(columns=['geometry'])
            
            logger.info(f"   🚀 Gravando TABELA em '{nome_tabela}' (Modo COPY)...")
            
            # AQUI ESTÁ A MUDANÇA: Usamos a função fast_pg_insert
            fast_pg_insert(gdf, nome_tabela, engine)

        logger.info(f"✅ {nome_tabela} concluída! Tempo total: {time.time() - start_time:.2f}s")

    except Exception as e:
        logger.error(f"❌ Erro crítico na camada {layer_gdb}: {e}")
        # Não damos raise aqui para não parar as outras camadas, apenas logamos
        pass 

def migrar_gdb_para_sql():
    if not os.path.exists(PATH_GDB):
        logger.error(f"Arquivo GDB não encontrado: {PATH_GDB}")
        return

    engine = get_database_engine()
    
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"❌ Erro conexão banco: {e}")
        return

    limpar_dados_antigos(engine)

    logger.info("🚀 INICIANDO MIGRAÇÃO (COPY MODE)")
    logger.info(f"📂 Arquivo: {os.path.basename(PATH_GDB)}")

    with tqdm(total=len(CAMADAS_ALVO), desc="Progresso Total") as pbar:
        for layer_gdb, nome_tabela in CAMADAS_ALVO.items():
            processar_camada(engine, layer_gdb, nome_tabela)
            pbar.update(1)

    logger.info("🏁 MIGRAÇÃO FINALIZADA")

if __name__ == "__main__":
    migrar_gdb_para_sql()