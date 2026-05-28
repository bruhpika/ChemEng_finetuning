import json
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except Exception:
            return []

def save_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def purge_urls(main_path, incomplete_path):
    main_chunks = load_json(main_path)
    inc_chunks = load_json(incomplete_path)
    
    # Identify URLs with incomplete chunks
    affected_urls = {c['source_url'] for c in inc_chunks if c.get('flag') == 'INCOMPLETE'}
    if not affected_urls:
        print(f"No affected URLs for {main_path}")
        return
    
    # Filter out any chunk that belongs to an affected URL
    clean_main = [c for c in main_chunks if c['source_url'] not in affected_urls]
    removed = len(main_chunks) - len(clean_main)
    
    save_json(clean_main, main_path)
    # Clear the incomplete chunks file as they will be re-processed
    if os.path.exists(incomplete_path):
        os.remove(incomplete_path)
        
    print(f"Purged {removed} chunks from {len(affected_urls)} URLs in {main_path}")

print("Purging Track A...")
ta_knowledge_dir = str(ROOT_DIR / "data" / "processed" / "blackboard" / "knowledge")
ta_tracking_dir = str(ROOT_DIR / "data" / "processed" / "blackboard" / "tracking")
purge_urls(f"{ta_knowledge_dir}/chunks_DWSIM.json", f"{ta_tracking_dir}/incomplete_chunks_DWSIM.json")
purge_urls(f"{ta_knowledge_dir}/chunks_MATLAB.json", f"{ta_tracking_dir}/incomplete_chunks_MATLAB.json")

print("\nPurging Track B...")
tb_dir = str(ROOT_DIR / "data" / "processed" / "track_b")
purge_urls(f"{tb_dir}/chunks_DWSIM.json", f"{tb_dir}/incomplete_chunks_DWSIM.json")
purge_urls(f"{tb_dir}/chunks_MATLAB.json", f"{tb_dir}/incomplete_chunks_MATLAB.json")
