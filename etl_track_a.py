import pandas as pd
from pathlib import Path

# CONFIGURATION CONSTANTS
SOURCE_FILE   = "cheme-llm/sources.csv"
OUTPUT_DIR    = "track_a_json_extraction/data/"
TRACK_COLUMN  = "track"
TOOL_COLUMN   = "software"
TRACK_A_VALUE = "Track A"
SAMPLE_SIZE   = 4
RANDOM_SEED   = 42

def write_csv(df, filename):
    path = Path(OUTPUT_DIR) / filename
    df.to_csv(path, index=False)
    n = len(df)
    print(f"Written: {filename} — {n} rows")
    if n == 0: print(f"WARNING: {filename} is empty — check filter values.")

# 1. Read SOURCE_FILE
df = pd.read_csv(SOURCE_FILE)

# 2. Validate columns
missing = [c for c in [TRACK_COLUMN, TOOL_COLUMN] if c not in df.columns]
if missing:
    raise ValueError(f"Missing columns: {missing}. Found: {list(df.columns)}")

# 3. Filter Track A rows
track_a_df = df[df[TRACK_COLUMN] == TRACK_A_VALUE]

# 4. Create OUTPUT_DIR
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

# 5. Write sources_dwsim.csv
write_csv(track_a_df[track_a_df[TOOL_COLUMN] == "DWSIM"], "sources_dwsim.csv")

# 6. Write sources_matlab.csv
write_csv(track_a_df[track_a_df[TOOL_COLUMN] == "MATLAB"], "sources_matlab.csv")

# 7. Write sources_test.csv
test_sample = track_a_df.sample(n=min(SAMPLE_SIZE, len(track_a_df)), random_state=RANDOM_SEED)
write_csv(test_sample, "sources_test.csv")
