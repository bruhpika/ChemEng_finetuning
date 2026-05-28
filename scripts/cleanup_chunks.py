import json
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

def cleanup_chunks():
    knowledge_dir = str(ROOT_DIR / "data" / "processed" / "blackboard" / "knowledge")
    files = ["chunks_DWSIM.json", "chunks_MATLAB.json"]
    
    for filename in files:
        path = os.path.join(knowledge_dir, filename)
        if not os.path.exists(path):
            continue
            
        print(f"Cleaning {filename}...")
        with open(path, "r", encoding="utf-8") as f:
            try:
                chunks = json.load(f)
            except Exception as e:
                print(f"  Error reading {filename}: {e}")
                continue
        
        initial_count = len(chunks)
        # Filter out incomplete chunks
        # Also filter out chunks with error topics
        clean_chunks = [
            c for c in chunks 
            if c.get("flag") != "INCOMPLETE" 
            and c.get("topic") not in ["API_EXHAUSTED", "PARSE_ERROR", "404 Error Page", "UPLOAD_FAILED"]
        ]
        
        final_count = len(clean_chunks)
        removed = initial_count - final_count
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(clean_chunks, f, indent=2, ensure_ascii=False)
            
        print(f"  Removed {removed} incomplete/error chunks. Remaining: {final_count}")

    # Also remove the dedicated incomplete files if they exist
    inc_files = ["incomplete_chunks_DWSIM.json", "incomplete_chunks_MATLAB.json"]
    for filename in inc_files:
        path = os.path.join(str(ROOT_DIR / "data" / "processed" / "blackboard" / "tracking"), filename)
        if os.path.exists(path):
            os.remove(path)
            print(f"Removed dedicated incomplete file: {filename}")

if __name__ == "__main__":
    cleanup_chunks()
