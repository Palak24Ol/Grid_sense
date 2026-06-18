import { useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet';
import { Users, ShieldAlert, MapPin, AlertCircle, Car, Clock,
         CalendarDays, Navigation, ChevronRight, Loader2 } from 'lucide-react';
import { client } from '../../api/client';
import clsx from 'clsx';

const CORRIDORS = [
  'Bellary Road 1','Bellary Road 2','Tumkur Road','Mysore Road',
  'ORR North 1','ORR North 2','ORR East 1','ORR East 2','ORR West 1',
  'Hosur Road','Magadi Road','Old Madras Road','West of Chord Road',
  'CBD 2','CBD 1','Hennur Main Road','Airport New South Road',
  'Old Airport Road','Varthur Road','Bannerghata Road',
];

const CAUSES = [
  { value: 'vehicle_breakdown', label: 'Vehicle Breakdown' },
  { value: 'accident',          label: 'Accident' },
  { value: 'pot_holes',         label: 'Potholes' },
  { value: 'tree_fall',         label: 'Tree Fall' },
  { value: 'water_logging',     label: 'Water Logging' },
  { value: 'construction',      label: 'Construction' },
  { value: 'protest',           label: 'Protest' },
  { value: 'public_event',      label: 'Public Event' },
  { value: 'vip_movement',      label: 'VIP Movement' },
];

const TIER_STYLE = {
  Critical: 'bg-red-500/20 text-red-400 border-red-500/40',
  Elevated: 'bg-orange-500/20 text-orange-400 border-orange-500/40',
  Routine:  'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
};

// Junction name → approx lat/lng for map markers
const JUNCTION_COORDS = {
  'MekhriCircle':                  [13.014, 77.584],
  'HebbalFlyoverJunc':             [13.034, 77.594],
  'YeshwanthpuraCircle':           [13.022, 77.546],
  'JalahalliCross(SM_Circle)':     [13.024, 77.519],
  'SilkBoardJunc':                 [12.917, 77.622],
  'AyyappaTempleJunc':             [12.930, 77.615],
  'VeerannapalyaJunction(BEL,HO)': [13.041, 77.613],
  'YelhankaCircle':                [13.100, 77.596],
  'GokuldasImagesJunc':            [13.008, 77.541],
};

function StatCard({ label, value, sub }) {
  return (
    <div className="bg-muted/20 rounded-lg p-3 border border-border">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-bold mt-0.5">{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  );
}

export default function DeploymentScreen() {
  const [form, setForm] = useState({
    corridor:            'Bellary Road 1',
    event_cause:         'vehicle_breakdown',
    vehicle_type:        'heavy_truck',
    hour_of_day:         20,
    day_of_week:         4,
    closure_probability: 0.45,
    predicted_priority:  'High',
    predicted_duration_mins: 60,
  });
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  const handleGenerate = async () => {
    setLoading(true); setError(null); setResult(null);
    try {
      const { data } = await client.post('/deploy/recommend', {
        ...form,
        hour_of_day:             Number(form.hour_of_day),
        day_of_week:             Number(form.day_of_week),
        closure_probability:     Number(form.closure_probability),
        predicted_duration_mins: Number(form.predicted_duration_mins),
      });
      setResult(data);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Deployment API error. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  const markerJunctions = result?.suggested_junctions?.map(j => ({
    name: j,
    coords: JUNCTION_COORDS[j],
  })).filter(j => j.coords) || [];

  return (
    <div className="h-full flex flex-col md:flex-row relative">

      {/* Map */}
      <div className="w-full md:w-1/2 h-1/2 md:h-full relative z-0">
        <MapContainer center={[12.98, 77.57]} zoom={12} style={{ height: '100%', width: '100%' }} zoomControl={false}>
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
          {markerJunctions.map(j => (
            <CircleMarker
              key={j.name}
              center={j.coords}
              radius={10}
              pathOptions={{ color: '#6366f1', fillColor: '#6366f1', fillOpacity: 0.6 }}
            >
              <Tooltip permanent>{j.name.replace(/_/g,' ')}</Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      {/* Panel */}
      <div className="w-full md:w-1/2 h-1/2 md:h-full bg-background border-l border-border overflow-y-auto flex flex-col z-10">

        <div className="p-4 border-b border-border bg-muted/30 shrink-0 flex items-center justify-between">
          <h2 className="font-semibold flex items-center gap-2">
            <Users className="w-5 h-5 text-primary" />
            Dynamic Deployment Planner
          </h2>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">

          {/* Form */}
          <div className="space-y-4">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Incident Parameters</p>

            <div className="grid grid-cols-2 gap-3">
              {/* Corridor */}
              <div className="col-span-2 space-y-1.5">
                <label className="text-xs text-muted-foreground flex items-center gap-1.5"><MapPin className="w-3.5 h-3.5" />Corridor</label>
                <select
                  value={form.corridor}
                  onChange={e => setForm(f => ({ ...f, corridor: e.target.value }))}
                  className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  {CORRIDORS.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>

              {/* Cause */}
              <div className="col-span-2 space-y-1.5">
                <label className="text-xs text-muted-foreground flex items-center gap-1.5"><AlertCircle className="w-3.5 h-3.5" />Event Cause</label>
                <select
                  value={form.event_cause}
                  onChange={e => setForm(f => ({ ...f, event_cause: e.target.value }))}
                  className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  {CAUSES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </div>

              {/* Vehicle */}
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground flex items-center gap-1.5"><Car className="w-3.5 h-3.5" />Vehicle</label>
                <select
                  value={form.vehicle_type}
                  onChange={e => setForm(f => ({ ...f, vehicle_type: e.target.value }))}
                  className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="heavy_truck">Heavy Truck</option>
                  <option value="bus">Bus</option>
                  <option value="car">Car</option>
                  <option value="2_wheeler">2 Wheeler</option>
                  <option value="none">None</option>
                </select>
              </div>

              {/* Priority */}
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground flex items-center gap-1.5"><ShieldAlert className="w-3.5 h-3.5" />Priority</label>
                <select
                  value={form.predicted_priority}
                  onChange={e => setForm(f => ({ ...f, predicted_priority: e.target.value }))}
                  className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="High">High</option>
                  <option value="Medium">Medium</option>
                  <option value="Low">Low</option>
                </select>
              </div>

              {/* Hour */}
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" />Hour (0–23)</label>
                <input
                  type="number" min={0} max={23}
                  value={form.hour_of_day}
                  onChange={e => setForm(f => ({ ...f, hour_of_day: e.target.value }))}
                  className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              {/* Day */}
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground flex items-center gap-1.5"><CalendarDays className="w-3.5 h-3.5" />Day of Week</label>
                <select
                  value={form.day_of_week}
                  onChange={e => setForm(f => ({ ...f, day_of_week: e.target.value }))}
                  className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  {['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'].map((d,i) =>
                    <option key={i} value={i}>{d}</option>
                  )}
                </select>
              </div>

              {/* Closure prob */}
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground">Closure Prob.</label>
                <input
                  type="number" min={0} max={1} step={0.05}
                  value={form.closure_probability}
                  onChange={e => setForm(f => ({ ...f, closure_probability: e.target.value }))}
                  className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              {/* Duration */}
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground">Duration (mins)</label>
                <input
                  type="number" min={5} max={480}
                  value={form.predicted_duration_mins}
                  onChange={e => setForm(f => ({ ...f, predicted_duration_mins: e.target.value }))}
                  className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
            </div>

            <button
              onClick={handleGenerate}
              disabled={loading}
              className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold py-2.5 rounded-lg transition-colors flex justify-center items-center gap-2 disabled:opacity-50"
            >
              {loading
                ? <><Loader2 className="w-4 h-4 animate-spin" />Generating Plan…</>
                : <><ChevronRight className="w-4 h-4" />Generate Deployment Plan</>
              }
            </button>

            {error && (
              <div className="p-3 bg-destructive/10 border border-destructive/30 rounded-lg text-sm text-destructive">
                {error}
              </div>
            )}
          </div>

          {/* Result */}
          {result && (
            <div className="space-y-4 border-t border-border pt-5">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Deployment Plan</p>
                <span className={clsx('px-3 py-0.5 rounded-full text-xs font-bold border', TIER_STYLE[result.escalation_tier] || TIER_STYLE.Routine)}>
                  {result.escalation_tier}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <StatCard label="Primary Station" value={result.recommended_station} />
                <StatCard label="Officers Needed" value={result.recommended_officer_count} sub="personnel" />
                <StatCard label="Duration" value={`${result.deployment_duration_mins} min`} />
                <StatCard label="Corridor Risk Score" value={result.corridor_risk_score?.toFixed(1)} sub="/ 100" />
              </div>

              <div className="bg-muted/10 rounded-lg p-3 border border-border text-xs text-muted-foreground space-y-1">
                <p className="font-medium text-foreground">ML Rationale</p>
                <p>{result.officer_count_rationale}</p>
                <p>{result.escalation_rationale}</p>
              </div>

              {result.suggested_junctions?.length > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground mb-2">Suggested Deployment Junctions</p>
                  <div className="flex flex-wrap gap-2">
                    {result.suggested_junctions.map(j => (
                      <span key={j} className="text-xs bg-primary/10 text-primary border border-primary/20 px-2 py-1 rounded-lg flex items-center gap-1">
                        <MapPin className="w-3 h-3" />{j.replace(/_/g,' ')}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Diversion routes */}
              {result.diversion_routes?.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                    <Navigation className="w-3.5 h-3.5 text-primary" />
                    Diversion Routes
                  </p>
                  {result.diversion_routes.map((r, i) => (
                    <div key={i} className="p-3 bg-primary/5 border border-primary/20 rounded-lg text-xs space-y-1">
                      <div className="flex items-center gap-1.5 font-medium">
                        <span>{r.from_junction}</span>
                        <ChevronRight className="w-3 h-3 text-muted-foreground" />
                        <span>{r.to_junction}</span>
                        <span className="ml-auto text-orange-400 font-bold">+{r.estimated_extra_mins} min</span>
                      </div>
                      <p className="text-muted-foreground">Via: <span className="text-foreground">{r.via_road}</span></p>
                      <p className="text-muted-foreground">{r.rationale}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
