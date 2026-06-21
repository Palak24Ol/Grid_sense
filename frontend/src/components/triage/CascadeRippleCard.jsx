import { TrendingUp, Users, MapPin } from 'lucide-react';
import { MapContainer, TileLayer, Popup, CircleMarker } from 'react-leaflet';
import clsx from 'clsx';

function RippleMapMini({ junctions }) {
  const center = junctions.length > 0
    ? [junctions[0].latitude, junctions[0].longitude]
    : [12.9716, 77.5946];

  return (
    <div className="h-48 w-full rounded-xl overflow-hidden border border-border relative z-0">
      <MapContainer center={center} zoom={13} style={{ height: '100%', width: '100%' }} zoomControl={false}>
        <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
        {junctions.map((j) => (
          <CircleMarker
            key={j.junction}
            center={[j.latitude, j.longitude]}
            radius={8}
            pathOptions={{ color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.6, weight: 2 }}
          >
            <Popup className="custom-popup">
              <div className="p-1">
                <div className="font-bold text-sm">{j.junction}</div>
                <div className="text-xs text-muted-foreground">High risk junction</div>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}

// Clean the interpretation text — remove any technical phrases
function cleanInterpretation(text) {
  if (!text) return '';
  return text
    .replace(/cascade multiplier[^.]*\./gi, '')
    .replace(/historical base[^.]*\./gi, '')
    .replace(/\d+\.\d+x multiplier/gi, '')
    .replace(/statistically[^.]*\./gi, '')
    .trim();
}

export default function CascadeRippleCard({ result }) {
  if (!result) return null;

  const riskLabel = {
    critical: 'Very High',
    high:     'High',
    medium:   'Medium',
  }[result.risk_level] || result.risk_level;

  const interpretation = cleanInterpretation(result.interpretation);

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden flex flex-col h-full">
      <div className="p-4 border-b border-border bg-muted/30 flex items-center justify-between">
        <h2 className="font-semibold flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-warning" />
          Nearby Road Impact
        </h2>
        <span className={clsx(
          "px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider",
          result.risk_level === 'critical' ? "badge-critical" :
          result.risk_level === 'high'     ? "badge-warning"  :
          "badge-medium"
        )}>
          {riskLabel} Risk
        </span>
      </div>

      <div className="p-6 flex-1 overflow-y-auto space-y-6">

        {/* Plain interpretation */}
        {interpretation && (
          <div className="p-4 rounded-xl border border-primary/30 bg-primary/8 text-sm leading-relaxed">
            {interpretation}
          </div>
        )}

        {/* Key numbers */}
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-xl p-4 border border-border bg-muted/20 flex flex-col items-center justify-center text-center gap-1">
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Traffic will be</span>
            <span className="text-3xl font-bold text-warning">
              {result.cascade_multiplier}x worse
            </span>
            <span className="text-xs text-muted-foreground mt-2">
              in the next {result.cascade_window_hours} hours
            </span>
          </div>

          <div className="rounded-xl p-4 border border-border bg-muted/20 flex flex-col items-center justify-center text-center gap-1">
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Extra Officers Needed</span>
            <span className="text-3xl font-bold text-primary flex items-center gap-2">
              <Users className="w-6 h-6" /> +{result.recommended_officer_buffer}
            </span>
            <span className="text-xs text-muted-foreground mt-2">
              additional officers
            </span>
          </div>
        </div>

        {/* Map */}
        {result.primary_junctions_at_risk && result.primary_junctions_at_risk.length > 0 && (
          <div className="space-y-3">
            <h3 className="font-medium text-sm flex items-center gap-2">
              <MapPin className="w-4 h-4 text-muted-foreground" />
              Junctions most at risk
            </h3>
            <RippleMapMini junctions={result.primary_junctions_at_risk} />
          </div>
        )}

        {/* Spillover roads */}
        {result.adjacent_corridor_spillover && result.adjacent_corridor_spillover.length > 0 && (
          <div className="space-y-3">
            <h3 className="section-label">Nearby roads also affected</h3>
            <div className="grid grid-cols-2 gap-3">
              {result.adjacent_corridor_spillover.map((adj) => (
                <div key={adj.corridor} className="p-3 border border-border rounded-lg bg-muted/10 flex justify-between items-center">
                  <span className="text-sm font-medium">{adj.corridor}</span>
                  <span className={clsx(
                    "text-xs font-bold px-2 py-0.5 rounded-full",
                    adj.risk_level === 'moderate' ? 'badge-warning' : 'badge-medium'
                  )}>
                    {adj.spillover_multiplier}x
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}