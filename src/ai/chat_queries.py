import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import carregar_cache_mercado
from typing import List, Dict, Any, Optional


def _carregar_dados_filtrados() -> List[Dict[str, Any]]:
    dados = carregar_cache_mercado()
    return [
        d for d in dados 
        if d.get('metricas_rede', {}).get('total_clientes', 0) > 10
        and d.get('metricas_rede', {}).get('consumo_anual_mwh', 0) > 0
    ]

def obter_ranking_subestacoes(
    criterio: str = "consumo", 
    ordem: str = "desc", 
    limite: int = 5
) -> List[Dict[str, Any]]:
    try:
        dados = _carregar_dados_filtrados()
        
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
        dados = _carregar_dados_filtrados()
        
        niveis_ordem = {"NORMAL": 0, "MÉDIO": 1, "CRÍTICO": 2}
        min_nivel = niveis_ordem.get(nivel_minimo.upper(), 1)
        
        resultados = []
        for item in dados:
            nivel = item.get('metricas_rede', {}).get('nivel_criticidade_gd', 'NORMAL')
            
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
    try:
        dados_cache = _carregar_dados_filtrados()
        
        # Todas as estatísticas vêm do cache (já filtrado por cidade)
        total_subs = len(dados_cache)
        total_cons = sum(d.get('metricas_rede', {}).get('total_clientes', 0) for d in dados_cache)
        total_gd = sum(d.get('geracao_distribuida', {}).get('total_unidades', 0) for d in dados_cache)
        pot_total = sum(d.get('geracao_distribuida', {}).get('potencia_total_kw', 0) for d in dados_cache)
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


def buscar_subestacao_detalhes(nome: str) -> Optional[Dict[str, Any]]:
    try:
        dados = _carregar_dados_filtrados()
        
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
        dados = _carregar_dados_filtrados()
        
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


def comparar_subestacoes(nomes: List[str]) -> List[Dict[str, Any]]:
    """Compara 2 ou mais subestações lado a lado"""
    try:
        dados = _carregar_dados_filtrados()
        
        resultados = []
        for nome_busca in nomes:
            nome_upper = nome_busca.upper()
            for item in dados:
                nome_sub = item.get('subestacao', '').upper()
                if nome_upper in nome_sub:
                    resultados.append({
                        "nome": item.get('subestacao', 'Desconhecida'),
                        "consumo_anual_mwh": float(item.get('metricas_rede', {}).get('consumo_anual_mwh', 0)),
                        "total_clientes": int(item.get('metricas_rede', {}).get('total_clientes', 0)),
                        "potencia_gd_kw": float(item.get('geracao_distribuida', {}).get('potencia_total_kw', 0)),
                        "unidades_gd": int(item.get('geracao_distribuida', {}).get('total_unidades', 0)),
                        "nivel_criticidade": item.get('metricas_rede', {}).get('nivel_criticidade_gd', 'NORMAL'),
                        "consumo_medio_kwh_cliente": float(item.get('metricas_rede', {}).get('consumo_anual_mwh', 0) * 1000 / max(item.get('metricas_rede', {}).get('total_clientes', 1), 1))
                    })
                    break
        
        return resultados
        
    except Exception as e:
        return [{"erro": f"Erro ao comparar subestações: {str(e)}"}]


def obter_insights_inteligentes() -> Dict[str, Any]:
    """Retorna insights automáticos baseados na análise dos dados"""
    try:
        dados = _carregar_dados_filtrados()
        
        insights = {
            "alertas": [],
            "oportunidades": [],
            "destaques": []
        }
        
        subs_alto_gd = [d for d in dados if d.get('metricas_rede', {}).get('nivel_criticidade_gd') == 'CRÍTICO']
        if subs_alto_gd:
            insights["alertas"].append({
                "tipo": "CRITICIDADE_GD",
                "mensagem": f"{len(subs_alto_gd)} subestação(ões) com criticidade ALTA de GD",
                "subestacoes": [s.get('subestacao') for s in subs_alto_gd[:3]]
            })
        
        dados_sorted = sorted(dados, key=lambda x: x.get('metricas_rede', {}).get('consumo_anual_mwh', 0), reverse=True)
        if dados_sorted:
            top_consumo = dados_sorted[0]
            insights["destaques"].append({
                "tipo": "MAIOR_CONSUMO",
                "subestacao": top_consumo.get('subestacao'),
                "valor": float(top_consumo.get('metricas_rede', {}).get('consumo_anual_mwh', 0)),
                "percentual_do_total": round(top_consumo.get('metricas_rede', {}).get('consumo_anual_mwh', 0) / sum(d.get('metricas_rede', {}).get('consumo_anual_mwh', 0) for d in dados) * 100, 1) if dados else 0
            })
        
        total_clientes = sum(d.get('metricas_rede', {}).get('total_clientes', 0) for d in dados)
        total_unidades_gd = sum(d.get('geracao_distribuida', {}).get('total_unidades', 0) for d in dados)
        if total_clientes > 0:
            taxa_penetracao = (total_unidades_gd / total_clientes) * 100
            insights["destaques"].append({
                "tipo": "PENETRACAO_GD",
                "taxa_percentual": round(taxa_penetracao, 2),
                "total_unidades_gd": int(total_unidades_gd),
                "total_clientes": int(total_clientes)
            })
        
        subs_baixo_gd = [d for d in dados if d.get('geracao_distribuida', {}).get('total_unidades', 0) < 10 and d.get('metricas_rede', {}).get('total_clientes', 0) > 1000]
        if subs_baixo_gd:
            insights["oportunidades"].append({
                "tipo": "EXPANSAO_GD",
                "mensagem": f"{len(subs_baixo_gd)} subestação(ões) com potencial para expansão de GD",
                "subestacoes": [s.get('subestacao') for s in subs_baixo_gd[:3]]
            })
        
        return insights
        
    except Exception as e:
        return {"erro": f"Erro ao gerar insights: {str(e)}"}


def analisar_territorio(nome_subestacao: str) -> Dict[str, Any]:
    """Analisa o território Voronoi de uma subestação"""
    try:
        from database import carregar_voronoi, carregar_subestacoes
        import geopandas as gpd
        
        gdf_voronoi = carregar_voronoi()
        gdf_subs = carregar_subestacoes()
        
        nome_upper = nome_subestacao.upper()
        subestacao = None
        for idx, row in gdf_subs.iterrows():
            if nome_upper in str(row.get('NOM', '')).upper():
                subestacao = row
                cod_id = row.get('COD_ID')
                break
        
        if subestacao is None:
            return {"erro": "Subestação não encontrada"}
        
        territorio = gdf_voronoi[gdf_voronoi['COD_ID'] == cod_id]
        
        if territorio.empty:
            return {"erro": "Território não encontrado para esta subestação"}
        
        territorio_proj = territorio.to_crs('EPSG:31984')
        area_m2 = territorio_proj.geometry.area.iloc[0]
        area_km2 = area_m2 / 1_000_000
        
        dados_mercado = _carregar_dados_filtrados()
        dados_sub = None
        for item in dados_mercado:
            if item.get('id_tecnico') == str(cod_id):
                dados_sub = item
                break
        
        resultado = {
            "nome": subestacao.get('NOM', 'Desconhecida'),
            "area_km2": round(area_km2, 2),
            "total_clientes": int(dados_sub.get('metricas_rede', {}).get('total_clientes', 0)) if dados_sub else 0,
            "consumo_anual_mwh": float(dados_sub.get('metricas_rede', {}).get('consumo_anual_mwh', 0)) if dados_sub else 0
        }
        
        if area_km2 > 0:
            resultado["densidade_clientes_km2"] = round(resultado["total_clientes"] / area_km2, 1)
            resultado["consumo_mwh_km2"] = round(resultado["consumo_anual_mwh"] / area_km2, 1)
        
        return resultado
        
    except Exception as e:
        return {"erro": f"Erro ao analisar território: {str(e)}"}


def buscar_subestacoes_proximas(nome_referencia: str, limite: int = 5) -> List[Dict[str, Any]]:
    """Encontra subestações próximas a uma subestação de referência"""
    try:
        from database import carregar_subestacoes
        import numpy as np
        
        gdf_subs = carregar_subestacoes()
        
        nome_upper = nome_referencia.upper()
        sub_ref = None
        for idx, row in gdf_subs.iterrows():
            if nome_upper in str(row.get('NOM', '')).upper():
                sub_ref = row
                break
        
        if sub_ref is None:
            return [{"erro": "Subestação de referência não encontrada"}]
        
        gdf_proj = gdf_subs.to_crs('EPSG:31984')
        ponto_ref = gdf_proj[gdf_proj['COD_ID'] == sub_ref['COD_ID']].geometry.iloc[0]
        
        distancias = []
        for idx, row in gdf_proj.iterrows():
            if row['COD_ID'] != sub_ref['COD_ID']:
                dist_m = ponto_ref.distance(row.geometry)
                dist_km = dist_m / 1000
                distancias.append({
                    "nome": row.get('NOM', 'Desconhecida'),
                    "distancia_km": round(dist_km, 2)
                })
        
        distancias.sort(key=lambda x: x['distancia_km'])
        
        return distancias[:limite]
        
    except Exception as e:
        return [{"erro": f"Erro ao buscar subestações próximas: {str(e)}"}]


def obter_metricas_performance() -> Dict[str, Any]:
    """Retorna métricas de performance do sistema elétrico"""
    try:
        dados = _carregar_dados_filtrados()
        
        total_clientes = sum(d.get('metricas_rede', {}).get('total_clientes', 0) for d in dados)
        total_consumo = sum(d.get('metricas_rede', {}).get('consumo_anual_mwh', 0) for d in dados)
        total_unidades_gd = sum(d.get('geracao_distribuida', {}).get('total_unidades', 0) for d in dados)
        total_potencia_gd = sum(d.get('geracao_distribuida', {}).get('potencia_total_kw', 0) for d in dados)
        
        consumo_medio_anual = (total_consumo * 1000 / total_clientes) if total_clientes > 0 else 0  # kWh
        consumo_medio_mensal = consumo_medio_anual / 12
        
        taxa_penetracao_gd = (total_unidades_gd / total_clientes * 100) if total_clientes > 0 else 0
        
        consumo_por_classe = {}
        for item in dados:
            perfil = item.get('perfil_consumo', {})
            for classe, info in perfil.items():
                if classe not in consumo_por_classe:
                    consumo_por_classe[classe] = {"consumo": 0, "clientes": 0}
                consumo_por_classe[classe]["consumo"] += info.get('consumo_anual_mwh', 0)
                consumo_por_classe[classe]["clientes"] += info.get('qtd_clientes', 0)
        
        for classe, dados_classe in consumo_por_classe.items():
            if dados_classe["clientes"] > 0:
                consumo_por_classe[classe]["consumo_medio_kwh_ano"] = round(
                    dados_classe["consumo"] * 1000 / dados_classe["clientes"], 1
                )
        
        return {
            "total_subestacoes": len(dados),
            "total_clientes": int(total_clientes),
            "consumo_total_anual_mwh": round(total_consumo, 2),
            "consumo_medio_cliente_kwh_mes": round(consumo_medio_mensal, 1),
            "taxa_penetracao_gd_percentual": round(taxa_penetracao_gd, 2),
            "total_unidades_gd": int(total_unidades_gd),
            "potencia_total_gd_mw": round(total_potencia_gd / 1000, 2),
            "consumo_por_classe": consumo_por_classe
        }
        
    except Exception as e:
        return {"erro": f"Erro ao calcular métricas: {str(e)}"}


# ==================== FUNÇÕES DE GRÁFICOS ====================

import plotly.graph_objects as go
import plotly.express as px


def gerar_grafico_consumo_por_classe() -> Dict[str, Any]:
    """Gera gráfico de pizza do consumo por classe"""
    try:
        dados = obter_distribuicao_consumo_por_classe()
        
        if "erro" in dados:
            return {"erro": dados["erro"]}
        
        dist = dados.get("distribuicao", {})
        
        labels = []
        values = []
        for classe, info in dist.items():
            labels.append(classe)
            values.append(info["consumo_anual_mwh"])
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.3,
            textinfo='label+percent',
            marker=dict(colors=px.colors.qualitative.Set3)
        )])
        
        fig.update_layout(
            title="Distribuição de Consumo por Classe",
            height=500
        )
        
        return {
            "tipo": "plotly",
            "spec": fig.to_json(),
            "titulo": "Consumo por Classe de Consumidor"
        }
    except Exception as e:
        return {"erro": f"Erro ao gerar gráfico: {str(e)}"}


def gerar_grafico_ranking_subestacoes(
    criterio: str = "consumo",
    limite: int = 10
) -> Dict[str, Any]:
    """Gera gráfico de barras do ranking de subestações"""
    try:
        dados = obter_ranking_subestacoes(criterio, "desc", limite)
        
        if not dados or "erro" in dados[0]:
            return {"erro": "Erro ao buscar dados"}
        
        nomes = [d["nome"].split("(ID:")[0].strip() for d in dados]
        valores = [d["valor"] for d in dados]
        unidade = dados[0]["unidade"]
        
        fig = go.Figure(data=[go.Bar(
            x=valores,
            y=nomes,
            orientation='h',
            marker=dict(
                color=valores,
                colorscale='Viridis',
                showscale=True
            ),
            text=[f"{v:.1f} {unidade}" for v in valores],
            textposition='auto'
        )])
        
        titulo = f"Top {limite} Subestações - {'Consumo' if criterio == 'consumo' else 'Geração Distribuída'}"
        
        fig.update_layout(
            title=titulo,
            xaxis_title=f"Valor ({unidade})",
            yaxis_title="Subestação",
            height=max(400, limite * 40),
            yaxis={'categoryorder':'total ascending'}
        )
        
        return {
            "tipo": "plotly",
            "spec": fig.to_json(),
            "titulo": titulo
        }
    except Exception as e:
        return {"erro": f"Erro ao gerar gráfico: {str(e)}"}


def gerar_grafico_distribuicao_gd() -> Dict[str, Any]:
    """Gera gráfico de barras da distribuição de GD por subestação"""
    try:
        dados = _carregar_dados_filtrados()
        
        # Ordena por potência GD
        dados_sorted = sorted(
            dados,
            key=lambda x: x.get('geracao_distribuida', {}).get('potencia_total_kw', 0),
            reverse=True
        )[:15]  # Top 15
        
        nomes = [d['subestacao'].split("(ID:")[0].strip() for d in dados_sorted]
        potencias = [d.get('geracao_distribuida', {}).get('potencia_total_kw', 0) for d in dados_sorted]
        qtds = [d.get('geracao_distribuida', {}).get('total_unidades', 0) for d in dados_sorted]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='Potência (kW)',
            x=nomes,
            y=potencias,
            yaxis='y',
            marker=dict(color='#1f77b4')
        ))
        
        fig.add_trace(go.Scatter(
            name='Nº Unidades',
            x=nomes,
            y=qtds,
            yaxis='y2',
            mode='lines+markers',
            marker=dict(color='#ff7f0e', size=8),
            line=dict(width=2)
        ))
        
        fig.update_layout(
            title='Distribuição de Geração Distribuída (Top 15 Subestações)',
            xaxis=dict(title='Subestação', tickangle=-45),
            yaxis=dict(title='Potência Total (kW)', side='left'),
            yaxis2=dict(title='Quantidade de Unidades', overlaying='y', side='right'),
            height=600,
            hovermode='x unified',
            legend=dict(x=0.01, y=0.99)
        )
        
        return {
            "tipo": "plotly",
            "spec": fig.to_json(),
            "titulo": "Distribuição de GD por Subestação"
        }
    except Exception as e:
        return {"erro": f"Erro ao gerar gráfico: {str(e)}"}


def gerar_grafico_criticidade_vs_consumo() -> Dict[str, Any]:
    """Gera scatter plot de criticidade GD vs consumo"""
    try:
        dados = _carregar_dados_filtrados()
        
        consumos = []
        gd_percentuais = []
        nomes = []
        cores = []
        tamanhos = []
        
        mapa_cores = {"NORMAL": "green", "MÉDIO": "orange", "CRÍTICO": "red"}
        
        for d in dados:
            total_cli = d.get('metricas_rede', {}).get('total_clientes', 0)
            if total_cli < 100:
                continue
                
            consumo = d.get('metricas_rede', {}).get('consumo_anual_mwh', 0)
            gd_unidades = d.get('geracao_distribuida', {}).get('total_unidades', 0)
            nivel = d.get('metricas_rede', {}).get('nivel_criticidade_gd', 'NORMAL')
            
            if total_cli > 0:
                gd_pct = (gd_unidades / total_cli) * 100
            else:
                gd_pct = 0
            
            consumos.append(consumo)
            gd_percentuais.append(gd_pct)
            nomes.append(d['subestacao'].split("(ID:")[0].strip())
            cores.append(mapa_cores.get(nivel, "gray"))
            tamanhos.append(total_cli / 50)
        
        fig = go.Figure(data=go.Scatter(
            x=consumos,
            y=gd_percentuais,
            mode='markers',
            marker=dict(
                size=tamanhos,
                color=cores,
                opacity=0.6,
                line=dict(width=1, color='white')
            ),
            text=nomes,
            hovertemplate='<b>%{text}</b><br>Consumo: %{x:.1f} MWh/ano<br>GD: %{y:.2f}% dos clientes<extra></extra>'
        ))
        
        fig.update_layout(
            title='Criticidade de GD vs Consumo (tamanho = nº clientes)',
            xaxis_title='Consumo Anual (MWh)',
            yaxis_title='Penetração de GD (% clientes com GD)',
            height=600,
            hovermode='closest'
        )
        
        # Adiciona linhas de referência
        fig.add_hline(y=10, line_dash="dash", line_color="orange", annotation_text="Médio risco (10%)")
        fig.add_hline(y=20, line_dash="dash", line_color="red", annotation_text="Alto risco (20%)")
        
        return {
            "tipo": "plotly",
            "spec": fig.to_json(),
            "titulo": "Análise de Criticidade de GD"
        }
    except Exception as e:
        return {"erro": f"Erro ao gerar gráfico: {str(e)}"}



FUNCOES_DISPONIVEIS = {
    "obter_ranking_subestacoes": obter_ranking_subestacoes,
    "obter_subestacoes_em_risco": obter_subestacoes_em_risco,
    "obter_estatisticas_gerais": obter_estatisticas_gerais,
    "buscar_subestacao_detalhes": buscar_subestacao_detalhes,
    "obter_distribuicao_consumo_por_classe": obter_distribuicao_consumo_por_classe,
    # Novas funções avançadas
    "comparar_subestacoes": comparar_subestacoes,
    "obter_insights_inteligentes": obter_insights_inteligentes,
    "analisar_territorio": analisar_territorio,
    "buscar_subestacoes_proximas": buscar_subestacoes_proximas,
    "obter_metricas_performance": obter_metricas_performance,
    # Funções de gráficos
    "gerar_grafico_consumo_por_classe": gerar_grafico_consumo_por_classe,
    "gerar_grafico_ranking_subestacoes": gerar_grafico_ranking_subestacoes,
    "gerar_grafico_distribuicao_gd": gerar_grafico_distribuicao_gd,
    "gerar_grafico_criticidade_vs_consumo": gerar_grafico_criticidade_vs_consumo
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
