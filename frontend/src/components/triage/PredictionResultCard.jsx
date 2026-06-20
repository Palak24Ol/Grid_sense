import { AlertTriangle, Clock, Info } from 'lucide-react';

export default function PredictionResultCard({ result }) {
  if (!result) return null;

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden flex flex-col h-full">
      <div className="p-4 border-b border-border bg-muted/30 flex items-center justify-between">
        <h2 className="font-semibold">Prediction Results</h2>
        <span className="text-xs text-muted-foreground font-mono">
          Inference: {result.inference_ms}ms
        </span>
      </div>

      <div className="p-6 flex-1 overflow-y-auto space-y-6">
        
        {/* Top Metrics Row */}
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-xl p-4 border border-border bg-muted/20 flex flex-col items-center justify-center text-center gap-1">
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Predicted Priority</span>
            <span className={`text-3xl font-bold ${result.predicted_priority === 'High' ? 'text-destructive' : 'text-primary'}`}>
              {result.predicted_priority}
            </span>
            <span className="text-xs text-muted-foreground mt-2">
              {(result.priority_probability * 100).toFixed(1)}% confidence
            </span>
          </div>

          <div className="rounded-xl p-4 border border-border bg-muted/20 flex flex-col items-center justify-center text-center gap-1">
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Road Closure Risk</span>
            <span className={`text-2xl font-bold ${result.closure_flag ? 'text-destructive' : 'text-primary'}`}>
              {result.closure_flag ? 'High Risk' : 'Low Risk'}
            </span>
            <div className="w-full bg-muted rounded-full h-1.5 mt-2 overflow-hidden flex">
              <div 
                className={`h-full rounded-full ${result.closure_flag ? 'bg-destructive' : 'bg-primary'}`} 
                style={{ width: `${Math.min(100, Math.max(0, result.closure_probability * 100))}%` }} 
              />
            </div>
          </div>
        </div>

        {/* Predicted Duration */}
        <div className="p-4 rounded-xl border border-border bg-muted/20 flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center shrink-0 border border-primary/25">
            <Clock className="w-6 h-6 text-primary" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-lg">
              {Math.round(result.predicted_duration_mins)} minutes expected
            </h3>
            <p className="text-sm text-muted-foreground">
              Likely range: {Math.round(result.duration_p25)} - {Math.round(result.duration_p75)} mins ({result.duration_bucket} duration)
            </p>
          </div>
        </div>

        {/* Disagreement Flag Alert */}
        {result.disagreement_flag && (
          <div className="p-4 rounded-xl border border-warning/30 bg-warning/10 flex gap-3 items-start">
            <AlertTriangle className="w-5 h-5 text-warning shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-warning mb-1">System Override Warning</h4>
              <p className="text-sm text-warning/80 leading-relaxed">
                {result.disagreement_reason}
              </p>
            </div>
          </div>
        )}

        {/* SHAP AI Explanations */}
        {result.top_reasons && result.top_reasons.length > 0 && (
          <div className="p-4 rounded-xl border border-border bg-muted/10 space-y-2">
            <h4 className="font-semibold text-sm flex items-center gap-2">
              <Info className="w-4 h-4 text-primary" />
              Why did the AI predict this?
            </h4>
            <ul className="space-y-1">
              {result.top_reasons.map((reason, idx) => {
                const parts = reason.split(' (');
                const feature = parts[0];
                const value = parts.length > 1 ? '(' + parts[1] : '';
                
                let translated = feature.replace(/_/g, " ");
                if (feature.includes("cause_closure_rate")) translated = "Historical closure rate for this cause";
                else if (feature.includes("hour_cos") || feature.includes("hour_sin") || feature.includes("hour_of_day")) translated = "Time of day (cyclical traffic patterns)";
                else if (feature.includes("is_high_priority_corridor")) translated = "Location is a known high-priority corridor";
                else if (feature.includes("station_priority_rate")) translated = "Historical severity at this police station";
                else if (feature.includes("corridor_encoded")) translated = "Specific road/corridor historical profile";
                else if (feature.includes("event_cause_encoded")) translated = "Specific nature of the incident";
                else if (feature.includes("vehicle_type_encoded")) translated = "Type of vehicle involved";
                else if (feature.includes("is_rush_hour")) translated = "Occurred during peak rush hour";
                else if (feature.includes("is_daytime")) translated = "Occurred during daytime hours";
                
                return (
                <li key={idx} className="text-sm text-muted-foreground flex items-start gap-2">
                  <span className="text-primary/70 mt-0.5">•</span>
                  <span>{translated} <span className="text-xs opacity-60 ml-1">{value}</span></span>
                </li>
              )})}
            </ul>
          </div>
        )}

      </div>
      
      {/* Model info footer */}
      <div className="p-3 border-t border-border bg-muted/10 text-xs text-muted-foreground flex justify-between items-center">
        <div className="flex items-center gap-1">
          <Info className="w-3 h-3" />
          Powered by XGBoost & Random Forest Ensembles
        </div>
        <div className="font-mono">
          Models: {result.model_versions.closure_model}
        </div>
      </div>
    </div>
  );
}
