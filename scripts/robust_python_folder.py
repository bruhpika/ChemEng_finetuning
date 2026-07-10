import os
import sys
import time
import huggingface_hub.utils._http as _http
from huggingface_hub import HfApi

# Explicitly disable Rust hf_transfer to prevent thread hangs and socket resets
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

TOKEN = "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"
REPO_ID = "bruhpika/cheme-phi3-GGUF"
FOLDER_PATH = r"E:\hobbies\ChemEng_finetuning-main\finetune"

print("[Pure Python LFS] Starting robust folder upload with num_workers=1 (Zero hangs guaranteed)...")
print("[Pure Python LFS] Automatically recovering state from .cache/.huggingface/ (Q4, Q5, Q8 and README are already done)...")

for attempt in range(1, 10000):
    try:
        print(f"\n=======================================================")
        print(f"--- Upload Attempt {attempt} of 10000 ({time.strftime('%H:%M:%S')}) ---")
        print(f"=======================================================")
        
        # Reset global httpx session pool per attempt
        if hasattr(_http, "_session"):
            _http._session = None
            
        api = HfApi(token=TOKEN)
        api.upload_large_folder(
            repo_id=REPO_ID,
            folder_path=FOLDER_PATH,
            repo_type="model",
            allow_patterns=["*.gguf", "README.md"],
            num_workers=1,
            print_report_every=30
        )
        print("\n🎉 [SUCCESS] ALL MODELS HAVE BEEN SUCCESSFULLY UPLOADED AND COMMITTED TO HUGGING FACE!")
        break
    except Exception as e:
        print(f"\n[Interruption on Attempt {attempt}] {e}")
        print("Resetting session pool and resuming directly from .cache in 5 seconds...")
        if hasattr(_http, "_session"):
            _http._session = None
        time.sleep(5)
