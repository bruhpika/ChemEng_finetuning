import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

base_model_id = "microsoft/Phi-3-mini-4k-instruct"
try:
    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(base_model_id, trust_remote_code=True)
    print("Loading model...")
    model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
