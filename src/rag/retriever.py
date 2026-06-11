import os
import json
import chromadb
from chromadb.utils import embedding_functions

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CHROMA_DB_DIR = os.path.join(PROJECT_ROOT, "data", "chroma_db")

class KBRetriever:
    def __init__(self):
        """Initializes the connection to the ChromaDB vector store."""
        # Connect to the persistent database on disk
        self.client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
        
        # Load the exact same embedding model used during the build process
        self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        
        # Load the collection
        self.collection = self.client.get_collection(
            name="cheme_kb",
            embedding_function=self.ef
        )
        
    def retrieve(self, query: str, software: str = None, top_k: int = 3):
        """
        Embeds the user query and retrieves the top_k most semantically relevant chunks.
        Optionally filters results to only include a specific software (DWSIM or MATLAB).
        """
        # Build a metadata filter if the user selected a specific software
        where_filter = {}
        if software and software != "Both":
            where_filter = {"software": software}
            
        # Execute the vector similarity search
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter
        )
        
        # Format the raw ChromaDB output into a friendly list of dictionaries
        retrieved_chunks = []
        if results['metadatas'] and len(results['metadatas'][0]) > 0:
            for i in range(len(results['metadatas'][0])):
                # Extract the full JSON string we saved during the build phase
                raw_data = json.loads(results['metadatas'][0][i]['raw_json'])
                retrieved_chunks.append({
                    "distance": results['distances'][0][i], # Lower distance = closer semantic match
                    "chunk": raw_data
                })
                
        return retrieved_chunks

# Quick test execution block
if __name__ == "__main__":
    retriever = KBRetriever()
    print("Testing retriever...")
    res = retriever.retrieve("How do I configure a PID controller?", software="MATLAB", top_k=2)
    for i, r in enumerate(res):
        print(f"\nResult {i+1} (Score: {r['distance']:.4f}):")
        print(f"Topic: {r['chunk']['topic']}")
        print(f"Source: {r['chunk']['source_url']}")
