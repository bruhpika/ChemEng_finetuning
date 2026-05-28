import json
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

def check_incompletes(path):
    if not os.path.exists(path):
        return set()
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return {c['source_url'] for c in data if c.get('flag') == 'INCOMPLETE'}

ta_dwsim = check_incompletes(str(ROOT_DIR / 'data' / 'processed' / 'blackboard' / 'tracking' / 'incomplete_chunks_DWSIM.json'))
ta_matlab = check_incompletes(str(ROOT_DIR / 'data' / 'processed' / 'blackboard' / 'tracking' / 'incomplete_chunks_MATLAB.json'))
tb_dwsim = check_incompletes(str(ROOT_DIR / 'data' / 'processed' / 'track_b' / 'incomplete_chunks_DWSIM.json'))
tb_matlab = check_incompletes(str(ROOT_DIR / 'data' / 'processed' / 'track_b' / 'incomplete_chunks_MATLAB.json'))

print(f"Track A DWSIM: {len(ta_dwsim)} URLs")
print(f"Track A MATLAB: {len(ta_matlab)} URLs")
print(f"Track B DWSIM: {len(tb_dwsim)} URLs")
print(f"Track B MATLAB: {len(tb_matlab)} URLs")
