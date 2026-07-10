import os
import json
import chromadb
from chromadb.utils import embedding_functions

# Set absolute paths to our data directories
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CHROMA_DB_DIR = os.path.join(PROJECT_ROOT, "data", "chroma_db")

# List of all the KB chunk files we generated in Phase 2
KB_FILES = [
    os.path.join(PROJECT_ROOT, "data", "processed", "blackboard", "knowledge", "chunks_DWSIM.json"),
    os.path.join(PROJECT_ROOT, "data", "processed", "blackboard", "knowledge", "chunks_MATLAB.json"),
    os.path.join(PROJECT_ROOT, "data", "processed", "blackboard", "knowledge", "chunks__Part_1.json"),
    os.path.join(PROJECT_ROOT, "data", "processed", "blackboard", "knowledge", "chunks__Part_2.json"),
    os.path.join(PROJECT_ROOT, "data", "processed", "blackboard", "knowledge", "chunks__Part_3.json"),
    os.path.join(PROJECT_ROOT, "data", "processed", "blackboard", "knowledge", "chunks__Part_4.json"),
    os.path.join(PROJECT_ROOT, "data", "processed", "track_b", "chunks_DWSIM.json"),
    os.path.join(PROJECT_ROOT, "data", "processed", "track_b", "chunks_MATLAB.json"),
]

def load_all_chunks():
    """Reads all JSON files and combines them into one list of dictionaries."""
    chunks = []
    for file_path in KB_FILES:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                chunks.extend(data)
    return chunks

def format_chunk_for_embedding(chunk):
    """
    Combines the rich structured data (steps, theory, ui_paths) into a single 
    paragraph of text so the embedding model can understand the semantic meaning.
    """
    text_parts = [f"Topic: {chunk.get('topic', '')}"]
    
    if chunk.get('theory'):
        text_parts.append(f"Theory: {chunk.get('theory')}")
        
    if chunk.get('steps'):
        text_parts.append(f"Steps: {', '.join(chunk.get('steps'))}")
        
    if chunk.get('ui_paths'):
        text_parts.append(f"UI Paths: {', '.join(chunk.get('ui_paths'))}")
        
    if chunk.get('errors') and chunk.get('fixes'):
        text_parts.append(f"Errors: {', '.join(chunk.get('errors'))}")
        text_parts.append(f"Fixes: {', '.join(chunk.get('fixes'))}")
        
    return " | ".join(text_parts)

def build_vectorstore():
    print(f"Loading chunks from {len(KB_FILES)} files...")
    chunks = load_all_chunks()
    
    # Simple deduplication by chunk_id to ensure we don't store exact duplicates
    unique_chunks = {c["chunk_id"]: c for c in chunks if "chunk_id" in c}.values()
    print(f"Found {len(unique_chunks)} unique chunks.")

    print(f"Initializing ChromaDB at {CHROMA_DB_DIR}...")
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    
    # We use all-MiniLM-L6-v2 (from local snapshot when available for offline reliability)
    local_model_path = os.path.expanduser(
        "~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    )
    model_name = local_model_path if os.path.exists(local_model_path) else "all-MiniLM-L6-v2"
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
    
    # Create the database collection. We delete it first if it exists to ensure a fresh build.
    try:
        client.delete_collection("cheme_kb")
    except Exception:
        pass
        
    collection = client.create_collection(
        name="cheme_kb", 
        embedding_function=sentence_transformer_ef
    )
    
    docs = []
    metadatas = []
    ids = []
    
    for chunk in unique_chunks:
        doc_text = format_chunk_for_embedding(chunk)
        
        # We store the entire original chunk JSON as a string in metadata. 
        # This allows us to retrieve the structured data (to display in the Gradio UI)
        # just by doing a vector search, without needing a secondary database lookup.
        meta = {
            "software": chunk.get("software", "unknown"),
            "topic": chunk.get("topic", "unknown"),
            "source_type": chunk.get("source_type", "unknown"),
            "source_url": chunk.get("source_url", "unknown"),
            "raw_json": json.dumps(chunk)
        }
        
        docs.append(doc_text)
        metadatas.append(meta)
        ids.append(chunk["chunk_id"])
    
    print("Embedding and adding to ChromaDB (this may take a minute or two)...")
    # Add in batches to prevent memory spikes
    batch_size = 100
    for i in range(0, len(docs), batch_size):
        collection.add(
            documents=docs[i:i+batch_size],
            metadatas=metadatas[i:i+batch_size],
            ids=ids[i:i+batch_size]
        )
        print(f"Added batch {i//batch_size + 1}")
        
    print(f"Successfully built vector store with {collection.count()} chunks!")

if __name__ == "__main__":
    build_vectorstore()
