import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()
client = InferenceClient(provider="novita", api_key=os.getenv("HF_API_TOKEN"))

models_to_test = {
    "llama3_70b": "meta-llama/llama-3.1-70b-instruct",
    "llama3_3b": "meta-llama/Llama-3.2-3B-Instruct",
    "deepseek_v3": "deepseek-ai/DeepSeek-V3",
    "qwen_72b": "Qwen/Qwen2.5-72B-Instruct",
    "qwen_coder": "Qwen/Qwen2.5-Coder-32B-Instruct",
}

for name, model in models_to_test.items():
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hello, respond in one sentence"}],
            max_tokens=50
        )
        print(f"OK {name}: {r.choices[0].message.content[:100]}")
    except Exception as e:
        print(f"FAIL {name}: {str(e)[:80]}")
