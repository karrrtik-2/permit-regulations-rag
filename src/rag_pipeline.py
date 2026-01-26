import json
from typing import List, Dict, Any
from pymongo import MongoClient
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import ConversationChain
from langchain_core.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
import os
from dotenv import load_dotenv

class OrderAssistant:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Initialize MongoDB
        self.mongo_uri = os.getenv('MONGODB_URI')
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client['logistics_db']
        self.collection = self.db['orders']
        
        # Initialize OpenAI
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.embeddings = OpenAIEmbeddings(openai_api_key=self.openai_api_key)
        self.llm = ChatOpenAI(
            temperature=0,
            openai_api_key=self.openai_api_key
        )
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )
        
        # Setup vector search
        self.setup_vector_search()
        
        # Initialize conversation memory
        self.memory = ConversationBufferMemory()
        
        # Setup conversation chain
        self.conversation = self.setup_conversation_chain()

    def setup_vector_search(self):
        """Setup MongoDB indexes for vector and text search"""
        # Vector search index
        self.collection.create_index([("vector_embedding", "vectorSearch")])
        
        # Text search indexes
        self.collection.create_index([
            ("order.commodityDataValue.description", "text"),
            ("order.Company_Info.name", "text"),
            ("order.pickupFormattedAddress", "text"),
            ("order.deliveryFormatedAddress", "text"),
            ("order_status", "text")
        ])

    def process_document(self, doc: Dict[str, Any]) -> str:
        """Convert document fields into searchable text"""
        order = doc.get('order', {})
        commodity = order.get('commodityDataValue', {})
        company = order.get('Company_Info', {})
        
        searchable_text = f"""
        Order ID: {doc.get('id')}
        Status: {doc.get('order_status')}
        Company: {company.get('name')}
        DOT: {company.get('dot')}
        MC: {company.get('mc')}
        Pickup: {order.get('pickupFormattedAddress')}
        Delivery: {order.get('deliveryFormatedAddress')}
        Commodity: {commodity.get('description')}
        Weight: {commodity.get('weight')}
        Dimensions: {commodity.get('length', {}).get('feet')}'{commodity.get('length', {}).get('inch')}" x 
                   {commodity.get('width', {}).get('feet')}'{commodity.get('width', {}).get('inch')}" x 
                   {commodity.get('height', {}).get('feet')}'{commodity.get('height', {}).get('inch')}"
        Total Cost: {order.get('total')}
        Order Date: {doc.get('order_created_date')}
        """
        return searchable_text

    def ingest_documents(self, json_file_path: str):
        """Ingest documents from JSON file into MongoDB with vector embeddings"""
        with open(json_file_path, 'r') as file:
            documents = json.load(file)
        
        for doc in documents:
            # Process document into searchable text
            searchable_text = self.process_document(doc)
            
            # Create chunks
            chunks = self.text_splitter.split_text(searchable_text)
            
            # Create embeddings for each chunk
            for chunk in chunks:
                vector_embedding = self.embeddings.embed_query(chunk)
                
                # Store document with embedding
                doc_with_embedding = {
                    **doc,
                    'searchable_text': chunk,
                    'vector_embedding': vector_embedding
                }
                
                self.collection.insert_one(doc_with_embedding)

    def setup_conversation_chain(self):
        """Setup the conversation chain"""
        template = """
        Assistant: I am an AI assistant helping with logistics order information.
        
        Current conversation:
        {history}
        
        Human: {input}
        Assistant: Let me search the orders database to help you with that.
        """
        
        prompt = PromptTemplate(
            input_variables=["history", "input"],
            template=template
        )
        
        conversation = ConversationChain(
            llm=self.llm,
            memory=self.memory,
            prompt=prompt,
            verbose=True
        )
        
        return conversation

    def search_documents(self, query: str) -> List[Dict]:
        """Search for relevant documents using vector similarity"""
        query_vector = self.embeddings.embed_query(query)
        
        results = self.collection.aggregate([
            {
                "$search": {
                    "vector": {
                        "query": query_vector,
                        "path": "vector_embedding",
                        "numCandidates": 5
                    }
                }
            },
            {
                "$limit": 3
            }
        ])
        
        return list(results)

    def answer_question(self, query: str) -> Dict:
        """Answer questions based on the documents"""
        # Search for relevant documents
        relevant_docs = self.search_documents(query)
        
        # Prepare context from relevant documents
        context = "\n\n".join([doc.get('searchable_text', '') for doc in relevant_docs])
        
        # Prepare the full query with context
        full_query = f"Based on this information:\n{context}\n\nQuestion: {query}"
        
        # Get response using conversation chain
        response = self.conversation.predict(input=full_query)
        
        return {
            "question": query,
            "answer": response,
            "relevant_documents": relevant_docs
        }

def main():
    # Initialize the assistant
    assistant = OrderAssistant()
    
    # Ingest documents (only need to do this once)
    assistant.ingest_documents('123.json')
    
    print("Logistics Order Assistant initialized. Ask me questions about the orders!")
    
    while True:
        query = input("\nYour question (or type 'exit' to quit): ")
        
        if query.lower() == 'exit':
            break
        
        try:
            response = assistant.answer_question(query)
            print("\nAnswer:", response['answer'])
            
        except Exception as e:
            print(f"\nError: {str(e)}")
            print("Please try asking your question in a different way.")

if __name__ == "__main__":
    main()