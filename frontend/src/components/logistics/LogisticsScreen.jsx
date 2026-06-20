import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Polyline, Tooltip } from 'react-leaflet';
import { Package, Truck, AlertTriangle, Navigation, TrendingUp, RefreshCw, Info } from 'lucide-react';
import { client } from '../../api/client';
import clsx from 'clsx';

const CORRIDOR_COORDS = {
  'Tumkur Road':    [[12.993, 77.541], [13.035, 77.521]],
  'Bellary Road 1': [[13.014, 77.583], [13.058, 77.591]],
  'Mysore Road':    [[12.958, 77.530], [12.927, 77.484]],
  'ORR North 2':    [[13.055, 77.597], [13.063, 77.553]],
  'Bellary Road 2': [[13.050, 77.590], [13.072, 77.601]],
};

const RISK_COLORS = { high: '#ef4444', medium: '#F9E107', low: '#22c55e' };
const RISK_BADGE = {
  high:   'badge-critical',
  medium: 'badge-warning',
  low:    'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
};

export default function LogisticsScreen() {
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
  const recent7dTotal = corridors.reduce((sum, c) => sum + (c.recent_7d_incidents || 0), 0);

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
                  {c.incident_count} incidents in dataset<br />
                  Avg delay: {c.avg_delay_mins ?? '—'} min
                </Tooltip>
              </Polyline>
            );
          })}
        </MapContainer>
      </div>

      {/* Panel */}
      <div className="w-full md:w-1/2 h-1/2 md:h-full bg-background border-l border-border overflow-y-auto flex flex-col z-10">

        <div className="p-4 border-b border-border bg-card shrink-0 flex items-center justify-between">
          <h2 className="text-sm font-bold text-foreground flex items-center gap-2">
            <Package className="w-4 h-4 text-primary" />
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

        {!loading && data && !data.error && (
          <div className="flex-1 overflow-y-auto p-5 space-y-5">

            {/* Summary stats */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-muted/20 border border-border rounded-xl p-3 text-center flex flex-col items-center justify-center gap-1">
                <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">High Risk</span>
                <p className="text-2xl font-bold text-destructive">{data.high_risk_corridors}</p>
              </div>
              <div className="bg-muted/20 border border-border rounded-xl p-3 text-center flex flex-col items-center justify-center gap-1">
                <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Incidents (last 7d)</span>
                <p className="text-2xl font-bold text-warning">{recent7dTotal}</p>
              </div>
              <div className="bg-muted/20 border border-border rounded-xl p-3 text-center flex flex-col items-center justify-center gap-1">
                <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Incidents/Week</span>
                <p className="text-2xl font-bold text-foreground">{data.weekly_avg_lcv_incidents}</p>
              </div>
            </div>

            {/* Surge day callout */}
            {data.surge_day_reference && !data.surge_day_reference.error && (
              <div className="p-4 bg-destructive/10 border border-destructive/30 rounded-xl">
                <p className="text-xs font-bold uppercase tracking-wider text-destructive flex items-center gap-1.5 mb-2">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Worst-Case Reference — {data.surge_day_reference.date}
                </p>
                <p className="text-sm text-foreground/80">
                  {data.surge_day_reference.surge_multiplier}x surge ({data.surge_day_reference.total_lcv_incidents} vs {data.surge_day_reference.baseline_daily_avg}/day baseline).
                  Cause: <span className="font-medium capitalize">{(data.surge_day_reference.primary_cause || 'unknown').replace(/_/g, ' ')}</span>.
                  {' '}{data.surge_day_reference.estimated_total_delay_hrs} total delay-hours across fleet.
                </p>
              </div>
            )}

            {/* Disclosure — now reflects what's actually computed, not a stale snapshot */}
            <div className="flex items-start gap-2 p-3 bg-primary/10 border border-primary/20 rounded-lg text-xs text-primary/80">
              <Info className="w-4 h-4 shrink-0 mt-0.5" />
              <p>
                <strong>Methodology:</strong> {data.data_note || `Computed live from ${data.total_lcv_incidents_dataset} historical LCV incidents.`}
              </p>
            </div>

            {/* Corridor list */}
            <div>
              <p className="section-label mb-3">
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
                        <TrendingUp className="w-3 h-3" />{c.incident_count} total
                      </span>
                      <span>{c.recent_7d_incidents} last 7d</span>
                      <span className="text-warning">{c.avg_delay_mins != null ? `+${c.avg_delay_mins} min avg` : 'no delay data'}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Selected corridor detail */}
            {selected && (
              <div className="border border-primary/30 bg-primary/10 rounded-xl p-4 space-y-3">
                <p className="font-bold text-sm text-foreground">{selected.corridor} — Detail</p>

                {selected.impacted_hubs?.length > 0 && (
                  <div>
                    <p className="text-xs text-muted-foreground mb-1.5">Impacted Hubs</p>
                    <div className="flex flex-wrap gap-2">
                      {selected.impacted_hubs.map(h => (
                        <span key={h} className="text-xs bg-muted/30 border border-border px-2 py-0.5 rounded-md">
                          {h}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {selected.suggested_reroute ? (
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
                ) : (
                  <p className="text-xs text-muted-foreground">No diversion route on file for this corridor.</p>
                )}
              </div>
            )}

          </div>
        )}

        {!loading && (!data || data.error) && (
          <div className="flex-1 flex items-center justify-center p-6 text-center">
            <div className="space-y-2">
              <AlertTriangle className="w-8 h-8 text-muted-foreground mx-auto" />
              <p className="text-sm text-muted-foreground">
                {data?.error || 'LCV API unavailable. Is the backend running?'}
              </p>
              <button onClick={load} className="text-xs text-primary hover:underline">Retry</button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
