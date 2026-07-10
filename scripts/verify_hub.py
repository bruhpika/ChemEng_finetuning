import urllib.request
import json
import time

url = "https://huggingface.co/api/models/bruhpika/cheme-phi3-GGUF/tree/main"

for i in range(10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print("\n=========================================================")
            print("🎉 LIVE FILES VERIFIED ON HUGGING FACE HUB:")
            print("=========================================================")
            for item in data:
                print(f" -> {item.get('path')} ({item.get('size', 0) / (1024**3):.2f} GB)")
            break
    except Exception as e:
        time.sleep(2)
