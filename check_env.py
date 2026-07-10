import torch
import platform
import psutil

print("Python:", platform.python_version())
print("CUDA available:", torch.cuda.is_available())

mem = psutil.virtual_memory()
print(f"RAM Total: {mem.total/1e9:.1f}GB, Available: {mem.available/1e9:.1f}GB")

if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
    vram = torch.cuda.get_device_properties(0).total_memory / 1e9
    print(f"VRAM: {vram:.1f}GB")
else:
    print("No GPU detected - CPU only mode")

print("\nPhi-3-mini-4k-instruct model size: ~7.5GB fp16")
print(f"Can load in RAM: {'YES' if mem.available/1e9 > 8 else 'NO - NOT ENOUGH RAM'}")
