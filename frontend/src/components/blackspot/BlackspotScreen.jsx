import { useEffect } from 'react';
import { useBlackspotStore } from '../../store/useBlackspotStore';
import BlackspotLeaderboard from './BlackspotLeaderboard';
import BlackspotMapLayer from './BlackspotMapLayer';
import JunctionDetailDrawer from './JunctionDetailDrawer';
import NeglectStationCard from './NeglectStationCard';
import { MapContainer, TileLayer } from 'react-leaflet';

export default function BlackspotScreen() {
  const { fetchBlackspots, fetchNeglectIndex } = useBlackspotStore();

  useEffect(() => {
    fetchBlackspots();
    fetchNeglectIndex();
  }, [fetchBlackspots, fetchNeglectIndex]);

  return (
    <div className="h-full flex relative overflow-hidden">
      {/* Background Map spanning full height */}
      <div className="absolute inset-0 z-0">
        <MapContainer 
          center={[12.9716, 77.5946]} 
          zoom={12} 
          style={{ height: '100%', width: '100%' }}
          zoomControl={false}
        >
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
          <BlackspotMapLayer />
        </MapContainer>
      </div>

      {/* Floating Left Panel - Leaderboard */}
      <div className="relative z-10 w-[400px] h-full p-6 pointer-events-none flex flex-col gap-6">
        <div className="pointer-events-auto flex-1 flex flex-col gap-6">
          <BlackspotLeaderboard />
          <NeglectStationCard />
        </div>
      </div>

      {/* Junction Detail Drawer (Slides from Right) */}
      <JunctionDetailDrawer />
    </div>
  );
}
