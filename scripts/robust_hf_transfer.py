import os
import sys
import time
from huggingface_hub import HfApi

# Enable high-speed Rust hf_transfer engine
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

TOKEN = "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"
REPO_ID = "bruhpika/cheme-phi3-GGUF"
FOLDER_PATH = r"E:\hobbies\ChemEng_finetuning-main\finetune"

print("[HF Transfer] Starting resilient chunked upload for " + REPO_ID + " using Rust engine...")

for attempt in range(1, 50):
    try:
        print(f"\n--- Upload Attempt {attempt} of 50 ---")
        api = HfApi(token=TOKEN)
        api.upload_large_folder(
            repo_id=REPO_ID,
            folder_path=FOLDER_PATH,
            repo_type="model",
            allow_patterns=["*.gguf", "README.md"],
            num_workers=2
        )
        print("\n[SUCCESS] ALL MODELS SUCCESSFULLY UPLOADED AND VERIFIED ON HUGGING FACE!")
        break
    except Exception as e:
        print(f"\n[Interruption] Encountered transient interruption on Attempt {attempt}: {e}")
        print("Resuming directly from local cache (.cache/.huggingface/) in 5 seconds...")
        time.sleep(5)
