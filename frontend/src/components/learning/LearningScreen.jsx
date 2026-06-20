import { useState, useEffect } from "react";
import { client } from "../../api/client";
import {
  Brain, TrendingUp, TrendingDown, Minus,
  CheckCircle2, XCircle, AlertTriangle, BarChart3,
  RefreshCw, Clock, Target, Activity
} from "lucide-react";
import clsx from "clsx";

const CAUSE_LABELS = {
  vehicle_breakdown: "Breakdown",
  accident: "Accident",
  pot_holes: "Potholes",
  tree_fall: "Tree Fall",
  water_logging: "Water Logging",
  construction: "Construction",
  protest: "Protest",
  public_event: "Public Event",
  vip_movement: "VIP Movement",
  procession: "Procession",
  none: "Other",
};

const CAUSE_COLORS = {
  vehicle_breakdown: "#F9E107",
  accident: "#ef4444",
  pot_holes: "#f97316",
  tree_fall: "#22c55e",
  water_logging: "#3b82f6",
  construction: "#a855f7",
  protest: "#ec4899",
  public_event: "#14b8a6",
  vip_movement: "#6366f1",
  procession: "#84cc16",
  none: "#6b7280",
};

function StatCard({ icon: Icon, label, value, sub, accent, trend }) {
  return (
    <div className={clsx(
      "bg-card border border-border rounded-xl p-4 flex flex-col gap-2",
      accent && "border-primary/30 bg-primary/5"
    )}>
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">{label}</span>
        <Icon className={clsx("w-4 h-4", accent ? "text-primary" : "text-muted-foreground")} />
      </div>
      <div className="flex items-end gap-2">
        <span className={clsx("text-2xl font-bold", accent ? "text-primary" : "text-foreground")}>
          {value ?? "—"}
        </span>
        {trend === "good" && <TrendingUp className="w-4 h-4 text-emerald-400 mb-1" />}
        {trend === "bad" && <TrendingDown className="w-4 h-4 text-red-400 mb-1" />}
        {trend === "neutral" && <Minus className="w-4 h-4 text-muted-foreground mb-1" />}
      </div>
      {sub && <p className="text-[10px] text-muted-foreground">{sub}</p>}
    </div>
  );
}

function MiniBar({ label, count, total, color }) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-muted-foreground w-24 shrink-0 truncate">{label}</span>
      <div className="flex-1 h-2 bg-muted/40 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-xs font-medium text-foreground w-6 text-right">{count}</span>
    </div>
  );
}

function DurationChart({ history }) {
  const withActual = history.filter(h => h.actual_duration_mins != null);
  if (withActual.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-xs text-muted-foreground border border-dashed border-border rounded-xl">
        No outcome data yet — submit actual durations via POST /api/v1/learning/outcome/:id
      </div>
    );
  }

  const maxVal = Math.max(...withActual.flatMap(h => [h.predicted_duration_mins || 0, h.actual_duration_mins || 0]));
  const chartH = 120;
  const chartW = 500;
  const pad = 32;
  const innerW = chartW - pad * 2;
  const innerH = chartH - 16;
  const step = Math.max(1, Math.floor(innerW / withActual.length));

  const toY = (v) => innerH - (v / (maxVal || 1)) * innerH;

  const predPath = withActual.map((h, i) =>
    `${i === 0 ? "M" : "L"}${pad + i * step},${toY(h.predicted_duration_mins || 0)}`
  ).join(" ");

  const actualPath = withActual.map((h, i) =>
    `${i === 0 ? "M" : "L"}${pad + i * step},${toY(h.actual_duration_mins || 0)}`
  ).join(" ");

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-4 text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1.5"><span className="w-6 h-0.5 bg-primary inline-block" /> Predicted</span>
        <span className="flex items-center gap-1.5"><span className="w-6 h-0.5 bg-emerald-400 inline-block" /> Actual</span>
      </div>
      <svg viewBox={`0 0 ${chartW} ${chartH}`} className="w-full" style={{ height: chartH }}>
        <path d={predPath} fill="none" stroke="#F9E107" strokeWidth="2" strokeLinejoin="round" />
        <path d={actualPath} fill="none" stroke="#22c55e" strokeWidth="2" strokeLinejoin="round" strokeDasharray="5,3" />
        {withActual.map((h, i) => (
          <g key={i}>
            <circle cx={pad + i * step} cy={toY(h.predicted_duration_mins || 0)} r="3" fill="#F9E107" />
            <circle cx={pad + i * step} cy={toY(h.actual_duration_mins || 0)} r="3" fill="#22c55e" />
          </g>
        ))}
      </svg>
      <p className="text-[10px] text-muted-foreground text-center">
        {withActual.length} incident{withActual.length !== 1 ? "s" : ""} with confirmed outcomes
      </p>
    </div>
  );
}

function RecentTable({ history }) {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border text-muted-foreground">
            <th className="text-left py-2 pr-3 font-medium">Corridor</th>
            <th className="text-left py-2 pr-3 font-medium">Cause</th>
            <th className="text-left py-2 pr-3 font-medium">Time</th>
            <th className="text-left py-2 pr-3 font-medium">Priority</th>
            <th className="text-right py-2 pr-3 font-medium">Pred. Dur.</th>
            <th className="text-right py-2 pr-3 font-medium">Actual</th>
            <th className="text-right py-2 font-medium">Closure</th>
          </tr>
        </thead>
        <tbody>
          {history.slice(0, 15).map((row, i) => {
            const hasDiff = row.actual_duration_mins != null;
            const diff = hasDiff ? row.actual_duration_mins - row.predicted_duration_mins : null;
            const diffGood = diff != null && Math.abs(diff) < 15;
            return (
              <tr key={row.id || i} className={clsx("border-b border-border/50 hover:bg-muted/20 transition-colors", row.disagreement_flag && "bg-warning/5")}>
                <td className="py-2 pr-3 truncate max-w-[120px] text-foreground font-medium">{row.corridor}</td>
                <td className="py-2 pr-3 text-muted-foreground">{CAUSE_LABELS[row.event_cause] || row.event_cause}</td>
                <td className="py-2 pr-3 text-muted-foreground">{days[row.day_of_week ?? 0]} {String(row.hour_of_day ?? 0).padStart(2, "0")}:00</td>
                <td className="py-2 pr-3">
                  <span className={clsx(
                    "px-1.5 py-0.5 rounded text-[10px] font-bold",
                    row.predicted_priority === "High"
                      ? "bg-red-500/15 text-red-400"
                      : "bg-muted text-muted-foreground"
                  )}>{row.predicted_priority}</span>
                </td>
                <td className="py-2 pr-3 text-right text-foreground">{Math.round(row.predicted_duration_mins || 0)}m</td>
                <td className="py-2 pr-3 text-right">
                  {hasDiff ? (
                    <span className={clsx("font-medium", diffGood ? "text-emerald-400" : "text-warning")}>
                      {Math.round(row.actual_duration_mins)}m
                    </span>
                  ) : (
                    <span className="text-muted-foreground/50">—</span>
                  )}
                </td>
                <td className="py-2 text-right">
                  {row.actual_closure != null ? (
                    row.actual_closure
                      ? <XCircle className="w-3.5 h-3.5 text-red-400 ml-auto" />
                      : <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 ml-auto" />
                  ) : (
                    <span className="text-muted-foreground/40 text-[10px]">pending</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {history.length === 0 && (
        <div className="text-center py-8 text-xs text-muted-foreground">
          No predictions logged yet. Run the triage engine to start building history.
        </div>
      )}
    </div>
  );
}

export default function LearningScreen() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await client.get("/learning/summary");
      setData(res.data);
      setLastRefresh(new Date().toLocaleTimeString());
    } catch (e) {
      setError(e?.response?.data?.detail || "Backend not reachable");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const biasDirection = (b) => {
    if (b == null) return null;
    if (b > 5) return "bad";
    if (b < -5) return "bad";
    return "good";
  };

  const totalCauseCount = data
    ? Object.values(data.cause_distribution || {}).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6 max-w-5xl mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/25 flex items-center justify-center">
            <Brain className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-foreground">Post-Event Learning System</h2>
            <p className="text-[10px] text-muted-foreground">
              Tracks prediction accuracy and model drift over time
            </p>
          </div>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors border border-border rounded-lg px-3 py-1.5"
        >
          <RefreshCw className={clsx("w-3 h-3", loading && "animate-spin")} />
          {lastRefresh ? `Updated ${lastRefresh}` : "Refresh"}
        </button>
      </div>

      {error && (
        <div className="p-4 bg-destructive/10 border border-destructive/30 rounded-xl text-sm text-destructive flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {loading && !data && (
        <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
          <div className="flex flex-col items-center gap-3">
            <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            Loading learning metrics…
          </div>
        </div>
      )}

      {data && (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard
              icon={Activity}
              label="Total Predictions"
              value={data.total_predictions}
              sub="across all corridors"
              accent
            />
            <StatCard
              icon={Clock}
              label="Duration MAE"
              value={data.duration_mae_mins != null ? `${data.duration_mae_mins}m` : "—"}
              sub={`${data.with_actual_outcomes} confirmed outcomes`}
              trend={data.duration_mae_mins != null ? (data.duration_mae_mins < 30 ? "good" : "bad") : null}
            />
            <StatCard
              icon={Target}
              label="Closure Accuracy"
              value={data.closure_accuracy_pct != null ? `${data.closure_accuracy_pct}%` : "—"}
              sub="predicted vs actual closure"
              trend={data.closure_accuracy_pct != null ? (data.closure_accuracy_pct > 65 ? "good" : "bad") : null}
            />
            <StatCard
              icon={AlertTriangle}
              label="Disagreement Rate"
              value={`${data.disagreement_rate_pct}%`}
              sub="ML vs heuristic conflict"
              trend={data.disagreement_rate_pct < 20 ? "good" : "bad"}
            />
          </div>

          {/* Duration bias banner */}
          {data.duration_mean_bias_mins != null && (
            <div className={clsx(
              "rounded-xl p-3.5 border text-xs flex items-center gap-3",
              Math.abs(data.duration_mean_bias_mins) < 10
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                : data.duration_mean_bias_mins > 0
                  ? "bg-warning/10 border-warning/30 text-warning"
                  : "bg-blue-500/10 border-blue-500/30 text-blue-400"
            )}>
              {Math.abs(data.duration_mean_bias_mins) < 10
                ? <CheckCircle2 className="w-4 h-4 shrink-0" />
                : data.duration_mean_bias_mins > 0
                  ? <TrendingUp className="w-4 h-4 shrink-0" />
                  : <TrendingDown className="w-4 h-4 shrink-0" />
              }
              <div>
                <strong>Model bias: {data.duration_mean_bias_mins > 0 ? "+" : ""}{data.duration_mean_bias_mins} min</strong>
                {" — "}
                {Math.abs(data.duration_mean_bias_mins) < 10
                  ? "Duration predictions are well-calibrated."
                  : data.duration_mean_bias_mins > 0
                    ? "Model is systematically over-predicting clearance time. Consider retraining with recent data."
                    : "Model is systematically under-predicting. Officers may be under-prepared."}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Duration predicted vs actual chart */}
            <div className="bg-card border border-border rounded-xl p-4 space-y-4">
              <div className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-primary" />
                <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                  Predicted vs Actual Duration
                </h3>
              </div>
              <DurationChart history={data.prediction_history || []} />
            </div>

            {/* Cause distribution */}
            <div className="bg-card border border-border rounded-xl p-4 space-y-4">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-primary" />
                <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                  Incidents by Cause
                </h3>
              </div>
              <div className="space-y-3">
                {Object.entries(data.cause_distribution || {})
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 8)
                  .map(([cause, count]) => (
                    <MiniBar
                      key={cause}
                      label={CAUSE_LABELS[cause] || cause}
                      count={count}
                      total={totalCauseCount}
                      color={CAUSE_COLORS[cause] || "#6b7280"}
                    />
                  ))}
              </div>
              {/* Priority split */}
              <div className="border-t border-border pt-3 flex gap-3 text-xs">
                {Object.entries(data.priority_distribution || {}).map(([p, c]) => (
                  <div key={p} className={clsx(
                    "flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium",
                    p === "High" ? "bg-red-500/15 text-red-400" : "bg-muted text-muted-foreground"
                  )}>
                    <span className={clsx("w-1.5 h-1.5 rounded-full", p === "High" ? "bg-red-400" : "bg-muted-foreground")} />
                    {p}: {c}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Prediction history table */}
          <div className="bg-card border border-border rounded-xl p-4 space-y-4">
            <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-2">
              <Clock className="w-4 h-4 text-primary" />
              Recent Prediction Log
              <span className="ml-auto text-[10px] font-normal text-muted-foreground normal-case">
                Yellow row = ML/heuristic disagreement
              </span>
            </h3>
            <RecentTable history={data.prediction_history || []} />
          </div>

          {/* Model version info */}
          <div className="bg-muted/20 border border-border rounded-xl p-4 text-[11px] text-muted-foreground space-y-1">
            <p className="font-semibold text-foreground text-xs mb-2">How This Works</p>
            <p>Every triage prediction is logged to the database with its inputs and outputs. When an incident resolves, the actual duration and closure outcome are recorded via <code className="bg-muted px-1 rounded">POST /api/v1/learning/outcome/:id</code>.</p>
            <p className="mt-1">The system then computes MAE (Mean Absolute Error), closure accuracy, and systematic bias — flagging when the model is drifting and needs retraining.</p>
          </div>
        </>
      )}
    </div>
  );
}