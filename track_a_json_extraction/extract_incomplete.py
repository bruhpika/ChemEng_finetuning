import json
import os

def main():
    track_a_dir = "data/track_a"
    files = [f for f in os.listdir(track_a_dir) if f.startswith("chunks_") and f.endswith(".json")]
    
    for filename in files:
        filepath = os.path.join(track_a_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        incomplete_chunks = [chunk for chunk in data if chunk.get("flag") == "INCOMPLETE"]
        
        if incomplete_chunks:
            out_filename = filename.replace("chunks_", "incomplete_chunks_")
            out_filepath = os.path.join(track_a_dir, out_filename)
            with open(out_filepath, 'w', encoding='utf-8') as f:
                json.dump(incomplete_chunks, f, indent=2)
            print(f"Extracted {len(incomplete_chunks)} incomplete chunks to {out_filename}")
        else:
            print(f"No incomplete chunks found in {filename}")

if __name__ == "__main__":
    main()
