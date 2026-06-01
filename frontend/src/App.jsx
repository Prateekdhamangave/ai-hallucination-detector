import axios from "axios";
import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Legend,
  ResponsiveContainer, Tooltip, XAxis, YAxis
} from "recharts";

const API = "http://127.0.0.1:8000";

const theme = {
  bg: "#0f0f0f", surface: "#1a1a1a", card: "#222222",
  border: "#2e2e2e", primary: "#e2e2e2", secondary: "#888888",
  accent: "#5eead4", text: "#f0f0f0", textMuted: "#666666",
  tableHeader: "#1f1f1f",
};

const modelColors = ["#5eead4", "#818cf8", "#fb923c"];

const categoryColors = {
  factual: "#5eead4", reasoning: "#818cf8", mathematical: "#facc15",
  coding: "#fb923c", medical: "#f87171", creative: "#a3e635", general: "#888888"
};

const getScoreColor = (score, max = 10) => {
  const ratio = score / max;
  if (ratio >= 0.8) return "#4ade80";
  if (ratio >= 0.6) return "#facc15";
  if (ratio >= 0.4) return "#fb923c";
  return "#f87171";
};

const getVerdictColor = (verdict) => {
  if (!verdict) return theme.secondary;
  if (verdict.includes("✅")) return "#4ade80";
  if (verdict.includes("⚠️")) return "#facc15";
  if (verdict.includes("🔶")) return "#fb923c";
  if (verdict.includes("❌")) return "#f87171";
  return theme.secondary;
};

function ScoreBar({ label, value, max = 10 }) {
  const pct = Math.round((value / max) * 100);
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ color: theme.secondary, fontSize: 11 }}>{label}</span>
        <span style={{ color: getScoreColor(value, max), fontWeight: "bold", fontSize: 11 }}>{value}/{max}</span>
      </div>
      <div style={{ background: theme.border, borderRadius: 4, height: 6 }}>
        <div style={{ background: getScoreColor(value, max), width: `${pct}%`, height: 6, borderRadius: 4 }} />
      </div>
    </div>
  );
}

function CategoryBadge({ category }) {
  const color = categoryColors[category] || "#888888";
  return (
    <span style={{
      background: color + "22", color: color,
      border: `1px solid ${color}`,
      padding: "3px 10px", borderRadius: 12, fontSize: 11, fontWeight: "bold"
    }}>
      {category?.toUpperCase() || "GENERAL"}
    </span>
  );
}

export default function App() {
  const [prompt, setPrompt] = useState("");
  const [results, setResults] = useState(null);
  const [judge, setJudge] = useState(null);
  const [promptCategory, setPromptCategory] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("evaluate");

  const [safetyResults, setSafetyResults] = useState(null);
  const [safetyLoading, setSafetyLoading] = useState(false);
  const [expandedModel, setExpandedModel] = useState(null);

  const [robustnessPrompt, setRobustnessPrompt] = useState("");
  const [robustnessResults, setRobustnessResults] = useState(null);
  const [robustnessLoading, setRobustnessLoading] = useState(false);
  const [expandedRobustModel, setExpandedRobustModel] = useState(null);

  const [benchmarkFile, setBenchmarkFile] = useState(null);
  const [benchmarkResults, setBenchmarkResults] = useState(null);
  const [benchmarkLoading, setBenchmarkLoading] = useState(false);
  const [benchmarkHistory, setBenchmarkHistory] = useState([]);

  const [profiles, setProfiles] = useState([]);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const handleEvaluate = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setResults(null);
    setJudge(null);
    setPromptCategory(null);
    try {
      const res = await axios.post(`${API}/evaluate-all`, { prompt });
      if (res.data.error) {
        alert("Error: " + res.data.details);
      } else {
        setResults(res.data.results);
        setJudge(res.data.judge);
        setPromptCategory(res.data.prompt_category);
      }
    } catch (err) {
      alert("Network Error: " + err.message);
    }
    setLoading(false);
  };

  const handleSafetyTest = async () => {
    setSafetyLoading(true);
    setSafetyResults(null);
    try {
      const res = await axios.post(`${API}/safety-test`);
      setSafetyResults(res.data);
    } catch (err) {
      alert("Error: " + err.message);
    }
    setSafetyLoading(false);
  };

  const handleRobustnessTest = async () => {
    if (!robustnessPrompt.trim()) return;
    setRobustnessLoading(true);
    setRobustnessResults(null);
    try {
      const res = await axios.post(`${API}/robustness-test`, { prompt: robustnessPrompt });
      setRobustnessResults(res.data);
    } catch (err) {
      alert("Error: " + err.message);
    }
    setRobustnessLoading(false);
  };

  const handleBenchmark = async () => {
    if (!benchmarkFile) return;
    setBenchmarkLoading(true);
    setBenchmarkResults(null);
    const formData = new FormData();
    formData.append("file", benchmarkFile);
    try {
      const res = await axios.post(`${API}/benchmark/upload`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      setBenchmarkResults(res.data);
    } catch (err) {
      alert("Error: " + err.message);
    }
    setBenchmarkLoading(false);
  };

  const handleLoadProfiles = async () => {
    try {
      const res = await axios.get(`${API}/performance-profiles`);
      setProfiles(res.data);
    } catch (err) {
      alert("Error loading profiles: " + err.message);
    }
  };

  const handleHistory = async () => {
    setHistoryLoading(true);
    setHistory([]);
    try {
      const res = await axios.get(`${API}/judge-history`);
      setHistory(res.data);
    } catch (err) {
      alert("Error loading history: " + err.message);
    }
    setHistoryLoading(false);
  };

  const handleBenchmarkHistory = async () => {
    try {
      const res = await axios.get(`${API}/benchmark/history`);
      setBenchmarkHistory(res.data);
    } catch (err) {
      console.error("Benchmark history error:", err.message);
    }
  };

  const getBarChartData = () => {
    if (!results) return [];
    return Object.entries(results).map(([model, data]) => ({
      model,
      Accuracy: data.judge_scores?.factual_accuracy ?? 0,
      Completeness: data.judge_scores?.completeness ?? 0,
      Clarity: data.judge_scores?.clarity ?? 0,
      Reasoning: data.judge_scores?.reasoning_quality ?? 0,
      "Final Score": data.judge_scores?.final_score ?? 0,
    }));
  };

  const getSafetyChartData = () => {
    if (!safetyResults) return [];
    return (safetyResults.leaderboard || []).map((item) => ({
      model: item.model, "Safety Score": item.safety_score,
    }));
  };

  const getRobustnessChartData = () => {
    if (!robustnessResults) return [];
    return (robustnessResults.leaderboard || []).map((item) => ({
      model: item.model, "Robustness Score": item.robustness_score,
    }));
  };

  const getBenchmarkChartData = () => {
    if (!benchmarkResults) return [];
    return Object.entries(benchmarkResults.avg_scores || {}).map(([model, score]) => ({
      model, "Avg Score": score
    }));
  };

  const getGroupedHistory = () => {
    const grouped = {};
    history.forEach((row) => {
      const key = row.prompt + "_" + (row.timestamp || "").slice(0, 16);
      if (!grouped[key]) {
        grouped[key] = {
          prompt: row.prompt,
          category: row.category,
          timestamp: row.timestamp,
          winner: row.winner,
          models: {}
        };
      }
      grouped[key].models[row.model] = {
        overall: row.scores?.final_score,
        strengths: row.strengths,
        weaknesses: row.weaknesses,
        response: row.response,
        latency: row.latency
      };
    });
    return Object.values(grouped).reverse();
  };

  const tabStyle = (tab) => ({
    padding: "10px 20px", border: "none", borderRadius: 8,
    cursor: "pointer", fontSize: 13, fontWeight: "bold",
    background: activeTab === tab ? theme.accent : "transparent",
    color: activeTab === tab ? "#0f0f0f" : theme.secondary,
  });

  const btnStyle = (color = theme.accent, disabled = false) => ({
    background: disabled ? theme.border : color,
    color: disabled ? theme.secondary : "#0f0f0f",
    padding: "11px 24px", border: "none", borderRadius: 8,
    cursor: disabled ? "not-allowed" : "pointer",
    fontSize: 14, fontWeight: "bold"
  });

  return (
    <div style={{ fontFamily: "'Segoe UI', Arial, sans-serif", background: theme.bg, minHeight: "100vh", color: theme.text, padding: 30 }}>
      <div style={{ maxWidth: 1300, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ marginBottom: 28, borderBottom: `1px solid ${theme.border}`, paddingBottom: 20 }}>
          <h1 style={{ color: theme.text, margin: 0, fontSize: 26 }}> AI Agent Evaluator</h1>
          <p style={{ color: theme.secondary, marginTop: 6, fontSize: 13 }}>
            Self-Improving AI Evaluation Platform · LLM-as-Judge · PostgreSQL · Safety · Robustness · Benchmark
          </p>
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 8, marginBottom: 24, flexWrap: "wrap" }}>
          <button style={tabStyle("evaluate")} onClick={() => setActiveTab("evaluate")}> Evaluate</button>
          <button style={tabStyle("benchmark")} onClick={() => { setActiveTab("benchmark"); handleBenchmarkHistory(); }}> Benchmark</button>
          <button style={tabStyle("safety")} onClick={() => setActiveTab("safety")}>Safety</button>
          <button style={tabStyle("robustness")} onClick={() => setActiveTab("robustness")}> Robustness</button>
          <button style={tabStyle("profiles")} onClick={() => { setActiveTab("profiles"); handleLoadProfiles(); }}> Profiles</button>
          <button style={tabStyle("history")} onClick={() => { setActiveTab("history"); handleHistory(); }}> History</button>
        </div>

        {/* Global Download Buttons */}
        <div style={{ display: "flex", gap: 10, marginBottom: 28, flexWrap: "wrap" }}>
          <a href={`${API}/download/pdf`} target="_blank" rel="noreferrer">
            <button style={{ ...btnStyle("#f87171"), fontSize: 12, padding: "8px 16px" }}> Download PDF</button>
          </a>
          <a href={`${API}/download/csv`} target="_blank" rel="noreferrer">
            <button style={{ ...btnStyle("#4ade80"), fontSize: 12, padding: "8px 16px" }}> Download CSV</button>
          </a>
          <a href={`${API}/download/json`} target="_blank" rel="noreferrer">
            <button style={{ ...btnStyle("#818cf8"), fontSize: 12, padding: "8px 16px" }}> Download JSON</button>
          </a>
        </div>

        {/* ── EVALUATE TAB ── */}
        {activeTab === "evaluate" && (
          <>
            <div style={{ background: theme.surface, padding: 24, borderRadius: 12, marginBottom: 28, border: `1px solid ${theme.border}` }}>
              <h2 style={{ color: theme.accent, marginTop: 0, fontSize: 17 }}> Ask Any Question</h2>
              <p style={{ color: theme.secondary, fontSize: 13, marginTop: -8 }}>
                Judge LLM automatically evaluates all responses · Prompt category auto-detected · Saved to PostgreSQL
              </p>
              <textarea rows={3}
                style={{ width: "100%", padding: 12, borderRadius: 8, border: `1px solid ${theme.border}`, background: theme.card, color: theme.text, fontSize: 14, resize: "vertical", outline: "none", boxSizing: "border-box", marginBottom: 16 }}
                value={prompt} onChange={(e) => setPrompt(e.target.value)}
                placeholder="e.g. What is machine learning? Explain quantum computing. Who was Nikola Tesla?" />
              <button onClick={handleEvaluate} disabled={loading} style={btnStyle(theme.accent, loading)}>
                {loading ? " Querying Models + Running Judge..." : " Evaluate All Models"}
              </button>
            </div>

            {judge && (
              <div style={{ background: "#0d1a0d", border: "1px solid #4ade80", borderRadius: 12, padding: 20, marginBottom: 20 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
                  <span style={{ fontSize: 28 }}></span>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                      <p style={{ color: "#4ade80", fontWeight: "bold", margin: 0, fontSize: 16 }}>
                        Winner: <span style={{ color: theme.text, fontSize: 20 }}>{judge.winner?.toUpperCase()}</span>
                      </p>
                      {promptCategory && <CategoryBadge category={promptCategory} />}
                    </div>
                    <p style={{ color: theme.secondary, fontSize: 13, margin: 0, marginTop: 4 }}>{judge.winner_explanation}</p>
                  </div>
                </div>
                {judge.judge_latency && (
                  <p style={{ color: theme.textMuted, fontSize: 11, margin: 0 }}>⏱ Judge evaluated in {judge.judge_latency}s</p>
                )}
              </div>
            )}

            {results && (
              <>
                <h2 style={{ color: theme.accent, fontSize: 17, marginBottom: 16 }}> Model Responses & Judge Scores</h2>
                <div style={{ display: "flex", gap: 16, marginBottom: 30, flexWrap: "wrap" }}>
                  {Object.entries(results).map(([model, data], idx) => {
                    const isWinner = judge?.winner === model;
                    return (
                      <div key={model} style={{ flex: "1 1 320px", background: theme.surface, border: `1px solid ${isWinner ? "#4ade80" : theme.border}`, borderRadius: 12, padding: 20, boxShadow: isWinner ? "0 0 20px rgba(74,222,128,0.1)" : "none" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                          <h3 style={{ color: modelColors[idx] || theme.accent, margin: 0, fontSize: 15 }}> {model} {isWinner ? "" : ""}</h3>
                          {data.latency && <span style={{ color: theme.textMuted, fontSize: 11 }}>⏱ {data.latency}s</span>}
                        </div>
                        <div style={{ textAlign: "center", marginBottom: 16, padding: 12, background: theme.card, borderRadius: 8 }}>
                          <div style={{ color: theme.secondary, fontSize: 11 }}>JUDGE FINAL SCORE</div>
                          <div style={{ color: getScoreColor(data.judge_scores?.final_score, 100), fontWeight: "bold", fontSize: 36 }}>
                            {data.judge_scores?.final_score ?? 0}
                          </div>
                          <div style={{ color: theme.textMuted, fontSize: 10 }}>out of 100</div>
                        </div>
                        <div style={{ marginBottom: 14 }}>
                          <ScoreBar label="Factual Accuracy" value={data.judge_scores?.factual_accuracy ?? 0} />
                          <ScoreBar label="Completeness" value={data.judge_scores?.completeness ?? 0} />
                          <ScoreBar label="Clarity" value={data.judge_scores?.clarity ?? 0} />
                          <ScoreBar label="Reasoning Quality" value={data.judge_scores?.reasoning_quality ?? 0} />
                        </div>
                        {data.judge_scores?.strengths && (
                          <div style={{ background: "#0d1a0d", border: "1px solid #1a3a1a", borderRadius: 8, padding: 10, marginBottom: 8 }}>
                            <span style={{ color: "#4ade80", fontSize: 11, fontWeight: "bold" }}> STRENGTH: </span>
                            <span style={{ color: theme.secondary, fontSize: 12 }}>{data.judge_scores.strengths}</span>
                          </div>
                        )}
                        {data.judge_scores?.weaknesses && (
                          <div style={{ background: "#1a0d0d", border: "1px solid #3a1a1a", borderRadius: 8, padding: 10, marginBottom: 14 }}>
                            <span style={{ color: "#f87171", fontSize: 11, fontWeight: "bold" }}> WEAKNESS: </span>
                            <span style={{ color: theme.secondary, fontSize: 12 }}>{data.judge_scores.weaknesses}</span>
                          </div>
                        )}
                        <div style={{ background: theme.card, padding: 12, borderRadius: 8, border: `1px solid ${theme.border}`, fontSize: 13, lineHeight: 1.7, whiteSpace: "pre-wrap", color: theme.primary, maxHeight: 160, overflowY: "auto" }}>
                          {data.response}
                        </div>
                      </div>
                    );
                  })}
                </div>

                <h2 style={{ color: theme.accent, fontSize: 17, marginBottom: 16 }}>Judge Score Comparison</h2>
                <div style={{ background: theme.surface, padding: 20, borderRadius: 12, border: `1px solid ${theme.border}`, marginBottom: 28 }}>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={getBarChartData()}>
                      <CartesianGrid strokeDasharray="3 3" stroke={theme.border} />
                      <XAxis dataKey="model" stroke={theme.secondary} tick={{ fill: theme.secondary }} />
                      <YAxis domain={[0, 100]} stroke={theme.secondary} tick={{ fill: theme.secondary }} />
                      <Tooltip contentStyle={{ background: theme.card, border: `1px solid ${theme.border}`, color: theme.text }} />
                      <Legend wrapperStyle={{ color: theme.secondary }} />
                      <Bar dataKey="Accuracy" fill="#5eead4" />
                      <Bar dataKey="Completeness" fill="#818cf8" />
                      <Bar dataKey="Clarity" fill="#fb923c" />
                      <Bar dataKey="Reasoning" fill="#facc15" />
                      <Bar dataKey="Final Score" fill="#4ade80" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <h2 style={{ color: theme.accent, fontSize: 17, marginBottom: 16 }}> Full Comparison Table</h2>
                <div style={{ background: theme.surface, borderRadius: 12, border: `1px solid ${theme.border}`, overflow: "auto", marginBottom: 30 }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 800 }}>
                    <thead>
                      <tr style={{ background: theme.tableHeader }}>
                        {["Model", "Final Score", "Accuracy", "Completeness", "Clarity", "Reasoning", "Latency", "Strengths", "Weaknesses"].map(h => (
                          <th key={h} style={{ padding: 12, color: theme.secondary, fontSize: 11, textAlign: "center", borderBottom: `1px solid ${theme.border}`, whiteSpace: "nowrap" }}>{h.toUpperCase()}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(results).map(([model, data]) => (
                        <tr key={model} style={{ textAlign: "center", borderBottom: `1px solid ${theme.border}` }}>
                          <td style={{ padding: 12, fontWeight: "bold", color: judge?.winner === model ? "#4ade80" : theme.text }}>{model} {judge?.winner === model ? "" : ""}</td>
                          <td style={{ padding: 12, fontWeight: "bold", color: getScoreColor(data.judge_scores?.final_score, 100) }}>{data.judge_scores?.final_score ?? 0}</td>
                          <td style={{ padding: 12, color: getScoreColor(data.judge_scores?.factual_accuracy) }}>{data.judge_scores?.factual_accuracy ?? 0}</td>
                          <td style={{ padding: 12, color: getScoreColor(data.judge_scores?.completeness) }}>{data.judge_scores?.completeness ?? 0}</td>
                          <td style={{ padding: 12, color: getScoreColor(data.judge_scores?.clarity) }}>{data.judge_scores?.clarity ?? 0}</td>
                          <td style={{ padding: 12, color: getScoreColor(data.judge_scores?.reasoning_quality) }}>{data.judge_scores?.reasoning_quality ?? 0}</td>
                          <td style={{ padding: 12, color: theme.secondary, fontSize: 12 }}>{data.latency ? `${data.latency}s` : "—"}</td>
                          <td style={{ padding: 12, color: "#4ade80", fontSize: 12, textAlign: "left", maxWidth: 150 }}>{data.judge_scores?.strengths ?? "—"}</td>
                          <td style={{ padding: 12, color: "#f87171", fontSize: 12, textAlign: "left", maxWidth: 150 }}>{data.judge_scores?.weaknesses ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}

        {/* ── BENCHMARK TAB ── */}
        {activeTab === "benchmark" && (
          <div>
            <div style={{ background: theme.surface, padding: 24, borderRadius: 12, marginBottom: 28, border: "1px solid #2e3a4e" }}>
              <h2 style={{ color: "#818cf8", marginTop: 0, fontSize: 17 }}> Benchmark Dataset Evaluation</h2>
              <p style={{ color: theme.secondary, fontSize: 13, marginTop: -8, lineHeight: 1.7 }}>
                Upload a CSV file with a <strong style={{ color: theme.primary }}>"prompt"</strong> or <strong style={{ color: theme.primary }}>"question"</strong> column.
                System evaluates all questions across all models automatically.
              </p>
              <div style={{ background: theme.card, padding: 14, borderRadius: 8, marginBottom: 16, border: `1px solid ${theme.border}` }}>
                <p style={{ color: theme.secondary, fontSize: 12, margin: 0, marginBottom: 8 }}> Your CSV should look like this:</p>
                <code style={{ color: "#4ade80", fontSize: 12, lineHeight: 2 }}>
                  prompt<br />
                  What is machine learning?<br />
                  Who invented the telephone?<br />
                  Explain quantum computing.
                </code>
              </div>
              <input type="file" accept=".csv"
                onChange={(e) => setBenchmarkFile(e.target.files[0])}
                style={{ display: "none" }} id="csv-upload" />
              <label htmlFor="csv-upload" style={{ ...btnStyle("#818cf8"), display: "inline-block", marginRight: 12, cursor: "pointer" }}>
                  Choose CSV File
              </label>
              {benchmarkFile && <span style={{ color: "#4ade80", fontSize: 13 }}> {benchmarkFile.name}</span>}
              <br /><br />
              <button onClick={handleBenchmark} disabled={benchmarkLoading || !benchmarkFile}
                style={btnStyle("#818cf8", benchmarkLoading || !benchmarkFile)}>
                {benchmarkLoading ? " Running Benchmark... (may take several minutes)" : " Run Full Benchmark"}
              </button>
            </div>

            {benchmarkResults && (
              <>
                <h2 style={{ color: "#818cf8", fontSize: 17, marginBottom: 16 }}> Benchmark Results</h2>
                <div style={{ display: "flex", gap: 16, marginBottom: 28, flexWrap: "wrap" }}>
                  <div style={{ flex: "1 1 180px", background: theme.surface, border: "1px solid #818cf8", borderRadius: 12, padding: 20, textAlign: "center" }}>
                    <div style={{ color: theme.secondary, fontSize: 12 }}>TOTAL QUESTIONS</div>
                    <div style={{ color: "#818cf8", fontWeight: "bold", fontSize: 36 }}>{benchmarkResults.total_questions}</div>
                  </div>
                  <div style={{ flex: "1 1 180px", background: theme.surface, border: "1px solid #4ade80", borderRadius: 12, padding: 20, textAlign: "center" }}>
                    <div style={{ color: theme.secondary, fontSize: 12 }}>BEST MODEL</div>
                    <div style={{ color: "#4ade80", fontWeight: "bold", fontSize: 28, marginTop: 8 }}>{benchmarkResults.best_model?.toUpperCase()}</div>
                  </div>
                  {Object.entries(benchmarkResults.avg_scores || {}).map(([model, score], idx) => (
                    <div key={model} style={{ flex: "1 1 150px", background: theme.surface, border: `1px solid ${modelColors[idx] || theme.border}`, borderRadius: 12, padding: 20, textAlign: "center" }}>
                      <div style={{ color: theme.secondary, fontSize: 12 }}>{model.toUpperCase()}</div>
                      <div style={{ color: modelColors[idx] || theme.accent, fontWeight: "bold", fontSize: 32, marginTop: 8 }}>{score}</div>
                      <div style={{ color: theme.textMuted, fontSize: 11 }}>avg score</div>
                      <div style={{ color: theme.secondary, fontSize: 12, marginTop: 4 }}> {benchmarkResults.model_wins?.[model] ?? 0} wins</div>
                    </div>
                  ))}
                </div>

                <div style={{ background: theme.surface, padding: 20, borderRadius: 12, border: `1px solid ${theme.border}`, marginBottom: 28 }}>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={getBenchmarkChartData()}>
                      <CartesianGrid strokeDasharray="3 3" stroke={theme.border} />
                      <XAxis dataKey="model" stroke={theme.secondary} tick={{ fill: theme.secondary }} />
                      <YAxis domain={[0, 100]} stroke={theme.secondary} tick={{ fill: theme.secondary }} />
                      <Tooltip contentStyle={{ background: theme.card, border: `1px solid ${theme.border}`, color: theme.text }} />
                      <Bar dataKey="Avg Score" fill="#818cf8" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <h2 style={{ color: "#818cf8", fontSize: 17, marginBottom: 16 }}> Per Question Results</h2>
                <div style={{ background: theme.surface, borderRadius: 12, border: `1px solid ${theme.border}`, overflow: "auto", marginBottom: 28 }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 700 }}>
                    <thead>
                      <tr style={{ background: theme.tableHeader }}>
                        {["#", "Prompt", "Category", "Winner", ...Object.keys(benchmarkResults.avg_scores || {}).map(m => m + " Score")].map(h => (
                          <th key={h} style={{ padding: 10, color: theme.secondary, fontSize: 11, textAlign: "center", borderBottom: `1px solid ${theme.border}`, whiteSpace: "nowrap" }}>{h.toUpperCase()}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(benchmarkResults.results || []).map((row, idx) => (
                        <tr key={idx} style={{ borderBottom: `1px solid ${theme.border}`, textAlign: "center" }}>
                          <td style={{ padding: 10, color: theme.textMuted, fontSize: 12 }}>{idx + 1}</td>
                          <td style={{ padding: 10, color: theme.text, fontSize: 12, textAlign: "left", maxWidth: 200 }}>{row.prompt}</td>
                          <td style={{ padding: 10 }}><CategoryBadge category={row.category} /></td>
                          <td style={{ padding: 10, color: "#4ade80", fontWeight: "bold", fontSize: 13 }}>{row.winner}</td>
                          {Object.keys(benchmarkResults.avg_scores || {}).map(model => (
                            <td key={model} style={{ padding: 10, color: getScoreColor(row.models[model]?.final_score, 100) }}>
                              {row.models[model]?.final_score ?? "—"}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {/* ── PAST BENCHMARK RUNS ── */}
            {benchmarkHistory.length > 0 && (
              <>
                <h2 style={{ color: "#818cf8", fontSize: 17, marginBottom: 16 }}> Past Benchmark Runs</h2>
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  {(benchmarkHistory || []).map((run) => (
                    <div key={run.id} style={{ background: theme.surface, border: `1px solid ${theme.border}`, borderRadius: 12, overflow: "hidden" }}>

                      {/* Run Header */}
                      <div style={{ padding: "16px 20px", background: theme.card, borderBottom: `1px solid ${theme.border}`, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
                        <div>
                          <div style={{ color: theme.text, fontWeight: "bold", fontSize: 15 }}>{run.run_name}</div>
                          <div style={{ color: theme.secondary, fontSize: 12, marginTop: 4 }}>
                            {run.total_questions} questions · Best Model:
                            <span style={{ color: "#4ade80", fontWeight: "bold", marginLeft: 4 }}>{run.best_model?.toUpperCase()}</span>
                            <span style={{ color: theme.textMuted, marginLeft: 12 }}>{run.timestamp?.slice(0, 16)}</span>
                          </div>
                        </div>
                        {/* Download buttons per run */}
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          <a href={`${API}/download/benchmark/pdf/${run.id}`} target="_blank" rel="noreferrer">
                            <button style={{ background: "#f87171", color: "#0f0f0f", padding: "7px 14px", border: "none", borderRadius: 6, fontSize: 11, fontWeight: "bold", cursor: "pointer" }}> PDF Report</button>
                          </a>
                          <a href={`${API}/download/benchmark/csv/${run.id}`} target="_blank" rel="noreferrer">
                            <button style={{ background: "#4ade80", color: "#0f0f0f", padding: "7px 14px", border: "none", borderRadius: 6, fontSize: 11, fontWeight: "bold", cursor: "pointer" }}> CSV Report</button>
                          </a>
                          <a href={`${API}/download/benchmark/json/${run.id}`} target="_blank" rel="noreferrer">
                            <button style={{ background: "#818cf8", color: "#0f0f0f", padding: "7px 14px", border: "none", borderRadius: 6, fontSize: 11, fontWeight: "bold", cursor: "pointer" }}> JSON Report</button>
                          </a>
                        </div>
                      </div>

                      {/* Avg Scores Row */}
                      <div style={{ padding: "14px 20px", display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center" }}>
                        {Object.entries(run.avg_scores).map(([model, score], idx) => (
                          <div key={model} style={{ textAlign: "center" }}>
                            <div style={{ color: modelColors[idx] || theme.accent, fontWeight: "bold", fontSize: 24 }}>{score}</div>
                            <div style={{ color: theme.secondary, fontSize: 11, marginTop: 2 }}>{model} avg</div>
                          </div>
                        ))}
                      </div>

                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {/* ── SAFETY TAB ── */}
        {activeTab === "safety" && (
          <div>
            <div style={{ background: theme.surface, padding: 24, borderRadius: 12, marginBottom: 28, border: "1px solid #3d2e2e" }}>
              <h2 style={{ color: "#f87171", marginTop: 0, fontSize: 17 }}>🛡️ Adversarial Safety Testing</h2>
              <p style={{ color: theme.secondary, fontSize: 13, marginTop: -8 }}>
                Tests all models against <strong style={{ color: theme.primary }}>8 adversarial prompts</strong> including jailbreaks, harmful requests, prompt injections.
              </p>
              <button onClick={handleSafetyTest} disabled={safetyLoading} style={btnStyle("#f87171", safetyLoading)}>
                {safetyLoading ? " Running Safety Tests..." : " Run Safety Tests on All Models"}
              </button>
            </div>

            {safetyResults && (
              <>
                <h2 style={{ color: "#f87171", fontSize: 17, marginBottom: 16 }}> Safety Leaderboard</h2>
                <div style={{ display: "flex", gap: 16, marginBottom: 28, flexWrap: "wrap" }}>
                  {(safetyResults.leaderboard || []).map((item, idx) => (
                    <div key={item.model} style={{ flex: "1 1 200px", background: theme.surface, border: `1px solid ${idx === 0 ? "#4ade80" : theme.border}`, borderRadius: 12, padding: 20, textAlign: "center" }}>
                      <div style={{ fontSize: 28 }}>{idx === 0 ? "🥇" : idx === 1 ? "🥈" : "🥉"}</div>
                      <div style={{ color: theme.text, fontWeight: "bold", fontSize: 16, marginTop: 8 }}>{item.model}</div>
                      <div style={{ color: item.safety_score >= 0.75 ? "#4ade80" : "#f87171", fontWeight: "bold", fontSize: 32, marginTop: 8 }}>
                        {(item.safety_score * 100).toFixed(0)}%
                      </div>
                      <div style={{ color: theme.secondary, fontSize: 12, marginTop: 4 }}>{item.safe_count}/{item.total} safe</div>
                    </div>
                  ))}
                </div>

                <div style={{ background: theme.surface, padding: 20, borderRadius: 12, border: `1px solid ${theme.border}`, marginBottom: 28 }}>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={getSafetyChartData()}>
                      <CartesianGrid strokeDasharray="3 3" stroke={theme.border} />
                      <XAxis dataKey="model" stroke={theme.secondary} tick={{ fill: theme.secondary }} />
                      <YAxis domain={[0, 1]} stroke={theme.secondary} tick={{ fill: theme.secondary }} />
                      <Tooltip contentStyle={{ background: theme.card, border: `1px solid ${theme.border}`, color: theme.text }} />
                      <Bar dataKey="Safety Score" fill="#4ade80" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <h2 style={{ color: "#f87171", fontSize: 17, marginBottom: 16 }}> Detailed Test Results</h2>
                {Object.entries((safetyResults.results || {})).map(([model, data], idx) => (
                  <div key={model} style={{ background: theme.surface, border: `1px solid ${theme.border}`, borderRadius: 12, marginBottom: 16, overflow: "hidden" }}>
                    <div onClick={() => setExpandedModel(expandedModel === model ? null : model)}
                      style={{ padding: "16px 20px", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                        <span style={{ color: modelColors[idx] || theme.accent, fontWeight: "bold", fontSize: 15 }}> {model}</span>
                        <span style={{ background: data.safety_score >= 0.75 ? "#0d2a0d" : "#2a0d0d", color: data.safety_score >= 0.75 ? "#4ade80" : "#f87171", padding: "4px 12px", borderRadius: 20, fontSize: 13, fontWeight: "bold" }}>
                          Safety: {(data.safety_score * 100).toFixed(0)}%
                        </span>
                        <span style={{ color: theme.secondary, fontSize: 12 }}>{data.safe_count}/{data.total_tests} passed</span>
                      </div>
                      <span style={{ color: theme.secondary }}>{expandedModel === model ? "▲ Hide" : "▼ Show Tests"}</span>
                    </div>
                    {expandedModel === model && (
                      <div style={{ borderTop: `1px solid ${theme.border}` }}>
                        {data.results.map((test, tidx) => (
                          <div key={tidx} style={{ padding: "16px 20px", borderBottom: `1px solid ${theme.border}`, background: tidx % 2 === 0 ? theme.card : theme.surface }}>
                            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                              <span style={{ color: theme.secondary, fontSize: 11, background: "#2a2a2a", padding: "3px 10px", borderRadius: 12 }}>{test.category}</span>
                              <span style={{ color: test.is_safe ? "#4ade80" : "#f87171", fontWeight: "bold", fontSize: 13 }}>{test.verdict}</span>
                            </div>
                            <p style={{ color: theme.secondary, fontSize: 12, margin: "6px 0", fontStyle: "italic" }}>"{test.prompt}"</p>
                            <p style={{ color: theme.primary, fontSize: 13, margin: 0 }}>{String(test.response || "").slice(0, 200)}{(test.response?.length || 0) > 200 ? "..." : ""}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </>
            )}
          </div>
        )}

        {/* ── ROBUSTNESS TAB ── */}
        {activeTab === "robustness" && (
          <div>
            <div style={{ background: theme.surface, padding: 24, borderRadius: 12, marginBottom: 28, border: "1px solid #2e3a2e" }}>
              <h2 style={{ color: "#a3e635", marginTop: 0, fontSize: 17 }}>🔁 Robustness Testing</h2>
              <p style={{ color: theme.secondary, fontSize: 13, marginTop: -8 }}>
                Generates <strong style={{ color: theme.primary }}>8 variations</strong> and tests if models give consistent answers.
              </p>
              <textarea rows={2}
                style={{ width: "100%", padding: 12, borderRadius: 8, border: "1px solid #2e3a2e", background: theme.card, color: theme.text, fontSize: 14, resize: "vertical", outline: "none", boxSizing: "border-box", marginBottom: 16 }}
                value={robustnessPrompt} onChange={(e) => setRobustnessPrompt(e.target.value)}
                placeholder="e.g. Who is the founder of Microsoft?" />
              <button onClick={handleRobustnessTest} disabled={robustnessLoading} style={btnStyle("#a3e635", robustnessLoading)}>
                {robustnessLoading ? " Testing Variations..." : " Run Robustness Test"}
              </button>
            </div>

            {robustnessResults && (
              <>
                <h2 style={{ color: "#a3e635", fontSize: 17, marginBottom: 16 }}> Robustness Leaderboard</h2>
                <div style={{ display: "flex", gap: 16, marginBottom: 28, flexWrap: "wrap" }}>
                  {(robustnessResults.leaderboard || []).map((item, idx) => (
                    <div key={item.model} style={{ flex: "1 1 200px", background: theme.surface, border: `1px solid ${idx === 0 ? "#a3e635" : theme.border}`, borderRadius: 12, padding: 20, textAlign: "center" }}>
                      <div style={{ fontSize: 28 }}>{idx === 0 ? "🥇" : idx === 1 ? "🥈" : "🥉"}</div>
                      <div style={{ color: theme.text, fontWeight: "bold", fontSize: 16, marginTop: 8 }}>{item.model}</div>
                      <div style={{ color: item.robustness_score >= 0.75 ? "#a3e635" : "#fb923c", fontWeight: "bold", fontSize: 32, marginTop: 8 }}>
                        {(item.robustness_score * 100).toFixed(0)}%
                      </div>
                      <div style={{ color: theme.secondary, fontSize: 12, marginTop: 4 }}>consistency</div>
                    </div>
                  ))}
                </div>

                <div style={{ background: theme.surface, padding: 20, borderRadius: 12, border: `1px solid ${theme.border}`, marginBottom: 28 }}>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={getRobustnessChartData()}>
                      <CartesianGrid strokeDasharray="3 3" stroke={theme.border} />
                      <XAxis dataKey="model" stroke={theme.secondary} tick={{ fill: theme.secondary }} />
                      <YAxis domain={[0, 1]} stroke={theme.secondary} tick={{ fill: theme.secondary }} />
                      <Tooltip contentStyle={{ background: theme.card, border: `1px solid ${theme.border}`, color: theme.text }} />
                      <Bar dataKey="Robustness Score" fill="#a3e635" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <h2 style={{ color: "#a3e635", fontSize: 17, marginBottom: 16 }}> Variation Results</h2>
                {Object.entries((robustnessResults.results || {})).map(([model, data], idx) => (
                  <div key={model} style={{ background: theme.surface, border: `1px solid ${theme.border}`, borderRadius: 12, marginBottom: 16, overflow: "hidden" }}>
                    <div onClick={() => setExpandedRobustModel(expandedRobustModel === model ? null : model)}
                      style={{ padding: "16px 20px", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                        <span style={{ color: modelColors[idx] || theme.accent, fontWeight: "bold", fontSize: 15 }}> {model}</span>
                        <span style={{ background: "#1a2a0d", color: "#a3e635", padding: "4px 12px", borderRadius: 20, fontSize: 13, fontWeight: "bold" }}>
                          {(data.robustness_score * 100).toFixed(0)}% consistent
                        </span>
                      </div>
                      <span style={{ color: theme.secondary }}>{expandedRobustModel === model ? "▲ Hide" : "▼ Show Variations"}</span>
                    </div>
                    {expandedRobustModel === model && (
                      <div style={{ borderTop: `1px solid ${theme.border}` }}>
                        {data.responses.map((item, ridx) => (
                          <div key={ridx} style={{ padding: "16px 20px", borderBottom: `1px solid ${theme.border}`, background: ridx % 2 === 0 ? theme.card : theme.surface }}>
                            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                              <span style={{ color: theme.secondary, fontSize: 11, background: "#2a2a2a", padding: "3px 10px", borderRadius: 12 }}>{item.type}</span>
                              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                                <span style={{ color: "#a3e635", fontSize: 12 }}>Consistency: {item.consistency_score}</span>
                                <span style={{ color: getVerdictColor(item.verdict), fontWeight: "bold", fontSize: 13 }}>{item.verdict}</span>
                              </div>
                            </div>
                            <p style={{ color: theme.secondary, fontSize: 12, margin: "6px 0", fontStyle: "italic" }}>"{item.prompt}"</p>
                            <p style={{ color: theme.primary, fontSize: 13, margin: 0 }}>{String(item.response || "").slice(0, 200)}{(item.response?.length || 0) > 200 ? "..." : ""}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </>
            )}
          </div>
        )}

        {/* ── PROFILES TAB ── */}
        {activeTab === "profiles" && (
          <div>
            <h2 style={{ color: theme.accent, fontSize: 17, marginBottom: 8 }}> Model Performance Profiles</h2>
            <p style={{ color: theme.secondary, fontSize: 13, marginBottom: 24 }}>
              Auto-learned from all evaluations. Shows which model performs best per question category.
            </p>
            {profiles.length === 0 ? (
              <p style={{ color: theme.secondary }}>No profile data yet. Run some evaluations first!</p>
            ) : (
              <div style={{ background: theme.surface, borderRadius: 12, border: `1px solid ${theme.border}`, overflow: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 700 }}>
                  <thead>
                    <tr style={{ background: theme.tableHeader }}>
                      {["Model", "Category", "Avg Score", "Wins", "Total", "Win Rate", "Updated"].map(h => (
                        <th key={h} style={{ padding: 12, color: theme.secondary, fontSize: 11, textAlign: "center", borderBottom: `1px solid ${theme.border}` }}>{h.toUpperCase()}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {profiles.map((row, idx) => (
                      <tr key={idx} style={{ textAlign: "center", borderBottom: `1px solid ${theme.border}` }}>
                        <td style={{ padding: 12, fontWeight: "bold", color: theme.text }}>{row.model}</td>
                        <td style={{ padding: 12 }}><CategoryBadge category={row.prompt_category} /></td>
                        <td style={{ padding: 12, fontWeight: "bold", color: getScoreColor(row.avg_score, 100) }}>{row.avg_score}</td>
                        <td style={{ padding: 12, color: "#4ade80" }}>{row.win_count}</td>
                        <td style={{ padding: 12, color: theme.secondary }}>{row.total_count}</td>
                        <td style={{ padding: 12, fontWeight: "bold", color: getScoreColor(row.win_rate, 1) }}>
                          {(row.win_rate * 100).toFixed(0)}%
                        </td>
                        <td style={{ padding: 12, color: theme.textMuted, fontSize: 11 }}>{row.updated_at?.slice(0, 16)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ── HISTORY TAB ── */}
        {activeTab === "history" && (
          <div>
            <h2 style={{ color: theme.accent, fontSize: 17, marginBottom: 16 }}> Evaluation History</h2>
            {historyLoading && (
              <p style={{ color: theme.secondary }}>⏳ Loading history...</p>
            )}
            {!historyLoading && history.length === 0 && (
              <p style={{ color: theme.secondary }}>No history yet. Run some evaluations first!</p>
            )}
            {!historyLoading && history.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                {getGroupedHistory().map((row, idx) => (
                  <div key={idx} style={{ background: theme.surface, border: `1px solid ${theme.border}`, borderRadius: 12, overflow: "hidden" }}>
                    <div style={{ padding: "16px 20px", borderBottom: `1px solid ${theme.border}`, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10, background: theme.card }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                        <span style={{ color: theme.text, fontWeight: "bold", fontSize: 15 }}>{row.prompt}</span>
                        {row.category && <CategoryBadge category={row.category} />}
                      </div>
                      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                        {row.winner && row.winner !== "unknown" && (
                          <span style={{ color: "#4ade80", fontSize: 13, fontWeight: "bold" }}> {row.winner}</span>
                        )}
                        <span style={{ color: theme.textMuted, fontSize: 11 }}>{row.timestamp?.slice(0, 16)}</span>
                      </div>
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap" }}>
                      {Object.entries(row.models).map(([model, data], midx) => (
                        <div key={model} style={{ flex: "1 1 300px", padding: 16, borderRight: `1px solid ${theme.border}`, borderBottom: `1px solid ${theme.border}` }}>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
                            <span style={{ color: modelColors[midx] || theme.accent, fontWeight: "bold", fontSize: 14 }}>
                                {model} {row.winner === model ? "" : ""}
                            </span>
                            <span style={{ color: getScoreColor(data.overall, 100), fontWeight: "bold", fontSize: 18 }}>
                              {data.overall ?? "—"}
                            </span>
                          </div>
                          {data.strengths && (
                            <div style={{ fontSize: 11, color: "#4ade80", marginBottom: 4 }}>✅ {data.strengths}</div>
                          )}
                          {data.weaknesses && (
                            <div style={{ fontSize: 11, color: "#f87171", marginBottom: 8 }}>⚠️ {data.weaknesses}</div>
                          )}
                          <div style={{ background: theme.card, padding: 10, borderRadius: 8, fontSize: 12, color: theme.secondary, lineHeight: 1.6, maxHeight: 130, overflowY: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                            {data.response ?? "No response recorded"}
                          </div>
                          {data.latency && (
                            <div style={{ color: theme.textMuted, fontSize: 11, marginTop: 6 }}>⏱ {data.latency}s</div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
