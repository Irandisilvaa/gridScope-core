import os
import sys
import json
import hashlib
import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from google import genai
from google.genai import types
from google.genai.errors import ServerError
from fastapi import FastAPI, HTTPException, Path, Query
from pydantic import BaseModel, Field
import uvicorn
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CHAT_API_KEY, CHAT_MODEL, CIDADE_ALVO, DISTRIBUIDORA_ALVO
from ai.chat_queries import FUNCOES_DISPONIVEIS
from database import (criar_tabela_feedback, salvar_feedback_chat,
                    criar_tabelas_historico, criar_conversa, salvar_mensagem, 
                    carregar_conversas, carregar_mensagens)

logger = logging.getLogger(__name__)

client = genai.Client(api_key=CHAT_API_KEY)


@asynccontextmanager
async def lifespan(_app):
    try:
        criar_tabela_feedback()
        criar_tabelas_historico()
    except Exception:
        logger.exception("Falha ao inicializar tabelas do chat")
    yield


app = FastAPI(title="GridScope Chat IA", version="1.0", lifespan=lifespan)

MAX_CHAT_MESSAGE_CHARS = 4_000
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CONTENT_CHARS = 4_000
MAX_CHAT_TOTAL_CHARS = 20_000
MAX_TOOL_ARGS_CHARS = 4_000
MAX_TOOL_RESULT_CHARS = 12_000
MAX_FUNCTION_ITERATIONS = 10

CONTEXTO_SISTEMA = f"""
Você é um assistente especializado em análise de redes elétricas de distribuição.
**Responda SEMPRE em Português do Brasil.**

Dados disponíveis: Sistema elétrico de {CIDADE_ALVO}, operado pela {DISTRIBUIDORA_ALVO}.
Use as funções disponíveis para consultar dados reais do banco quando solicitado.

Conceitos importantes:

Geração Distribuída (GD): Energia gerada próxima ao ponto de consumo (painéis solares, pequenas usinas). Pode causar fluxo reverso de potência na rede.

Criticidade de GD:
- BAIXA: < 10% dos clientes com GD
- MÉDIA: 10-20% dos clientes com GD  
- ALTA: > 20% dos clientes com GD (risco de sobrecarga)

Territórios Voronoi: Áreas de influência de cada subestação, onde cada ponto está mais próximo daquela subestação do que de qualquer outra.

Classes de consumo:
- Residencial: Casas e apartamentos
- Comercial: Lojas e serviços
- Industrial: Fábricas
- Rural: Propriedades rurais
- Poder Público: Órgãos governamentais

Seja objetivo e use dados reais das funções.

DIRETRIZES PARA GRÁFICOS (MUITO IMPORTANTE):
1. NUNCA desenhe gráficos usando texto ou caracteres (como [###...]).
2. SEMPRE que o usuário pedir um gráfico, visualização ou comparação visual, USE AS FUNÇÕES DE GRÁFICO disponíveis (`gerar_grafico_*`).
3. Se não houver uma função de gráfico específica para o que foi pedido, explique que não pode gerar o gráfico, mas apresente os dados em tabela.
4. Gráficos disponíveis:
   - Consumo por classe -> `gerar_grafico_consumo_por_classe`
   - Ranking/Top subestações -> `gerar_grafico_ranking_subestacoes`
   - Distribuição de GD -> `gerar_grafico_distribuicao_gd`
   - Criticidade vs Consumo -> `gerar_grafico_criticidade_vs_consumo`
"""

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(ServerError)
)
def call_gemini_with_retry(client, model, contents, config):
    return client.models.generate_content(
        model=model,
        contents=contents,
        config=config
    )

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
            ),
            types.FunctionDeclaration(
                name="gerar_grafico_consumo_por_classe",
                description=" Gera o gráfico visual de pizza. OBRIGATÓRIO usar esta função para mostrar a distribuição de consumo.",
                parameters={
                    "type": "object",
                    "properties": {}
                }
            ),
            types.FunctionDeclaration(
                name="gerar_grafico_ranking_subestacoes",
                description="Gera o gráfico visual de barras. OBRIGATÓRIO usar esta função para mostrar rankings de subestações.",
                parameters={
                    "type": "object",
                    "properties": {
                        "criterio": {
                            "type": "string",
                            "enum": ["consumo", "geracao"],
                            "description": "Critério de ordenação: 'consumo' (MWh/ano) ou 'geracao' (kW de GD)"
                        },
                        "limite": {
                            "type": "integer",
                            "description": "Número de subestações no ranking (padrão: 10)"
                        }
                    },
                    "required": ["criterio"]
                }
            ),
            types.FunctionDeclaration(
                name="gerar_grafico_distribuicao_gd",
                description="Gera o gráfico visual de distribuição de GD. OBRIGATÓRIO usar esta função para mostrar dados de GD.",
                parameters={
                    "type": "object",
                    "properties": {}
                }
            ),
            types.FunctionDeclaration(
                name="gerar_grafico_criticidade_vs_consumo",
                description="Gera o gráfico visual de scatter plot. OBRIGATÓRIO usar esta função para análises de criticidade.",
                parameters={
                    "type": "object",
                    "properties": {}
                }
            )
        ]
    )
]

class ChatRequest(BaseModel):
    mensagem: str = Field(..., min_length=1, max_length=MAX_CHAT_MESSAGE_CHARS)
    historico: List[Dict[str, str]] = Field(default_factory=list)
    conversa_id: Optional[int] = Field(default=None, gt=0)
    usuario_id: Optional[str] = Field(default=None, min_length=1, max_length=128)

class ChatResponse(BaseModel):
    resposta: str
    historico_atualizado: List[Dict[str, str]]
    conversa_id: Optional[int] = None
    graficos: Optional[List[Dict[str, Any]]] = None

class FeedbackRequest(BaseModel):
    pergunta: str = Field(..., min_length=1, max_length=MAX_CHAT_MESSAGE_CHARS)
    resposta: str = Field(..., min_length=1, max_length=MAX_TOOL_RESULT_CHARS)
    feedback: bool
    comentario: Optional[str] = Field(default=None, max_length=2_000)


def _validar_limites_chat(request: ChatRequest) -> None:
    if not request.mensagem.strip():
        raise HTTPException(status_code=422, detail="A mensagem não pode ser vazia")
    if len(request.historico) > MAX_HISTORY_MESSAGES:
        raise HTTPException(status_code=422, detail="Histórico excede o limite permitido")

    total_chars = len(request.mensagem)
    for message in request.historico:
        if set(message) != {"role", "content"}:
            raise HTTPException(status_code=422, detail="Item de histórico inválido")
        if message["role"] not in {"user", "model"}:
            raise HTTPException(status_code=422, detail="Papel de mensagem inválido")
        if not message["content"].strip():
            raise HTTPException(status_code=422, detail="Conteúdo de histórico vazio")
        if len(message["content"]) > MAX_HISTORY_CONTENT_CHARS:
            raise HTTPException(status_code=422, detail="Mensagem do histórico excede o limite permitido")
        total_chars += len(message["content"])

    if total_chars > MAX_CHAT_TOTAL_CHARS:
        raise HTTPException(status_code=422, detail="Conteúdo total do chat excede o limite permitido")

@app.post("/chat/message", response_model=ChatResponse)
def enviar_mensagem(request: ChatRequest):
    try:
        _validar_limites_chat(request)
        conversa_id = request.conversa_id
        if not conversa_id and request.usuario_id:
            titulo = request.mensagem[:50] + "..." if len(request.mensagem) > 50 else request.mensagem
            conversa_id = criar_conversa(request.usuario_id, titulo)
            print(f"📝 Nova conversa criada: ID {conversa_id}")
        if conversa_id:
            salvar_mensagem(conversa_id, "user", request.mensagem)
            print(f"💾 Mensagem do usuário salva na conversa {conversa_id}")
        
        contents = [types.Content(role="user", parts=[types.Part(text=CONTEXTO_SISTEMA)])]
        
        for msg in request.historico:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
        
        contents.append(types.Content(role="user", parts=[types.Part(text=request.mensagem)]))
        
        try:
            response = call_gemini_with_retry(
                client,
                'gemini-3-flash-preview',
                contents,
                types.GenerateContentConfig(
                    tools=tools,
                    temperature=0.7
                )
            )
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                return ChatResponse(
                    resposta="⏰ **Cota da API Gemini excedida!**\n\nO plano gratuito do modelo `gemini-3-flash-preview` permite apenas **20 requisições por dia**.\n\n**Soluções:**\n1. Aguardar até amanhã (~3h AM) para renovação da cota\n2. Criar nova API key em outro projeto do Google Cloud\n3. Fazer upgrade para plano pago\n\n[Gerenciar API Keys](https://aistudio.google.com/app/apikey)",
                    historico_atualizado=request.historico,
                    conversa_id=conversa_id
                )
            raise
        
        historico_atual = request.historico.copy()
        historico_atual.append({"role": "user", "content": request.mensagem})
        
        generation_config = types.GenerateContentConfig(
            max_output_tokens=2800,
            temperature=0.68
        )
        
        max_iterations = MAX_FUNCTION_ITERATIONS
        iteration = 0
        graficos_gerados = []  # Lista para coletar gráficos
        
        while iteration < max_iterations:
            iteration += 1
            
            try:
                has_function_call = (
                    response.candidates and 
                    len(response.candidates) > 0 and
                    response.candidates[0].content.parts and
                    len(response.candidates[0].content.parts) > 0 and
                    hasattr(response.candidates[0].content.parts[0], 'function_call') and
                    response.candidates[0].content.parts[0].function_call
                )
                if not has_function_call:
                    print(f"✅ Fim do function calling (iteração {iteration})")
                    break
            except Exception as e:
                print(f"⚠️ Erro ao verificar function_call: {e}")
                break
            
            function_call = response.candidates[0].content.parts[0].function_call
            function_name = function_call.name
            function_args = dict(function_call.args)

            if len(json.dumps(function_args, ensure_ascii=False, default=str)) > MAX_TOOL_ARGS_CHARS:
                resultado = {"erro": "Argumentos da ferramenta excedem o limite permitido"}
            else:
                logger.info("Chamando função do chat: %s", function_name)

                if function_name in FUNCOES_DISPONIVEIS:
                    try:
                        resultado = FUNCOES_DISPONIVEIS[function_name](**function_args)
                        logger.info("Função do chat executada: %s", function_name)
                    except Exception:
                        logger.exception("Falha ao executar função do chat: %s", function_name)
                        resultado = {"erro": "Falha ao executar a ferramenta"}

                    if len(json.dumps(resultado, ensure_ascii=False, default=str)) > MAX_TOOL_RESULT_CHARS:
                        resultado = {"erro": "Resultado da ferramenta excede o limite permitido"}

                    if function_name.startswith("gerar_grafico_"):
                        if isinstance(resultado, dict) and "spec" in resultado and "tipo" in resultado:
                            graficos_gerados.append(resultado)
                            print(f"📊 Gráfico capturado: {resultado.get('titulo', 'Sem título')}")
                        else:
                            print(f"⚠️ A função {function_name} não retornou um gráfico válido:Keys={resultado.keys() if isinstance(resultado, dict) else 'Not Dict'}")

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
                response = call_gemini_with_retry(
                    client,
                    'gemini-3-flash-preview',
                    contents,
                    types.GenerateContentConfig(
                        tools=tools,
                        max_output_tokens=2500,  # Aumentado para 2500 para evitar cortar respostas
                        temperature=0.75
                    )
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
        
        
        
        
        resposta_final = ""
        if hasattr(response, 'candidates') and response.candidates:
            logger.debug("Resposta Gemini contém %s candidatos", len(response.candidates))
            if len(response.candidates) > 0:
                first_candidate = response.candidates[0]
                if hasattr(first_candidate, 'content') and first_candidate.content:
                    logger.debug("Resposta Gemini contém %s partes", len(first_candidate.content.parts))
                    if hasattr(first_candidate.content, 'parts') and first_candidate.content.parts:
                        for part in first_candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                resposta_final = part.text
                                break
        
        if not resposta_final or resposta_final.strip() == "":
            try:
                if hasattr(response, 'text') and response.text:
                    resposta_final = response.text
                    logger.debug("Texto extraído de response.text")
            except Exception as ex:
                logger.debug("response.text não disponível: %s", ex)
        
        if not resposta_final or resposta_final.strip() == "":
            print("⚠️ Resposta vazia detectada. Forçando uma última chamada para gerar texto...")
            try:
                retry_contents = [types.Content(role="user", parts=[types.Part(text=CONTEXTO_SISTEMA)])]
                
                for msg in historico_atual:
                    role = "user" if msg.get("role") == "user" else "model"
                    content_text = msg.get("content", "")
                    if content_text:
                        retry_contents.append(types.Content(role=role, parts=[types.Part(text=str(content_text))]))
                
                # Adiciona o prompt de força
                retry_contents.append(types.Content(role="user", parts=[types.Part(text="Com base nos dados acima, responda minha pergunta original de forma direta e em Português.")]))

                final_response = client.models.generate_content(
                    model=CHAT_MODEL,
                    contents=retry_contents,
                    config=generation_config
                )
                
                if hasattr(final_response, 'text') and final_response.text:
                    resposta_final = final_response.text
                    logger.debug("Texto recuperado com chamada extra")
            except Exception:
                logger.exception("Falha no retry de resposta vazia")

        if not resposta_final or resposta_final.strip() == "":
            resposta_final = "⚠️ O modelo processou a requisição mas não retornou texto. Os dados foram consultados com sucesso no banco."
        
        if "{" in resposta_final and '"tipo": "plotly"' in resposta_final:
            import re
            padrao = r'\{.*?"tipo":\s*"plotly".*?\}'
            resposta_final = re.sub(padrao, '', resposta_final, flags=re.DOTALL)
            resposta_final = re.sub(r'\n\s*\n', '\n\n', resposta_final).strip()

        historico_atual.append({"role": "assistant", "content": resposta_final})

        if conversa_id:
            salvar_mensagem(conversa_id, "assistant", resposta_final)
            print(f"💾 Resposta do assistente salva na conversa {conversa_id}")
        
        return ChatResponse(
            resposta=resposta_final,
            historico_atualizado=historico_atual,
            conversa_id=conversa_id,
            graficos=graficos_gerados if graficos_gerados else None
        )
        
    except Exception as e:
        logger.exception("Falha ao processar mensagem do chat")
        raise HTTPException(status_code=500, detail="Erro interno ao processar o chat") from e

@app.post("/chat/feedback")
def enviar_feedback(request: FeedbackRequest):
    try:
        salvar_feedback_chat(
            pergunta=request.pergunta,
            resposta=request.resposta,
            feedback=request.feedback,
            comentario=request.comentario
        )
        return {"status": "ok", "mensagem": "Obrigado pelo feedback!"}
    except Exception as e:
        logger.exception("Falha ao salvar feedback do chat")
        raise HTTPException(status_code=500, detail="Erro interno ao salvar o feedback") from e

@app.post("/chat/conversa/nova")
def nova_conversa(
    usuario_id: str = Query(..., min_length=1, max_length=128),
    titulo: str = Query(..., min_length=1, max_length=200),
):
    try:
        conversa_id = criar_conversa(usuario_id, titulo)
        if conversa_id:
            return {"status": "ok", "conversa_id": conversa_id}
        else:
            raise HTTPException(status_code=500, detail="Erro ao criar conversa")
    except Exception as e:
        logger.exception("Falha ao criar conversa")
        raise HTTPException(status_code=500, detail="Erro interno ao criar a conversa") from e

@app.get("/chat/conversas")
def listar_conversas(usuario_id: str = Query(..., min_length=1, max_length=128)):
    try:
        conversas = carregar_conversas(usuario_id)
        return {"conversas": conversas}
    except Exception as e:
        logger.exception("Falha ao listar conversas")
        raise HTTPException(status_code=500, detail="Erro interno ao listar conversas") from e

@app.get("/chat/conversa/{conversa_id}")
def obter_conversa(conversa_id: int = Path(..., gt=0)):
    try:
        mensagens = carregar_mensagens(conversa_id)
        return {"mensagens": mensagens}
    except Exception as e:
        logger.exception("Falha ao carregar conversa")
        raise HTTPException(status_code=500, detail="Erro interno ao carregar a conversa") from e

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
