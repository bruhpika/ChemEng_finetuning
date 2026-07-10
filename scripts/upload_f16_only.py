import os
import sys
import time
import huggingface_hub.utils._http as _http
from huggingface_hub import HfApi

# Enable high-speed Rust hf_transfer engine
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

TOKEN = "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"
REPO_ID = "bruhpika/cheme-phi3-GGUF"
FILE_PATH = r"E:\hobbies\ChemEng_finetuning-main\finetune\cheme-phi3-f16.gguf"
REPO_PATH = "cheme-phi3-f16.gguf"

file_size_gb = os.path.getsize(FILE_PATH) / (1024**3)
print(f"[HF Direct LFS] Starting chunk-by-chunk LFS upload of {REPO_PATH} ({file_size_gb:.2f} GB)...")
print("[HF Direct LFS] Armed with automatic httpx session reset to completely eliminate dead socket crashes!")

for attempt in range(1, 10000):
    try:
        print(f"\n=======================================================")
        print(f"--- Upload Attempt {attempt} of 10000 ({time.strftime('%H:%M:%S')}) ---")
        print(f"=======================================================")
        
        # Reset the global singleton httpx session so we never get 'Cannot send a request, as the client has been closed.'
        if hasattr(_http, "_session"):
            _http._session = None
            
        api = HfApi(token=TOKEN)
        api.upload_file(
            path_or_fileobj=FILE_PATH,
            path_in_repo=REPO_PATH,
            repo_id=REPO_ID,
            repo_type="model",
            commit_message=f"Upload {REPO_PATH} (F16 Quantization)"
        )
        print("\n[SUCCESS] cheme-phi3-f16.gguf HAS BEEN SUCCESSFULLY UPLOADED AND COMMITTED TO HUGGING FACE!")
        break
    except Exception as e:
        print(f"\n[Transient Error on Attempt {attempt}] {e}")
        print("Resetting socket session and resuming in 5 seconds...")
        if hasattr(_http, "_session"):
            _http._session = None
        time.sleep(5)
