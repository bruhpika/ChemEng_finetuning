import os
from huggingface_hub import HfApi, login
import glob

token = "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"
login(token=token, add_to_git_credential=True)

api = HfApi()
repo_id = "bruhpika/cheme-phi3-GGUF"

print(f"Creating repository {repo_id}...")
api.create_repo(repo_id=repo_id, exist_ok=True, repo_type="model")

folder_path = r"E:\hobbies\ChemEng_finetuning-main\finetune"
files_to_upload = glob.glob(os.path.join(folder_path, "*.gguf"))
readme_path = os.path.join(folder_path, "README.md")
if os.path.exists(readme_path):
    files_to_upload.append(readme_path)

for file_path in files_to_upload:
    file_name = os.path.basename(file_path)
    print(f"Uploading {file_name}...")
    api.upload_file(
        path_or_fileobj=file_path,
        path_in_repo=file_name,
        repo_id=repo_id,
        repo_type="model"
    )

print("All files uploaded successfully!")
