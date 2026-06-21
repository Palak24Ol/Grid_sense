import { useTriageStore } from '../../store/useTriageStore';
import { AlertCircle, Clock, Car, MapPin, Activity, CalendarDays } from 'lucide-react';
import clsx from 'clsx';

const HOURS = Array.from({ length: 24 }, (_, i) => {
  const ampm = i < 12 ? 'AM' : 'PM';
  const h    = i === 0 ? 12 : i > 12 ? i - 12 : i;
  return { value: i, label: `${h}:00 ${ampm}` };
});

export default function TriageForm() {
  const { formData, setFormData, submitPrediction, loading } = useTriageStore();

  const handleToggleType = (type) => {
    setFormData({
      event_type: type,
      event_cause: type === 'planned' ? 'public_event' : 'vehicle_breakdown',
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
          Check an Incident
        </h2>
      </div>

      <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-5 space-y-6">

        {/* Incident Type Toggle */}
        <div className="space-y-3">
          <label className="section-label">What kind of incident?</label>
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
              Sudden Incident
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
              Planned Event
            </button>
          </div>
        </div>

        {/* Cause */}
        <div className="space-y-2">
          <label className="section-label flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            What caused it?
          </label>
          {formData.event_type === 'unplanned' ? (
            <select
              value={formData.event_cause}
              onChange={(e) => setFormData({ event_cause: e.target.value })}
              className="w-full bg-muted/30 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary/60 focus:bg-muted/50 transition-colors appearance-none cursor-pointer"
            >
              <option value="vehicle_breakdown">Vehicle Breakdown</option>
              <option value="accident">Accident</option>
              <option value="pot_holes">Potholes</option>
              <option value="tree_fall">Tree Fall</option>
              <option value="water_logging">Water Logging</option>
              <option value="none">Other</option>
            </select>
          ) : (
            <select
              value={formData.event_cause}
              onChange={(e) => setFormData({ event_cause: e.target.value })}
              className="w-full bg-primary/10 border border-primary/50 text-primary rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary transition-colors appearance-none cursor-pointer"
            >
              <option value="public_event">Match / Festival</option>
              <option value="protest">Rally / Protest</option>
              <option value="vip_movement">VIP Movement</option>
              <option value="construction">Construction Work</option>
            </select>
          )}
        </div>

        {/* Location */}
        <div className="space-y-2">
          <label className="section-label flex items-center gap-2">
            <MapPin className="w-4 h-4" />
            Where is it?
          </label>
          <select
            value={formData.corridor}
            onChange={(e) => setFormData({ corridor: e.target.value })}
            className="w-full bg-muted/30 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary/60 focus:bg-muted/50 transition-colors appearance-none cursor-pointer"
          >
            <option value="Hosur Road">Hosur Road</option>
            <option value="Mysore Road">Mysore Road</option>
            <option value="ORR South">ORR South</option>
            <option value="Bellary Road 1">Bellary Road 1</option>
            <option value="Non-corridor">Other / Off main road</option>
          </select>
        </div>

        {/* Vehicle Type — only for sudden incidents */}
        {formData.event_type === 'unplanned' && (
          <div className="space-y-2">
            <label className="section-label flex items-center gap-2">
              <Car className="w-4 h-4" />
              Vehicle involved?
            </label>
            <select
              value={formData.vehicle_type}
              onChange={(e) => setFormData({ vehicle_type: e.target.value })}
              className="w-full bg-muted/30 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary/60 focus:bg-muted/50 transition-colors appearance-none cursor-pointer"
            >
              <option value="none">None / Not applicable</option>
              <option value="heavy_truck">Heavy Truck</option>
              <option value="bus">Bus</option>
              <option value="car">Car</option>
              <option value="2_wheeler">Two Wheeler</option>
            </select>
          </div>
        )}

        {/* Time inputs */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="section-label flex items-center gap-2">
              <CalendarDays className="w-4 h-4" />
              Day
            </label>
            <select
              value={formData.day_of_week}
              onChange={(e) => setFormData({ day_of_week: e.target.value })}
              className="w-full bg-muted/30 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary/60 focus:bg-muted/50 transition-colors appearance-none cursor-pointer"
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
            <label className="section-label flex items-center gap-2">
              <Clock className="w-4 h-4" />
              Time
            </label>
            <select
              value={formData.hour_of_day}
              onChange={(e) => setFormData({ hour_of_day: Number(e.target.value) })}
              className="w-full bg-muted/30 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary/60 focus:bg-muted/50 transition-colors appearance-none cursor-pointer"
            >
              {HOURS.map(({ value, label }) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
        </div>
      </form>

      <div className="p-4 border-t border-border bg-muted/10">
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-bold py-2.5 rounded-xl transition-all flex justify-center items-center gap-2 disabled:opacity-50 text-sm glow-yellow"
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
              Checking…
            </>
          ) : (
            formData.event_type === 'unplanned' ? 'Check This Incident' : 'Predict Event Impact'
          )}
        </button>
      </div>
    </div>
  );
}
