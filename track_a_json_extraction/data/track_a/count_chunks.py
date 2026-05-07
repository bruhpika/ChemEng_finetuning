import json
import os

def count_chunks(path):
    if not os.path.exists(path):
        return 0, 0
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        total = len(data)
        incomplete = sum(1 for c in data if c.get('flag') == 'INCOMPLETE')
        return total, incomplete

matlab_path = r'e:\hobbies\ChemEng_finetuning-main\track_a_json_extraction\data\track_a\chunks_MATLAB.json'
dwsim_path = r'e:\hobbies\ChemEng_finetuning-main\track_a_json_extraction\data\track_a\chunks_DWSIM.json'

m_total, m_inc = count_chunks(matlab_path)
d_total, d_inc = count_chunks(dwsim_path)

print(f"MATLAB: Total={m_total}, Incomplete={m_inc}, Complete={m_total - m_inc}")
print(f"DWSIM: Total={d_total}, Incomplete={d_inc}, Complete={d_total - d_inc}")

def print_one_complete(path):
    if not os.path.exists(path): return
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        complete = [c for c in data if c.get('flag') != 'INCOMPLETE']
        if complete:
            print(f"\n--- Example Complete Chunk from {os.path.basename(path)} ---")
            print(json.dumps(complete[0], indent=2))

print_one_complete(matlab_path)
print_one_complete(dwsim_path)
