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
          <div className="p-4 rounded-xl border border-border bg-muted/20 flex flex-col items-center justify-center text-center">
            <span className="text-sm text-muted-foreground mb-1">Predicted Priority</span>
            <span className={`text-3xl font-bold ${result.predicted_priority === 'High' ? 'text-destructive' : 'text-primary'}`}>
              {result.predicted_priority}
            </span>
            <span className="text-xs text-muted-foreground mt-2">
              {(result.priority_probability * 100).toFixed(1)}% confidence
            </span>
          </div>

          <div className="p-4 rounded-xl border border-border bg-muted/20 flex flex-col items-center justify-center text-center">
            <span className="text-sm text-muted-foreground mb-1">Road Closure Risk</span>
            <span className={`text-3xl font-bold ${result.closure_flag ? 'text-destructive' : 'text-primary'}`}>
              {result.closure_flag ? 'Yes' : 'No'}
            </span>
            <span className="text-xs text-muted-foreground mt-2">
              {(result.closure_probability * 100).toFixed(1)}% probability
            </span>
          </div>
        </div>

        {/* Predicted Duration */}
        <div className="p-4 rounded-xl border border-border flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-blue-500/10 flex items-center justify-center shrink-0">
            <Clock className="w-6 h-6 text-blue-500" />
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
          <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 flex gap-3 items-start">
            <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-amber-500 mb-1">System Override Warning</h4>
              <p className="text-sm text-amber-500/80 leading-relaxed">
                {result.disagreement_reason}
              </p>
            </div>
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
