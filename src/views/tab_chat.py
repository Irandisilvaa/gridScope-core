import streamlit as st
import requests
import time
import socket
import plotly.graph_objects as go
import json

CHAT_API_URL = "http://127.0.0.1:8002"


def consultar_chat(mensagem: str, historico: list, conversa_id: int = None, usuario_id: str = None) -> dict:
    try:
        payload = {
            "mensagem": mensagem,
            "historico": historico,
            "conversa_id": conversa_id,
            "usuario_id": usuario_id
        }
        
        response = requests.post(
            f"{CHAT_API_URL}/chat/message",
            json=payload,
            timeout=180
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "resposta": f"❌ Erro na API: {response.status_code}",
                "historico_atualizado": historico,
                "conversa_id": conversa_id
            }
            
    except requests.exceptions.ConnectionError:
        return {
            "resposta": "❌ Não foi possível conectar à API de chat. Certifique-se de que o serviço está rodando (python src/ai/chat_service.py)",
            "historico_atualizado": historico,
            "conversa_id": conversa_id
        }
    except Exception as e:
        return {
            "resposta": f"❌ Erro: {str(e)}",
            "historico_atualizado": historico,
            "conversa_id": conversa_id
        }


def tab_chat():   
    if "chat_mensagens" not in st.session_state:
        st.session_state.chat_mensagens = []
    
    if "chat_historico" not in st.session_state:
        st.session_state.chat_historico = []
    
    if "conversa_id" not in st.session_state:
        st.session_state.conversa_id = None
    
    if "usuario_id" not in st.session_state:
        st.session_state.usuario_id = socket.gethostname()
    
    with st.sidebar:
        st.subheader("Histórico")
        
        if st.button("+ Nova Conversa", use_container_width=True):
            st.session_state.chat_mensagens = []
            st.session_state.chat_historico = []
            st.session_state.conversa_id = None
            st.rerun()
        
        st.markdown("---")
        
        try:
            response = requests.get(
                f"{CHAT_API_URL}/chat/conversas",
                params={"usuario_id": st.session_state.usuario_id},
                timeout=5
            )
            
            if response.status_code == 200:
                conversas = response.json().get("conversas", [])
                
                if conversas:
                    st.caption("Conversas Recentes:")
                    for conv in conversas[:5]:
                        titulo_curto = conv["titulo"][:40] + "..." if len(conv["titulo"]) > 40 else conv["titulo"]
                        
                        if st.button(
                            f"{titulo_curto}",
                            key=f"conv_{conv['id']}",
                            use_container_width=True
                        ):
                            try:
                                msg_response = requests.get(
                                    f"{CHAT_API_URL}/chat/conversa/{conv['id']}",
                                    timeout=5
                                )
                                if msg_response.status_code == 200:
                                    mensagens = msg_response.json().get("mensagens", [])
                                    st.session_state.chat_mensagens = mensagens
                                    st.session_state.chat_historico = [
                                        {"role": m["role"], "content": m["content"]} for m in mensagens
                                    ]
                                    st.session_state.conversa_id = conv["id"]
                                    st.rerun()
                                else:
                                    st.error(f"Erro ao carregar conversa: Status {msg_response.status_code}")
                            except Exception as e:
                                st.error(f"Erro ao carregar conversa: {str(e)}")
                else:
                    st.caption("_Nenhuma conversa ainda_")
        except Exception as e:
            st.caption(f"⚠️ Erro ao carregar histórico: {str(e)}")
            print(f"DEBUG - Erro ao carregar conversas: {str(e)}")
    
    st.markdown("### Perguntas Sugeridas")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Quantos consumidores temos?", use_container_width=True):
            st.session_state.pergunta_sugerida = "Quantos consumidores temos no total?"
    
    with col2:
        if st.button("Qual subestação gera mais energia?", use_container_width=True):
            st.session_state.pergunta_sugerida = "Qual subestação tem maior potência de geração distribuída?"
    
    with col3:
        if st.button("Quais subestações estão em risco?", use_container_width=True):
            st.session_state.pergunta_sugerida = "Quais subestações estão em risco crítico de geração distribuída?"
    
    col4, col5, col6 = st.columns(3)
    
    with col4:
        if st.button("Distribuição por classe", use_container_width=True):
            st.session_state.pergunta_sugerida = "Como está a distribuição de consumo por classe (residencial, comercial, industrial)?"
    
    with col5:
        if st.button("Top 5 consumidores", use_container_width=True):
            st.session_state.pergunta_sugerida = "Me mostre as 5 subestações que mais consomem energia"
    
    with col6:
        if st.button("Estatísticas gerais", use_container_width=True):
            st.session_state.pergunta_sugerida = "Me dê um resumo das estatísticas gerais do sistema"
    
    st.markdown("---")
    
    st.markdown("### Conversa")
    
    chat_container = st.container()
    
    with chat_container:
        for msg in st.session_state.chat_mensagens:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(msg["content"])
            else:
                with st.chat_message("assistant"):
                    st.markdown(msg["content"])
                    
                    graficos = msg.get("graficos", [])
                    if graficos:
                         for i, grafico in enumerate(graficos):
                            if grafico.get("tipo") == "plotly" and grafico.get("spec"):
                                try:
                                    fig_dict = json.loads(grafico["spec"])
                                    fig = go.Figure(fig_dict)
                                    unique_key = f"hist_{hash(msg['content'])}_{i}"
                                    st.plotly_chart(fig, use_container_width=True, key=unique_key)
                                except Exception as e:
                                    st.error(f"Erro ao renderizar gráfico histórico: {str(e)}")
    
    pergunta_input = st.chat_input("Digite sua pergunta sobre os dados...")
    
    if "pergunta_sugerida" in st.session_state:
        pergunta_input = st.session_state.pergunta_sugerida
        del st.session_state.pergunta_sugerida
    
    if pergunta_input:
        st.session_state.chat_mensagens.append({
            "role": "user",
            "content": pergunta_input
        })
        
        with chat_container:
            with st.chat_message("user"):
                st.markdown(pergunta_input)
        
        with st.spinner("Consultando dados do sistema e processando resposta..."):
            resultado = consultar_chat(
                pergunta_input, 
                st.session_state.chat_historico,
                st.session_state.conversa_id,
                st.session_state.usuario_id
            )
        
        resposta_ia = resultado.get("resposta", "Erro ao processar resposta")
        
        if not resposta_ia or resposta_ia.strip() == "":
            resposta_ia = "Recebi uma resposta vazia da API. Tente novamente."
        
        nova_mensagem = {
            "role": "assistant",
            "content": resposta_ia,
            "graficos": resultado.get("graficos", [])
        }
        
        st.session_state.chat_mensagens.append(nova_mensagem)
        
        st.session_state.chat_historico = resultado.get("historico_atualizado", [])
        
        if resultado.get("conversa_id"):
            st.session_state.conversa_id = resultado.get("conversa_id")
        
        with chat_container:
            with st.chat_message("assistant"):
                st.markdown(resposta_ia)
                
                graficos = nova_mensagem.get("graficos", [])
                if graficos:
                    for i, grafico in enumerate(graficos):
                        if grafico.get("tipo") == "plotly" and grafico.get("spec"):
                            try:
                                fig_dict = json.loads(grafico["spec"])
                                fig = go.Figure(fig_dict)
                                st.plotly_chart(
                                    fig, 
                                    use_container_width=True, 
                                    key=f"grafico_live_{len(st.session_state.chat_mensagens)}_{i}"
                                )
                            except Exception as e:
                                st.error(f"Erro ao renderizar gráfico: {str(e)}")
                
                col1, col2, col3 = st.columns([1, 1, 8])
                with col1:
                    if st.button("👍 Útil", key=f"like_new_{len(st.session_state.chat_mensagens)}"):
                        try:
                            requests.post(f"{CHAT_API_URL}/chat/feedback", json={
                                "pergunta": pergunta_input,
                                "resposta": resposta_ia,
                                "feedback": True
                            })
                            st.success("Obrigado!")
                        except:
                            st.error("Erro ao enviar feedback")
                with col2:
                    if st.button("👎 Não útil", key=f"dislike_{len(st.session_state.chat_mensagens)}"):
                        try:
                            requests.post(f"{CHAT_API_URL}/chat/feedback", json={
                                "pergunta": pergunta_input,
                                "resposta": resposta_ia,
                                "feedback": False
                            })
                            st.success("Obrigado pelo feedback!")
                        except:
                            st.error("Erro ao enviar feedback")
        
        st.rerun()
    
    st.markdown("---")
    if st.button("Limpar Conversa"):
        st.session_state.chat_historico = []
        st.session_state.chat_mensagens = []
        st.rerun()
    
    st.markdown("---")
    st.caption("Dica: Faça perguntas específicas sobre subestações, consumo, geração distribuída ou estatísticas do sistema")
    
    try:
        health = requests.get(f"{CHAT_API_URL}/health", timeout=2)
        if health.status_code == 200:
            info = health.json()
        else:
            st.error("❌ API de Chat não está respondendo corretamente")
    except:
        st.error("❌ API de Chat offline. Inicie o serviço com: `python src/ai/chat_service.py`")


if __name__ == "__main__":
    tab_chat()

render_view = tab_chat
