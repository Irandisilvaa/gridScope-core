import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_engine, carregar_cache_mercado
from sqlalchemy import text
from typing import List, Dict, Any, Optional


def obter_ranking_subestacoes(
    criterio: str = "consumo", 
    ordem: str = "desc", 
    limite: int = 5
) -> List[Dict[str, Any]]:
    try:
        dados = carregar_cache_mercado()
        
        resultados = []
        for item in dados:
            nome = item.get('subestacao', 'Desconhecida')
            clientes = item.get('metricas_rede', {}).get('total_clientes', 0)
            
            if criterio.lower() == "consumo":
                valor = item.get('metricas_rede', {}).get('consumo_anual_mwh', 0)
                unidade = "MWh/ano"
            else:
                valor = item.get('geracao_distribuida', {}).get('potencia_total_kw', 0)
                unidade = "kW"
            
            resultados.append({
                "nome": nome,
                "valor": float(valor),
                "unidade": unidade,
                "total_clientes": int(clientes)
            })
        
        resultados.sort(key=lambda x: x['valor'], reverse=(ordem.lower() == "desc"))
        
        return resultados[:limite]
        
    except Exception as e:
        return [{"erro": f"Erro ao buscar ranking: {str(e)}"}]


def obter_subestacoes_em_risco(nivel_minimo: str = "MEDIO") -> List[Dict[str, Any]]:
    try:
        dados = carregar_cache_mercado()
        
        niveis_ordem = {"BAIXO": 0, "MEDIO": 1, "ALTO": 2}
        min_nivel = niveis_ordem.get(nivel_minimo.upper(), 1)
        
        resultados = []
        for item in dados:
            nivel = item.get('metricas_rede', {}).get('nivel_criticidade_gd', 'BAIXO')
            
            if niveis_ordem.get(nivel, 0) >= min_nivel:
                resultados.append({
                    "nome": item.get('subestacao', 'Desconhecida'),
                    "nivel_risco": nivel,
                    "potencia_gd_kw": float(item.get('geracao_distribuida', {}).get('potencia_total_kw', 0)),
                    "num_unidades_gd": int(item.get('geracao_distribuida', {}).get('total_unidades', 0)),
                    "total_clientes": int(item.get('metricas_rede', {}).get('total_clientes', 0))
                })
        
        resultados.sort(key=lambda x: x['potencia_gd_kw'], reverse=True)
        
        return resultados
        
    except Exception as e:
        return [{"erro": f"Erro ao buscar subestações em risco: {str(e)}"}]


def obter_estatisticas_gerais() -> Dict[str, Any]:
    engine = get_engine()
    
    try:
        with engine.connect() as conn:
            total_subs = conn.execute(text("SELECT COUNT(*) FROM subestacoes")).scalar()
            
            total_cons = conn.execute(text("SELECT COUNT(*) FROM consumidores")).scalar()
            
            total_gd = conn.execute(text("SELECT COUNT(*) FROM geracao_gd")).scalar()
            
            pot_total = conn.execute(text('SELECT SUM("POT_INST") FROM geracao_gd')).scalar() or 0
        
        dados_cache = carregar_cache_mercado()
        consumo_total = sum(d.get('metricas_rede', {}).get('consumo_anual_mwh', 0) for d in dados_cache)
        
        return {
            "total_subestacoes": int(total_subs),
            "total_consumidores": int(total_cons),
            "total_unidades_gd": int(total_gd),
            "potencia_total_gd_kw": float(pot_total),
            "consumo_total_anual_mwh": float(consumo_total)
        }
        
    except Exception as e:
        return {"erro": f"Erro ao buscar estatísticas: {str(e)}"}
        
    finally:
        engine.dispose()


def buscar_subestacao_detalhes(nome: str) -> Optional[Dict[str, Any]]:
    try:
        dados = carregar_cache_mercado()
        
        nome_upper = nome.upper()
        
        for item in dados:
            nome_sub = item.get('subestacao', '').upper()
            if nome_upper in nome_sub:
                item_clean = {k: v for k, v in item.items() if k != 'geometry'}
                return item_clean
        
        return None
        
    except Exception as e:
        return {"erro": f"Erro ao buscar subestação: {str(e)}"}


def obter_distribuicao_consumo_por_classe() -> Dict[str, Any]:
    try:
        dados = carregar_cache_mercado()
        
        classes = {}
        consumo_total_geral = 0
        
        for item in dados:
            perfil = item.get('perfil_consumo', {})
            for classe, info in perfil.items():
                consumo_mwh = info.get('consumo_anual_mwh', 0)
                qtd_clientes = info.get('qtd_clientes', 0)
                
                if classe not in classes:
                    classes[classe] = {"consumo_mwh": 0, "qtd_clientes": 0}
                
                classes[classe]["consumo_mwh"] += consumo_mwh
                classes[classe]["qtd_clientes"] += qtd_clientes
                consumo_total_geral += consumo_mwh
        
        resultado = {}
        for classe, dados in classes.items():
            pct = (dados["consumo_mwh"] / consumo_total_geral * 100) if consumo_total_geral > 0 else 0
            resultado[classe] = {
                "consumo_anual_mwh": float(dados["consumo_mwh"]),
                "percentual": float(pct),
                "qtd_clientes": int(dados["qtd_clientes"])
            }
        
        return {
            "distribuicao": resultado,
            "consumo_total_mwh": float(consumo_total_geral)
        }
        
    except Exception as e:
        return {"erro": f"Erro ao calcular distribuição: {str(e)}"}


FUNCOES_DISPONIVEIS = {
    "obter_ranking_subestacoes": obter_ranking_subestacoes,
    "obter_subestacoes_em_risco": obter_subestacoes_em_risco,
    "obter_estatisticas_gerais": obter_estatisticas_gerais,
    "buscar_subestacao_detalhes": buscar_subestacao_detalhes,
    "obter_distribuicao_consumo_por_classe": obter_distribuicao_consumo_por_classe
}


if __name__ == "__main__":
    # Testes
    print("🧪 Testando funções de consulta ao banco...\n")
    
    print("1️⃣ Ranking de consumo (top 3):")
    ranking = obter_ranking_subestacoes("consumo", "desc", 3)
    for r in ranking:
        print(f"   {r['nome']}: {r['valor']:.2f} {r['unidade']}")
    
    print("\n2️⃣ Subestações em risco (nível MEDIO ou superior):")
    riscos = obter_subestacoes_em_risco("MEDIO")
    for r in riscos[:3]:
        print(f"   {r['nome']}: {r['nivel_risco']} - {r['potencia_gd_kw']:.2f} kW")
    
    print("\n3️⃣ Estatísticas gerais:")
    stats = obter_estatisticas_gerais()
    print(f"   Subestações: {stats['total_subestacoes']}")
    print(f"   Consumidores: {stats['total_consumidores']}")
    print(f"   Unidades GD: {stats['total_unidades_gd']}")
    
    print("\n4️⃣ Distribuição por classe:")
    dist = obter_distribuicao_consumo_por_classe()
    for classe, dados in dist.get('distribuicao', {}).items():
        print(f"   {classe}: {dados['percentual']:.1f}% ({dados['consumo_anual_mwh']:.2f} MWh)")
    
    print("\n✅ Testes concluídos!")
