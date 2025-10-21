import os
import streamlit as st
from langchain import hub
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma



st.set_page_config(page_title="PROCON Digital", page_icon="⚖️", layout="centered")

st.title("⚖️ PROCON Digital - Assistente Virtual")
st.markdown("Tire suas dúvidas sobre o Código de Defesa do Consumidor e outras leis relacionadas.")


# --- 2. Função de Cache para Carregar o Backend (RAG Chain) ---
# A anotação @st.cache_resource garante que esta função complexa
# só será executada uma vez, na primeira vez que o app for carregado.
# O resultado (a rag_chain) fica em cache para as execuções seguintes.
@st.cache_resource
def load_rag_chain():
    """
    Função para carregar todos os componentes necessários e montar a RAG chain.
    O resultado desta função é armazenado em cache para performance.
    """
    # Usando o st.spinner para dar feedback visual durante a carga inicial
    with st.spinner("Inicializando o assistente... Carregando leis e modelos..."):
        # Carrega a API Key dos segredos do Streamlit

        try:
            # Tenta carregar do st.secrets (para deploy)
            mistral_api_key = st.secrets["MISTRAL_API_KEY"]
        except KeyError:
            # Se não encontrar, tenta carregar de uma variável de ambiente (para dev local)
            mistral_api_key = os.environ.get("MISTRAL_API_KEY")

        if not mistral_api_key:
            st.error(
                "A MISTRAL_API_KEY não foi encontrada. Configure-a no arquivo .streamlit/secrets.toml ou como variável de ambiente.")
            st.stop()  # Interrompe a execução se a chave não for encontrada

        os.environ['MISTRAL_API_KEY'] = mistral_api_key

        # 1. Carregar Modelo
        model = ChatMistralAI(
            model_name='mistral-large-latest',
            temperature=0,
            max_retries=2,
        )

        # 2. Carregar Documentos
        pdf_paths = ['lei_cdc.pdf', 'procon_lei.pdf', 'informacoes.pdf']  # Certifique-se que esses arquivos estão na mesma pasta
        all_pdf_pages = []
        for path in pdf_paths:
            try:
                loader = PyPDFLoader(path)

                all_pdf_pages.extend(loader.load())
            except Exception as e:
                st.error(f"Erro ao carregar o PDF '{path}'. Verifique se o arquivo existe.")
                return None

        # 3. Dividir Documentos em Chunks
        splitter_text = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )
        chunks = splitter_text.split_documents(documents=all_pdf_pages)

        if not chunks:
            st.error("Nenhum texto foi extraído dos PDFs. Verifique os arquivos.")
            return None

        # 4. Criar Embeddings e Vector Store (ChromaDB)
        embedding_mistral = MistralAIEmbeddings()
        store_vetor = Chroma.from_documents(
            documents=chunks,
            embedding=embedding_mistral,
            collection_name='procon_lei_mistral_st',  # Nome de coleção
        )
        retriever = store_vetor.as_retriever()

        # 5. Montar a RAG Chain
        prompt = hub.pull('rlm/rag-prompt')
        rag_chain = (
                {
                    'context': retriever,
                    'question': RunnablePassthrough()
                }
                | prompt
                | model
                | StrOutputParser()
        )

    st.success("Assistente pronto para uso!")
    return rag_chain


# --- 3. Carregar a Chain (usando a função de cache) ---
rag_chain = load_rag_chain()

# --- 4. Interface do Usuário (Frontend) ---

# Inicializa o histórico de chat na sessão do Streamlit
if "messages" not in st.session_state:
    st.session_state.messages = []

# Exibe as mensagens do histórico
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Campo de entrada para a pergunta do usuário (agora como um chat)
user_question = st.chat_input("Qual a sua dúvida?")

if user_question:
    if rag_chain:
        # Adiciona a pergunta do usuário ao histórico e exibe
        st.session_state.messages.append({"role": "user", "content": user_question})
        with st.chat_message("user"):
            st.markdown(user_question)

        # Mostra um "spinner" enquanto o backend processa
        with st.spinner("Analisando as leis e buscando a melhor resposta..."):
            try:
                # Obtém a resposta do RAG chain
                response = rag_chain.invoke(user_question)

                # Exibe a resposta do assistente
                with st.chat_message("assistant"):
                    st.markdown(response)

                # Adiciona a resposta do assistente ao histórico
                st.session_state.messages.append({"role": "assistant", "content": response})

            except Exception as e:
                st.error(f"Ocorreu um erro ao processar sua pergunta: {e}")
    else:
        st.warning("O sistema de RAG não pôde ser inicializado. Verifique os logs de erro.")