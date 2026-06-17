import { useTriageStore } from '../../store/useTriageStore';
import { AlertCircle, CalendarClock, Car, MapPin, Activity, CalendarDays } from 'lucide-react';
import clsx from 'clsx';

export default function TriageForm() {
  const { formData, setFormData, submitPrediction, loading } = useTriageStore();

  const handleToggleType = (type) => {
    setFormData({ 
      event_type: type,
      event_cause: type === 'planned' ? 'public_event' : 'vehicle_breakdown'
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    submitPrediction();
  };

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm flex flex-col h-full overflow-hidden">
      <div className="p-4 border-b border-border bg-muted/30 flex items-center justify-between">
        <h2 className="font-semibold flex items-center gap-2">
          <Activity className="w-5 h-5 text-primary" />
          GridSense Triage Engine
        </h2>
      </div>

      <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-5 space-y-6">
        
        {/* Event Type Toggle */}
        <div className="space-y-3">
          <label className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            Mode
          </label>
          <div className="flex bg-muted p-1 rounded-lg">
            <button
              type="button"
              onClick={() => handleToggleType('unplanned')}
              className={clsx(
                "flex-1 py-1.5 text-sm font-medium rounded-md transition-all",
                formData.event_type === 'unplanned' 
                  ? "bg-card text-foreground shadow-sm" 
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              Unplanned Triage
            </button>
            <button
              type="button"
              onClick={() => handleToggleType('planned')}
              className={clsx(
                "flex-1 py-1.5 text-sm font-medium rounded-md transition-all flex items-center justify-center gap-2",
                formData.event_type === 'planned' 
                  ? "bg-primary/20 text-primary shadow-sm" 
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              Cascade Ripple
            </button>
          </div>
        </div>

        {/* Cause Select */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            Event Cause
          </label>
          {formData.event_type === 'unplanned' ? (
            <select 
              value={formData.event_cause}
              onChange={(e) => setFormData({ event_cause: e.target.value })}
              className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="vehicle_breakdown">Vehicle Breakdown</option>
              <option value="accident">Accident</option>
              <option value="pot_holes">Potholes</option>
              <option value="tree_fall">Tree Fall</option>
              <option value="water_logging">Water Logging</option>
              <option value="none">None / Other</option>
            </select>
          ) : (
            <select 
              value={formData.event_cause}
              onChange={(e) => setFormData({ event_cause: e.target.value })}
              className="w-full bg-background border border-primary/50 text-primary rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="public_event">Public Event</option>
              <option value="protest">Protest</option>
              <option value="vip_movement">VIP Movement</option>
              <option value="construction">Construction</option>
            </select>
          )}
        </div>

        {/* Corridor Select */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <MapPin className="w-4 h-4" />
            Location (Corridor)
          </label>
          <select 
            value={formData.corridor}
            onChange={(e) => setFormData({ corridor: e.target.value })}
            className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="Hosur Road">Hosur Road</option>
            <option value="Mysore Road">Mysore Road</option>
            <option value="ORR South">ORR South</option>
            <option value="Bellary Road 1">Bellary Road 1</option>
            <option value="Non-corridor">Off-Corridor (Non-named)</option>
          </select>
        </div>

        {/* Vehicle Type (Only for Unplanned) */}
        {formData.event_type === 'unplanned' && (
          <div className="space-y-2">
            <label className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Car className="w-4 h-4" />
              Involved Vehicle
            </label>
            <select 
              value={formData.vehicle_type}
              onChange={(e) => setFormData({ vehicle_type: e.target.value })}
              className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="none">None / N/A</option>
              <option value="heavy_truck">Heavy Truck</option>
              <option value="bus">Bus</option>
              <option value="car">Car</option>
              <option value="2_wheeler">2 Wheeler</option>
            </select>
          </div>
        )}

        {/* Time Inputs */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <CalendarDays className="w-4 h-4" />
              Day of Week
            </label>
            <select 
              value={formData.day_of_week}
              onChange={(e) => setFormData({ day_of_week: e.target.value })}
              className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="0">Monday</option>
              <option value="1">Tuesday</option>
              <option value="2">Wednesday</option>
              <option value="3">Thursday</option>
              <option value="4">Friday</option>
              <option value="5">Saturday</option>
              <option value="6">Sunday</option>
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <CalendarClock className="w-4 h-4" />
              Hour
            </label>
            <input 
              type="number"
              min="0"
              max="23"
              value={formData.hour_of_day}
              onChange={(e) => setFormData({ hour_of_day: e.target.value })}
              className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        </div>
      </form>

      <div className="p-4 border-t border-border bg-muted/10">
        <button 
          onClick={handleSubmit}
          disabled={loading}
          className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold py-2.5 rounded-lg transition-colors flex justify-center items-center gap-2 disabled:opacity-50"
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
              Processing...
            </>
          ) : (
            formData.event_type === 'unplanned' ? 'Run Triage Model' : 'Predict Cascade Ripple'
          )}
        </button>
      </div>
    </div>
  );
}
