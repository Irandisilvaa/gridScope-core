import os
import sys
import geopandas as gpd
import pandas as pd
import logging

# Configuração simples
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("Inspecao")

# --- CONFIGURAÇÃO DO ARQUIVO ---
# Ajuste o nome se necessário
NOME_GDB = os.getenv("FILE_GDB", "Energisa_SE_6587_2024-12-31_V11_20250902-1412.gdb")
DIR_DADOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dados")
# Se o script estiver na raiz, ajuste o path:
if not os.path.exists(DIR_DADOS):
    DIR_DADOS = os.path.join(os.getcwd(), "dados")

PATH_GDB = os.path.join(DIR_DADOS, NOME_GDB)

def inspecionar_tabela(layer_name):
    logger.info(f"\n🔍 Inspecionando camada: {layer_name}")
    try:
        # Lê apenas as primeiras 5 linhas para ver as colunas (rápido)
        gdf = gpd.read_file(PATH_GDB, layer=layer_name, rows=5)
        cols = list(gdf.columns)
        logger.info(f"   📋 Colunas encontradas ({len(cols)}):")
        logger.info(f"   {', '.join(cols)}")
        return gdf, cols
    except Exception as e:
        logger.error(f"   ❌ Erro ao ler {layer_name}: {e}")
        return None, []

def teste_de_conexoes():
    if not os.path.exists(PATH_GDB):
        logger.error(f"GDB não encontrado em: {PATH_GDB}")
        return

    logger.info(f"📂 Abrindo GDB: {NOME_GDB}")

    # 1. Carregar Amostras
    # SUBESTAÇÕES
    df_sub, cols_sub = inspecionar_tabela("SUB")
    
    # TRANSFORMADORES
    df_trafo, cols_trafo = inspecionar_tabela("UNTRMT")
    
    # CONSUMIDORES
    df_cons, cols_cons = inspecionar_tabela("UCBT_tab") # Tente UCBT ou UCBT_tab
    if df_cons is None:
         df_cons, cols_cons = inspecionar_tabela("UCBT")

    # 2. TENTATIVA DE DETECTAR CHAVES (Lógica de Sherlock Holmes)
    logger.info("\n🕵️‍♂️  ANÁLISE DE VÍNCULOS (TOPOLOGIA)")
    
    # A) Vínculo Transformador -> Subestação (ou Circuito)
    # Procuramos colunas comuns ou colunas que indicam posse (SUB, CTMT, PAC)
    possiveis_chaves_trafo = [c for c in cols_trafo if 'SUB' in c or 'CTMT' in c or 'ALIM' in c]
    logger.info(f"   ⚡ Chaves prováveis no TRAFO para subir a rede: {possiveis_chaves_trafo}")

    # B) Vínculo Consumidor -> Transformador
    # Procuramos colunas como UNI_TR_MT, TRANSF, MT, TRAFO
    possiveis_chaves_cons = [c for c in cols_cons if 'TR' in c or 'MT' in c or 'UNI' in c]
    logger.info(f"   🏠 Chaves prováveis no CONSUMIDOR para o Trafo: {possiveis_chaves_cons}")

    # 3. TESTE REAL DE JOIN (Lendo mais dados para ter certeza)
    logger.info("\n🧪 Testando integridade dos dados (Amostragem Real)...")
    
    try:
        # Ler IDs dos Trafos
        # Vamos assumir os nomes padrão ANEEL, mas o script acima nos ajuda a confirmar
        # Tente identificar o nome exato baseado no print acima se falhar
        
        # Exemplo padrão ANEEL: 
        # TRAFO: COD_ID (Identificador) e CTMT (Circuito) ou SUB (Subestação)
        # CONSUMIDOR: UNI_TR_MT (Liga com COD_ID do Trafo)
        
        # Vamos tentar ler um pedaço maior para ver se bate
        logger.info("   Lendo dados para Cruzamento...")
        gdf_trafo_full = gpd.read_file(PATH_GDB, layer="UNTRMT", columns=['COD_ID', 'CTMT', 'SUB'], engine="pyogrio")
        gdf_cons_full = gpd.read_file(PATH_GDB, layer="UCBT_tab", columns=['UNI_TR_MT'], engine="pyogrio")
        
        # Limpeza rápida
        total_cons = len(gdf_cons_full)
        cons_com_trafo = gdf_cons_full[gdf_cons_full['UNI_TR_MT'].isin(gdf_trafo_full['COD_ID'])]
        total_ligados = len(cons_com_trafo)
        
        porcentagem = (total_ligados / total_cons) * 100
        
        logger.info(f"   📊 RESULTADO DO MATCH:")
        logger.info(f"   Total Consumidores: {total_cons}")
        logger.info(f"   Consumidores com Trafo encontrado na base: {total_ligados}")
        logger.info(f"   Taxa de Sucesso Topológico: {porcentagem:.2f}%")
        
        if porcentagem > 90:
            logger.info("   ✅ SUCESSO! A topologia está perfeita. Podemos usar a Opção 1.")
            logger.info("   🚀 Próximo passo: Agrupar pontos por SUB e gerar Concave Hull.")
        else:
            logger.warning("   ⚠️ A taxa de conexão está baixa. Verifique se os nomes das colunas de ligação estão certos.")

    except Exception as e:
        logger.error(f"   ❌ Não foi possível realizar o teste de cruzamento automático: {e}")
        logger.info("   DICA: Olhe os nomes das colunas impressos acima e ajuste o script.")

if __name__ == "__main__":
    teste_de_conexoes()