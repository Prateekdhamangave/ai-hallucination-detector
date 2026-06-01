import traceback
import io
import sys

print("=== BENCHMARK UPLOAD DEBUG ===")

# Step 1: Test imports
print("\n[1] Testing imports...")
try:
    from app.llm_client import query_all_models, MODELS
    from app.evaluator import run_llm_judge, classify_prompt
    from app.database import log_benchmark_run, log_benchmark_result, update_model_performance
    import pandas as pd
    print("    OK - all imports successful")
    print("    MODELS keys:", list(MODELS.keys()))
except Exception as e:
    print("    FAILED:", e)
    traceback.print_exc()
    sys.exit(1)

# Step 2: Test CSV parsing
print("\n[2] Testing CSV parse...")
try:
    csv_content = b"prompt\nWhat is AI?\nWho invented Python?"
    df = pd.read_csv(io.BytesIO(csv_content))
    col = None
    for c in ["prompt", "question", "Prompt", "Question"]:
        if c in df.columns:
            col = c
            break
    prompts = df[col].dropna().tolist()
    print("    OK - prompts:", prompts)
except Exception as e:
    print("    FAILED:", e)
    traceback.print_exc()
    sys.exit(1)

# Step 3: Test single prompt flow
print("\n[3] Testing single prompt (What is AI?)...")
try:
    prompt = "What is AI?"
    category = classify_prompt(prompt)
    print("    classify OK:", category)

    model_responses = query_all_models(prompt)
    print("    query_all_models OK:", list(model_responses.keys()))

    judge_result = run_llm_judge(prompt, model_responses)
    winner = judge_result.get("winner", "unknown")
    scores = judge_result.get("scores", {})
    evaluations = judge_result.get("evaluations", {})
    print("    judge OK - winner:", winner)
    print("    judge keys:", list(judge_result.keys()))
    print("    evaluations:", evaluations)
    print("    scores:", scores)
except Exception as e:
    print("    FAILED:", e)
    traceback.print_exc()
    sys.exit(1)

# Step 4: Test building row data
print("\n[4] Testing row building...")
try:
    row = {"prompt": prompt, "category": category, "winner": winner, "models": {}}
    model_score_totals = {}
    model_wins = {}

    for model, data in model_responses.items():
        response_text = data.get("response", "") if isinstance(data, dict) else str(data)
        # Try both 'scores' and 'evaluations' keys
        judge_scores = judge_result.get("scores", {}).get(model, {}) or \
                       judge_result.get("evaluations", {}).get(model, {}) or {}
        final_score = judge_scores.get("final_score", 50)

        row["models"][model] = {
            "response": response_text,
            "final_score": final_score,
            "factual_accuracy": judge_scores.get("factual_accuracy", 5),
            "completeness": judge_scores.get("completeness", 5),
            "clarity": judge_scores.get("clarity", 5),
            "reasoning_quality": judge_scores.get("reasoning_quality", 5),
        }
        model_score_totals[model] = [final_score]
        model_wins[model] = 1 if winner == model else 0

    print("    OK - row models:", list(row["models"].keys()))
    print("    scores sample:", {m: row["models"][m]["final_score"] for m in row["models"]})
except Exception as e:
    print("    FAILED:", e)
    traceback.print_exc()
    sys.exit(1)

# Step 5: Test database logging
print("\n[5] Testing database logging...")
try:
    from datetime import datetime
    run_name = f"Debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    avg_scores = {m: round(sum(s)/len(s), 1) for m, s in model_score_totals.items()}
    best_model = max(avg_scores, key=avg_scores.get)

    run_id = log_benchmark_run(
        run_name=run_name,
        total_questions=1,
        models_tested=list(model_score_totals.keys()),
        best_model=best_model,
        avg_scores=avg_scores
    )
    print("    log_benchmark_run OK - run_id:", run_id)

    for model, mdata in row["models"].items():
        judge_scores_dict = {
            "final_score": mdata.get("final_score", 50),
            "factual_accuracy": mdata.get("factual_accuracy", 5),
            "completeness": mdata.get("completeness", 5),
            "clarity": mdata.get("clarity", 5),
            "reasoning_quality": mdata.get("reasoning_quality", 5)
        }
        log_benchmark_result(
            run_id=run_id,
            prompt=prompt,
            prompt_category=category,
            model=model,
            response=mdata["response"],
            judge_scores=judge_scores_dict,
            winner=winner
        )
        print(f"    log_benchmark_result OK for {model}")

    update_model_performance(
        model="llama",
        prompt_category=category,
        score=50.0,
        is_winner=True
    )
    print("    update_model_performance OK")
except Exception as e:
    print("    FAILED:", e)
    traceback.print_exc()
    sys.exit(1)

print("\n=== ALL STEPS PASSED - Bug is elsewhere ===")
print("Check your App.jsx frontend for the actual error")
