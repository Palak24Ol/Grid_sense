import { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useMapStore } from '../../store/useMapStore';

// Custom Map Updater component to react to viewport changes
function MapUpdater({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom);
  }, [center, zoom, map]);
  return null;
}

const createIncidentIcon = (priority) => {
  const color = priority === 'High' ? 'bg-destructive' : priority === 'Medium' ? 'bg-amber-500' : 'bg-primary';
  return L.divIcon({
    className: 'custom-leaflet-icon',
    html: `<div class="w-4 h-4 rounded-full ${color} border-2 border-card shadow-[0_0_10px_rgba(0,0,0,0.5)]"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });
};

export default function CommandCenterMap({ incidents = [], className = "h-full w-full rounded-xl overflow-hidden shadow-md border border-border" }) {
  const { viewport } = useMapStore();

  return (
    <div className={className}>
      <MapContainer 
        center={viewport.center} 
        zoom={viewport.zoom} 
        style={{ height: '100%', width: '100%', zIndex: 0 }}
      >
        <MapUpdater center={viewport.center} zoom={viewport.zoom} />
        
        {/* Dark Mode Map Tiles (CartoDB Dark Matter) */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        />

        {incidents.map(inc => (
          <Marker 
            key={inc.id} 
            position={[inc.latitude, inc.longitude]}
            icon={createIncidentIcon(inc.priority)}
          >
            <Popup className="custom-popup">
              <div className="p-1">
                <h3 className="font-bold text-sm mb-1">{inc.junction || "Unknown Junction"}</h3>
                <p className="text-xs text-muted-foreground capitalize">{inc.event_cause.replace('_', ' ')}</p>
                <div className="mt-2 text-xs">
                  <span className={`px-2 py-0.5 rounded-full ${inc.priority === 'High' ? 'bg-destructive/20 text-destructive' : 'bg-primary/20 text-primary'}`}>
                    {inc.priority} Priority
                  </span>
                </div>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
