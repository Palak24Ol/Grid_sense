import { useTriageStore } from '../../store/useTriageStore';
import TriageForm from './TriageForm';
import PredictionResultCard from './PredictionResultCard';
import CascadeRippleCard from './CascadeRippleCard';

export default function TriageScreen() {
  const { formData, triageResult, cascadeResult, loading } = useTriageStore();

  return (
    <div className="p-6 h-full flex flex-col md:flex-row gap-6 max-w-7xl mx-auto">
      {/* Left Column - Form */}
      <div className="w-full md:w-1/3 flex flex-col gap-6">
        <TriageForm />
      </div>
      
      {/* Right Column - Results */}
      <div className="w-full md:w-2/3 flex flex-col gap-6">
        {!triageResult && !cascadeResult && !loading && (
          <div className="flex-1 flex items-center justify-center border-2 border-dashed border-border rounded-xl text-muted-foreground bg-card/50">
            Enter incident details to generate a prediction.
          </div>
        )}
        
        {loading && (
          <div className="flex-1 flex items-center justify-center border border-border rounded-xl bg-card">
            <div className="flex flex-col items-center gap-4">
              <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
              <div className="text-sm font-medium animate-pulse">Running Prediction Models...</div>
            </div>
          </div>
        )}

        {formData.event_type === 'unplanned' && triageResult && !loading && (
          <PredictionResultCard result={triageResult} />
        )}

        {formData.event_type === 'planned' && cascadeResult && !loading && (
          <CascadeRippleCard result={cascadeResult} />
        )}
      </div>
    </div>
  );
}
