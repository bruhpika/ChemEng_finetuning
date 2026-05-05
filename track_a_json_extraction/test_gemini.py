import google.generativeai as genai
import os

# Load first key from file
key_path = os.path.abspath(os.path.join(os.getcwd(), "..", "gemini_api_key.txt"))
with open(key_path, "r") as f:
    for line in f:
        if "API KEY:" in line:
            key = line.split(":")[-1].strip()
            break

genai.configure(api_key=key)
model = genai.GenerativeModel("gemini-flash-latest")

try:
    print(f"Testing Gemini API with key ending in {key[-4:]}...")
    response = model.generate_content("Say hello")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
