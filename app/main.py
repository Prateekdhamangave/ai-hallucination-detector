import io
import csv
import json
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

import pandas as pd

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_CENTER

from app.llm_client import query_all_models
from app.evaluator import run_llm_judge, run_safety_test, run_robustness_test, classify_prompt
from app.database import (
    init_db,
    log_evaluation,
    log_hallucination_test,
    get_all_evaluations,
    get_all_hallucination_tests,
    log_judge_evaluation,
    get_judge_evaluations,
    log_benchmark_run,
    log_benchmark_result,
    get_benchmark_runs,
    get_benchmark_results,
    update_model_performance,
    get_model_performance_profiles
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


class PromptRequest(BaseModel):
    prompt: str

class EvalRequest(BaseModel):
    prompt: str
    expected: Optional[str] = None


# ─────────────────────────────────────────────
# EVALUATE ALL
# ─────────────────────────────────────────────

@app.post("/evaluate-all")
def evaluate_all(req: PromptRequest):
    try:
        prompt_category = classify_prompt(req.prompt)
        model_responses = query_all_models(req.prompt)
        judge_result = run_llm_judge(req.prompt, model_responses)

        results = {}
        for model, data in model_responses.items():
            response_text = data.get("response", "") if isinstance(data, dict) else str(data)
            latency = data.get("latency", 0) if isinstance(data, dict) else 0
            judge_scores = (judge_result.get("evaluations", {}) or judge_result.get("scores", {})).get(model, {}) or {}

            results[model] = {
                "response": response_text,
                "latency": round(latency, 3),
                "judge_scores": judge_scores
            }

            # ✅ Matches database.py signature exactly
            log_judge_evaluation(
                prompt=req.prompt,
                prompt_category=prompt_category,
                model=model,
                response=response_text,
                judge_scores=judge_scores,
                latency=latency,
                winner=judge_result.get("winner", "unknown")
            )

            # ✅ Matches database.py: is_winner not won
            update_model_performance(
                model=model,
                prompt_category=prompt_category,
                score=judge_scores.get("final_score", 0),
                is_winner=(judge_result.get("winner", "") == model)
            )

        return {
            "prompt": req.prompt,
            "prompt_category": prompt_category,
            "results": results,
            "judge": {
                "winner": judge_result.get("winner", "unknown"),
                "winner_explanation": judge_result.get("winner_explanation", ""),
                "judge_latency": judge_result.get("judge_latency", 0)
            }
        }
    except Exception as e:
        return {"error": True, "details": str(e)}


# ─────────────────────────────────────────────
# SAFETY TEST
# ─────────────────────────────────────────────

@app.post("/safety-test")
def safety_test():
    try:
        from app.llm_client import MODELS, query_llm
        results = {}
        leaderboard = []
        for model_key in MODELS.keys():
            def make_query_fn(mk):
                def query_fn(prompt, model_k=None):
                    return query_llm(prompt, mk)
                return query_fn
            result = run_safety_test(model_key, make_query_fn(model_key))
            results[model_key] = result
            leaderboard.append({
                "model": model_key,
                "safety_score": result["safety_score"],
                "safe_count": result["safe_count"],
                "total": result["total_tests"]
            })
        leaderboard.sort(key=lambda x: x["safety_score"], reverse=True)
        return {"results": results, "leaderboard": leaderboard}
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": True, "details": str(e)}


# ─────────────────────────────────────────────
# ROBUSTNESS TEST
# ─────────────────────────────────────────────

@app.post("/robustness-test")
def robustness_test(req: PromptRequest):
    try:
        from app.llm_client import MODELS, query_llm
        results = {}
        leaderboard = []
        for model_key in MODELS.keys():
            def make_query_fn(mk):
                def query_fn(prompt, model_k=None):
                    return query_llm(prompt, mk)
                return query_fn
            result = run_robustness_test(req.prompt, model_key, make_query_fn(model_key))
            results[model_key] = result
            leaderboard.append({
                "model": model_key,
                "robustness_score": result["robustness_score"]
            })
        leaderboard.sort(key=lambda x: x["robustness_score"], reverse=True)
        return {"results": results, "leaderboard": leaderboard}
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": True, "details": str(e)}


# ─────────────────────────────────────────────
# BENCHMARK UPLOAD
# ─────────────────────────────────────────────

@app.post("/benchmark/upload")
async def benchmark_upload(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))

        col = None
        for c in ["prompt", "question", "Prompt", "Question"]:
            if c in df.columns:
                col = c
                break
        if not col:
            raise HTTPException(status_code=400, detail="CSV must have a 'prompt' or 'question' column")

        prompts = df[col].dropna().tolist()
        run_name = f"Benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        all_results = []
        model_score_totals = {}
        model_wins = {}

        for prompt in prompts:
            category = classify_prompt(prompt)
            model_responses = query_all_models(prompt)
            judge_result = run_llm_judge(prompt, model_responses)
            winner = judge_result.get("winner", "unknown")

            row = {"prompt": prompt, "category": category, "winner": winner, "models": {}}

            for model, data in model_responses.items():
                response_text = data.get("response", "") if isinstance(data, dict) else str(data)
                judge_scores = (judge_result.get("evaluations", {}) or judge_result.get("scores", {})).get(model, {}) or {}
                final_score = judge_scores.get("final_score", 50)

                row["models"][model] = {
                    "response": response_text,
                    "final_score": final_score,
                    "factual_accuracy": judge_scores.get("factual_accuracy", 5),
                    "completeness": judge_scores.get("completeness", 5),
                    "clarity": judge_scores.get("clarity", 5),
                    "reasoning_quality": judge_scores.get("reasoning_quality", 5),
                    "latency": data.get("latency", 0) if isinstance(data, dict) else 0
                }

                if model not in model_score_totals:
                    model_score_totals[model] = []
                    model_wins[model] = 0
                model_score_totals[model].append(final_score)
                if winner == model:
                    model_wins[model] += 1

            all_results.append(row)

        avg_scores = {
            m: round(sum(s) / len(s), 1)
            for m, s in model_score_totals.items()
        }
        best_model = max(avg_scores, key=avg_scores.get)

        # ✅ log_benchmark_run first to get run_id
        run_id = log_benchmark_run(
            run_name=run_name,
            total_questions=len(prompts),
            models_tested=list(model_score_totals.keys()),
            best_model=best_model,
            avg_scores=avg_scores
        )

        # ✅ log_benchmark_result uses run_id + judge_scores dict
        for row in all_results:
            for model, mdata in row["models"].items():
                judge_scores_dict = {
                    "final_score": mdata["final_score"],
                    "factual_accuracy": mdata["factual_accuracy"],
                    "completeness": mdata["completeness"],
                    "clarity": mdata["clarity"],
                    "reasoning_quality": mdata["reasoning_quality"]
                }
                log_benchmark_result(
                    run_id=run_id,
                    prompt=row["prompt"],
                    prompt_category=row["category"],
                    model=model,
                    response=mdata["response"],
                    judge_scores=judge_scores_dict,
                    winner=row["winner"]
                )

        return {
            "run_id": run_id,
            "run_name": run_name,
            "total_questions": len(prompts),
            "best_model": best_model,
            "avg_scores": avg_scores,
            "model_wins": model_wins,
            "results": all_results
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


# ─────────────────────────────────────────────
# BENCHMARK HISTORY
# ─────────────────────────────────────────────

@app.get("/benchmark/history")
def benchmark_history():
    try:
        runs = get_benchmark_runs()
        result = []
        for run in runs:
            result.append({
                "id": run[0],
                "run_name": run[1],
                "total_questions": run[2],
                "models_tested": json.loads(run[3]) if run[3] else [],
                "best_model": run[4],
                "avg_scores": json.loads(run[5]) if run[5] else {},
                "timestamp": str(run[6])
            })
        return result
    except Exception as e:
        return []


# ─────────────────────────────────────────────
# HISTORY ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/judge-history")
def judge_history():
    try:
        rows = get_judge_evaluations()
        result = []
        for row in rows:
            # judge_evaluations columns:
            # 0:id 1:prompt 2:prompt_category 3:model 4:response
            # 5:factual_accuracy 6:completeness 7:clarity 8:reasoning_quality
            # 9:final_score 10:strengths 11:weaknesses 12:latency 13:winner 14:timestamp
            scores = {
                "factual_accuracy": row[5],
                "completeness": row[6],
                "clarity": row[7],
                "reasoning_quality": row[8],
                "final_score": row[9],
                "strengths": row[10],
                "weaknesses": row[11]
            }
            result.append({
                "id": row[0],
                "prompt": row[1],
                "category": row[2],
                "model": row[3],
                "response": row[4],
                "scores": scores,
                "winner": row[13],
                "strengths": row[10],
                "weaknesses": row[11],
                "latency": row[12],
                "timestamp": str(row[14])
            })
        return result
    except Exception as e:
        return []


@app.get("/history")
def history():
    try:
        rows = get_all_evaluations()
        return [{"id": r[0], "prompt": r[1], "model": r[2],
                 "response": r[3], "score": r[10], "timestamp": str(r[11])}
                for r in rows]
    except Exception as e:
        return []


@app.get("/hallucination-history")
def hallucination_history():
    try:
        return get_all_hallucination_tests()
    except Exception as e:
        return []


# ─────────────────────────────────────────────
# PERFORMANCE PROFILES
# ─────────────────────────────────────────────

@app.get("/performance-profiles")
def performance_profiles():
    try:
        rows = get_model_performance_profiles()
        return [{
            "model": row[1],
            "prompt_category": row[2],
            "avg_score": row[3],
            "win_count": row[4],
            "total_count": row[5],
            "win_rate": row[6],
            "updated_at": str(row[7])
        } for row in rows]
    except Exception as e:
        return []


# ─────────────────────────────────────────────
# GLOBAL DOWNLOADS — Evaluate tab
# ─────────────────────────────────────────────

@app.get("/download/csv")
def download_csv():
    rows = get_judge_evaluations()
    output = io.StringIO()
    writer = csv.writer(output)

    # Group by prompt+timestamp — pivoted format
    grouped = {}
    for row in rows:
        prompt = row[1]
        ts = str(row[14])[:16]
        key = f"{prompt}_{ts}"
        if key not in grouped:
            grouped[key] = {
                "prompt": prompt,
                "category": row[2] or "general",
                "winner": row[13],
                "timestamp": ts,
                "models": {}
            }
        model = row[3]
        grouped[key]["models"][model] = {
            "response": str(row[4] or "")[:200],
            "final_score": row[9] or 0,
            "factual_accuracy": row[5] or 0,
            "completeness": row[6] or 0,
            "clarity": row[7] or 0,
            "reasoning_quality": row[8] or 0,
            "strengths": row[10] or "",
            "weaknesses": row[11] or "",
            "latency": row[12] or 0
        }

    all_models = sorted(set(
        m for g in grouped.values() for m in g["models"].keys()
    ))

    header = ["Prompt", "Category", "Winner", "Timestamp"]
    for m in all_models:
        header += [
            f"{m}_Response", f"{m}_FinalScore", f"{m}_Accuracy",
            f"{m}_Completeness", f"{m}_Clarity", f"{m}_Reasoning",
            f"{m}_Strengths", f"{m}_Weaknesses", f"{m}_Latency"
        ]
    writer.writerow(header)

    for g in grouped.values():
        row_data = [g["prompt"], g["category"], g["winner"], g["timestamp"]]
        for m in all_models:
            md = g["models"].get(m, {})
            row_data += [
                md.get("response", ""), md.get("final_score", ""),
                md.get("factual_accuracy", ""), md.get("completeness", ""),
                md.get("clarity", ""), md.get("reasoning_quality", ""),
                md.get("strengths", ""), md.get("weaknesses", ""),
                md.get("latency", "")
            ]
        writer.writerow(row_data)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=evaluations.csv"}
    )


@app.get("/download/json")
def download_json():
    rows = get_judge_evaluations()
    data = []
    for row in rows:
        data.append({
            "id": row[0], "prompt": row[1], "category": row[2],
            "model": row[3], "response": row[4],
            "scores": {
                "factual_accuracy": row[5], "completeness": row[6],
                "clarity": row[7], "reasoning_quality": row[8],
                "final_score": row[9]
            },
            "strengths": row[10], "weaknesses": row[11],
            "latency": row[12], "winner": row[13], "timestamp": str(row[14])
        })
    output = json.dumps(data, indent=2)
    return StreamingResponse(
        io.BytesIO(output.encode()),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=evaluations.json"}
    )


@app.get("/download/pdf")
def download_pdf():
    rows = get_judge_evaluations()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            leftMargin=0.6*inch, rightMargin=0.6*inch,
                            topMargin=0.6*inch, bottomMargin=0.6*inch)
    styles = getSampleStyleSheet()
    elements = []

    title_s = ParagraphStyle("T", parent=styles["Title"],
        fontSize=20, textColor=colors.HexColor("#5eead4"), spaceAfter=4)
    h2_s = ParagraphStyle("H2", parent=styles["Heading2"],
        fontSize=13, textColor=colors.HexColor("#818cf8"), spaceBefore=12, spaceAfter=6)
    small_s = ParagraphStyle("S", parent=styles["Normal"],
        fontSize=8, textColor=colors.HexColor("#666666"))

    elements.append(Paragraph("AI Agent Evaluation Report", title_s))
    elements.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · Records: {len(rows)}",
        small_s))
    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph("Evaluation Summary", h2_s))

    grouped = {}
    for row in rows:
        key = row[1]
        if key not in grouped:
            grouped[key] = {"category": row[2], "winner": row[13], "models": {}}
        grouped[key]["models"][row[3]] = {"final_score": row[9] or 0}

    tdata = [["Prompt", "Category", "Winner", "Scores"]]
    for prompt, data in grouped.items():
        scores_str = " | ".join(f"{m}: {d['final_score']}" for m, d in data["models"].items())
        tdata.append([
            prompt[:60] + ("..." if len(prompt) > 60 else ""),
            data["category"] or "general",
            data["winner"] or "—",
            scores_str
        ])
    t = Table(tdata, colWidths=[2.8*inch, 0.9*inch, 1*inch, 2.1*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a1a1a")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#5eead4")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("GRID", (0,0), (-1,-1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("PADDING", (0,0), (-1,-1), 5),
    ]))
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=evaluations.pdf"}
    )


# ─────────────────────────────────────────────
# BENCHMARK HELPER FUNCTIONS
# ─────────────────────────────────────────────

def _get_run_info(run_id: int):
    runs = get_benchmark_runs()
    run = next((r for r in runs if r[0] == run_id), None)
    if not run:
        return None
    return {
        "id": run[0], "run_name": run[1], "total_questions": run[2],
        "models_tested": json.loads(run[3]) if run[3] else [],
        "best_model": run[4],
        "avg_scores": json.loads(run[5]) if run[5] else {},
        "timestamp": str(run[6])
    }


def _get_grouped_results(run_id: int):
    # benchmark_results columns:
    # 0:id 1:run_id 2:prompt 3:prompt_category 4:model 5:response
    # 6:final_score 7:factual_accuracy 8:completeness 9:clarity
    # 10:reasoning_quality 11:winner 12:timestamp
    rows = get_benchmark_results(run_id)
    grouped = {}
    for row in rows:
        prompt = row[2]
        if prompt not in grouped:
            grouped[prompt] = {
                "prompt": prompt,
                "category": row[3] or "general",
                "winner": row[11],
                "models": {}
            }
        grouped[prompt]["models"][row[4]] = {
            "response": str(row[5] or ""),
            "final_score": row[6] or 0,
            "factual_accuracy": row[7] or 0,
            "completeness": row[8] or 0,
            "clarity": row[9] or 0,
            "reasoning_quality": row[10] or 0,
        }
    return list(grouped.values())


def _get_category_analysis(results):
    cat_data = {}
    for item in results:
        cat = item["category"] or "general"
        if cat not in cat_data:
            cat_data[cat] = {}
        for model, mdata in item["models"].items():
            if model not in cat_data[cat]:
                cat_data[cat][model] = {"scores": [], "wins": 0, "total": 0}
            cat_data[cat][model]["scores"].append(mdata["final_score"])
            cat_data[cat][model]["total"] += 1
            if item["winner"] == model:
                cat_data[cat][model]["wins"] += 1
    analysis = {}
    for cat, models in cat_data.items():
        analysis[cat] = {}
        for model, d in models.items():
            s = d["scores"]
            analysis[cat][model] = {
                "avg_score": round(sum(s)/len(s), 1) if s else 0,
                "wins": d["wins"], "total": d["total"],
                "win_rate": round(d["wins"]/d["total"]*100, 1) if d["total"] else 0
            }
    return analysis


# ─────────────────────────────────────────────
# BENCHMARK DOWNLOAD — JSON
# ─────────────────────────────────────────────

@app.get("/download/benchmark/json/{run_id}")
def download_benchmark_json(run_id: int):
    run_info = _get_run_info(run_id)
    if not run_info:
        raise HTTPException(status_code=404, detail=f"Benchmark run {run_id} not found")
    results = _get_grouped_results(run_id)
    category_analysis = _get_category_analysis(results)
    data = {
        "report_title": "AI Agent Benchmark Report",
        "run_id": run_id,
        "run_name": run_info["run_name"],
        "timestamp": run_info["timestamp"],
        "exported_at": datetime.now().isoformat(),
        "summary": {
            "total_questions": run_info["total_questions"],
            "models_tested": run_info["models_tested"],
            "best_model": run_info["best_model"],
            "avg_scores": run_info["avg_scores"]
        },
        "category_analysis": category_analysis,
        "results": results
    }
    output = json.dumps(data, indent=2)
    return StreamingResponse(
        io.BytesIO(output.encode()),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=benchmark_report_{run_id}.json"}
    )


# ─────────────────────────────────────────────
# BENCHMARK DOWNLOAD — CSV (Pivoted)
# ─────────────────────────────────────────────

@app.get("/download/benchmark/csv/{run_id}")
def download_benchmark_csv(run_id: int):
    run_info = _get_run_info(run_id)
    if not run_info:
        raise HTTPException(status_code=404, detail=f"Benchmark run {run_id} not found")
    results = _get_grouped_results(run_id)
    category_analysis = _get_category_analysis(results)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["AI AGENT BENCHMARK REPORT"])
    writer.writerow(["Run Name", run_info["run_name"]])
    writer.writerow(["Timestamp", run_info["timestamp"]])
    writer.writerow(["Total Questions", run_info["total_questions"]])
    writer.writerow(["Best Model", run_info["best_model"].upper()])
    writer.writerow([])

    writer.writerow(["OVERALL AVERAGE SCORES"])
    writer.writerow(["Model", "Avg Score"])
    for model, score in run_info["avg_scores"].items():
        writer.writerow([model, score])
    writer.writerow([])

    writer.writerow(["PERFORMANCE BY CATEGORY"])
    writer.writerow(["Category", "Model", "Avg Score", "Wins", "Total Questions", "Win Rate %"])
    for cat, models in category_analysis.items():
        for model, d in models.items():
            writer.writerow([cat, model, d["avg_score"], d["wins"], d["total"], d["win_rate"]])
    writer.writerow([])

    writer.writerow(["PER QUESTION BENCHMARK RESULTS (PIVOTED)"])
    all_models = sorted(set(m for item in results for m in item["models"].keys()))
    header = ["#", "Prompt", "Category", "Winner"]
    for m in all_models:
        header += [f"{m}_FinalScore", f"{m}_Accuracy", f"{m}_Completeness",
                   f"{m}_Clarity", f"{m}_Reasoning"]
    writer.writerow(header)
    for i, item in enumerate(results):
        row = [i+1, item["prompt"], item["category"], item["winner"]]
        for m in all_models:
            md = item["models"].get(m, {})
            row += [md.get("final_score",""), md.get("factual_accuracy",""),
                    md.get("completeness",""), md.get("clarity",""),
                    md.get("reasoning_quality","")]
        writer.writerow(row)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=benchmark_report_{run_id}.csv"}
    )


# ─────────────────────────────────────────────
# BENCHMARK DOWNLOAD — PDF (Full Professional Report)
# ─────────────────────────────────────────────

@app.get("/download/benchmark/pdf/{run_id}")
def download_benchmark_pdf(run_id: int):
    run_info = _get_run_info(run_id)
    if not run_info:
        raise HTTPException(status_code=404, detail=f"Benchmark run {run_id} not found")

    results = _get_grouped_results(run_id)
    category_analysis = _get_category_analysis(results)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=0.65*inch, rightMargin=0.65*inch,
        topMargin=0.65*inch, bottomMargin=0.65*inch
    )
    styles = getSampleStyleSheet()
    elements = []

    title_s = ParagraphStyle("TT", parent=styles["Title"],
        fontSize=22, textColor=colors.HexColor("#5eead4"),
        spaceAfter=4, alignment=TA_CENTER)
    subtitle_s = ParagraphStyle("ST", parent=styles["Normal"],
        fontSize=10, textColor=colors.HexColor("#888888"),
        spaceAfter=2, alignment=TA_CENTER)
    h2_s = ParagraphStyle("H2", parent=styles["Heading2"],
        fontSize=13, textColor=colors.HexColor("#818cf8"),
        spaceBefore=14, spaceAfter=6)
    h3_s = ParagraphStyle("H3", parent=styles["Heading3"],
        fontSize=10, textColor=colors.HexColor("#5eead4"),
        spaceBefore=8, spaceAfter=4)
    small_s = ParagraphStyle("SM", parent=styles["Normal"],
        fontSize=8, textColor=colors.HexColor("#555555"))
    winner_s = ParagraphStyle("WN", parent=styles["Normal"],
        fontSize=11, textColor=colors.HexColor("#4ade80"),
        spaceBefore=4, spaceAfter=4)

    def make_table(data, col_widths, header_bg="#1a1a1a", header_fg="#5eead4"):
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor(header_bg)),
            ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor(header_fg)),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,0), 8),
            ("FONTSIZE", (0,1), (-1,-1), 7.5),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f4f4f4")]),
            ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#cccccc")),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("PADDING", (0,0), (-1,-1), 5),
        ]))
        return t

    # ── PAGE 1: Title + Executive Summary ──
    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph("AI Agent Benchmark Report", title_s))
    elements.append(Paragraph(f"Run: {run_info['run_name']}", subtitle_s))
    elements.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ·  "
        f"Questions: {run_info['total_questions']}  ·  "
        f"Models: {', '.join(run_info['models_tested'])}",
        subtitle_s
    ))
    elements.append(Spacer(1, 0.2*inch))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#5eead4")))
    elements.append(Spacer(1, 0.15*inch))

    elements.append(Paragraph("1. Executive Summary", h2_s))
    summary_data = [["Metric", "Value"]]
    summary_data.append(["Total Questions Evaluated", str(run_info["total_questions"])])
    summary_data.append(["Models Tested", ", ".join(run_info["models_tested"])])
    summary_data.append(["Best Performing Model", run_info["best_model"].upper()])
    for model, score in run_info["avg_scores"].items():
        summary_data.append([f"{model} — Average Score", str(score)])
    elements.append(make_table(summary_data, [3*inch, 3.8*inch]))
    elements.append(Spacer(1, 0.12*inch))
    elements.append(Paragraph(
        f"🏆  Best Model: {run_info['best_model'].upper()}  "
        f"(Avg Score: {run_info['avg_scores'].get(run_info['best_model'], 'N/A')})",
        winner_s
    ))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))

    # ── SECTION 2: Per Question Score Overview ──
    elements.append(Paragraph("2. Per Question Score Overview", h2_s))
    elements.append(Paragraph(
        "Each row = one question. Scores per model. Winner cell highlighted green.", small_s))
    elements.append(Spacer(1, 0.08*inch))

    all_models = sorted(set(m for item in results for m in item["models"].keys()))
    q_header = ["#", "Question", "Category", "Winner"] + \
               [f"{m}\nScore" for m in all_models]
    q_data = [q_header]
    for i, item in enumerate(results):
        q_short = (item["prompt"][:55] + "…") if len(item["prompt"]) > 55 else item["prompt"]
        row = [str(i+1), q_short, (item["category"] or "general").upper(), item["winner"] or "—"]
        for m in all_models:
            row.append(str(item["models"].get(m, {}).get("final_score", "—")))
        q_data.append(row)

    q_col_widths = [0.25*inch, 2.5*inch, 0.75*inch, 0.85*inch] + [0.65*inch]*len(all_models)
    qt = Table(q_data, colWidths=q_col_widths, repeatRows=1)
    qt_style = [
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a1a1a")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#5eead4")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 7.5),
        ("FONTSIZE", (0,1), (-1,-1), 7),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f4f4f4")]),
        ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#cccccc")),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("ALIGN", (1,1), (1,-1), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("PADDING", (0,0), (-1,-1), 4),
    ]
    for i, item in enumerate(results):
        winner = item.get("winner", "")
        for j, m in enumerate(all_models):
            if m == winner:
                col_idx = 4 + j
                qt_style.append(("BACKGROUND", (col_idx, i+1), (col_idx, i+1), colors.HexColor("#0d2a0d")))
                qt_style.append(("TEXTCOLOR", (col_idx, i+1), (col_idx, i+1), colors.HexColor("#4ade80")))
    qt.setStyle(TableStyle(qt_style))
    elements.append(qt)
    elements.append(Spacer(1, 0.15*inch))

    # ── SECTION 3: Category Performance ──
    elements.append(PageBreak())
    elements.append(Paragraph("3. Performance by Category", h2_s))
    elements.append(Paragraph(
        "How each model performs per question category. Higher avg score and win rate = better.",
        small_s))
    elements.append(Spacer(1, 0.1*inch))

    for cat, models in category_analysis.items():
        elements.append(Paragraph(f"Category: {cat.upper()}", h3_s))
        cat_data = [["Model", "Avg Score", "Wins", "Total Qs", "Win Rate"]]
        for j, (model, d) in enumerate(
            sorted(models.items(), key=lambda x: x[1]["avg_score"], reverse=True)
        ):
            medal = "🥇 " if j == 0 else "🥈 " if j == 1 else "🥉 "
            cat_data.append([medal+model, str(d["avg_score"]),
                             str(d["wins"]), str(d["total"]), f"{d['win_rate']}%"])
        elements.append(make_table(cat_data,
            [1.6*inch, 1*inch, 0.8*inch, 0.9*inch, 1*inch], header_fg="#facc15"))
        elements.append(Spacer(1, 0.1*inch))

    # ── SECTION 4: Detailed Scores Per Question ──
    elements.append(PageBreak())
    elements.append(Paragraph("4. Detailed Score Breakdown Per Question", h2_s))
    elements.append(Paragraph(
        "Full breakdown: Factual Accuracy · Completeness · Clarity · Reasoning · Final Score. "
        "Winner row highlighted green.", small_s))
    elements.append(Spacer(1, 0.08*inch))

    for i, item in enumerate(results):
        elements.append(Paragraph(f"Q{i+1}: {item['prompt']}", h3_s))
        elements.append(Paragraph(
            f"Category: {(item['category'] or 'general').upper()}   Winner: {item['winner'] or '—'}",
            small_s))
        detail_data = [["Model", "Final", "Accuracy", "Completeness", "Clarity", "Reasoning"]]
        model_list = list(item["models"].items())
        for model, mdata in model_list:
            is_w = model == item.get("winner", "")
            detail_data.append([
                ("🏆 " if is_w else "") + model,
                str(mdata.get("final_score", 0)),
                str(mdata.get("factual_accuracy", 0)),
                str(mdata.get("completeness", 0)),
                str(mdata.get("clarity", 0)),
                str(mdata.get("reasoning_quality", 0))
            ])
        dt = Table(detail_data,
                   colWidths=[1.4*inch, 0.7*inch, 0.85*inch, 1.05*inch, 0.75*inch, 1*inch])
        dt_style = [
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1f1f1f")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#a3e635")),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,0), 8),
            ("FONTSIZE", (0,1), (-1,-1), 7.5),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f9f9f9")]),
            ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#dddddd")),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("ALIGN", (0,1), (0,-1), "LEFT"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("PADDING", (0,0), (-1,-1), 4),
        ]
        for row_idx, (model, _) in enumerate(model_list):
            if model == item.get("winner", ""):
                dt_style.append(("BACKGROUND", (0, row_idx+1), (-1, row_idx+1), colors.HexColor("#e8fff0")))
                dt_style.append(("FONTNAME", (0, row_idx+1), (0, row_idx+1), "Helvetica-Bold"))
        dt.setStyle(TableStyle(dt_style))
        elements.append(dt)
        elements.append(Spacer(1, 0.12*inch))

    # ── Footer ──
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#5eead4")))
    elements.append(Spacer(1, 0.08*inch))
    elements.append(Paragraph(
        f"AI Agent Evaluation Platform  ·  Run: {run_info['run_name']}  ·  "
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ParagraphStyle("F", parent=styles["Normal"],
                       fontSize=7, textColor=colors.HexColor("#888888"), alignment=TA_CENTER)
    ))

    doc.build(elements)
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=benchmark_report_{run_id}.pdf"}
    )