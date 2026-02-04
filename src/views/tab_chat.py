import streamlit as st
import requests
import time

CHAT_API_URL = "http://127.0.0.1:8002"


def consultar_chat(mensagem: str, historico: list) -> dict:
    try:
        payload = {
            "mensagem": mensagem,
            "historico": historico
        }
        
        response = requests.post(
            f"{CHAT_API_URL}/chat/message",
            json=payload,
            timeout=120
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "resposta": f"❌ Erro na API: {response.status_code}",
                "historico_atualizado": historico
            }
            
    except requests.exceptions.ConnectionError:
        return {
            "resposta": "❌ Não foi possível conectar à API de chat. Certifique-se de que o serviço está rodando (python src/ai/chat_service.py)",
            "historico_atualizado": historico
        }
    except Exception as e:
        return {
            "resposta": f"❌ Erro: {str(e)}",
            "historico_atualizado": historico
        }


def render_view():
    st.title("💬 Chat com IA - Consulta de Dados")
    st.markdown("Faça perguntas sobre os dados do sistema elétrico")
    
    if "chat_historico" not in st.session_state:
        st.session_state.chat_historico = []
    
    if "chat_mensagens" not in st.session_state:
        st.session_state.chat_mensagens = []
    
    st.markdown("### 💡 Perguntas Sugeridas")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Quantos consumidores temos?", use_container_width=True):
            st.session_state.pergunta_sugerida = "Quantos consumidores temos no total?"
    
    with col2:
        if st.button("⚡ Qual subestação gera mais energia?", use_container_width=True):
            st.session_state.pergunta_sugerida = "Qual subestação tem maior potência de geração distribuída?"
    
    with col3:
        if st.button("🚨 Quais subestações estão em risco?", use_container_width=True):
            st.session_state.pergunta_sugerida = "Quais subestações estão em risco crítico de geração distribuída?"
    
    col4, col5, col6 = st.columns(3)
    
    with col4:
        if st.button("🏠 Distribuição por classe", use_container_width=True):
            st.session_state.pergunta_sugerida = "Como está a distribuição de consumo por classe (residencial, comercial, industrial)?"
    
    with col5:
        if st.button("📈 Top 5 consumidores", use_container_width=True):
            st.session_state.pergunta_sugerida = "Me mostre as 5 subestações que mais consomem energia"
    
    with col6:
        if st.button("🔍 Estatísticas gerais", use_container_width=True):
            st.session_state.pergunta_sugerida = "Me dê um resumo das estatísticas gerais do sistema"
    
    st.markdown("---")
    
    st.markdown("### 💬 Conversa")
    
    chat_container = st.container()
    
    with chat_container:
        for msg in st.session_state.chat_mensagens:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(msg["content"])
            else:
                with st.chat_message("assistant"):
                    st.markdown(msg["content"])
    
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
        
        with st.spinner("Consultando dados..."):
            resultado = consultar_chat(pergunta_input, st.session_state.chat_historico)
        
        resposta_ia = resultado.get("resposta", "Erro ao processar resposta")
        
        # DEBUG: Verificar resposta
        print(f"🔍 DEBUG - Resposta recebida: {resposta_ia[:200] if resposta_ia else 'VAZIA'}")
        
        if not resposta_ia or resposta_ia.strip() == "":
            resposta_ia = "⚠️ Recebi uma resposta vazia da API. Tente novamente."
        
        st.session_state.chat_mensagens.append({
            "role": "assistant",
            "content": resposta_ia
        })
        
        st.session_state.chat_historico = resultado.get("historico_atualizado", [])
        
        st.rerun()
    
    st.markdown("---")
    if st.button("🗑️ Limpar Conversa"):
        st.session_state.chat_historico = []
        st.session_state.chat_mensagens = []
        st.rerun()
    
    st.markdown("---")
    st.caption("💡 Dica: Faça perguntas específicas sobre subestações, consumo, geração distribuída ou estatísticas do sistema")
    
    try:
        health = requests.get(f"{CHAT_API_URL}/health", timeout=2)
        if health.status_code == 200:
            info = health.json()
            if info.get("api_configured"):
                st.success(f"✅ Chat IA Online - Modelo: {info.get('model')}")
            else:
                st.warning("⚠️ API Key do Gemini não configurada! Adicione GEMINI_API_KEY no arquivo .env")
        else:
            st.error("❌ API de Chat não está respondendo corretamente")
    except:
        st.error("❌ API de Chat offline. Inicie o serviço com: `python src/ai/chat_service.py`")


if __name__ == "__main__":
    render_view()
