import pandas as pd
import geopandas as gpd
import os
import sys
import random

# --- CONFIGURAÇÃO DE CAMINHOS ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Tenta pegar o caminho do config, senão define manual
try:
    from config import PATH_GDB
except ImportError:
    # Ajuste aqui se necessário
    PATH_GDB = r"C:\Users\irand\Documents\gridscope-core\data\raw\SE_2023.gdb"

# --- SINÔNIMOS DE COLUNAS ---
COLUNAS_POSSIVEIS = {
    "NOME_SUB": ["NOM", "NOME", "DS_SUB", "NO_SUB", "NOME_SUBESTACAO", "DS_NOME"],
    "ID_SUB": ["COD_ID", "ID", "PAC", "CD_SUB", "SUB_ID", "CODIGO", "UNI_TR_S"],
    "TABELA_SUB": ["SUB", "SSD", "SUBESTACAO", "LOC_SUB"], 
    "TABELA_CONSUMIDOR": ["UCBT_tab", "UCBT", "CONSUMIDOR", "CLIENTE"] 
}

def encontrar_coluna(df, lista_candidatas):
    """ Retorna o nome real da coluna no DF se bater com a lista. """
    cols_existentes = [c.upper() for c in df.columns]
    for tentativa in lista_candidatas:
        if tentativa in cols_existentes:
            return df.columns[cols_existentes.index(tentativa)]
    return None

def buscar_dados_reais_para_ia(nome_subestacao):
    print(f"\n🤖 IA (ETL V3 - Sherlock): Buscando '{nome_subestacao}'...")
    
    if not os.path.exists(PATH_GDB):
        print(f"❌ GDB não encontrado: {PATH_GDB}")
        return {"erro": "GDB 404"}

    try:
        # --- 1. LOCALIZAR SUBESTAÇÃO ---
        layer_sub = None
        for layer in COLUNAS_POSSIVEIS["TABELA_SUB"]:
            try:
                gpd.read_file(PATH_GDB, layer=layer, rows=1)
                layer_sub = layer
                break
            except: continue
        
        if not layer_sub:
            print("❌ Camada de Subestação não encontrada.")
            return gerar_estimativa_fallback(nome_subestacao)

        gdf_sub = gpd.read_file(PATH_GDB, layer=layer_sub, engine='pyogrio')
        
        col_nome = encontrar_coluna(gdf_sub, COLUNAS_POSSIVEIS["NOME_SUB"])
        col_id = encontrar_coluna(gdf_sub, COLUNAS_POSSIVEIS["ID_SUB"])
        
        if not col_nome or not col_id:
            print(f"❌ Colunas de Nome/ID não identificadas em {layer_sub}.")
            return gerar_estimativa_fallback(nome_subestacao)

        # Filtra pelo nome
        filtro = gdf_sub[col_nome].astype(str).str.upper().str.contains(nome_subestacao.upper(), na=False)
        sub_encontrada = gdf_sub[filtro]
        
        if sub_encontrada.empty:
            print(f"⚠️ Subestação '{nome_subestacao}' não encontrada.")
            return gerar_estimativa_fallback(nome_subestacao)
            
        id_sub_alvo = sub_encontrada.iloc[0][col_id]
        nome_real = sub_encontrada.iloc[0][col_nome]
        print(f"✅ Subestação: {nome_real} | ID Alvo: {id_sub_alvo}")

        # --- 2. LOCALIZAR CONSUMIDORES (MODO SHERLOCK) ---
        layer_uc = "UCBT_tab" # Tenta o padrão primeiro
        try:
            gpd.read_file(PATH_GDB, layer=layer_uc, rows=1, ignore_geometry=True)
        except:
            # Tenta variações se falhar
            for l in COLUNAS_POSSIVEIS["TABELA_CONSUMIDOR"]:
                try: 
                    gpd.read_file(PATH_GDB, layer=l, rows=1, ignore_geometry=True)
                    layer_uc = l
                    break
                except: continue

        print(f"⏳ Varrendo tabela '{layer_uc}' em busca do ID {id_sub_alvo}...")
        df_uc = gpd.read_file(PATH_GDB, layer=layer_uc, engine='pyogrio', ignore_geometry=True)
        
        # --- A MÁGICA: Busca em TODAS as colunas ---
        clientes = pd.DataFrame()
        coluna_de_ligacao_encontrada = None

        # Converte ID alvo para string para garantir comparação
        id_str = str(id_sub_alvo).strip()
        id_num = id_sub_alvo if isinstance(id_sub_alvo, (int, float)) else None

        # Prioriza colunas óbvias para ganhar tempo
        cols_prioridade = ["SUB", "CTMT", "UNI_TR_S", "CONJUNTO", "PAC"]
        cols_teste = [c for c in df_uc.columns if c in cols_prioridade] + [c for c in df_uc.columns if c not in cols_prioridade]

        for col in cols_teste:
            # Pega uma amostra para ver se tem chance de ser essa coluna
            # Se a coluna só tem texto "A, B, C", não adianta comparar com ID numérico
            if df_uc[col].dtype == 'object':
                match = df_uc[df_uc[col].astype(str).str.strip() == id_str]
            else:
                if id_num is not None:
                    match = df_uc[df_uc[col] == id_num]
                else:
                    continue # Coluna numérica vs ID string -> pula

            if not match.empty:
                print(f"🎉 ENCONTRADO! A coluna de ligação é: '{col}'")
                clientes = match
                coluna_de_ligacao_encontrada = col
                break
        
        if clientes.empty:
            print(f"⚠️ Varri todas as {len(df_uc.columns)} colunas e nenhuma possui o ID {id_sub_alvo}.")
            print("   -> Tente verificar se o ID na tabela SUB é o mesmo usado na UCBT.")
            return gerar_estimativa_fallback(nome_real)

        print(f"✅ Sucesso: {len(clientes)} clientes vinculados encontrados.")

        # --- 3. SOMAR ENERGIA ---
        perfil_mensal = {}
        total_anual = 0.0
        
        for i in range(1, 13):
            mes_str = f"{i:02d}"
            possiveis_cols = [f"ENE_{mes_str}", f"ENE{mes_str}", f"CONS_{mes_str}"]
            
            col_energia = encontrar_coluna(clientes, possiveis_cols)
            
            if col_energia:
                soma = clientes[col_energia].fillna(0).sum() / 1000.0 # MWh
                perfil_mensal[i] = soma
                total_anual += soma
            else:
                perfil_mensal[i] = 0.0

        print(f"📊 Volume Total Extraído: {total_anual:.2f} MWh")

        return {
            "subestacao": nome_real,
            "total_clientes": len(clientes),
            "consumo_anual_mwh": float(total_anual),
            "consumo_mensal": perfil_mensal,
            "origem": "BDGD (Real)"
        }

    except Exception as e:
        print(f"❌ Erro ETL: {e}")
        return gerar_estimativa_fallback(nome_subestacao)

def gerar_estimativa_fallback(nome_sub):
    print("🔄 [FALLBACK] Usando dados estatísticos...")
    clientes_est = 5000
    base_kwh = 180.0
    perfil = {}
    total = 0.0
    for i in range(1, 13):
        val = (clientes_est * base_kwh) / 1000.0
        perfil[i] = val
        total += val
        
    return {
        "subestacao": nome_sub,
        "consumo_anual_mwh": total,
        "consumo_mensal": perfil,
        "origem": "Estimado",
        "alerta": True
    }