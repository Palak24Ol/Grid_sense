import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Polyline, Tooltip } from 'react-leaflet';
import { Package, Truck, AlertTriangle, Navigation, TrendingUp, RefreshCw } from 'lucide-react';
import { client } from '../../api/client';
import clsx from 'clsx';

const CORRIDOR_COORDS = {
  'Tumkur Road':    [[12.993, 77.541], [13.035, 77.521]],
  'Bellary Road 1': [[13.014, 77.583], [13.058, 77.591]],
  'Mysore Road':    [[12.958, 77.530], [12.927, 77.484]],
  'ORR North 2':    [[13.055, 77.597], [13.063, 77.553]],
  'Bellary Road 2': [[13.050, 77.590], [13.072, 77.601]],
};

const RISK_COLORS = { high: '#ef4444', medium: '#f97316', low: '#22c55e' };
const RISK_BADGE = {
  high:   'bg-red-500/20 text-red-400 border-red-500/30',
  medium: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  low:    'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
};

export default function FlipkartScreen() {
  const [data, setData]       = useState(null);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    client.get('/lcv/risk')
      .then(r => {
        setData(r.data);
        if (r.data.corridors?.length) setSelected(r.data.corridors[0]);
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const corridors = data?.corridors || [];

  return (
    <div className="h-full flex flex-col md:flex-row relative">

      {/* Map */}
      <div className="w-full md:w-1/2 h-1/2 md:h-full relative z-0">
        <MapContainer center={[12.98, 77.57]} zoom={12} style={{ height: '100%', width: '100%' }} zoomControl={false}>
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
          {corridors.map(c => {
            const coords = CORRIDOR_COORDS[c.corridor];
            if (!coords) return null;
            return (
              <Polyline
                key={c.corridor}
                positions={coords}
                pathOptions={{
                  color: RISK_COLORS[c.risk_level] || '#6b7280',
                  weight: selected?.corridor === c.corridor ? 7 : 3,
                  opacity: 0.85,
                  dashArray: c.risk_level === 'medium' ? '6 4' : undefined,
                }}
              >
                <Tooltip sticky>
                  <strong>{c.corridor}</strong><br />
                  {c.active_lcv_incidents} active LCV incidents<br />
                  Avg delay: {c.avg_delay_mins} min
                </Tooltip>
              </Polyline>
            );
          })}
        </MapContainer>
      </div>

      {/* Panel */}
      <div className="w-full md:w-1/2 h-1/2 md:h-full bg-background border-l border-border overflow-y-auto flex flex-col z-10">

        <div className="p-4 border-b border-border bg-muted/30 shrink-0 flex items-center justify-between">
          <h2 className="font-semibold flex items-center gap-2">
            <Package className="w-5 h-5 text-primary" />
            LCV Logistics Intelligence
          </h2>
          <button onClick={load} className="text-muted-foreground hover:text-foreground transition-colors">
            <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />
          </button>
        </div>

        {loading && (
          <div className="flex-1 flex items-center justify-center gap-2 text-muted-foreground text-sm">
            <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            Loading LCV data…
          </div>
        )}

        {!loading && data && (
          <div className="flex-1 overflow-y-auto p-5 space-y-5">

            {/* Summary stats */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-muted/20 border border-border rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-red-400">{data.high_risk_corridors}</p>
                <p className="text-xs text-muted-foreground mt-0.5">High Risk</p>
              </div>
              <div className="bg-muted/20 border border-border rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-orange-400">{data.active_disruptions}</p>
                <p className="text-xs text-muted-foreground mt-0.5">Active Disruptions</p>
              </div>
              <div className="bg-muted/20 border border-border rounded-lg p-3 text-center">
                <p className="text-2xl font-bold">{data.weekly_avg_lcv_incidents}</p>
                <p className="text-xs text-muted-foreground mt-0.5">Incidents/Week</p>
              </div>
            </div>

            {/* Surge day callout */}
            {data.surge_day_reference && (
              <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl">
                <p className="text-xs font-semibold text-red-400 flex items-center gap-1.5 mb-2">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Worst-Case Reference — {data.surge_day_reference.date}
                </p>
                <p className="text-sm text-foreground/80">
                  {data.surge_day_reference.surge_multiplier}x surge ({data.surge_day_reference.total_lcv_incidents} vs {data.surge_day_reference.baseline_daily_avg} baseline).
                  Cause: <span className="font-medium capitalize">{data.surge_day_reference.primary_cause.replace('_', ' ')}</span>.
                  {' '}{data.surge_day_reference.estimated_total_delay_hrs} total delay-hours across fleet.
                </p>
              </div>
            )}

            {/* Corridor list */}
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Corridor Risk Breakdown
              </p>
              <div className="space-y-2">
                {corridors.map(c => (
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
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Truck className="w-4 h-4 text-muted-foreground" />
                        <span className="font-medium">{c.corridor}</span>
                      </div>
                      <span className={clsx('px-2 py-0.5 rounded-full text-xs font-bold border uppercase', RISK_BADGE[c.risk_level])}>
                        {c.risk_level}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <TrendingUp className="w-3 h-3" />{c.incident_count} incidents
                      </span>
                      <span>{c.active_lcv_incidents} active</span>
                      <span className="text-orange-400">+{c.avg_delay_mins} min avg</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Selected corridor detail */}
            {selected && (
              <div className="border border-primary/30 bg-primary/5 rounded-xl p-4 space-y-3">
                <p className="font-semibold text-sm">{selected.corridor} — Detail</p>

                <div>
                  <p className="text-xs text-muted-foreground mb-1.5">Impacted Hubs</p>
                  <div className="flex flex-wrap gap-2">
                    {selected.impacted_hubs?.map(h => (
                      <span key={h} className="text-xs bg-muted/30 border border-border px-2 py-0.5 rounded-md">
                        {h}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
                  <p className="text-xs font-medium text-emerald-400 flex items-center gap-1.5 mb-1">
                    <Navigation className="w-3.5 h-3.5" />
                    Suggested Reroute
                  </p>
                  <p className="text-sm font-semibold">{selected.suggested_reroute}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    +{selected.reroute_extra_mins} min vs. direct route
                  </p>
                </div>
              </div>
            )}

          </div>
        )}

        {!loading && !data && (
          <div className="flex-1 flex items-center justify-center p-6 text-center">
            <div className="space-y-2">
              <AlertTriangle className="w-8 h-8 text-muted-foreground mx-auto" />
              <p className="text-sm text-muted-foreground">LCV API unavailable. Is the backend running?</p>
              <button onClick={load} className="text-xs text-primary hover:underline">Retry</button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
