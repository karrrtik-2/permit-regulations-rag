import os
from typing import List, Optional, Any, Dict
from langchain_core.language_models import LLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
import streamlit as st
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from openai import OpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
import tempfile

load_dotenv()

from langchain_core.language_models import LLM
from typing import Optional, List, Any
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from openai import OpenAI
import os
api_key = os.getenv("DEEP_INFRA_KEY")
mongo_uri = os.getenv("MONGO_URI")

client = OpenAI(
    base_url="https://api.deepinfra.com/v1/openai",
    api_key=api_key
)
class CustomLLM(LLM):
    client: Any  # Declare the client attribute

    def __init__(self):
        super().__init__()
        # Initialize the OpenAI client
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @property
    def _llm_type(self) -> str:
        """Return the type of LLM."""
        return "custom_llm"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        # Enhanced prompt to handle structured data
        enhanced_prompt = f"""
        You are analyzing transportation orders data. Use the following structured information 
        along with the original text to answer questions accurately:
        
        {prompt}
        
        Please provide specific, to the point and very short answers based on both the structured analysis 
        and the original text content. If you're comparing multiple orders, mention specific 
        order IDs and relevant details.
        """
        
        messages = [{"role": "user", "content": enhanced_prompt}]
        
        with open("12345.txt", "a") as log_file:
            log_file.write("Data fed to LLM:\n")
            log_file.write(json.dumps(messages, indent=2))
            log_file.write("\n\n")
        
        stream = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=messages,
            temperature=0.2,
            top_p=1,
            max_tokens=300,
            stream=True
        )

        response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                response += chunk.choices[0].delta.content
        
        return response
    
def get_file_text(uploaded_files):
    text = ""
    for uploaded_file in uploaded_files:
        if uploaded_file.type == "application/pdf":
            # Save the uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                temp_pdf.write(uploaded_file.read())
                temp_pdf_path = temp_pdf.name

            # Extract text and track text-based pages
            pdf_reader = PdfReader(temp_pdf_path)
            text_based_pages = set()
            for page_number, page in enumerate(pdf_reader.pages, start=1):
                extracted_text = page.extract_text()
                if extracted_text:
                    text += extracted_text
                    text_based_pages.add(page_number)

            # Clean up temporary file
            os.remove(temp_pdf_path)
        elif uploaded_file.type == "text/plain":
            text += uploaded_file.read().decode("utf-8")
    
    return text

def get_text_chunks(text):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=50,
        chunk_overlap=10,
        length_function=len
    )
    chunks = text_splitter.split_text(text)
    return chunks

import json
from typing import Dict, List, Set

def parse_orders_data(text: str) -> List[Dict]:
    """Parse the text file containing multiple JSON objects into a structured format."""
    # Split the text into individual JSON objects
    orders = []
    current_json = ""
    lines = text.split('\n')
    for line in lines:
        current_json += line
        if line.strip() == '}':
            try:
                order_data = json.loads(current_json)
                orders.append(order_data['order'])
                current_json = ""
            except json.JSONDecodeError:
                continue
    return orders

def analyze_orders(orders: List[Dict]) -> Dict:
    """Create an analysis structure for quick querying."""
    analysis = {
        'states': {},  # States and their frequencies
        'common_states': set(),  # States that appear in all orders
        'routes': {},  # Route information by state
        'drivers': set(),  # All unique drivers
        'clients': set(),  # All unique clients
        'total_weights': {},  # Weight information by order
        'equipment': {
            'trucks': set(),
            'trailers': set()
        }
    }
    
    # First pass to collect all states
    all_states = set()
    for order in orders:
        states = {route['product_name'] for route in order.get('routeData', [])}
        all_states.update(states)
        
        # Add to frequencies
        for state in states:
            analysis['states'][state] = analysis['states'].get(state, 0) + 1
    
    # Find common states
    analysis['common_states'] = {
        state for state, freq in analysis['states'].items()
        if freq == len(orders)
    }
    
    # Collect other information
    for order in orders:
        # Add driver info
        if 'driverData' in order:
            driver_name = f"{order['driverData'].get('name', '')} {order['driverData'].get('last_name', '')}".strip()
            analysis['drivers'].add(driver_name)
            
        # Add client info
        if 'clientData' in order:
            client_name = f"{order['clientData'].get('name', '')} {order['clientData'].get('last_name', '')}".strip()
            analysis['clients'].add(client_name)
            
        # Add equipment info
        if 'truck_detail' in order:
            truck_info = f"{order['truck_detail'].get('year', '')} {order['truck_detail'].get('make', '')} {order['truck_detail'].get('model', '')}".strip()
            analysis['equipment']['trucks'].add(truck_info)
            
        if 'Trailer_Info' in order:
            trailer_info = f"{order['Trailer_Info'].get('year', '')} {order['Trailer_Info'].get('make', '')}".strip()
            analysis['equipment']['trailers'].add(trailer_info)
            
        # Add weight info
        analysis['total_weights'][order['id']] = order.get('totalWeight', 0)
    
    # Convert sets to lists for JSON serialization
    analysis['common_states'] = list(analysis['common_states'])
    analysis['drivers'] = list(analysis['drivers'])
    analysis['clients'] = list(analysis['clients'])
    analysis['equipment']['trucks'] = list(analysis['equipment']['trucks'])
    analysis['equipment']['trailers'] = list(analysis['equipment']['trailers'])
    
    return analysis

def get_vectorstore(text_chunks, analysis_data):
    """Modified vectorstore creation to include structured analysis data."""
    embeddings = OpenAIEmbeddings(
        model="text-embedding-ada-002",
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Add analysis data as additional context
    enhanced_chunks = text_chunks + [json.dumps(analysis_data)]
    
    vectorstore = FAISS.from_texts(texts=enhanced_chunks, embedding=embeddings)
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
    st.set_page_config(page_title="Chat with PDF", page_icon=":books:")
    st.header("Chat with your PDF 💬")
    
    if "conversation" not in st.session_state:
        st.session_state.conversation = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "analysis_data" not in st.session_state:
        st.session_state.analysis_data = None

    uploaded_files = st.file_uploader(
        "Upload your PDF or TXT Documents", 
        type=['pdf', 'txt'],
        accept_multiple_files=True
    )
    
    if st.button("Process"):
        with st.spinner("Processing"):
            raw_text = get_file_text(uploaded_files)
            
            # Parse and analyze orders
            orders = parse_orders_data(raw_text)
            analysis_data = analyze_orders(orders)
            st.session_state.analysis_data = analysis_data
            
            text_chunks = get_text_chunks(raw_text)
            vectorstore = get_vectorstore(text_chunks, analysis_data)
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