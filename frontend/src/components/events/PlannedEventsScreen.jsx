import { useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip } from "react-leaflet";
import {
  CalendarDays, MapPin, AlertCircle, Clock, 
  ShieldAlert, Users, Loader2, Navigation, ChevronRight, Zap, Radio
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

const PLANNED_EVENTS = [
  { value: "public_event", label: "Public Event / Match" },
  { value: "protest",      label: "Protest / Rally" },
  { value: "procession",   label: "Procession" },
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

export default function PlannedEventsScreen() {
  const [form, setForm] = useState({
    corridor:            "Bellary Road 1",
    event_cause:         "public_event",
    hour_of_day:         19,
    day_of_week:         6, // Sunday
  });
  
  const [cascadeResult, setCascadeResult] = useState(null);
  const [deployResult, setDeployResult]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  const handleGenerate = async () => {
    setLoading(true); setError(null); setCascadeResult(null); setDeployResult(null);
    try {
      const cascadePayload = {
        corridor: form.corridor,
        event_cause: form.event_cause,
        hour_of_day: Number(form.hour_of_day),
        day_of_week: Number(form.day_of_week)
      };

      // 1. Fetch cascade multiplier and risk
      const { data: cascadeData } = await client.post("/predict/cascade", cascadePayload);
      
      // 2. Fetch deployment recommendation using assumptions for a planned event
      const deployPayload = {
        ...cascadePayload,
        vehicle_type: "none",
        closure_probability: 0.5, // Hardcoded > 0.25 to trigger diversion routes
        predicted_priority: "High", // Assume High risk for planned events
        predicted_duration_mins: 120, // 2 hour event block
      };
      const { data: deployData } = await client.post("/deploy/recommend", deployPayload);

      setCascadeResult(cascadeData);
      setDeployResult(deployData);
    } catch (e) {
      setError(e?.response?.data?.detail || "API error — is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  const markerJunctions = deployResult?.suggested_junctions
    ?.map((j) => ({ name: j, coords: JUNCTION_COORDS[j] }))
    .filter((j) => j.coords) || [];

  const tier = deployResult?.escalation_tier;

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
              <CalendarDays className="w-4 h-4 text-primary" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-foreground">Planned Event Intelligence</h2>
              <p className="text-[10px] text-muted-foreground">Pre-deployment planning for high-impact events</p>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-6">

          {/* Form */}
          <div>
            <p className="section-label mb-4">Event Parameters</p>
            <div className="grid grid-cols-2 gap-3">

              <div className="col-span-2">
                <FieldLabel icon={AlertCircle}>Event Type</FieldLabel>
                <StyledSelect value={form.event_cause} onChange={(e) => setForm((f) => ({ ...f, event_cause: e.target.value }))}>
                  {PLANNED_EVENTS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                </StyledSelect>
              </div>

              <div className="col-span-2">
                <FieldLabel icon={MapPin}>Location (Corridor)</FieldLabel>
                <StyledSelect value={form.corridor} onChange={(e) => setForm((f) => ({ ...f, corridor: e.target.value }))}>
                  {CORRIDORS.map((c) => <option key={c} value={c}>{c}</option>)}
                </StyledSelect>
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
                <FieldLabel icon={Clock}>Time (Hour 0–23)</FieldLabel>
                <StyledInput type="number" min={0} max={23} value={form.hour_of_day}
                  onChange={(e) => setForm((f) => ({ ...f, hour_of_day: e.target.value }))} />
              </div>

            </div>

            <button
              onClick={handleGenerate}
              disabled={loading}
              className="mt-5 w-full bg-primary hover:bg-primary/90 text-primary-foreground font-bold py-2.5 rounded-xl transition-all flex justify-center items-center gap-2 disabled:opacity-50 text-sm glow-yellow"
            >
              {loading
                ? <><Loader2 className="w-4 h-4 animate-spin" />Analyzing Impact…</>
                : <><Zap className="w-4 h-4" />Generate Pre-deployment Plan</>
              }
            </button>

            {error && (
              <div className="mt-3 p-3 bg-destructive/10 border border-destructive/30 rounded-xl text-sm text-destructive">
                {error}
              </div>
            )}
          </div>

          {/* Result */}
          {deployResult && cascadeResult && (
            <div className="space-y-4 border-t border-border pt-5">

              {/* Tier badge & Warning */}
              <div className="flex items-center justify-between">
                <p className="section-label">Pre-Deployment Brief</p>
                {tier && (
                  <div className={clsx("px-3 py-1 rounded-full text-xs font-bold border flex items-center gap-1.5", TIER_CONFIG[tier]?.cls)}>
                    <span className={clsx("w-1.5 h-1.5 rounded-full", TIER_CONFIG[tier]?.dot)} />
                    {tier} Escalation
                  </div>
                )}
              </div>
              
              {/* Product decision disclosure for the demo */}
              <div className="bg-warning/10 border border-warning/30 rounded-lg p-2.5 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-warning mt-0.5 shrink-0" />
                <p className="text-[10px] text-warning/90 leading-tight">
                  <strong>Assumed Pre-deployment Mode:</strong> For planned events, GridSense defaults to worst-case readiness (High Priority, 50% Closure Risk, 2-hour duration) to ensure maximum safety and diversion availability.
                </p>
              </div>

              {/* Metric grid */}
              <div className="grid grid-cols-2 gap-2.5">
                <MetricCard label="Cascade Impact"    value={`${cascadeResult.cascade_multiplier}x`} sub="traffic multiplier" highlight />
                <MetricCard label="Primary Station"   value={deployResult.recommended_station} highlight />
                <MetricCard label="Officers Needed"   value={deployResult.recommended_officer_count} sub="personnel required" highlight />
                <MetricCard label="Corridor Risk"     value={`${deployResult.corridor_risk_score?.toFixed(1)} / 100`} />
              </div>

              {/* Rationale */}
              <div className="bg-muted/20 rounded-xl p-4 border border-border space-y-1.5">
                <p className="text-xs font-semibold text-primary uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Radio className="w-3.5 h-3.5" /> ML Rationale
                </p>
                <p className="text-xs text-muted-foreground leading-relaxed">{deployResult.officer_count_rationale}</p>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  <strong>Cascade Intelligence:</strong> {cascadeResult.interpretation}
                </p>
              </div>

              {/* Junctions */}
              {deployResult.suggested_junctions?.length > 0 && (
                <div>
                  <p className="section-label mb-2.5">Barricade / Deploy At These Junctions</p>
                  <div className="flex flex-wrap gap-2">
                    {deployResult.suggested_junctions.map((j) => (
                      <span key={j} className="text-xs bg-primary/10 text-primary border border-primary/25 px-2.5 py-1.5 rounded-lg flex items-center gap-1.5 font-medium">
                        <MapPin className="w-3 h-3" />
                        {j.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Diversion routes */}
              {deployResult.diversion_routes?.length > 0 && (
                <div>
                  <p className="section-label mb-2.5 flex items-center gap-1.5">
                    <Navigation className="w-3.5 h-3.5 text-primary" />
                    Recommended Diversion Routes
                  </p>
                  <div className="space-y-2">
                    {deployResult.diversion_routes.map((r, i) => (
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
