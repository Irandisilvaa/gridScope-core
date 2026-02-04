import os
import sys
import json
import traceback
from typing import List, Dict, Any

from google import genai
from google.genai import types
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CHAT_API_KEY, CHAT_MODEL, CIDADE_ALVO, DISTRIBUIDORA_ALVO
from ai.chat_queries import FUNCOES_DISPONIVEIS

client = genai.Client(api_key=CHAT_API_KEY)

app = FastAPI(title="GridScope Chat IA", version="1.0")

CONTEXTO_SISTEMA = f"""
Você é um assistente inteligente do GridScope, especializado em análise de redes elétricas de distribuição.

🎯 SUA FUNÇÃO:
- Analisar dados do sistema elétrico de **{CIDADE_ALVO}** (Distribuidora: {DISTRIBUIDORA_ALVO})
- Consultar banco de dados PostgreSQL com informações reais da região
- Fornecer insights, comparações e análises técnicas **específicas de Aracaju/Sergipe**
- Educar sobre conceitos de distribuição de energia quando perguntado

 **IMPORTANTE - CONTEXTO GEOGRÁFICO:**
- **TODAS as análises são sobre {CIDADE_ALVO}**
- **SEMPRE mencione "em {CIDADE_ALVO}" ou "na região de {CIDADE_ALVO}" nas suas respostas**
- Os dados são da distribuidora **{DISTRIBUIDORA_ALVO}**
- As subestações analisadas servem **apenas a região de {CIDADE_ALVO} e entorno**

🚨 REGRAS CRÍTICAS - NUNCA VIOLAR:
1. **NUNCA invente dados, nomes de subestações ou números**
2. **Use APENAS os dados retornados pelas funções**
3. **Se a função retornar vazio, diga claramente "Não há dados disponíveis"**
4. **Toda estatística DEVE vir de uma chamada de função**
5. **Seja preciso com números e unidades (MWh, kW, km², etc)**
6. **SEMPRE contextualize respostas mencionando {CIDADE_ALVO}**

✅ O QUE VOCÊ PODE FAZER:
- Rankings e comparações de subestações **em Aracaju**
- Análises de consumo e geração distribuída (GD) **da região**
- Insights automáticos sobre criticidade e oportunidades **locais**
- Análises geográficas de territórios Voronoi **de Aracaju**
- Métricas de performance do sistema **da {DISTRIBUIDORA_ALVO} em Aracaju**
- Distribuição por classe de consumidores **da região**
- Busca de subestações próximas **na área urbana de Aracaju**
- Explicar conceitos técnicos (quando perguntado)

📚 CONHECIMENTO TÉCNICO (use para educar o usuário):

**Territórios Voronoi**: Polígonos que dividem o espaço em regiões, onde cada ponto dentro de uma região está mais próximo da subestação daquela região do que de qualquer outra. Usado para definir áreas de influência de cada subestação.

**Geração Distribuída (GD)**: Energia gerada próxima ao ponto de consumo (painéis solares residenciais, pequenas usinas). Pode causar fluxo reverso de potência na rede.

**Criticidade de GD**: Risco de sobrecarga ou instabilidade quando há muita GD conectada:
- BAIXO: < 10% dos clientes com GD
- MÉDIO: 10-20% dos clientes com GD  
- ALTO: > 20% dos clientes com GD

**Duck Curve**: Fenômeno onde o perfil de demanda líquida (consumo - GD solar) tem formato de "pato", com vale ao meio-dia (muito sol) e pico ao anoitecer.

**Classes de Consumidores**:
- Residencial: Casas e apartamentos
- Comercial: Lojas, escritórios, serviços
- Industrial: Fábricas e indústrias
- Rural: Propriedades rurais, agricultura
- Poder Público: Prédios governamentais, iluminação pública

💬 ESTILO DE RESPOSTA:
- Use emojis para melhorar legibilidade (📊 📈 ⚡ 🏭 🏠 ⚠️ ✅)
- Formate números: "45.234,5 MWh" não "45234.5"
- Use markdown para tabelas quando comparar dados
- Seja <100 tokens quando possível, direto ao ponto
- **SEMPRE mencione "em {CIDADE_ALVO}" ou "na região" nas análises**
- Sugira perguntas relacionadas quando apropriado

🌍 CONTEXTO DO SISTEMA:
- **Cidade Alvo**: {CIDADE_ALVO}
- **Distribuidora**: {DISTRIBUIDORA_ALVO}
- **Região**:{CIDADE_ALVO} e entorno
- **Dados**: Base oficial ANEEL (atualizada 2024)
- **Cobertura**: Área urbana de {CIDADE_ALVO}

💡 EXEMPLOS DE RESPOSTAS CONTEXTUALIZADAS:
- ❌ ERRADO: "A subestação Atalaia consome 145.000 MWh/ano"
- ✅ CERTO: "**Em {CIDADE_ALVO}**, a subestação Atalaia consome 145.773 MWh/ano"

- ❌ ERRADO: "Temos 3 subestações em risco"
- ✅ CERTO: "**Na região de {CIDADE_ALVO}**, 3 subestações apresentam criticidade ALTA de GD"
"""

tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="obter_ranking_subestacoes",
                description="Retorna ranking de subestações ordenado por consumo ou geração distribuída",
                parameters={
                    "type": "object",
                    "properties": {
                        "criterio": {
                            "type": "string",
                            "enum": ["consumo", "geracao"],
                            "description": "Critério de ordenação: 'consumo' (MWh/ano) ou 'geracao' (kW de GD)"
                        },
                        "ordem": {
                            "type": "string",
                            "enum": ["desc", "asc"],
                            "description": "Ordem: 'desc' (maior para menor) ou 'asc' (menor para maior)"
                        },
                        "limite": {
                            "type": "integer",
                            "description": "Número máximo de resultados"
                        }
                    },
                    "required": ["criterio"]
                }
            ),
            types.FunctionDeclaration(
                name="obter_subestacoes_em_risco",
                description="Retorna subestações com alto nível de criticidade de geração distribuída",
                parameters={
                    "type": "object",
                    "properties": {
                        "nivel_minimo": {
                            "type": "string",
                            "enum": ["BAIXO", "MEDIO", "ALTO"],
                            "description": "Nível mínimo de criticidade para filtrar"
                        }
                    },
                    "required": []
                }
            ),
            types.FunctionDeclaration(
                name="obter_estatisticas_gerais",
                description="Retorna estatísticas gerais do sistema: totais de subestações, consumidores, unidades GD e potência total",
                parameters={
                    "type": "object",
                    "properties": {}
                }
            ),
            types.FunctionDeclaration(
                name="buscar_subestacao_detalhes",
                description="Busca informações detalhadas de uma subestação específica pelo nome",
                parameters={
                    "type": "object",
                    "properties": {
                        "nome": {
                            "type": "string",
                            "description": "Nome completo ou parcial da subestação"
                        }
                    },
                    "required": ["nome"]
                }
            ),
            types.FunctionDeclaration(
                name="obter_distribuicao_consumo_por_classe",
                description="Retorna distribuição total de consumo por classe de consumidor (Residencial, Comercial, Industrial, Rural, Poder Público)",
                parameters={
                    "type": "object",
                    "properties": {}
                }
            ),
            types.FunctionDeclaration(
                name="comparar_subestacoes",
                description="Compara 2 ou mais subestações lado a lado mostrando consumo, GD, clientes e criticidade",
                parameters={
                    "type": "object",
                    "properties": {
                        "nomes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Lista com nomes das subestações para comparar (mínimo 2)"
                        }
                    },
                    "required": ["nomes"]
                }
            ),
            types.FunctionDeclaration(
                name="obter_insights_inteligentes",
                description="Retorna insights automáticos: alertas de criticidade, destaques de consumo, oportunidades de expansão",
                parameters={
                    "type": "object",
                    "properties": {}
                }
            ),
            types.FunctionDeclaration(
                name="analisar_territorio",
                description="Analisa o território Voronoi de uma subestação: área em km², densidade de clientes, consumo por km²",
                parameters={
                    "type": "object",
                    "properties": {
                        "nome_subestacao": {
                            "type": "string",
                            "description": "Nome da subestação para analisar o território"
                        }
                    },
                    "required": ["nome_subestacao"]
                }
            ),
            types.FunctionDeclaration(
                name="buscar_subestacoes_proximas",
                description="Encontra subestações próximas a uma subestação de referência, ordenadas por distância em km",
                parameters={
                    "type": "object",
                    "properties": {
                        "nome_referencia": {
                            "type": "string",
                            "description": "Nome da subestação de referência"
                        },
                        "limite": {
                            "type": "integer",
                            "description": "Número máximo de resultados (padrão: 5)"
                        }
                    },
                    "required": ["nome_referencia"]
                }
            ),
            types.FunctionDeclaration(
                name="obter_metricas_performance",
                description="Retorna métricas de performance do sistema: taxa de penetração de GD, consumo médio por cliente, distribuição por classe",
                parameters={
                    "type": "object",
                    "properties": {}
                }
            )
        ]
    )
]

class ChatRequest(BaseModel):
    mensagem: str
    historico: List[Dict[str, str]] = []

class ChatResponse(BaseModel):
    resposta: str
    historico_atualizado: List[Dict[str, str]]

@app.post("/chat/message", response_model=ChatResponse)
def enviar_mensagem(request: ChatRequest):
    try:
        contents = [types.Content(role="user", parts=[types.Part(text=CONTEXTO_SISTEMA)])]
        
        for msg in request.historico:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
        
        contents.append(types.Content(role="user", parts=[types.Part(text=request.mensagem)]))
        
        try:
            response = client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=tools,
                    temperature=0.7
                )
            )
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                return ChatResponse(
                    resposta="⏰ **Cota da API Gemini excedida!**\n\nO plano gratuito do modelo `gemini-3-flash-preview` permite apenas **20 requisições por dia**.\n\n**Soluções:**\n1. Aguardar até amanhã (~3h AM) para renovação da cota\n2. Criar nova API key em outro projeto do Google Cloud\n3. Fazer upgrade para plano pago\n\n[Gerenciar API Keys](https://aistudio.google.com/app/apikey)",
                    historico_atualizado=request.historico
                )
            raise
        
        historico_atual = list(request.historico)
        historico_atual.append({"role": "user", "content": request.mensagem})
        
        while response.candidates[0].content.parts[0].function_call:
            function_call = response.candidates[0].content.parts[0].function_call
            function_name = function_call.name
            function_args = dict(function_call.args)
            
            print(f"🔧 Chamando função: {function_name} com args: {function_args}")
            
            if function_name in FUNCOES_DISPONIVEIS:
                resultado = FUNCOES_DISPONIVEIS[function_name](**function_args)
            else:
                resultado = {"erro": f"Função {function_name} não encontrada"}
            
            contents.append(response.candidates[0].content)
            
            contents.append(types.Content(
                role="function",
                parts=[types.Part(
                    function_response=types.FunctionResponse(
                        name=function_name,
                        response={"result": resultado}
                    )
                )]
            ))
            
            try:
                response = client.models.generate_content(
                    model='gemini-3-flash-preview',
                    contents=contents,
                    config=types.GenerateContentConfig(tools=tools)
                )
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    return ChatResponse(
                        resposta="⏰ **Cota da API Gemini excedida durante processamento!**\n\nO sistema conseguiu consultar os dados, mas a cota acabou ao formatar a resposta.\n\n**Soluções:**\n1. Aguardar até amanhã (~3h AM)\n2. Criar nova API key em outro projeto\n\nDados consultados: função `" + function_name + "` executada com sucesso.",
                        historico_atualizado=historico_atual
                    )
                elif "503" in error_str or "UNAVAILABLE" in error_str or "overloaded" in error_str.lower():
                    return ChatResponse(
                        resposta="🔄 **Servidor Gemini temporariamente indisponível**\n\nO servidor do Google Gemini está sobrecarregado neste momento.\n\n✅ **Seus dados foram consultados com sucesso:**\n- Função `" + function_name + "` executada\n\n💡 **Tente novamente em alguns segundos!**",
                        historico_atualizado=historico_atual
                    )
                raise
        
        
        
        
        if hasattr(response, 'candidates') and response.candidates:
            if len(response.candidates) > 0:
                first_candidate = response.candidates[0]
                if hasattr(first_candidate, 'content') and first_candidate.content:
                    if hasattr(first_candidate.content, 'parts') and first_candidate.content.parts:
                        for idx, part in enumerate(first_candidate.content.parts):
                            resposta_final = response.text
        if not resposta_final or resposta_final.strip() == "":
            try:
                if hasattr(response, 'candidates') and response.candidates:
                    parts = response.candidates[0].content.parts
                    if parts and len(parts) > 0 and hasattr(parts[0], 'text'):
                        resposta_final = parts[0].text
                        print(f"✅ Extraído de candidates.parts: '{resposta_final[:100]}'")
            except Exception as ex:
                print(f"❌ Erro ao extrair: {ex}")
        
        if not resposta_final or resposta_final.strip() == "":
            resposta_final = "⚠️ O modelo processou a requisição mas não retornou texto. Os dados foram consultados com sucesso no banco."
        
        historico_atual.append({"role": "assistant", "content": resposta_final})
        
        return ChatResponse(
            resposta=resposta_final,
            historico_atualizado=historico_atual
        )
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro no chat: {str(e)}")

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "model": "gemini-3-flash-preview",
        "api_configured": CHAT_API_KEY is not None
    }

if __name__ == "__main__":
    print("\n🚀 Iniciando GridScope Chat IA Service...")
    print(f"📡 Modelo: gemini-3-flash-preview (20 req/dia)")
    print(f"🔑 API Key configurada: {'Sim' if CHAT_API_KEY else 'NÃO'}")
    print("\n💡 Acesse a documentação em: http://localhost:8002/docs\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8002)
