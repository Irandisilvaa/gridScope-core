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

from config import CHAT_API_KEY, CHAT_MODEL
from ai.chat_queries import FUNCOES_DISPONIVEIS

client = genai.Client(api_key=CHAT_API_KEY)

app = FastAPI(title="GridScope Chat IA", version="1.0")

CONTEXTO_SISTEMA = """
Você é um assistente de dados do GridScope, sistema de análise de redes elétricas.

SUA FUNÇÃO:
- Responder perguntas sobre os DADOS do sistema elétrico
- Consultar o banco de dados PostgreSQL quando necessário
- Apresentar estatísticas, rankings e análises dos dados

🚨 REGRAS CRÍTICAS - NUNCA VIOLAR:
1. **NUNCA invente dados, nomes de subestações ou números**
2. **Use APENAS os dados retornados pelas funções que você chamar**
3. **Se a função retornar vazio, diga que não há dados disponíveis**
4. **NUNCA mencione subestações que não estejam no resultado da consulta**
5. **Toda estatística DEVE vir de uma função chamada**

O QUE VOCÊ PODE RESPONDER:
✅ Perguntas sobre subestações (qual gera mais, qual consome mais, etc)
✅ Estatísticas do sistema (quantos consumidores, total de GD, etc)
✅ Análise de risco (quais subestações em risco crítico)
✅ Distribuição de consumo por classe (residencial, comercial, industrial)
✅ Detalhes específicos de uma subestação

O QUE VOCÊ NÃO DEVE RESPONDER:
❌ Como o sistema funciona tecnicamente
❌ Como foi desenvolvido
❌ Explicações sobre agentes de IA
❌ Arquitetura do sistema
❌ Código-fonte ou implementação

IMPORTANTE:
- SEMPRE responda em PORTUGUÊS do Brasil
- Use números formatados (ex: 45.234,5 MWh)
- Seja objetivo e direto
- Se não tiver dados, diga claramente "Não há dados disponíveis"
- Quando consultar o banco, cite APENAS os números retornados pela função
- **PROIBIDO inventar nomes ou valores que não vieram das funções**
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
                # Retornar resposta válida com mensagem de erro
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
        
        
        
        # Debug completo do response
        print(f"🔍 DEBUG - Tipo do response: {type(response)}")
        print(f"🔍 DEBUG - Tem candidates? {hasattr(response, 'candidates') and len(response.candidates) > 0 if hasattr(response, 'candidates') else 'Não'}")
        
        if hasattr(response, 'candidates') and response.candidates:
            print(f"🔍 DEBUG - Número de candidates: {len(response.candidates)}")
            if len(response.candidates) > 0:
                first_candidate = response.candidates[0]
                print(f"🔍 DEBUG - Tem content? {hasattr(first_candidate, 'content')}")
                if hasattr(first_candidate, 'content') and first_candidate.content:
                    print(f"🔍 DEBUG - Número de parts: {len(first_candidate.content.parts) if hasattr(first_candidate.content, 'parts') else 0}")
                    if hasattr(first_candidate.content, 'parts') and first_candidate.content.parts:
                        for idx, part in enumerate(first_candidate.content.parts):
                            print(f"🔍 DEBUG - Part {idx}: {dir(part)[:5]}")  # Primeiros 5 atributos
        
        resposta_final = response.text
        
        # Debug: verificar se resposta está vazia
        print(f"🔍 DEBUG - response.text: '{resposta_final[:100] if resposta_final else 'VAZIO'}'")
        
        # Fallback: tentar extrair de candidates se text estiver vazio
        if not resposta_final or resposta_final.strip() == "":
            print(f"⚠️ response.text vazio! Tentando extrair de candidates...")
            try:
                if hasattr(response, 'candidates') and response.candidates:
                    parts = response.candidates[0].content.parts
                    if parts and len(parts) > 0 and hasattr(parts[0], 'text'):
                        resposta_final = parts[0].text
                        print(f"✅ Extraído de candidates.parts: '{resposta_final[:100]}'")
            except Exception as ex:
                print(f"❌ Erro ao extrair: {ex}")
        
        # Se ainda vazio, mensagem de erro
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
