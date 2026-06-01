import os
import json
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, echo=False)

def get_connection():
    return engine.connect()

def init_db():
    with engine.connect() as conn:

        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS evaluations (
                id SERIAL PRIMARY KEY,
                prompt TEXT,
                model TEXT,
                response TEXT,
                expected TEXT,
                exact_match REAL,
                semantic_similarity REAL,
                keyword_overlap REAL,
                rouge_score REAL,
                bleu_score REAL,
                overall_score REAL,
                timestamp TEXT
            )
        '''))

        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS hallucination_tests (
                id SERIAL PRIMARY KEY,
                prompt TEXT,
                model TEXT,
                response TEXT,
                wikipedia_summary TEXT,
                wikipedia_title TEXT,
                wikipedia_url TEXT,
                hallucination_score REAL,
                alignment_score REAL,
                semantic_similarity REAL,
                keyword_overlap REAL,
                verdict TEXT,
                timestamp TEXT
            )
        '''))

        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS judge_evaluations (
                id SERIAL PRIMARY KEY,
                prompt TEXT,
                prompt_category TEXT,
                model TEXT,
                response TEXT,
                factual_accuracy REAL,
                completeness REAL,
                clarity REAL,
                reasoning_quality REAL,
                final_score REAL,
                strengths TEXT,
                weaknesses TEXT,
                latency REAL,
                winner TEXT,
                timestamp TEXT
            )
        '''))

        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS benchmark_runs (
                id SERIAL PRIMARY KEY,
                run_name TEXT,
                total_questions INTEGER,
                models_tested TEXT,
                best_model TEXT,
                avg_scores TEXT,
                timestamp TEXT
            )
        '''))

        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS benchmark_results (
                id SERIAL PRIMARY KEY,
                run_id INTEGER,
                prompt TEXT,
                prompt_category TEXT,
                model TEXT,
                response TEXT,
                final_score REAL,
                factual_accuracy REAL,
                completeness REAL,
                clarity REAL,
                reasoning_quality REAL,
                winner TEXT,
                timestamp TEXT
            )
        '''))

        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS model_performance (
                id SERIAL PRIMARY KEY,
                model TEXT,
                prompt_category TEXT,
                avg_score REAL,
                win_count INTEGER,
                total_count INTEGER,
                win_rate REAL,
                updated_at TEXT
            )
        '''))

        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS failure_patterns (
                id SERIAL PRIMARY KEY,
                prompt TEXT,
                model TEXT,
                failure_type TEXT,
                description TEXT,
                score REAL,
                timestamp TEXT
            )
        '''))

        conn.commit()
    print("✅ PostgreSQL tables initialized on Neon.tech")


# ─────────────────────────────────────────────
# EVALUATIONS
# ─────────────────────────────────────────────

def log_evaluation(prompt, model, response, expected, scores):
    with engine.connect() as conn:
        conn.execute(text('''
            INSERT INTO evaluations
            (prompt, model, response, expected, exact_match,
             semantic_similarity, keyword_overlap, rouge_score,
             bleu_score, overall_score, timestamp)
            VALUES (:prompt, :model, :response, :expected,
                    :exact_match, :semantic_similarity, :keyword_overlap,
                    :rouge_score, :bleu_score, :overall_score, :timestamp)
        '''), {
            "prompt": prompt,
            "model": model,
            "response": response,
            "expected": expected,
            "exact_match": scores.get("exact_match", 0),
            "semantic_similarity": scores.get("semantic_similarity", 0),
            "keyword_overlap": scores.get("keyword_overlap", 0),
            "rouge_score": scores.get("rouge_score", 0),
            "bleu_score": scores.get("bleu_score", 0),
            "overall_score": scores.get("overall_score", 0),
            "timestamp": datetime.now().isoformat()
        })
        conn.commit()

def get_all_evaluations():
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM evaluations ORDER BY timestamp DESC")
        )
        return result.fetchall()


# ─────────────────────────────────────────────
# HALLUCINATION TESTS
# ─────────────────────────────────────────────

def log_hallucination_test(prompt, model, response, wiki_data, hallucination_result):
    with engine.connect() as conn:
        conn.execute(text('''
            INSERT INTO hallucination_tests
            (prompt, model, response, wikipedia_summary, wikipedia_title,
             wikipedia_url, hallucination_score, alignment_score,
             semantic_similarity, keyword_overlap, verdict, timestamp)
            VALUES (:prompt, :model, :response, :wikipedia_summary,
                    :wikipedia_title, :wikipedia_url, :hallucination_score,
                    :alignment_score, :semantic_similarity,
                    :keyword_overlap, :verdict, :timestamp)
        '''), {
            "prompt": prompt,
            "model": model,
            "response": response,
            "wikipedia_summary": wiki_data.get("summary", ""),
            "wikipedia_title": wiki_data.get("title", ""),
            "wikipedia_url": wiki_data.get("url", ""),
            "hallucination_score": hallucination_result.get("hallucination_score", 0),
            "alignment_score": hallucination_result.get("alignment_score", 0),
            "semantic_similarity": hallucination_result.get("semantic_similarity", 0),
            "keyword_overlap": hallucination_result.get("keyword_overlap", 0),
            "verdict": hallucination_result.get("verdict", ""),
            "timestamp": datetime.now().isoformat()
        })
        conn.commit()

def get_all_hallucination_tests():
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM hallucination_tests ORDER BY timestamp DESC")
        )
        return result.fetchall()


# ─────────────────────────────────────────────
# JUDGE EVALUATIONS
# ─────────────────────────────────────────────

def log_judge_evaluation(prompt, prompt_category, model, response,
                          judge_scores, latency, winner):
    with engine.connect() as conn:
        conn.execute(text('''
            INSERT INTO judge_evaluations
            (prompt, prompt_category, model, response,
             factual_accuracy, completeness, clarity,
             reasoning_quality, final_score, strengths,
             weaknesses, latency, winner, timestamp)
            VALUES (:prompt, :prompt_category, :model, :response,
                    :factual_accuracy, :completeness, :clarity,
                    :reasoning_quality, :final_score, :strengths,
                    :weaknesses, :latency, :winner, :timestamp)
        '''), {
            "prompt": prompt,
            "prompt_category": prompt_category,
            "model": model,
            "response": response,
            "factual_accuracy": judge_scores.get("factual_accuracy", 0),
            "completeness": judge_scores.get("completeness", 0),
            "clarity": judge_scores.get("clarity", 0),
            "reasoning_quality": judge_scores.get("reasoning_quality", 0),
            "final_score": judge_scores.get("final_score", 0),
            "strengths": judge_scores.get("strengths", ""),
            "weaknesses": judge_scores.get("weaknesses", ""),
            "latency": latency,
            "winner": winner,
            "timestamp": datetime.now().isoformat()
        })
        conn.commit()

def get_judge_evaluations():
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM judge_evaluations ORDER BY timestamp DESC")
        )
        return result.fetchall()


# ─────────────────────────────────────────────
# BENCHMARK RUNS
# ─────────────────────────────────────────────

def log_benchmark_run(run_name, total_questions, models_tested,
                       best_model, avg_scores):
    with engine.connect() as conn:
        result = conn.execute(text('''
            INSERT INTO benchmark_runs
            (run_name, total_questions, models_tested,
             best_model, avg_scores, timestamp)
            VALUES (:run_name, :total_questions, :models_tested,
                    :best_model, :avg_scores, :timestamp)
            RETURNING id
        '''), {
            "run_name": run_name,
            "total_questions": total_questions,
            "models_tested": json.dumps(models_tested),
            "best_model": best_model,
            "avg_scores": json.dumps(avg_scores),
            "timestamp": datetime.now().isoformat()
        })
        run_id = result.fetchone()[0]
        conn.commit()
    return run_id

def log_benchmark_result(run_id, prompt, prompt_category,
                          model, response, judge_scores, winner):
    with engine.connect() as conn:
        conn.execute(text('''
            INSERT INTO benchmark_results
            (run_id, prompt, prompt_category, model, response,
             final_score, factual_accuracy, completeness,
             clarity, reasoning_quality, winner, timestamp)
            VALUES (:run_id, :prompt, :prompt_category, :model,
                    :response, :final_score, :factual_accuracy,
                    :completeness, :clarity, :reasoning_quality,
                    :winner, :timestamp)
        '''), {
            "run_id": run_id,
            "prompt": prompt,
            "prompt_category": prompt_category,
            "model": model,
            "response": response,
            "final_score": judge_scores.get("final_score", 0),
            "factual_accuracy": judge_scores.get("factual_accuracy", 0),
            "completeness": judge_scores.get("completeness", 0),
            "clarity": judge_scores.get("clarity", 0),
            "reasoning_quality": judge_scores.get("reasoning_quality", 0),
            "winner": winner,
            "timestamp": datetime.now().isoformat()
        })
        conn.commit()

def get_benchmark_runs():
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM benchmark_runs ORDER BY timestamp DESC")
        )
        return result.fetchall()

def get_benchmark_results(run_id):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM benchmark_results WHERE run_id=:run_id ORDER BY timestamp"),
            {"run_id": run_id}
        )
        return result.fetchall()


# ─────────────────────────────────────────────
# MODEL PERFORMANCE PROFILES
# model_performance columns:
# 0:id  1:model  2:prompt_category  3:avg_score
# 4:win_count  5:total_count  6:win_rate  7:updated_at
# ─────────────────────────────────────────────

def update_model_performance(model, prompt_category, score, is_winner):
    with engine.connect() as conn:
        result = conn.execute(text('''
            SELECT id, model, prompt_category, avg_score,
                   win_count, total_count, win_rate, updated_at
            FROM model_performance
            WHERE model=:model AND prompt_category=:prompt_category
        '''), {"model": model, "prompt_category": prompt_category})
        row = result.fetchone()

        if row:
            # row[3]=avg_score, row[4]=win_count, row[5]=total_count, row[6]=win_rate
            old_avg = row[3] or 0
            old_wins = row[4] or 0
            old_total = row[5] or 0

            new_total = old_total + 1
            new_wins = old_wins + (1 if is_winner else 0)
            new_avg = round((old_avg * old_total + score) / new_total, 4)
            new_win_rate = round(new_wins / new_total, 4)

            conn.execute(text('''
                UPDATE model_performance
                SET avg_score=:avg_score, win_count=:win_count,
                    total_count=:total_count, win_rate=:win_rate,
                    updated_at=:updated_at
                WHERE model=:model AND prompt_category=:prompt_category
            '''), {
                "avg_score": new_avg,
                "win_count": new_wins,
                "total_count": new_total,
                "win_rate": new_win_rate,
                "updated_at": datetime.now().isoformat(),
                "model": model,
                "prompt_category": prompt_category
            })
        else:
            conn.execute(text('''
                INSERT INTO model_performance
                (model, prompt_category, avg_score, win_count,
                 total_count, win_rate, updated_at)
                VALUES (:model, :prompt_category, :avg_score,
                        :win_count, :total_count, :win_rate, :updated_at)
            '''), {
                "model": model,
                "prompt_category": prompt_category,
                "avg_score": round(score, 4),
                "win_count": 1 if is_winner else 0,
                "total_count": 1,
                "win_rate": 1.0 if is_winner else 0.0,
                "updated_at": datetime.now().isoformat()
            })
        conn.commit()

def get_model_performance_profiles():
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM model_performance ORDER BY model, prompt_category")
        )
        return result.fetchall()