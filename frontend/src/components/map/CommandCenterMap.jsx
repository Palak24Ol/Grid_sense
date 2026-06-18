import { useEffect, useState, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useMapStore } from '../../store/useMapStore';
import { getIncidents } from '../../api/incidents';

// ─── Map viewport updater ──────────────────────────────────────────────────
function MapUpdater({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom);
  }, [center, zoom, map]);
  return null;
}

// ─── Priority → colour + pulse ────────────────────────────────────────────
// Modified to use Gridlock Theme Colors (Medium = Flipkart Yellow)
const PRIORITY_STYLES = {
  High:   { bg: '#ef4444', border: '#fca5a5', shadow: 'rgba(239,68,68,0.6)',   size: 14, pulse: true  },
  Medium: { bg: '#F9E107', border: '#fcd34d', shadow: 'rgba(249,225,7,0.5)',  size: 12, pulse: false },
  Low:    { bg: '#22c55e', border: '#86efac', shadow: 'rgba(34,197,94,0.4)',   size: 10, pulse: false },
};

const createIncidentIcon = (priority) => {
  const s = PRIORITY_STYLES[priority] || PRIORITY_STYLES.Low;
  const pulseRing = s.pulse
    ? `<div style="
        position:absolute; top:50%; left:50%;
        transform:translate(-50%,-50%);
        width:${s.size + 10}px; height:${s.size + 10}px;
        border-radius:50%;
        background:${s.bg};
        opacity:0.35;
        animation:pulseRing 1.8s ease-out infinite;
      "></div>`
    : '';
  return L.divIcon({
    className: '',
    html: `
      <div style="position:relative;width:${s.size + 10}px;height:${s.size + 10}px;display:flex;align-items:center;justify-content:center;">
        ${pulseRing}
        <div style="
          width:${s.size}px; height:${s.size}px;
          border-radius:50%;
          background:${s.bg};
          border:2px solid ${s.border};
          box-shadow:0 0 8px ${s.shadow};
          position:relative; z-index:1;
        "></div>
      </div>`,
    iconSize: [s.size + 10, s.size + 10],
    iconAnchor: [(s.size + 10) / 2, (s.size + 10) / 2],
  });
};

// ─── Cause label formatter ─────────────────────────────────────────────────
const formatCause = (cause = '') =>
  cause.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

// ─── Filter pills ──────────────────────────────────────────────────────────
const FILTERS = ['All', 'High', 'Medium', 'Low'];

// ─── Stat bar ──────────────────────────────────────────────────────────────
function StatBar({ incidents }) {
  const high   = incidents.filter(i => i.priority === 'High').length;
  const medium = incidents.filter(i => i.priority === 'Medium').length;
  const low    = incidents.filter(i => i.priority === 'Low').length;
  const closures = incidents.filter(i => i.requires_road_closure).length;

  const chip = (label, value, color) => (
    <div style={{
      display:'flex', alignItems:'center', gap:6,
      padding:'5px 12px', borderRadius:8,
      background: color + '18', border:`1px solid ${color}30`,
    }}>
      <span style={{fontSize:11, color:'#9ca3af'}}>{label}</span>
      <span style={{fontSize:15, fontWeight:700, color}}>{value}</span>
    </div>
  );

  return (
    <div style={{
      position:'absolute', top:12, left:'50%', transform:'translateX(-50%)',
      zIndex:1000, display:'flex', gap:8,
      background:'rgba(15,20,30,0.85)',
      backdropFilter:'blur(8px)',
      border:'1px solid rgba(255,255,255,0.08)',
      borderRadius:12, padding:'8px 14px',
      boxShadow:'0 4px 24px rgba(0,0,0,0.5)',
      fontFamily:'inherit',
    }}>
      {chip('Active jams', incidents.length, '#60a5fa')}
      <div style={{width:1, background:'rgba(255,255,255,0.1)'}} />
      {chip('Act Now', high, '#ef4444')}
      {chip('Watch', medium, '#F9E107')}
      {chip('Clear', low, '#22c55e')}
      <div style={{width:1, background:'rgba(255,255,255,0.1)'}} />
      {chip('Road closures', closures, '#a78bfa')}
    </div>
  );
}

// ─── Filter bar ────────────────────────────────────────────────────────────
function FilterBar({ active, onChange }) {
  return (
    <div style={{
      position:'absolute', bottom:28, left:'50%', transform:'translateX(-50%)',
      zIndex:1000, display:'flex', gap:6,
      background:'rgba(15,20,30,0.85)',
      backdropFilter:'blur(8px)',
      border:'1px solid rgba(255,255,255,0.08)',
      borderRadius:20, padding:'5px 8px',
      boxShadow:'0 4px 24px rgba(0,0,0,0.5)',
      fontFamily:'inherit',
    }}>
      {FILTERS.map(f => {
        const isActive = active === f;
        const color = f === 'High' ? '#ef4444' : f === 'Medium' ? '#F9E107' : f === 'Low' ? '#22c55e' : '#60a5fa';
        return (
          <button
            key={f}
            onClick={() => onChange(f)}
            style={{
              padding:'4px 14px', borderRadius:14, border:'none', cursor:'pointer',
              fontSize:12, fontWeight: isActive ? 600 : 400,
              background: isActive ? (f === 'Medium' ? '#F9E107' : color) : 'transparent',
              color: isActive ? (f === 'Medium' ? '#181C21' : '#fff') : '#9ca3af',
              transition:'all 0.15s',
            }}
          >
            {f}
          </button>
        );
      })}
    </div>
  );
}

// ─── Loading overlay ───────────────────────────────────────────────────────
function LoadingOverlay() {
  return (
    <div style={{
      position:'absolute', inset:0, zIndex:2000,
      background:'rgba(10,15,25,0.75)',
      backdropFilter:'blur(4px)',
      display:'flex', flexDirection:'column',
      alignItems:'center', justifyContent:'center',
      gap:14,
    }}>
      <div style={{
        width:36, height:36, borderRadius:'50%',
        border:'3px solid rgba(96,165,250,0.2)',
        borderTopColor:'#60a5fa',
        animation:'spin 0.8s linear infinite',
      }} />
      <span style={{color:'#9ca3af', fontSize:13}}>Loading live incidents…</span>
    </div>
  );
}

// ─── Popup card ────────────────────────────────────────────────────────────
function IncidentPopup({ inc }) {
  const priorityColor = inc.priority === 'High' ? '#ef4444' : inc.priority === 'Medium' ? '#F9E107' : '#22c55e';
  const badgeTextColor = inc.priority === 'Medium' ? '#F9E107' : priorityColor;
  return (
    <div style={{fontFamily:'inherit', minWidth:180}}>
      <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:6}}>
        <span style={{fontWeight:600, fontSize:13, color:'#f1f5f9'}}>
          {inc.junction || 'Unknown junction'}
        </span>
        <span style={{
          fontSize:10, fontWeight:700, padding:'2px 7px', borderRadius:6,
          background: priorityColor + '22', color: badgeTextColor,
          border:`1px solid ${priorityColor}44`,
          textTransform:'uppercase', letterSpacing:'0.05em',
        }}>
          {inc.priority === 'High' ? 'Act Now' : inc.priority === 'Medium' ? 'Watch' : 'Clear'}
        </span>
      </div>
      <div style={{fontSize:12, color:'#94a3b8', marginBottom:4}}>
        📍 {inc.corridor}
      </div>
      <div style={{fontSize:12, color:'#94a3b8', marginBottom:4}}>
        🚗 {formatCause(inc.event_cause)}
        {inc.event_type === 'planned' && (
          <span style={{marginLeft:6, fontSize:10, color:'#818cf8', background:'#818cf822', padding:'1px 5px', borderRadius:4}}>Planned</span>
        )}
      </div>
      <div style={{fontSize:12, color:'#94a3b8', marginBottom:6}}>
        ⏱ Expected to clear in {inc.duration_mins >= 60
          ? `${Math.round(inc.duration_mins / 60 * 10) / 10} hrs`
          : `${inc.duration_mins} mins`}
      </div>
      {inc.requires_road_closure && (
        <div style={{
          fontSize:11, fontWeight:600, color:'#f87171',
          background:'#ef444415', border:'1px solid #ef444430',
          borderRadius:6, padding:'3px 8px', marginBottom:4,
        }}>
          ⛔ Road closed
        </div>
      )}
      <div style={{fontSize:11, color:'#64748b', marginTop:4}}>
        🚔 {inc.police_station}
      </div>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────
export default function CommandCenterMap({
  className = "h-full w-full rounded-xl overflow-hidden shadow-md border border-border",
}) {
  const { viewport } = useMapStore();

  const [incidents,   setIncidents]   = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState(null);
  const [activeFilter, setActiveFilter] = useState('All');
  const [lastUpdated, setLastUpdated] = useState(null);

  // ── fetch on mount ───────────────────────────────────────────────────────
  const fetchIncidents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getIncidents();
      setIncidents(data.incidents || []);
      setLastUpdated(new Date().toLocaleTimeString('en-IN', { hour:'2-digit', minute:'2-digit' }));
    } catch (err) {
      setError('Could not load incidents. Showing last known data.');
      console.error('[CommandCenterMap] fetch failed:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIncidents();
  }, [fetchIncidents]);

  // ── filter ───────────────────────────────────────────────────────────────
  const visible = activeFilter === 'All'
    ? incidents
    : incidents.filter(i => i.priority === activeFilter);

  return (
    <>
      {/* keyframe animations injected once */}
      <style>{`
        @keyframes pulseRing {
          0%   { transform:translate(-50%,-50%) scale(0.8); opacity:0.6; }
          100% { transform:translate(-50%,-50%) scale(2.2); opacity:0; }
        }
        @keyframes spin {
          to { transform:rotate(360deg); }
        }
        .leaflet-popup-content-wrapper {
          background: #181C21 !important;
          border: 1px solid rgba(255,255,255,0.08) !important;
          border-radius: 10px !important;
          box-shadow: 0 8px 32px rgba(0,0,0,0.6) !important;
          color: #f1f5f9 !important;
        }
        .leaflet-popup-tip { background: #181C21 !important; }
        .leaflet-popup-close-button { color: #64748b !important; }
      `}</style>

      <div className={className} style={{ position:'relative' }}>

        {/* ── loading overlay ── */}
        {loading && <LoadingOverlay />}

        {/* ── error banner ── */}
        {error && (
          <div style={{
            position:'absolute', top:12, left:'50%', transform:'translateX(-50%)',
            zIndex:1001, background:'#7f1d1d', color:'#fca5a5',
            fontSize:12, padding:'6px 16px', borderRadius:8,
            border:'1px solid #ef444440',
          }}>
            ⚠ {error}
          </div>
        )}

        {/* ── stat bar (hides while loading) ── */}
        {!loading && incidents.length > 0 && (
          <StatBar incidents={incidents} />
        )}

        {/* ── filter bar ── */}
        {!loading && incidents.length > 0 && (
          <FilterBar active={activeFilter} onChange={setActiveFilter} />
        )}

        {/* ── last updated badge ── */}
        {lastUpdated && (
          <div style={{
            position:'absolute', top:12, right:12, zIndex:1000,
            background:'rgba(15,20,30,0.8)',
            border:'1px solid rgba(255,255,255,0.08)',
            borderRadius:8, padding:'4px 10px',
            fontSize:11, color:'#64748b',
            backdropFilter:'blur(4px)',
          }}>
            Updated {lastUpdated}
          </div>
        )}

        {/* ── refresh button ── */}
        <button
          onClick={fetchIncidents}
          disabled={loading}
          style={{
            position:'absolute', bottom:28, right:12, zIndex:1000,
            background:'rgba(15,20,30,0.85)',
            border:'1px solid rgba(255,255,255,0.12)',
            borderRadius:8, padding:'6px 10px',
            color:'#9ca3af', cursor:'pointer', fontSize:12,
            backdropFilter:'blur(4px)',
            transition:'color 0.15s',
          }}
          title="Refresh incidents"
        >
          ↻ Refresh
        </button>

        {/* ── map ── */}
        <MapContainer
          center={viewport.center}
          zoom={viewport.zoom}
          style={{ height:'100%', width:'100%', zIndex:0 }}
          zoomControl={true}
        >
          <MapUpdater center={viewport.center} zoom={viewport.zoom} />

          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          />

          {visible.map(inc => (
            <Marker
              key={inc.id}
              position={[inc.latitude, inc.longitude]}
              icon={createIncidentIcon(inc.priority)}
            >
              <Popup>
                <IncidentPopup inc={inc} />
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </>
  );
}
