"""
ChemE-LLM — QLoRA Fine-Tuning Script for Google Colab (Phase 4)
---------------------------------------------------------------
This script fine-tunes the Microsoft Phi-3-mini model using the synthetic Q&A dataset
generated in Phase 3. It uses 4-bit quantization (QLoRA) to allow training on a 
free Google Colab T4 GPU.

INSTRUCTIONS FOR COLAB:
1. Open Google Colab and create a new notebook with a T4 GPU instance.
2. Run this in the first cell to install dependencies:
   !pip install -q -U transformers datasets trl peft bitsandbytes accelerate
3. Upload `finetune_dataset.jsonl` to your Google Drive.
4. Copy and paste the code below into Colab cells.
"""

# %% [Cell 1] Import Libraries & Mount Google Drive
import os
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer
from google.colab import drive

# Mount Google Drive so we can access the dataset and save the adapter permanently
drive.mount('/content/drive')
BASE_DIR = '/content/drive/MyDrive/ChemE_LLM' # Create this folder in your Drive!
os.makedirs(BASE_DIR, exist_ok=True)

DATASET_PATH = os.path.join(BASE_DIR, 'finetune_dataset.jsonl')
OUTPUT_DIR = os.path.join(BASE_DIR, 'adapter')

# %% [Cell 2] Load Tokenizer and Base Model in 4-bit
model_id = "microsoft/Phi-3-mini-4k-instruct"

print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
# Phi-3 does not have a pad token by default, use eos_token
tokenizer.pad_token = tokenizer.eos_token 

print("Configuring 4-bit quantization...")
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)

print("Loading base model onto GPU...")
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True,
)

# %% [Cell 3] Configure LoRA Adapter
model = prepare_model_for_kbit_training(model)

# These target modules work best for Phi-3 architecture
peft_config = LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
    target_modules=["o_proj", "qkv_proj", "gate_up_proj", "down_proj"] 
)

model = get_peft_model(model, peft_config)
model.print_trainable_parameters()

# %% [Cell 4] Load and Format Dataset
print(f"Loading dataset from {DATASET_PATH}...")
dataset = load_dataset("json", data_files=DATASET_PATH, split="train")

def format_prompt(example):
    """
    Formats the synthetic QA pairs into the exact prompt template 
    Phi-3 expects: <|user|> ... <|end|> <|assistant|> ... <|end|>
    """
    instruction = example.get("instruction", "")
    input_text = example.get("input", "")
    output = example.get("output", "")
    
    question = instruction
    if input_text:
        question += "\n" + input_text
        
    return {"text": f"<|user|>\n{question}<|end|>\n<|assistant|>\n{output}<|end|>"}

print("Formatting prompts...")
dataset = dataset.map(format_prompt)

# %% [Cell 5] Setup SFT Trainer and Train
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4, # Effective batch size = 8
    optim="paged_adamw_32bit",
    logging_steps=10,
    learning_rate=2e-4,
    fp16=True,
    max_grad_norm=0.3,
    num_train_epochs=1, # 1 epoch over ~5000 rows is perfect to prevent overfitting
    warmup_ratio=0.03,
    group_by_length=True,
    lr_scheduler_type="cosine",
    report_to="none", # Set to "wandb" if you use Weights & Biases
)

trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    peft_config=peft_config,
    dataset_text_field="text",
    max_seq_length=512, # Keeps VRAM usage low
    tokenizer=tokenizer,
    args=training_args,
)

print("Starting training! (This will take ~1-2 hours on a T4 GPU)...")
trainer.train()

# %% [Cell 6] Save the Fine-Tuned Adapter
print(f"Saving adapter weights to {OUTPUT_DIR}...")
trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print("Training complete! 🚀")
print("Download the 'adapter' folder from your Google Drive and put it in your local ChemEng_finetuning-main/finetune/ directory.")
