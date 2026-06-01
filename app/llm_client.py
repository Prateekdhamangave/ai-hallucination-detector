import os
import time
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

load_dotenv()

HF_API_TOKEN = os.getenv("HF_API_TOKEN")

client = InferenceClient(
    provider="novita",
    api_key=HF_API_TOKEN
)

AVAILABLE_MODELS = {
    "llama": "meta-llama/llama-3.1-8b-instruct",
    "deepseek_v3": "deepseek-ai/DeepSeek-V3",
    "qwen": "Qwen/Qwen2.5-72B-Instruct",
}

# Alias so both names work
MODELS = AVAILABLE_MODELS

JUDGE_MODEL = "meta-llama/llama-3.1-8b-instruct"

CACHE = {}

def query_llm(prompt: str, model_key: str = "llama", temperature: float = 0.2) -> dict:
    cache_key = f"{model_key}:{prompt}"
    if cache_key in CACHE:
        return CACHE[cache_key]

    model = AVAILABLE_MODELS.get(model_key, AVAILABLE_MODELS["llama"])

    for attempt in range(3):
        try:
            start_time = time.time()
            completion = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=temperature
            )
            latency = time.time() - start_time
            result = {
                "response": completion.choices[0].message.content,
                "latency": round(latency, 3),
                "model": model_key
            }
            CACHE[cache_key] = result
            return result
        except Exception as e:
            if attempt == 2:
                err = str(e)
                if "402" in err or "Payment Required" in err:
                    msg = "⚠️ API credits required. Add balance at novita.ai to enable this model."
                else:
                    msg = f"⚠️ Model unavailable: {err[:100]}"
                return {
                    "response": msg,
                    "latency": None,
                    "model": model_key,
                    "error": True
                }

def query_all_models(prompt: str) -> dict:
    results = {}
    with ThreadPoolExecutor(max_workers=len(AVAILABLE_MODELS)) as executor:
        futures = {
            executor.submit(query_llm, prompt, key): key
            for key in AVAILABLE_MODELS
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result(timeout=60)
            except TimeoutError:
                results[key] = {
                    "response": "Timeout error",
                    "latency": None,
                    "model": key
                }
    return results

def query_judge(prompt: str) -> dict:
    try:
        start_time = time.time()
        completion = client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.1
        )
        latency = time.time() - start_time
        return {
            "response": completion.choices[0].message.content,
            "latency": round(latency, 3),
            "model": "judge"
        }
    except Exception as e:
        return {
            "response": f"Error: {str(e)}",
            "latency": None,
            "model": "judge"
        }