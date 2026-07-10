import urllib.request
import json
import zipfile
import os

def main():
    print("Fetching latest llama.cpp release...")
    url = "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        
    assets = data.get('assets', [])
    download_url = None
    for asset in assets:
        # Looking for windows AVX2 or similar build
        if 'bin-win-cpu-x64.zip' in asset['name']:
            download_url = asset['browser_download_url']
            break
            
    if not download_url:
        print("Could not find a suitable Windows release.")
        return
        
    zip_path = "llama-bin.zip"
    print(f"Downloading {download_url}...")
    urllib.request.urlretrieve(download_url, zip_path)
    
    print("Extracting...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall("llama-bin")
        
    print("Done! llama-quantize.exe should be in llama-bin/")

if __name__ == "__main__":
    main()
