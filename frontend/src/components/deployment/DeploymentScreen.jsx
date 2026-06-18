import { useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip } from "react-leaflet";
import {
  Users, ShieldAlert, MapPin, AlertCircle, Car, Clock,
  CalendarDays, Navigation, ChevronRight, Loader2, Zap,
} from "lucide-react";
import { client } from "../../api/client";
import clsx from "clsx";

const CORRIDORS = [
  "Bellary Road 1","Bellary Road 2","Tumkur Road","Mysore Road",
  "ORR North 1","ORR North 2","ORR East 1","ORR East 2","ORR West 1",
  "Hosur Road","Magadi Road","Old Madras Road","West of Chord Road",
  "CBD 2","CBD 1","Hennur Main Road","Airport New South Road",
  "Old Airport Road","Varthur Road","Bannerghata Road",
];

const EVENT_CAUSES = [
  { value: "vehicle_breakdown", label: "Vehicle Breakdown" },
  { value: "accident",          label: "Accident" },
  { value: "pot_holes",         label: "Potholes" },
  { value: "tree_fall",         label: "Tree Fall" },
  { value: "water_logging",     label: "Water Logging" },
  { value: "construction",      label: "Construction Activity" },
  { value: "protest",           label: "Protest / Rally" },
  { value: "public_event",      label: "Public Event / Festival" },
  { value: "vip_movement",      label: "VIP Movement" },
];

const TIER_CONFIG = {
  Critical: { cls: "bg-red-500/15 text-red-400 border-red-500/30",     dot: "bg-red-400" },
  Elevated: { cls: "bg-warning/15 text-warning border-warning/30",      dot: "bg-warning" },
  Routine:  { cls: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30", dot: "bg-emerald-400" },
};

const JUNCTION_COORDS = {
  "MekhriCircle":                  [13.014, 77.584],
  "HebbalFlyoverJunc":             [13.034, 77.594],
  "YeshwanthpuraCircle":           [13.022, 77.546],
  "JalahalliCross(SM_Circle)":     [13.024, 77.519],
  "SilkBoardJunc":                 [12.917, 77.622],
  "AyyappaTempleJunc":             [12.930, 77.615],
  "VeerannapalyaJunction(BEL,HO)": [13.041, 77.613],
  "YelhankaCircle":                [13.100, 77.596],
  "GokuldasImagesJunc":            [13.008, 77.541],
};

function FieldLabel({ icon: Icon, children }) {
  return (
    <label className="text-xs font-medium text-muted-foreground flex items-center gap-1.5 mb-1.5">
      {Icon && <Icon className="w-3.5 h-3.5 text-primary/70" />}
      {children}
    </label>
  );
}

function StyledSelect({ value, onChange, children }) {
  return (
    <select
      value={value}
      onChange={onChange}
      className="w-full bg-muted/30 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary/60 focus:bg-muted/50 transition-colors appearance-none cursor-pointer"
    >
      {children}
    </select>
  );
}

function StyledInput({ ...props }) {
  return (
    <input
      {...props}
      className="w-full bg-muted/30 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary/60 focus:bg-muted/50 transition-colors"
    />
  );
}

function MetricCard({ label, value, sub, highlight }) {
  return (
    <div className={clsx(
      "rounded-xl p-3 border flex flex-col gap-1",
      highlight
        ? "bg-primary/8 border-primary/30"
        : "bg-muted/20 border-border"
    )}>
      <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">{label}</p>
      <p className={clsx("text-lg font-bold leading-tight", highlight ? "text-primary" : "text-foreground")}>
        {value}
      </p>
      {sub && <p className="text-[10px] text-muted-foreground">{sub}</p>}
    </div>
  );
}

export default function DeploymentScreen() {
  const [form, setForm] = useState({
    corridor:            "Bellary Road 1",
    event_cause:         "vehicle_breakdown",
    vehicle_type:        "heavy_truck",
    hour_of_day:         20,
    day_of_week:         4,
    closure_probability: 0.45,
    predicted_priority:  "High",
    predicted_duration_mins: 60,
  });
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  const handleGenerate = async () => {
    setLoading(true); setError(null); setResult(null);
    try {
      const { data } = await client.post("/deploy/recommend", {
        ...form,
        hour_of_day:             Number(form.hour_of_day),
        day_of_week:             Number(form.day_of_week),
        closure_probability:     Number(form.closure_probability),
        predicted_duration_mins: Number(form.predicted_duration_mins),
      });
      setResult(data);
    } catch (e) {
      setError(e?.response?.data?.detail || "Deployment API error — is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  const markerJunctions = result?.suggested_junctions
    ?.map((j) => ({ name: j, coords: JUNCTION_COORDS[j] }))
    .filter((j) => j.coords) || [];

  const tier = result?.escalation_tier;

  return (
    <div className="h-full flex flex-col md:flex-row relative">

      {/* Map pane */}
      <div className="w-full md:w-1/2 h-1/2 md:h-full relative z-0">
        <MapContainer
          center={[12.98, 77.57]} zoom={12}
          style={{ height: "100%", width: "100%" }}
          zoomControl={false}
        >
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
          {markerJunctions.map((j) => (
            <CircleMarker
              key={j.name}
              center={j.coords}
              radius={10}
              pathOptions={{ color: "#F9E107", fillColor: "#F9E107", fillOpacity: 0.7, weight: 2 }}
            >
              <Tooltip permanent className="leaflet-tooltip-yellow">
                {j.name.replace(/_/g, " ")}
              </Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      {/* Panel */}
      <div className="w-full md:w-1/2 h-1/2 md:h-full bg-background border-l border-border overflow-y-auto flex flex-col z-10">

        {/* Header */}
        <div className="px-5 py-4 border-b border-border bg-card flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/25 flex items-center justify-center">
              <Users className="w-4 h-4 text-primary" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-foreground">Officer Deployment Planner</h2>
              <p className="text-[10px] text-muted-foreground">ML-powered manpower & diversion recommendations</p>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-6">

          {/* Form */}
          <div>
            <p className="section-label mb-4">Incident Parameters</p>
            <div className="grid grid-cols-2 gap-3">

              <div className="col-span-2">
                <FieldLabel icon={MapPin}>Corridor</FieldLabel>
                <StyledSelect value={form.corridor} onChange={(e) => setForm((f) => ({ ...f, corridor: e.target.value }))}>
                  {CORRIDORS.map((c) => <option key={c} value={c}>{c}</option>)}
                </StyledSelect>
              </div>

              <div className="col-span-2">
                <FieldLabel icon={AlertCircle}>Event Cause</FieldLabel>
                <StyledSelect value={form.event_cause} onChange={(e) => setForm((f) => ({ ...f, event_cause: e.target.value }))}>
                  {EVENT_CAUSES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                </StyledSelect>
              </div>

              <div>
                <FieldLabel icon={Car}>Vehicle Type</FieldLabel>
                <StyledSelect value={form.vehicle_type} onChange={(e) => setForm((f) => ({ ...f, vehicle_type: e.target.value }))}>
                  <option value="heavy_truck">Heavy Truck</option>
                  <option value="bus">Bus</option>
                  <option value="car">Car</option>
                  <option value="2_wheeler">2 Wheeler</option>
                  <option value="none">None</option>
                </StyledSelect>
              </div>

              <div>
                <FieldLabel icon={ShieldAlert}>Priority Level</FieldLabel>
                <StyledSelect value={form.predicted_priority} onChange={(e) => setForm((f) => ({ ...f, predicted_priority: e.target.value }))}>
                  <option value="High">High</option>
                  <option value="Medium">Medium</option>
                  <option value="Low">Low</option>
                </StyledSelect>
              </div>

              <div>
                <FieldLabel icon={Clock}>Hour of Day (0–23)</FieldLabel>
                <StyledInput type="number" min={0} max={23} value={form.hour_of_day}
                  onChange={(e) => setForm((f) => ({ ...f, hour_of_day: e.target.value }))} />
              </div>

              <div>
                <FieldLabel icon={CalendarDays}>Day of Week</FieldLabel>
                <StyledSelect value={form.day_of_week} onChange={(e) => setForm((f) => ({ ...f, day_of_week: e.target.value }))}>
                  {["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"].map((d, i) =>
                    <option key={i} value={i}>{d}</option>
                  )}
                </StyledSelect>
              </div>

              <div>
                <FieldLabel>Closure Probability</FieldLabel>
                <StyledInput type="number" min={0} max={1} step={0.05} value={form.closure_probability}
                  onChange={(e) => setForm((f) => ({ ...f, closure_probability: e.target.value }))} />
              </div>

              <div>
                <FieldLabel>Duration (mins)</FieldLabel>
                <StyledInput type="number" min={5} max={480} value={form.predicted_duration_mins}
                  onChange={(e) => setForm((f) => ({ ...f, predicted_duration_mins: e.target.value }))} />
              </div>
            </div>

            <button
              onClick={handleGenerate}
              disabled={loading}
              className="mt-5 w-full bg-primary hover:bg-primary/90 text-primary-foreground font-bold py-2.5 rounded-xl transition-all flex justify-center items-center gap-2 disabled:opacity-50 text-sm glow-yellow"
            >
              {loading
                ? <><Loader2 className="w-4 h-4 animate-spin" />Generating Plan…</>
                : <><Zap className="w-4 h-4" />Generate Deployment Brief</>
              }
            </button>

            {error && (
              <div className="mt-3 p-3 bg-destructive/10 border border-destructive/30 rounded-xl text-sm text-destructive">
                {error}
              </div>
            )}
          </div>

          {/* Result */}
          {result && (
            <div className="space-y-4 border-t border-border pt-5">

              {/* Tier badge */}
              <div className="flex items-center justify-between">
                <p className="section-label">Deployment Brief</p>
                {tier && (
                  <div className={clsx("px-3 py-1 rounded-full text-xs font-bold border flex items-center gap-1.5", TIER_CONFIG[tier]?.cls)}>
                    <span className={clsx("w-1.5 h-1.5 rounded-full", TIER_CONFIG[tier]?.dot)} />
                    {tier} Escalation
                  </div>
                )}
              </div>

              {/* Metric grid */}
              <div className="grid grid-cols-2 gap-2.5">
                <MetricCard label="Primary Station"   value={result.recommended_station} highlight />
                <MetricCard label="Officers Needed"   value={result.recommended_officer_count} sub="personnel required" highlight />
                <MetricCard label="Deploy Duration"   value={`${result.deployment_duration_mins} min`} />
                <MetricCard label="Corridor Risk"     value={`${result.corridor_risk_score?.toFixed(1)} / 100`} />
              </div>

              {/* Rationale */}
              <div className="bg-muted/20 rounded-xl p-4 border border-border space-y-1.5">
                <p className="text-xs font-semibold text-primary uppercase tracking-wider mb-2">ML Rationale</p>
                <p className="text-xs text-muted-foreground leading-relaxed">{result.officer_count_rationale}</p>
                <p className="text-xs text-muted-foreground leading-relaxed">{result.escalation_rationale}</p>
              </div>

              {/* Junctions */}
              {result.suggested_junctions?.length > 0 && (
                <div>
                  <p className="section-label mb-2.5">Deploy At These Junctions</p>
                  <div className="flex flex-wrap gap-2">
                    {result.suggested_junctions.map((j) => (
                      <span key={j} className="text-xs bg-primary/10 text-primary border border-primary/25 px-2.5 py-1.5 rounded-lg flex items-center gap-1.5 font-medium">
                        <MapPin className="w-3 h-3" />
                        {j.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Diversion routes */}
              {result.diversion_routes?.length > 0 && (
                <div>
                  <p className="section-label mb-2.5 flex items-center gap-1.5">
                    <Navigation className="w-3.5 h-3.5 text-primary" />
                    Diversion Routes
                  </p>
                  <div className="space-y-2">
                    {result.diversion_routes.map((r, i) => (
                      <div key={i} className="p-3.5 bg-primary/5 border border-primary/15 rounded-xl text-xs space-y-1.5">
                        <div className="flex items-center gap-2 font-semibold text-foreground">
                          <span>{r.from_junction}</span>
                          <ChevronRight className="w-3 h-3 text-muted-foreground" />
                          <span>{r.to_junction}</span>
                          <span className="ml-auto text-warning font-bold">+{r.estimated_extra_mins} min</span>
                        </div>
                        <p className="text-muted-foreground">
                          Via <span className="text-foreground font-medium">{r.via_road}</span>
                        </p>
                        <p className="text-muted-foreground/70">{r.rationale}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
