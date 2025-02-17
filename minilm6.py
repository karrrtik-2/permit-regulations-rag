import os
from typing import List, Optional, Any, Dict
from langchain_core.language_models import LLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
import streamlit as st
from dotenv import load_dotenv
from PyPDF2 import PdfReader
import pandas as pd
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from openai import OpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain

load_dotenv()

class CustomLLM(LLM):
    client: Optional[OpenAI] = None
    
    def __init__(self):
        super().__init__()
        api_key = os.getenv("DEEP_INFRA_KEY")
        if not api_key:
            raise ValueError("DEEP_INFRA_KEY not found in .env file")
        
        self.client = OpenAI(
            base_url="https://api.deepinfra.com/v1/openai",
            api_key=api_key
        )

    @property
    def _llm_type(self) -> str:
        return "custom_llama"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        messages = [{"role": "user", "content": prompt}]
        
        stream = self.client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct",
            messages=messages,
            temperature=0.7,
            top_p=1,
            max_tokens=2048,
            stream=True
        )

        response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                response += chunk.choices[0].delta.content
        
        return response

def get_file_text(uploaded_files):
    text = ""
    for file in uploaded_files:
        try:
            if file.name.endswith('.pdf'):
                pdf_reader = PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text()
            elif file.name.endswith('.xlsx'):
                df = pd.read_excel(file)
                text += df.to_string()
            elif file.name.endswith('.csv'):
                # Try reading with different encodings if necessary
                try:
                    df = pd.read_csv(file, encoding='utf-8')
                except UnicodeDecodeError:
                    df = pd.read_csv(file, encoding='latin1')
                text += df.to_string()
        except Exception as e:
            st.error(f"Error reading file {file.name}: {e}")
    return text

def get_text_chunks(text):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        length_function=len
    )
    chunks = text_splitter.split_text(text)
    return chunks

def get_vectorstore(text_chunks):
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = FAISS.from_texts(texts=text_chunks, embedding=embeddings)
    return vectorstore

def get_conversation_chain(vectorstore):
    memory = ConversationBufferMemory(
        memory_key='chat_history',
        return_messages=True
    )
    
    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm=CustomLLM(),
        retriever=vectorstore.as_retriever(),
        memory=memory
    )
    return conversation_chain

def main():
    st.set_page_config(page_title="Chat with PDF, XLSX, and CSV", page_icon=":books:")
    st.header("Chat with your PDF, XLSX, and CSV 💬")
    
    if "conversation" not in st.session_state:
        st.session_state.conversation = None
    if "messages" not in st.session_state:
        st.session_state.messages = []

    uploaded_files = st.file_uploader(
        "Upload your PDF, XLSX, or CSV Documents", 
        type=['pdf', 'xlsx', 'csv'],
        accept_multiple_files=True
    )
    
    if st.button("Process"):
        with st.spinner("Processing"):
            raw_text = get_file_text(uploaded_files)
            text_chunks = get_text_chunks(raw_text)
            vectorstore = get_vectorstore(text_chunks)
            st.session_state.conversation = get_conversation_chain(vectorstore)
            st.success("Done!")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("What would you like to know about the documents?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if st.session_state.conversation is not None:
                response = st.session_state.conversation({"question": prompt})
                st.markdown(response['answer'])
                st.session_state.messages.append({"role": "assistant", "content": response['answer']})
            else:
                st.warning("Please process a document first!")

if __name__ == '__main__':
    main()