import geopandas as gpd
import pandas as pd
from typing import Dict, Any

from database import carregar_subestacoes, carregar_consumidores
from utils import carregar_dados_cache

def buscar_dados_reais_para_ia(nome_subestacao: str) -> Dict[str, Any]:
    """
    Busca dados reais de consumo para a IA treinar/prever.
    Agora 100% conectado ao PostgreSQL.
    """
    print(f"\n🤖 IA: Analisando DNA da subestação '{nome_subestacao}'...")
    
    try:
        gdf_subs = carregar_subestacoes()
        
        filtro = gdf_subs['NOME'].str.upper().str.contains(nome_subestacao.strip().upper(), na=False)
        
        if filtro.sum() == 0:
            print(f"❌ Subestação '{nome_subestacao}' não encontrada no Banco.")
            return gerar_fallback(nome_subestacao)
            
        dados_sub = gdf_subs[filtro].iloc[0]
        id_sub = str(dados_sub['COD_ID'])
        nome_real = dados_sub['NOME']
        
        print(f"   📍 Alvo Identificado: {nome_real} (ID: {id_sub})")

        print(f"   🔍 Consultando Perfil de Mercado no Cache...")
        _, cache = carregar_dados_cache()
        
        dados_cache_sub = next((item for item in cache if str(item.get('id_tecnico')) == id_sub), None)
        
        if dados_cache_sub:
             print("   ✅ Dados encontrados no Cache de Mercado!")
             
             perfil_consumo = dados_cache_sub.get('perfil_consumo', {})
             
             total_mwh = sum(cls['consumo_anual_mwh'] for cls in perfil_consumo.values())
             perfil_mix = {"residencial": 0.0, "comercial": 0.0, "industrial": 0.0, "rural": 0.0}
             
             if total_mwh > 0:
                for cls, dados in perfil_consumo.items():
                    pct = dados['consumo_anual_mwh'] / total_mwh
                    cls_upper = cls.upper()
                    if 'RESIDENCIAL' in cls_upper: perfil_mix['residencial'] += pct
                    elif 'COMERCIAL' in cls_upper or 'PODER' in cls_upper: perfil_mix['comercial'] += pct
                    elif 'INDUSTRIAL' in cls_upper: perfil_mix['industrial'] += pct
                    elif 'RURAL' in cls_upper: perfil_mix['rural'] += pct
                    else: perfil_mix['comercial'] += pct

        else:
            print("   ⚠️ Dados não estão no cache. Consultando banco raw...")
        
        print("   🔍 Buscando sazonalidade detalhada no PostgreSQL...")
        cols_ene = [f'ENE_{i:02d}' for i in range(1, 13)]
        cols_classe = ['CLA_CONS', 'UNI_TR_MT']
        
        from database import get_engine
        engine = get_engine()
        
        sql = f"""
            SELECT 
                c."CLAS_SUB",
                SUM(c."ENE_01") as "ENE_01", SUM(c."ENE_02") as "ENE_02", SUM(c."ENE_03") as "ENE_03",
                SUM(c."ENE_04") as "ENE_04", SUM(c."ENE_05") as "ENE_05", SUM(c."ENE_06") as "ENE_06",
                SUM(c."ENE_07") as "ENE_07", SUM(c."ENE_08") as "ENE_08", SUM(c."ENE_09") as "ENE_09",
                SUM(c."ENE_10") as "ENE_10", SUM(c."ENE_11") as "ENE_11", SUM(c."ENE_12") as "ENE_12"
            FROM consumidores c
            JOIN transformadores t ON c."UNI_TR_MT" = t."COD_ID"
            WHERE t."SUB" = '{id_sub}'
            GROUP BY c."CLAS_SUB"
        """
        
        df_agregado = pd.read_sql(sql, engine)
        engine.dispose()
        
        if df_agregado.empty:
            print("⚠️ Aviso: Nenhum consumidor encontrado no Banco para esta SUB.")
            return gerar_fallback(nome_real)

        total_energia_ano = df_agregado[cols_ene].sum().sum()
        
        perfil_mix_banco = {"residencial": 0.0, "comercial": 0.0, "industrial": 0.0, "rural": 0.0}
        
        for idx, row in df_agregado.iterrows():
            try:
                val = row['CLAS_SUB']
                if pd.isna(val):
                    classe_cod = '0'
                else:
                    classe_cod = str(int(float(val))) if isinstance(val, (int, float)) else str(val)
            except:
                classe_cod = str(row['CLAS_SUB'])
            
            cons_ano = row[cols_ene].sum()
            pct = cons_ano / total_energia_ano if total_energia_ano > 0 else 0
            
            if classe_cod.startswith('1'): cat = 'residencial'
            elif classe_cod.startswith('2'): cat = 'comercial'
            elif classe_cod.startswith('3'): cat = 'industrial'
            elif classe_cod.startswith('4'): cat = 'rural'
            else: cat = 'comercial'
            
            perfil_mix_banco[cat] += pct

        print(f"   🧬 DNA Calculado (Banco): Ind={perfil_mix_banco['industrial']:.1%} | Res={perfil_mix_banco['residencial']:.1%} | Com={perfil_mix_banco['comercial']:.1%}")

        perfil_mensal = {}
        for i in range(1, 13):
            col = f"ENE_{i:02d}"
            val_mwh = df_agregado[col].sum() / 1000.0 
            perfil_mensal[i] = val_mwh

        return {
            "subestacao": nome_real,
            "id": id_sub,
            "consumo_mensal": perfil_mensal,
            "dna_perfil": perfil_mix_banco,
            "origem": "PostgreSQL Real"
        }

    except Exception as e:
        print(f"❌ Erro Crítico no ETL Banco: {e}")
        import traceback
        traceback.print_exc()
        return gerar_fallback(nome_subestacao)

def gerar_fallback(nome):
    """Retorna um perfil padrão para não travar o gráfico"""
    print(f"   ⚠️ Usando Perfil Genérico (Fallback) para {nome}")
    return {
        "subestacao": nome, 
        "id": "FALLBACK",
        "consumo_mensal": {i: 500 for i in range(1,13)},
        "dna_perfil": {"residencial": 0.6, "comercial": 0.3, "industrial": 0.1, "rural": 0.0},
        "alerta": True
    }