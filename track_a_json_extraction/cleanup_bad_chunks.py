import json
import os

def clean_json(filename):
    if not os.path.exists(filename):
        return
    
    with open(filename, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except:
            return

    original_count = len(data)
    # Remove chunks that contain "Access Denied" or are clearly bot-blocked
    clean_data = [
        c for c in data 
        if "Access Denied" not in str(c.get("theory", "")) 
        and "Access Denied" not in str(c.get("topic", ""))
        and "You don't have permission to access" not in str(c.get("theory", ""))
    ]
    
    if len(clean_data) < original_count:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(clean_data, f, indent=2)
        print(f"Cleaned {filename}: Removed {original_count - len(clean_data)} blocked chunks.")
    else:
        print(f"No blocked chunks found in {filename}.")

if __name__ == "__main__":
    os.chdir(os.path.join(os.path.dirname(__file__), "data", "track_a"))
    clean_json("chunks_MATLAB.json")
    clean_json("chunks_DWSIM.json")
    clean_json("incomplete_chunks_MATLAB.json")
    clean_json("incomplete_chunks_DWSIM.json")
