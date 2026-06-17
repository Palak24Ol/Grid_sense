import { useBlackspotStore } from '../../store/useBlackspotStore';
import { Marker, Popup, CircleMarker, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useEffect } from 'react';

const createChronicMarker = () => L.divIcon({
  className: 'custom-leaflet-icon',
  html: `<div class="relative w-6 h-6 flex items-center justify-center">
           <div class="absolute w-full h-full bg-destructive rounded-full animate-ping opacity-75"></div>
           <div class="relative w-3 h-3 bg-destructive rounded-full border border-card"></div>
         </div>`,
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

const createCriticalMarker = () => L.divIcon({
  className: 'custom-leaflet-icon',
  html: `<div class="w-4 h-4 rounded-full bg-amber-500 border-2 border-card shadow-[0_0_10px_rgba(245,158,11,0.5)]"></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

export default function BlackspotMapLayer() {
  const { blackspots, selectedJunction } = useBlackspotStore();
  const map = useMap();

  useEffect(() => {
    if (selectedJunction) {
      map.flyTo([selectedJunction.latitude, selectedJunction.longitude], 15, { animate: true, duration: 1.5 });
    }
  }, [selectedJunction, map]);

  return (
    <>
      {blackspots.map(b => {
        if (b.blackspot_tier === 'Chronic' || b.blackspot_tier === 'Critical') {
          return (
            <Marker 
              key={b.junction} 
              position={[b.latitude, b.longitude]}
              icon={b.blackspot_tier === 'Chronic' ? createChronicMarker() : createCriticalMarker()}
            >
              <Popup className="custom-popup">
                <div className="p-1">
                  <h3 className="font-bold text-sm mb-1">{b.junction}</h3>
                  <div className="text-xs space-y-1">
                    <p className="text-muted-foreground"><span className="text-foreground font-medium">Score:</span> {b.blackspot_score}</p>
                    <p className="text-muted-foreground"><span className="text-foreground font-medium">Recurrence:</span> {b.recurrence_weeks} weeks</p>
                    <p className="text-muted-foreground capitalize"><span className="text-foreground font-medium">Top Cause:</span> {b.top_cause.replace('_', ' ')}</p>
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        } else {
          return (
            <CircleMarker
              key={b.junction}
              center={[b.latitude, b.longitude]}
              radius={5}
              pathOptions={{ color: '#3b82f6', fillColor: '#3b82f6', fillOpacity: 0.8, weight: 1 }}
            >
              <Popup className="custom-popup">
                <div className="p-1 text-xs">
                  <h3 className="font-bold">{b.junction}</h3>
                  <p>Score: {b.blackspot_score}</p>
                </div>
              </Popup>
            </CircleMarker>
          );
        }
      })}
    </>
  );
}
