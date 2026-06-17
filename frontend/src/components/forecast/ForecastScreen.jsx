import { MapContainer, TileLayer } from 'react-leaflet';
import { CloudRain } from 'lucide-react';

export default function ForecastScreen() {
  return (
    <div className="h-full flex flex-col md:flex-row relative">
      <div className="w-full md:w-1/2 h-1/2 md:h-full relative z-0">
        <MapContainer center={[12.9716, 77.5946]} zoom={12} style={{ height: '100%', width: '100%' }} zoomControl={false}>
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
        </MapContainer>
      </div>
      <div className="w-full md:w-1/2 h-1/2 md:h-full bg-background border-l border-border p-6 overflow-y-auto flex flex-col gap-6 relative z-10">
        <div className="p-4 border-b border-border bg-muted/30">
          <h2 className="font-semibold flex items-center gap-2">
            <CloudRain className="w-5 h-5 text-primary" />
            2-Hour Forecast (Coming Soon)
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            Predictive heatmap for upcoming congestion based on weather and historical data.
          </p>
        </div>
      </div>
    </div>
  );
}
