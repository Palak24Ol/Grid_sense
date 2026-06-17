import { useEffect } from 'react';
import { useSurgeStore } from '../../store/useSurgeStore';
import SurgeDashboard from './SurgeDashboard';
import March7ReplayPanel from './March7ReplayPanel';
import SurgeVulnerabilityMap from './SurgeVulnerabilityMap';
import { MapContainer, TileLayer } from 'react-leaflet';

export default function SurgeScreen() {
  const { fetchSurgeData, vulnerability, loading } = useSurgeStore();

  useEffect(() => {
    fetchSurgeData();
  }, [fetchSurgeData]);

  return (
    <div className="h-full flex flex-col md:flex-row relative">
      {/* Background Map spanning full height, behind elements on mobile, side-by-side on desktop */}
      <div className="w-full md:w-1/2 h-1/2 md:h-full relative z-0">
        <MapContainer 
          center={[12.9716, 77.5946]} 
          zoom={12} 
          style={{ height: '100%', width: '100%' }}
          zoomControl={false}
        >
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
          <SurgeVulnerabilityMap />
        </MapContainer>
      </div>

      {/* Right Panel - Dashboards */}
      <div className="w-full md:w-1/2 h-1/2 md:h-full bg-background border-l border-border p-6 overflow-y-auto flex flex-col gap-6 relative z-10">
        {loading ? (
          <div className="flex-1 flex items-center justify-center text-muted-foreground animate-pulse">
            Loading Surge Data...
          </div>
        ) : !vulnerability ? (
          <div className="flex-1 flex items-center justify-center text-amber-500 bg-amber-500/10 border border-amber-500/20 rounded-xl p-4">
            Surge data not available. Run the pipeline first.
          </div>
        ) : (
          <>
            <SurgeDashboard />
            <March7ReplayPanel />
          </>
        )}
      </div>
    </div>
  );
}
