import { ShieldAlert, TrendingUp, Users, MapPin } from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import clsx from 'clsx';

// A simple small map focusing on the first at-risk junction, or Bangalore center
function RippleMapMini({ junctions }) {
  const center = junctions.length > 0 ? [junctions[0].latitude, junctions[0].longitude] : [12.9716, 77.5946];
  
  return (
    <div className="h-48 w-full rounded-xl overflow-hidden border border-border relative z-0">
      <MapContainer center={center} zoom={13} style={{ height: '100%', width: '100%' }} zoomControl={false}>
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
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
                <div className="text-xs text-destructive">Score: {j.blackspot_score}</div>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}

export default function CascadeRippleCard({ result }) {
  if (!result) return null;

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden flex flex-col h-full">
      <div className="p-4 border-b border-border bg-muted/30 flex items-center justify-between">
        <h2 className="font-semibold flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-amber-500" />
          Cascade Ripple Predictor
        </h2>
        <span className={clsx(
          "px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider",
          result.risk_level === 'critical' ? "bg-destructive/20 text-destructive" :
          result.risk_level === 'high' ? "bg-amber-500/20 text-amber-500" :
          "bg-primary/20 text-primary"
        )}>
          {result.risk_level} Risk
        </span>
      </div>

      <div className="p-6 flex-1 overflow-y-auto space-y-6">
        
        {/* Interpretation Box */}
        <div className="p-4 rounded-xl border border-primary/20 bg-primary/5 text-sm leading-relaxed">
          {result.interpretation}
        </div>

        {/* Top Metrics Row */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 rounded-xl border border-border bg-muted/20 flex flex-col items-center justify-center text-center">
            <span className="text-sm text-muted-foreground mb-1">Incident Multiplier</span>
            <span className="text-3xl font-bold text-amber-500">
              {result.cascade_multiplier}x
            </span>
            <span className="text-xs text-muted-foreground mt-2">
              in next {result.cascade_window_hours} hours
            </span>
          </div>

          <div className="p-4 rounded-xl border border-border bg-muted/20 flex flex-col items-center justify-center text-center">
            <span className="text-sm text-muted-foreground mb-1">Required Buffer</span>
            <span className="text-3xl font-bold text-primary flex items-center gap-2">
              <Users className="w-6 h-6" /> +{result.recommended_officer_buffer}
            </span>
            <span className="text-xs text-muted-foreground mt-2">
              additional officers
            </span>
          </div>
        </div>

        {/* Embedded Map */}
        {result.primary_junctions_at_risk && result.primary_junctions_at_risk.length > 0 && (
          <div className="space-y-3">
            <h3 className="font-medium text-sm flex items-center gap-2">
              <MapPin className="w-4 h-4 text-muted-foreground" />
              Primary Epicenters
            </h3>
            <RippleMapMini junctions={result.primary_junctions_at_risk} />
          </div>
        )}

        {/* Adjacent Spillover */}
        {result.adjacent_corridor_spillover && result.adjacent_corridor_spillover.length > 0 && (
          <div className="space-y-3">
            <h3 className="font-medium text-sm text-muted-foreground">Adjacent Corridor Spillover</h3>
            <div className="grid grid-cols-2 gap-3">
              {result.adjacent_corridor_spillover.map((adj) => (
                <div key={adj.corridor} className="p-3 border border-border rounded-lg bg-muted/10 flex justify-between items-center">
                  <span className="text-sm font-medium">{adj.corridor}</span>
                  <span className={clsx(
                    "text-xs font-bold px-2 py-0.5 rounded-full",
                    adj.risk_level === 'moderate' ? 'bg-amber-500/20 text-amber-500' : 'bg-primary/20 text-primary'
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
