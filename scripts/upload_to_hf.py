import os
from huggingface_hub import HfApi, create_repo
from dotenv import load_dotenv

load_dotenv()
token = os.environ.get("HF_TOKEN")
api = HfApi(token=token)

# Get username
user_info = api.whoami()
username = user_info['name']
repo_id = f"{username}/cheme-phi3-gguf"

print(f"Creating repository: {repo_id}...")
try:
    create_repo(repo_id, token=token, exist_ok=True, private=False)
except Exception as e:
    print(f"Repo creation error: {e}")

files_to_upload = [
    "cheme-phi3-q4_k_m.gguf",
    "cheme-phi3-q5_k_m.gguf",
    "cheme-phi3-q8_0.gguf",
    "cheme-phi3-f16.gguf"
]

for file in files_to_upload:
    path = os.path.join("finetune", file)
    if os.path.exists(path):
        print(f"Uploading {file}...")
        api.upload_file(
            path_or_fileobj=path,
            path_in_repo=file,
            repo_id=repo_id,
            token=token
        )
        print(f"Uploaded {file}!")
    else:
        print(f"File {path} not found.")

print(f"All files uploaded to https://huggingface.co/{repo_id}")
