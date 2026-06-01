import traceback
try:
    from app.llm_client import query_all_models
    from app.evaluator import run_llm_judge, classify_prompt
    from app.database import log_benchmark_run, log_benchmark_result

    prompt = 'What is machine learning?'
    print('Step 1 - classify:', classify_prompt(prompt))

    responses = query_all_models(prompt)
    print('Step 2 - responses:', list(responses.keys()))

    judge = run_llm_judge(prompt, responses)
    print('Step 3 - judge winner:', judge.get('winner'))

    winner = judge.get('winner', 'unknown')
    judge_scores = judge.get('scores', {}).get('llama', {})
    print('Step 4 - judge_scores:', judge_scores)

    run_id = log_benchmark_run(
        run_name='test_run',
        total_questions=1,
        models_tested=['llama'],
        best_model='llama',
        avg_scores={'llama': 50}
    )
    print('Step 5 - run_id:', run_id)

    log_benchmark_result(
        run_id=run_id,
        prompt=prompt,
        prompt_category='factual',
        model='llama',
        response='test response',
        judge_scores=judge_scores,
        winner=winner
    )
    print('Step 6 - log_benchmark_result OK')
    print('ALL STEPS PASSED')

except Exception as e:
    print('CRASHED AT:', e)
    traceback.print_exc()
