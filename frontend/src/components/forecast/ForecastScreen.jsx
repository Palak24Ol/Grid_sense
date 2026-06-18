import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Polyline, Tooltip } from 'react-leaflet';
import { CloudRain, TrendingUp, AlertTriangle, Clock, ChevronDown } from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip as ReTooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';
import { client } from '../../api/client';
import clsx from 'clsx';

// Corridor center coords for map overlays
const CORRIDOR_COORDS = {
  'Bellary Road 1':   [[13.014, 77.583], [13.058, 77.591]],
  'Tumkur Road':      [[12.993, 77.541], [13.035, 77.521]],
  'Mysore Road':      [[12.958, 77.530], [12.927, 77.484]],
  'ORR North 1':      [[13.031, 77.610], [13.041, 77.650]],
  'Hosur Road':       [[12.931, 77.613], [12.886, 77.641]],
  'Magadi Road':      [[12.973, 77.527], [12.985, 77.498]],
  'CBD 2':            [[12.976, 77.586], [12.982, 77.579]],
  'West of Chord Road':[[12.991, 77.539],[13.003, 77.526]],
};

const RISK_COLOR = { critical: '#ef4444', high: '#f97316', medium: '#eab308' };

function RiskBadge({ level }) {
  const colors = {
    critical: 'badge-critical',
    high:     'badge-warning',
    medium:   'badge-medium',
  };
  return (
    <span className={clsx('px-2 py-0.5 rounded-full text-xs font-bold border uppercase tracking-wider', colors[level])}>
      {level}
    </span>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  return (
    <div className="bg-card border border-border rounded-lg p-3 shadow-xl text-xs">
      <p className="font-semibold mb-1">{label}:00</p>
      <p className="text-primary">Predicted: {d?.predicted_incident_count?.toFixed(2)}</p>
      <p className="text-muted-foreground">Range: {d?.yhat_lower?.toFixed(2)} – {d?.yhat_upper?.toFixed(2)}</p>
      {d?.is_peak_hour && <p className="text-warning font-medium mt-1">⚠ Peak hour</p>}
    </div>
  );
}

export default function ForecastScreen() {
  const [corridors, setCorridors] = useState([]);
  const [selected, setSelected]   = useState(null);
  const [junctions, setJunctions] = useState([]);
  const [selJunction, setSelJunction] = useState(null);
  const [chartData, setChartData]     = useState([]);
  const [junctionMeta, setJunctionMeta] = useState(null);
  const [loadingCorridors, setLoadingCorridors] = useState(true);
  const [loadingChart, setLoadingChart]         = useState(false);

  // Load top corridors on mount
  useEffect(() => {
    client.get('/forecast/corridors')
      .then(r => {
        setCorridors(r.data.corridors || []);
        if (r.data.corridors?.length) setSelected(r.data.corridors[0]);
      })
      .catch(() => setCorridors([]))
      .finally(() => setLoadingCorridors(false));

    client.get('/forecast/junctions')
      .then(r => setJunctions(r.data.junctions || []))
      .catch(() => {});
  }, []);

  // Load chart when junction is picked
  useEffect(() => {
    if (!selJunction) return;
    setLoadingChart(true);
    client.get(`/forecast/junction/${encodeURIComponent(selJunction)}`)
      .then(r => {
        setJunctionMeta(r.data);
        const pts = (r.data.forecast || []).slice(0, 48).map(p => ({
          ...p,
          hour_label: String(p.hour_of_day).padStart(2, '0'),
        }));
        setChartData(pts);
      })
      .catch(() => setChartData([]))
      .finally(() => setLoadingChart(false));
  }, [selJunction]);

  const mapCorridors = corridors.map(c => ({
    ...c,
    coords: CORRIDOR_COORDS[c.corridor],
    color:  RISK_COLOR[c.risk_level] || '#6b7280',
  }));

  return (
    <div className="h-full flex flex-col md:flex-row relative">

      {/* Map */}
      <div className="w-full md:w-1/2 h-1/2 md:h-full relative z-0">
        <MapContainer center={[12.98, 77.57]} zoom={12} style={{ height: '100%', width: '100%' }} zoomControl={false}>
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
          {mapCorridors.filter(c => c.coords).map(c => (
            <Polyline
              key={c.corridor}
              positions={c.coords}
              pathOptions={{ color: c.color, weight: selected?.corridor === c.corridor ? 6 : 3, opacity: 0.85 }}
            >
              <Tooltip sticky>{c.corridor} — {c.risk_level?.toUpperCase()}</Tooltip>
            </Polyline>
          ))}
        </MapContainer>
      </div>

      {/* Panel */}
      <div className="w-full md:w-1/2 h-1/2 md:h-full bg-background border-l border-border overflow-y-auto flex flex-col z-10">

        {/* Header */}
        <div className="px-5 py-4 border-b border-border bg-card flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/25 flex items-center justify-center">
              <CloudRain className="w-4 h-4 text-primary" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-foreground">72-Hour Corridor Forecast</h2>
              <p className="text-[10px] text-muted-foreground">Prophet time-series predictions</p>
            </div>
          </div>
          <span className="text-xs text-muted-foreground">{new Date().toLocaleTimeString()}</span>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">

          {/* Top Corridors */}
          <div>
            <p className="section-label mb-3">
              Top Risk Corridors — Next 24h
            </p>
            {loadingCorridors ? (
              <div className="flex items-center gap-2 text-muted-foreground text-sm py-4">
                <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                Loading corridors…
              </div>
            ) : (
              <div className="space-y-2">
                {corridors.slice(0, 5).map(c => (
                  <button
                    key={c.corridor}
                    onClick={() => setSelected(c)}
                    className={clsx(
                      'w-full text-left p-3 rounded-lg border transition-all text-sm',
                      selected?.corridor === c.corridor
                        ? 'border-primary bg-primary/10'
                        : 'border-border bg-muted/10 hover:bg-muted/30'
                    )}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium">{c.corridor}</span>
                      <RiskBadge level={c.risk_level} />
                    </div>
                    <div className="flex gap-4 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <TrendingUp className="w-3 h-3" />
                        {c.next_24h_predicted_incidents} incidents/day
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        Peak {String(c.peak_hour).padStart(2, '0')}:00
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Junction Chart */}
          <div className="border border-border rounded-xl overflow-hidden">
            <div className="p-3 bg-muted/30 border-b border-border flex items-center gap-3">
              <span className="text-sm font-medium">Corridor Detail</span>
              <div className="relative flex-1">
                <select
                  className="w-full bg-muted/30 border border-border rounded-lg px-3 py-1.5 text-xs appearance-none focus:outline-none focus:border-primary/60 transition-colors pr-6"
                  value={selJunction || ''}
                  onChange={e => setSelJunction(e.target.value)}
                >
                  <option value="">— select corridor —</option>
                  {junctions.map(c => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
                </select>
                <ChevronDown className="w-3 h-3 absolute right-2 top-2 text-muted-foreground pointer-events-none" />
              </div>
            </div>

            <div className="p-4">
              {!selJunction && (
                <p className="text-xs text-muted-foreground text-center py-6">
                  Select a corridor above to view its 72-hour Prophet forecast
                </p>
              )}

              {selJunction && loadingChart && (
                <div className="flex items-center justify-center gap-2 text-muted-foreground text-sm py-8">
                  <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                  Running corridor forecast…
                </div>
              )}

              {selJunction && !loadingChart && chartData.length > 0 && (
                <>
                  {junctionMeta && (
                    <div className="flex gap-2.5 mb-4 text-xs">
                      <div className="bg-muted/20 border border-border rounded-xl px-3 py-2 flex-1">
                        <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-0.5">Corridor</p>
                        <p className="font-bold text-foreground text-sm">{junctionMeta.corridor}</p>
                      </div>
                      <div className="bg-muted/20 border border-border rounded-xl px-3 py-2 flex-1">
                        <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-0.5">Hist. Daily Avg</p>
                        <p className="font-bold text-foreground text-sm">{junctionMeta.historical_daily_avg} incidents</p>
                      </div>
                      {junctionMeta.model_mae && (
                        <div className="bg-primary/8 border border-primary/30 rounded-xl px-3 py-2 flex-1">
                          <p className="text-[10px] font-medium text-primary uppercase tracking-wider mb-0.5">Model MAE</p>
                          <p className="font-bold text-primary text-sm">{junctionMeta.model_mae}</p>
                        </div>
                      )}
                    </div>
                  )}

                  <ResponsiveContainer width="100%" height={200}>
                    <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                      <defs>
                        <linearGradient id="bandGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor="hsl(54 95% 51%)" stopOpacity={0.15} />
                          <stop offset="95%" stopColor="hsl(54 95% 51%)" stopOpacity={0.0}  />
                        </linearGradient>
                        <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor="hsl(54 95% 51%)" stopOpacity={0.35} />
                          <stop offset="95%" stopColor="hsl(54 95% 51%)" stopOpacity={0.05} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="hour_label" tick={{ fontSize: 10, fill: '#6b7280' }} interval={5} />
                      <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} />
                      <ReTooltip content={<CustomTooltip />} />
                      <ReferenceLine y={1.5} stroke="#f97316" strokeDasharray="4 2" label={{ value: 'peak', fill: '#f97316', fontSize: 9 }} />
                      {/* Confidence band */}
                      <Area type="monotone" dataKey="yhat_upper" stroke="none" fill="url(#bandGrad)" />
                      <Area type="monotone" dataKey="yhat_lower" stroke="none" fill="#0a0a0f" />
                      {/* Main line */}
                      <Area
                        type="monotone"
                        dataKey="predicted_incident_count"
                        stroke="hsl(54 95% 51%)"
                        strokeWidth={2}
                        fill="url(#lineGrad)"
                        dot={false}
                      />
                    </AreaChart>
                  </ResponsiveContainer>

                  {junctionMeta?.peak_windows?.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {junctionMeta.peak_windows.map((w, i) => (
                        <span key={i} className="text-xs badge-warning px-2.5 py-1 rounded-full flex items-center gap-1.5 font-medium">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          {w.label}: {String(w.start_hour).padStart(2,'0')}:00 – {String(w.end_hour).padStart(2,'0')}:00
                        </span>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
