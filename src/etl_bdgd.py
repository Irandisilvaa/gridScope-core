import geopandas as gpd
import os
import sys

# --- CONFIGURAÇÃO ---
# Nome EXATO da pasta .gdb que você descompactou dentro de 'dados'
NOME_PASTA_GDB = "Energisa_SE_6587_2023-12-31_V11_20250701-0833.gdb"

def carregar_subestacoes():
    """
    Lê o arquivo GDB da Energisa localizado na pasta '../dados'
    e retorna um GeoDataFrame limpo contendo as subestações.
    """
    # 1. Montar o caminho dinâmico (funciona no seu PC e no Servidor)
    dir_atual = os.path.dirname(os.path.abspath(__file__))
    caminho_gdb = os.path.join(dir_atual, "..", "dados", NOME_PASTA_GDB)
    
    # 2. Verificação de Segurança
    if not os.path.exists(caminho_gdb):
        print("\n❌ ERRO CRÍTICO: Pasta de dados não encontrada!")
        print(f"   O sistema procurou em: {caminho_gdb}")
        print("   -> Verifique se o nome da pasta .gdb está correto no script 'etl_bdgd.py'")
        print("   -> Verifique se a pasta 'dados' está na raiz do projeto.")
        sys.exit(1)

    print(f"📂 Carregando base oficial da ANEEL: {NOME_PASTA_GDB} ...")
    
    try:
        # 3. Ler a camada 'SUB' (Subestações)
        # O GeoPandas detecta automaticamente se é FileGDB
        gdf = gpd.read_file(caminho_gdb, layer='SUB')
        
        # 4. Selecionar apenas colunas essenciais
        # COD_ID: Identificador único
        # NOM: Nome da Subestação
        # geometry: O polígono do terreno
        colunas_desejadas = ['COD_ID', 'NOM', 'geometry']
        
        # Filtra apenas as colunas que realmente existem no arquivo
        cols_finais = [c for c in colunas_desejadas if c in gdf.columns]
        gdf_limpo = gdf[cols_finais]
        
        # Remover subestações sem nome ou inválidas (limpeza básica)
        gdf_limpo = gdf_limpo.dropna(subset=['NOM'])
        
        print(f"✅ Dados carregados com sucesso! Total de Subestações: {len(gdf_limpo)}")
        return gdf_limpo

    except Exception as e:
        print(f"\n❌ Erro ao ler o arquivo GDB. Detalhes: {e}")
        print("Dica: Verifique se você instalou as bibliotecas (pip install geopandas pyogrio)")
        sys.exit(1)

# Bloco de teste (roda se você executar 'python src/etl_bdgd.py')
if __name__ == "__main__":
    df = carregar_subestacoes()
    if df is not None:
        print("\n--- Amostra dos Dados ---")
        print(df.head())