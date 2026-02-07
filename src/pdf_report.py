"""
Módulo de Geração de Relatórios - GridScope
Centraliza lógica de exportação CSV e PDF com filtros dinâmicos
"""
import os
import sys
import io
import base64
import logging
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_engine, carregar_cache_mercado, carregar_voronoi
from jinja2 import Environment, FileSystemLoader

import google.generativeai as genai
from config import CHAT_API_KEY, CHAT_MODEL, GEMINI_API_KEYS, GROQ_API_KEY

# Groq client for PDF diagnostics 
try:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
    if groq_client:
        print("🚀 Groq configurado para diagnósticos PDF")
except ImportError:
    groq_client = None
    print("⚠️ Biblioteca Groq não instalada")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PDFReport")

# Multi-key rotation for PDF diagnostics
_current_key_index = 0
_exhausted_keys = set()

def _get_gemini_model():
    """Gets a Gemini model using the next available API key."""
    global _current_key_index, _exhausted_keys
    
    keys = GEMINI_API_KEYS if GEMINI_API_KEYS else ([CHAT_API_KEY] if CHAT_API_KEY else [])
    
    if not keys:
        return None
    
    # Find a non-exhausted key
    for i in range(len(keys)):
        idx = (_current_key_index + i) % len(keys)
        if idx not in _exhausted_keys:
            genai.configure(api_key=keys[idx])
            _current_key_index = idx
            return genai.GenerativeModel(CHAT_MODEL)
    
    # All keys exhausted, reset and try again
    _exhausted_keys.clear()
    _current_key_index = 0
    genai.configure(api_key=keys[0])
    return genai.GenerativeModel(CHAT_MODEL)

def _mark_key_exhausted():
    """Marks current key as exhausted and rotates to next."""
    global _current_key_index, _exhausted_keys
    _exhausted_keys.add(_current_key_index)
    keys = GEMINI_API_KEYS if GEMINI_API_KEYS else ([CHAT_API_KEY] if CHAT_API_KEY else [])
    _current_key_index = (_current_key_index + 1) % len(keys) if keys else 0
    logger.info(f"🔄 Rotacionando para chave Gemini {_current_key_index + 1}")


CLASSES_DISPONIVEIS = [
    "Residencial", "Comercial", "Industrial", 
    "Rural", "Poder Público"
]

METRICAS_DISPONIVEIS = {
    "clientes": "Nº de Clientes",
    "consumo_mwh": "Consumo (MWh)",
    "potencia_gd_kw": "Potência GD Instalada (kW)",
    "qtd_gd": "Qtd de GD"
}


def _format_number(value, decimals=0):
    """Formata número para padrão brasileiro."""
    if value is None:
        return "0"
    try:
        if decimals == 0:
            return f"{int(value):,}".replace(",", ".")
        else:
            return f"{float(value):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(value)


def _get_substation_area_km2(substation_id: str) -> str:
    """
    Calcula a área do território Voronoi da subestação em km².
    
    Args:
        substation_id: ID técnico da subestação
        
    Returns:
        Área formatada em km² ou "N/D" se não encontrada
    """
    try:
        gdf_voronoi = carregar_voronoi()
        
        if gdf_voronoi is None or gdf_voronoi.empty:
            return "N/D"
        
        # Filtra pelo COD_ID
        gdf_filtered = gdf_voronoi[gdf_voronoi['COD_ID'].astype(str) == str(substation_id)]
        
        if gdf_filtered.empty:
            return "N/D"
        
        gdf_proj = gdf_filtered.to_crs(epsg=31984)
        
        area_m2 = gdf_proj.geometry.area.iloc[0]
        area_km2 = area_m2 / 1_000_000
        
        return f"{area_km2:.2f}".replace(".", ",")
        
    except Exception as e:
        logger.warning(f"Erro ao calcular área: {e}")
        return "N/D"


def _get_neighborhood_from_coords(substation_id: str) -> str:
    """
    Obtém o bairro a partir das coordenadas do centróide da subestação.
    Usa geocodificação reversa com Nominatim via HTTP (sem dependência externa).
    
    Args:
        substation_id: ID técnico da subestação
        
    Returns:
        Nome do bairro ou "Aracaju - SE" como fallback
    """
    import requests
    
    try:
        gdf_voronoi = carregar_voronoi()
        
        if gdf_voronoi is None or gdf_voronoi.empty:
            return "Aracaju - SE"
        
        # Filtra pelo COD_ID
        gdf_filtered = gdf_voronoi[gdf_voronoi['COD_ID'].astype(str) == str(substation_id)]
        
        if gdf_filtered.empty:
            return "Aracaju - SE"
        
        # Obtém o centróide da geometria
        centroid = gdf_filtered.geometry.centroid.iloc[0]
        lat, lon = centroid.y, centroid.x
        
        # Faz geocodificação reversa via HTTP
        url = f"https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "addressdetails": 1,
            "accept-language": "pt-BR"
        }
        headers = {"User-Agent": "GridScope/5.0"}
        
        response = requests.get(url, params=params, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            address = data.get('address', {})
            
            # Tenta pegar o bairro (diferentes chaves possíveis)
            bairro = (
                address.get('suburb') or 
                address.get('neighbourhood') or 
                address.get('quarter') or
                address.get('city_district') or
                address.get('town') or
                address.get('city', 'Aracaju')
            )
            
            return f"{bairro} - SE"
        
        return "Aracaju - SE"
        
    except requests.exceptions.Timeout:
        logger.warning("Timeout na geocodificação reversa")
        return "Aracaju - SE"
    except Exception as e:
        logger.warning(f"Erro na geocodificação: {e}")
        return "Aracaju - SE"


def _generate_diagnostic_text(data: Dict) -> str:
    """
    Gera um diagnóstico textual usando Groq (primário) ou Gemini (fallback).
    Groq tem ~14.000 req/dia grátis vs 20 do Gemini, economizando cota do chat.
    """
    try:
        header = data.get('header', {})
        resumo = f"""
        Subestação: {header.get('substation_name')} ({header.get('feeder_id')})
        Bairro: {header.get('neighborhood')}
        Clientes: {header.get('total_clientes')}
        """
        
        # Adiciona dados específicos de GD para garantir que a IA veja
        gd_data = data.get('gd', [])
        try:
            total_potencia_gd = sum([float(str(item['potencia_kw']).replace('.', '').replace(',', '.')) for item in gd_data])
            total_qtd_gd = sum([int(str(item['qtd_clientes']).replace('.', '')) for item in gd_data])
        except Exception as e:
            logger.warning(f"Erro ao somar GD para prompt: {e}")
            total_potencia_gd = 0
            total_qtd_gd = 0
            
        resumo += f"\nDADOS GERAÇÃO DISTRIBUÍDA (GD):\n"
        resumo += f"- Potência Instalada Total: {total_potencia_gd:,.2f} kW\n"
        resumo += f"- Quantidade de Usinas: {total_qtd_gd}\n"
        
        resumo += "\nIndicadores Comparativos:\n"
        for ind in data.get('indicators', []):
            resumo += f"- {ind.get('indicador')}: {ind.get('subestacao')} (Média cidade: {ind.get('media_cidade')})\n"
            
        resumo += "\nRanking Criticidade:\n"
        for item in data.get('ranking', [])[:3]:
            resumo += f"- {item.get('nome')}: {item.get('criticidade')} (MMGD: {item.get('mmgd')})\n"

        prompt = f"""Você é um engenheiro elétrico especialista em redes de distribuição. Analise os dados abaixo e escreva um diagnóstico técnico de 4-5 linhas.

DADOS DA SUBESTAÇÃO:
{resumo}

INSTRUÇÕES:
- Compare os valores da subestação com a média da cidade
- Comente sobre a Geração Distribuída (GD) e seus impactos
- Indique se há riscos operacionais
- Escreva em português brasileiro
- Seja direto e técnico, sem saudações"""
        
        # GROQ (Primary) - ~14.000 req/dia grátis
        if groq_client:
            try:
                logger.info("🚀 Gerando diagnóstico com Groq...")
                response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",  # Modelo SOTA atual do Groq
                    messages=[
                        {"role": "system", "content": "Você é um engenheiro elétrico especialista em distribuição de energia. Responda sempre em português brasileiro de forma técnica e concisa."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.5,
                    max_tokens=400
                )
                if response.choices and response.choices[0].message.content:
                    logger.info("✅ Diagnóstico gerado com sucesso via Groq")
                    return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"⚠️ Groq falhou: {e}, tentando Gemini...")
        
        # GEMINI (Fallback)
        keys = GEMINI_API_KEYS if GEMINI_API_KEYS else ([CHAT_API_KEY] if CHAT_API_KEY else [])
        if keys:
            for attempt in range(len(keys)):
                try:
                    model = _get_gemini_model()
                    if model is None:
                        continue
                        
                    logger.info(f"🔄 Tentando Gemini (chave {attempt + 1})...")
                    response = model.generate_content(prompt)
                    
                    if response and response.text:
                        logger.info("✅ Diagnóstico gerado via Gemini (fallback)")
                        return response.text.strip()
                        
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        _mark_key_exhausted()
                        continue
                    raise
        
        return "⚠️ Não foi possível gerar diagnóstico (Groq e Gemini indisponíveis)."
        
    except Exception as e:
        logger.error(f"Erro ao gerar diagnóstico: {e}")
        return "Erro ao processar diagnóstico inteligente."



def get_bulk_data() -> pd.DataFrame:
    """
    Busca dados agregados de TODAS as subestações do cache.
    
    Returns:
        DataFrame com dados de todas as subestações
    """
    try:
        dados_cache = carregar_cache_mercado()
        
        if not dados_cache:
            logger.warning("Cache vazio, retornando dados mock")
            return _get_mock_data()
        
        registros = []
        
        for item in dados_cache:
            # Extrai informações básicas
            registro = {
                'subestacao': str(item.get('subestacao', '')).split(' (ID:')[0],
                'id': item.get('id_tecnico', ''),
                'regiao': item.get('regiao', 'Aracaju - SE'),
            }
            
            # Extrai métricas da rede
            metricas = item.get('metricas_rede', {})
            if isinstance(metricas, str):
                import ast
                try:
                    metricas = ast.literal_eval(metricas)
                except:
                    metricas = {}
            
            registro['total_clientes'] = metricas.get('total_clientes', 0)
            registro['consumo_total_mwh'] = metricas.get('consumo_anual_mwh', 0)
            
            # Extrai dados de GD
            gd = item.get('geracao_distribuida', {})
            if isinstance(gd, str):
                import ast
                try:
                    gd = ast.literal_eval(gd)
                except:
                    gd = {}
            
            registro['potencia_total_gd_kw'] = gd.get('potencia_total_kw', 0)
            registro['qtd_total_gd'] = gd.get('total_unidades', 0)
            
            # Extrai perfil de consumo por classe
            perfil = item.get('perfil_consumo', {})
            if isinstance(perfil, str):
                import ast
                try:
                    perfil = ast.literal_eval(perfil)
                except:
                    perfil = {}
            
            # Extrai detalhe de GD por classe
            detalhe_gd = gd.get('detalhe_por_classe', {})
            if isinstance(detalhe_gd, str):
                import ast
                try:
                    detalhe_gd = ast.literal_eval(detalhe_gd)
                except:
                    detalhe_gd = {}
            
            # Popula dados por classe
            for classe in CLASSES_DISPONIVEIS:
                # Dados do perfil de consumo
                dados_classe = perfil.get(classe, {})
                if isinstance(dados_classe, str):
                    import ast
                    try:
                        dados_classe = ast.literal_eval(dados_classe)
                    except:
                        dados_classe = {}
                
                # Processa dados de GD (suporta formato novo dict e antigo float)
                dados_gd_classe = detalhe_gd.get(classe, {})
                if isinstance(dados_gd_classe, (int, float)):
                    potencia = float(dados_gd_classe)
                    qtd = 0
                else:
                    potencia = float(dados_gd_classe.get('potencia_kw', 0))
                    qtd = int(dados_gd_classe.get('qtd', 0))

                registro[f'clientes_{classe}'] = dados_classe.get('qtd_clientes', 0)
                registro[f'consumo_mwh_{classe}'] = dados_classe.get('consumo_anual_mwh', 0)
                registro[f'potencia_gd_kw_{classe}'] = potencia
                registro[f'qtd_gd_{classe}'] = qtd
            
            registros.append(registro)
        
        df = pd.DataFrame(registros)
        logger.info(f"Carregados dados de {len(df)} subestações")
        return df
        
    except Exception as e:
        logger.error(f"Erro ao buscar dados bulk: {e}")
        return _get_mock_data()


def _get_mock_data() -> pd.DataFrame:
    """
    Retorna dados mock para desenvolvimento/testes.
    """
    import random
    
    subestacoes = [
        ("SE Farolândia", "12345", "Centro"),
        ("SE Siqueira Campos", "12346", "Centro"),
        ("SE Atalaia", "12347", "Sul"),
        ("SE Industrial", "12348", "Norte"),
        ("SE Jabotiana", "12349", "Oeste"),
    ]
    
    registros = []
    for nome, id_sub, regiao in subestacoes:
        registro = {
            'subestacao': nome,
            'id': id_sub,
            'regiao': regiao,
            'total_clientes': random.randint(1000, 10000),
            'consumo_total_mwh': random.uniform(1000, 50000),
            'potencia_total_gd_kw': random.uniform(100, 5000),
            'qtd_total_gd': random.randint(50, 500),
        }
        
        for classe in CLASSES_DISPONIVEIS:
            registro[f'clientes_{classe}'] = random.randint(0, 2000)
            registro[f'consumo_mwh_{classe}'] = random.uniform(0, 10000)
            registro[f'potencia_gd_kw_{classe}'] = random.uniform(0, 1000)
            registro[f'qtd_gd_{classe}'] = random.randint(0, 100)
        
        registros.append(registro)
    
    return pd.DataFrame(registros)


def filter_dataframe(
    df: pd.DataFrame,
    classes_selecionadas: List[str],
    metricas_selecionadas: List[str],
    tipo_valor: str = "absoluto"
) -> pd.DataFrame:
    """
    Aplica filtros dinâmicos ao DataFrame e converte para % se necessário.
    """
    # Colunas base sempre presentes
    colunas_base = ['subestacao', 'id', 'regiao']
    colunas_finais = colunas_base.copy()
    
    # Mapeia métricas para prefixos de coluna
    mapa_metricas = {
        "clientes": "clientes",
        "consumo_mwh": "consumo_mwh",
        "potencia_gd_kw": "potencia_gd_kw",
        "qtd_gd": "qtd_gd"
    }
    
    # Colunas de totais para cálculo de percentual
    mapa_totais = {
        "clientes": "total_clientes",
        "consumo_mwh": "consumo_total_mwh",
        "potencia_gd_kw": "potencia_total_gd_kw",
        "qtd_gd": "qtd_total_gd"
    }
    
    # Constrói lista de colunas dinâmicas
    for metrica in metricas_selecionadas:
        prefixo = mapa_metricas.get(metrica, metrica)
        for classe in classes_selecionadas:
            col_nome = f"{prefixo}_{classe}"
            if col_nome in df.columns:
                colunas_finais.append(col_nome)
    
    # Filtra DataFrame
    df_filtrado = df[colunas_finais].copy()
    
    # Converte para percentual se necessário
    if tipo_valor == "percentual":
        for metrica in metricas_selecionadas:
            prefixo = mapa_metricas.get(metrica, metrica)
            col_total = mapa_totais.get(metrica)
            
            if col_total and col_total in df.columns:
                for classe in classes_selecionadas:
                    col_nome = f"{prefixo}_{classe}"
                    if col_nome in df_filtrado.columns:
                        df_filtrado[col_nome] = (
                            df[col_nome] / df[col_total].replace(0, 1) * 100
                        ).round(2)
    
    # Renomeia colunas para formato amigável
    renomear = {
        'subestacao': 'Subestação',
        'id': 'ID',
        'regiao': 'Região'
    }
    
    for metrica in metricas_selecionadas:
        prefixo = mapa_metricas.get(metrica, metrica)
        sufixo = "(%)" if tipo_valor == "percentual" else ""
        
        for classe in classes_selecionadas:
            col_antiga = f"{prefixo}_{classe}"
            nome_metrica = METRICAS_DISPONIVEIS.get(metrica, metrica)
            col_nova = f"{classe}_{nome_metrica}{sufixo}".replace(" ", "_")
            renomear[col_antiga] = col_nova
    
    df_filtrado = df_filtrado.rename(columns=renomear)
    
    return df_filtrado


def generate_csv(
    df: pd.DataFrame,
    classes_selecionadas: List[str],
    metricas_selecionadas: List[str],
    tipo_valor: str = "absoluto"
) -> bytes:
    """
    Gera CSV filtrado em formato Tidy Data.
    """
    df_filtrado = filter_dataframe(df, classes_selecionadas, metricas_selecionadas, tipo_valor)
    
    data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    csv_buffer = io.StringIO()
    csv_buffer.write(f"# GridScope - Dataset Exportado em {data_geracao}\n")
    csv_buffer.write(f"# Classes: {', '.join(classes_selecionadas)}\n")
    csv_buffer.write(f"# Métricas: {', '.join(metricas_selecionadas)}\n")
    csv_buffer.write(f"# Tipo: {tipo_valor}\n")
    
    df_filtrado.to_csv(csv_buffer, index=False, encoding='utf-8')
    
    return csv_buffer.getvalue().encode('utf-8-sig')


def get_pdf_data(
    classes_selecionadas: List[str],
    metricas_selecionadas: List[str],
    tipo_valor: str = "absoluto",
    substation_id: Optional[str] = None
) -> Dict:
    """
    Prepara dados no formato esperado pelo template PDF.
    """
    df = get_bulk_data()
    
    # Totais da cidade
    total_clientes_cidade = int(df['total_clientes'].sum())
    total_consumo_cidade = float(df['consumo_total_mwh'].sum())
    total_potencia_gd_cidade = float(df['potencia_total_gd_kw'].sum())
    total_gd_cidade = int(df['qtd_total_gd'].sum())
    num_subestacoes = len(df)
    
    # Se especificou subestação, filtra
    if substation_id:
        df_sub = df[df['id'].astype(str) == str(substation_id)]
        if df_sub.empty:
            df_sub = df.iloc[[0]]  # Fallback para primeira
    else:
        df_sub = df.iloc[[0]]  # Usa primeira como referência
    
    row = df_sub.iloc[0]
    
    # Monta dados de consumo por classe (filtrado)
    consumption_data = []
    total_consumo_sub = float(row.get('consumo_total_mwh', 0) or 1)
    for classe in classes_selecionadas:
        consumo_classe = float(row.get(f'consumo_mwh_{classe}', 0) or 0)
        percentual = (consumo_classe / total_consumo_sub) * 100 if total_consumo_sub > 0 else 0
        consumption_data.append({
            'classe': classe,
            'energia_mwh': _format_number(consumo_classe, 0),
            'percentual': f"{percentual:.0f}"
        })
    
    # Monta dados de GD por classe (filtrado)
    gd_data = []
    for classe in classes_selecionadas:
        potencia_classe = float(row.get(f'potencia_gd_kw_{classe}', 0) or 0)
        qtd_classe = int(row.get(f'qtd_gd_{classe}', 0) or 0)
        gd_data.append({
            'classe': classe,
            'potencia_kw': _format_number(potencia_classe, 0),
            'qtd_clientes': _format_number(qtd_classe, 0)
        })
    
    # Monta indicadores comparativos
    indicators_data = []
    
    # Clientes - garante tipo numérico
    clientes_sub = float(row.get('total_clientes', 0) or 0)
    pct_clientes = (clientes_sub / total_clientes_cidade) * 100 if total_clientes_cidade > 0 else 0
    media_clientes = total_clientes_cidade / num_subestacoes if num_subestacoes > 0 else 0
    indicators_data.append({
        'categoria': 'Escala',
        'indicador': 'Total de Clientes',
        'subestacao': _format_number(clientes_sub, 0),
        'total_cidade': _format_number(total_clientes_cidade, 0),
        'pct_cidade': f"{pct_clientes:.1f}%",
        'media_cidade': _format_number(media_clientes, 0)
    })
    
    # Consumo - garante tipo numérico
    consumo_sub = float(row.get('consumo_total_mwh', 0) or 0)
    pct_consumo = (consumo_sub / total_consumo_cidade) * 100 if total_consumo_cidade > 0 else 0
    media_consumo = total_consumo_cidade / num_subestacoes if num_subestacoes > 0 else 0
    indicators_data.append({
        'categoria': 'Consumo',
        'indicador': 'Energia Consumida (MWh)',
        'subestacao': _format_number(consumo_sub, 0),
        'total_cidade': _format_number(total_consumo_cidade, 0),
        'pct_cidade': f"{pct_consumo:.1f}%",
        'media_cidade': _format_number(media_consumo, 0)
    })
    
    # GD - garante tipo numérico
    potencia_sub = float(row.get('potencia_total_gd_kw', 0) or 0)
    pct_potencia = (potencia_sub / total_potencia_gd_cidade) * 100 if total_potencia_gd_cidade > 0 else 0
    media_potencia = total_potencia_gd_cidade / num_subestacoes if num_subestacoes > 0 else 0
    indicators_data.append({
        'categoria': 'GD',
        'indicador': 'Potência Instalada (kW)',
        'subestacao': _format_number(potencia_sub, 0),
        'total_cidade': _format_number(total_potencia_gd_cidade, 0),
        'pct_cidade': f"{pct_potencia:.1f}%",
        'media_cidade': _format_number(media_potencia, 0)
    })
    
    # Qtd GD - garante tipo numérico
    qtd_gd_sub = float(row.get('qtd_total_gd', 0) or 0)
    pct_qtd = (qtd_gd_sub / total_gd_cidade) * 100 if total_gd_cidade > 0 else 0
    media_qtd = total_gd_cidade / num_subestacoes if num_subestacoes > 0 else 0
    indicators_data.append({
        'categoria': 'GD',
        'indicador': 'Quantidade de Unidades',
        'subestacao': _format_number(qtd_gd_sub, 0),
        'total_cidade': _format_number(total_gd_cidade, 0),
        'pct_cidade': f"{pct_qtd:.1f}%",
        'media_cidade': _format_number(media_qtd, 0)
    })
    
    # Monta ranking de criticidade
    ranking_data = []
    for idx, r in df.iterrows():
        # Garante tipos numéricos
        potencia = float(r.get('potencia_total_gd_kw', 0) or 0)
        consumo = float(r.get('consumo_total_mwh', 1) or 1)
        clientes = int(r.get('total_clientes', 0) or 0)
        qtd_gd = int(r.get('qtd_total_gd', 0) or 0)
        
        # Calcula demanda média e razão R (nova fórmula Irandi)
        demanda_media_kw = (consumo * 1000) / 8760 if consumo > 0 else 0
        razao_r = potencia / demanda_media_kw if demanda_media_kw > 0 else 0
        
        # Nova classificação: R < 0.4 = Normal, 0.4 <= R <= 1.0 = Médio, R > 1.0 = Crítico
        if razao_r < 0.4:
            criticidade = "NORMAL"
        elif razao_r <= 1.0:
            criticidade = "MÉDIO"
        else:
            criticidade = "CRÍTICO"
        
        if clientes <= 0 or not r['subestacao'] or str(r['subestacao']).strip() == 'SUB-' or not r['id']:
            continue

        ranking_data.append({
            'subestacao': r['subestacao'],
            'id': r['id'],
            'clientes': clientes,
            'potencia_gd': potencia,
            'qtd_gd': qtd_gd,
            'criticidade': criticidade,
            'razao_r': razao_r
        })
    
    # Ordena por criticidade
    ordem = {'CRÍTICO': 0, 'MÉDIO': 1, 'NORMAL': 2}
    ranking_data.sort(key=lambda x: (ordem.get(x['criticidade'], 3), -x['razao_r']))
    
    # Formata ranking
    ranking_formatted = []
    for i, item in enumerate(ranking_data[:10], 1):
        ranking_formatted.append({
            'posicao': i,
            'id': item['id'],
            'nome': item['subestacao'],
            'capacidade_mw': _format_number(item['potencia_gd'] / 1000, 2),
            'clientes': _format_number(item['clientes'], 0),
            'mmgd': _format_number(item['qtd_gd'], 0),
            'criticidade': item['criticidade']
        })
    
    return {
        'pdf_data': {
            'logo_b64': None,  # Pode ser preenchido com logo em base64
            'header': {
                'report_number': datetime.now().strftime("%Y%m%d%H%M%S"),
                'report_date': datetime.now().strftime("%d/%m/%Y"),
                'substation_name': row['subestacao'],
                'feeder_id': str(row['id']),
                'neighborhood': _get_neighborhood_from_coords(str(row['id'])),
                'covered_area_km2': _get_substation_area_km2(str(row['id'])),
                'total_clients': _format_number(row['total_clientes'], 0)
            },
            'filtros': {
                'classes': classes_selecionadas,
                'metricas': [METRICAS_DISPONIVEIS.get(m, m) for m in metricas_selecionadas],
                'tipo': 'Percentual (%)' if tipo_valor == 'percentual' else 'Valores Absolutos'
            },
            'consumption': consumption_data,
            'gd': gd_data,
            'indicators': indicators_data,
            'ranking': ranking_formatted,
            'diagnostico': None
        }
    }


def generate_pdf(
    classes_selecionadas: List[str],
    metricas_selecionadas: List[str],
    tipo_valor: str = "absoluto",
    substation_id: Optional[str] = None,
    secoes: Optional[List[str]] = None
) -> bytes:
    """
    Gera PDF do relatório usando xhtml2pdf (100% Python, sem deps externas).
    
    Args:
        classes_selecionadas: Classes de consumo a incluir
        metricas_selecionadas: Métricas a incluir
        tipo_valor: "absoluto" ou "percentual"
        substation_id: ID da subestação (opcional)
        secoes: Lista de seções a incluir: ["consumo", "gd", "comparacao", "ranking"]
    """
    import base64
    
    try:
        from xhtml2pdf import pisa
    except ImportError:
        logger.error("xhtml2pdf não instalado. Execute: pip install xhtml2pdf")
        raise ImportError("xhtml2pdf não está instalado. Adicione 'xhtml2pdf' ao requirements.txt")
    
    # Seções padrão
    if secoes is None:
        secoes = ["consumo", "gd", "comparacao", "ranking"]
    
    # Busca dados
    data_raw = get_pdf_data(classes_selecionadas, metricas_selecionadas, tipo_valor, substation_id)
    
    # Gera diagnóstico com IA (se configurada)
    if "diagnostico" in secoes:
        try:
            logger.info("Gerando diagnóstico com IA...")
            diagnostico_texto = _generate_diagnostic_text(data_raw['pdf_data'])
            data_raw['pdf_data']['diagnostico'] = diagnostico_texto
        except Exception as e:
            logger.warning(f"Falha ao gerar diagnóstico IA: {e}")
            data_raw['pdf_data']['diagnostico'] = "Diagnóstico indisponível no momento."
    
    data = data_raw
    
    # Adiciona controle de seções
    data['secoes'] = {
        'consumo': 'consumo' in secoes,
        'gd': 'gd' in secoes,
        'comparacao': 'comparacao' in secoes,
        'ranking': 'ranking' in secoes
    }
    
    # Carrega logo em base64
    logo_path = os.path.join(os.path.dirname(__file__), 'reports', 'logo.png')
    if os.path.exists(logo_path):
        try:
            with open(logo_path, 'rb') as f:
                logo_b64 = base64.b64encode(f.read()).decode('utf-8')
            data['pdf_data']['logo_b64'] = logo_b64
            logger.info(f"Logo carregada: {logo_path}")
        except Exception as e:
            logger.warning(f"Erro ao carregar logo: {e}")
            data['pdf_data']['logo_b64'] = None
    else:
        logger.warning(f"Logo não encontrada: {logo_path}")
        data['pdf_data']['logo_b64'] = None
    
    # Carrega template
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    
    if not os.path.exists(template_dir):
        os.makedirs(template_dir, exist_ok=True)
    
    template_path = os.path.join(template_dir, 'report.html')
    
    if os.path.exists(template_path):
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template('report.html')
        html_content = template.render(**data)
    else:
        raise FileNotFoundError(f"Template não encontrado: {template_path}")
    
    # Gera PDF usando xhtml2pdf
    pdf_buffer = io.BytesIO()
    
    try:
        pisa_status = pisa.CreatePDF(
            src=html_content,
            dest=pdf_buffer,
            encoding='utf-8'
        )
        
        if pisa_status.err:
            logger.error(f"Erro xhtml2pdf: {pisa_status.err}")
            raise Exception(f"Erro na geração do PDF: {pisa_status.err}")
    except Exception as e:
        import traceback
        logger.error(f"Erro completo: {traceback.format_exc()}")
        raise
    
    pdf_buffer.seek(0)
    
    return pdf_buffer.getvalue()


# Mantém compatibilidade com função antiga
def get_report_data(
    classes_selecionadas: List[str],
    metricas_selecionadas: List[str],
    tipo_valor: str = "absoluto",
    substation_id: Optional[str] = None
) -> Dict:
    """Alias para get_pdf_data para compatibilidade."""
    return get_pdf_data(classes_selecionadas, metricas_selecionadas, tipo_valor, substation_id)


# Exporta constantes para uso na UI
__all__ = [
    'CLASSES_DISPONIVEIS',
    'METRICAS_DISPONIVEIS',
    'get_bulk_data',
    'filter_dataframe',
    'generate_csv',
    'get_report_data',
    'get_pdf_data',
    'generate_pdf'
]
