import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

def main():
    base_model_id = "microsoft/Phi-3-mini-4k-instruct"
    adapter_path = os.path.join(os.path.dirname(__file__), "..", "finetune", "adapter")
    output_path = os.path.join(os.path.dirname(__file__), "..", "finetune", "merged_model")

    print(f"Loading base model: {base_model_id}")
    # Load base model. Note: For merging, we often want to load in fp16 or bf16
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
        device_map="cpu"  # Force CPU to avoid VRAM OOM during merge if VRAM is small
    )

    print(f"Loading tokenizer: {base_model_id}")
    tokenizer = AutoTokenizer.from_pretrained(base_model_id)

    print(f"Applying LoRA adapter from: {adapter_path}")
    model = PeftModel.from_pretrained(base_model, adapter_path)

    print("Merging weights... this may take a moment.")
    model = model.merge_and_unload()

    print(f"Saving merged model to: {output_path}")
    os.makedirs(output_path, exist_ok=True)
    model.save_pretrained(output_path, safe_serialization=True)
    tokenizer.save_pretrained(output_path)
    print("Done!")

if __name__ == "__main__":
    main()
