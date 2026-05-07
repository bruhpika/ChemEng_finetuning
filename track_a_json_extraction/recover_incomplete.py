import json
import os

def recover():
    # Since we updated the chunk_size from 1500 to 2800 in agent.py,
    # the best way to recover incomplete chunks is to re-run the extraction
    # on the cached raw text. The original raw texts are saved in data/track_a/cache/.
    
    data_dir = os.path.join(os.path.dirname(__file__), "data", "track_a")
    
    files_to_backup = [
        "chunks_MATLAB.json",
        "chunks_DWSIM.json",
        "incomplete_chunks_MATLAB.json",
        "incomplete_chunks_DWSIM.json",
        "flagged_chunks.log"
    ]
    
    print("Backing up old chunk files and preparing for re-extraction...")
    for f in files_to_backup:
        path = os.path.join(data_dir, f)
        if os.path.exists(path):
            backup_path = path + ".bak"
            if os.path.exists(backup_path):
                os.remove(backup_path)
            os.rename(path, backup_path)
            print(f"Backed up {f} to {f}.bak")
            
    print("\nRecovery preparation complete.")
    print("Please run `python agent.py` to re-extract the cached texts using the improved 2800-char chunking and Playwright fallback.")

if __name__ == "__main__":
    recover()
