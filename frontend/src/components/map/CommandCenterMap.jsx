import { useEffect, useState, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useMapStore } from '../../store/useMapStore';
import { getIncidents } from '../../api/incidents';

// ─── Map viewport updater ─────────────────────────────────────────────────
function MapUpdater({ center, zoom }) {
  const map = useMap();
  useEffect(() => { map.setView(center, zoom); }, [center, zoom, map]);
  return null;
}

// ─── Priority config ──────────────────────────────────────────────────────
// Real dataset only has High / Low — no Medium
const P = {
  High: { bg:'#ef4444', border:'#fca5a5', shadow:'rgba(239,68,68,0.6)',  size:14, pulse:true  },
  Low:  { bg:'#22c55e', border:'#86efac', shadow:'rgba(34,197,94,0.4)',  size:10, pulse:false },
};

const createIncidentIcon = (priority) => {
  const s = P[priority] || P.Low;
  const ring = s.pulse
    ? `<div style="position:absolute;top:50%;left:50%;
        transform:translate(-50%,-50%);
        width:${s.size+10}px;height:${s.size+10}px;border-radius:50%;
        background:${s.bg};opacity:0.35;
        animation:pulseRing 1.8s ease-out infinite;"></div>`
    : '';
  return L.divIcon({
    className: '',
    html: `<div style="position:relative;width:${s.size+10}px;height:${s.size+10}px;
              display:flex;align-items:center;justify-content:center;">
              ${ring}
              <div style="width:${s.size}px;height:${s.size}px;border-radius:50%;
                background:${s.bg};border:2px solid ${s.border};
                box-shadow:0 0 8px ${s.shadow};position:relative;z-index:1;"></div>
           </div>`,
    iconSize: [s.size+10, s.size+10],
    iconAnchor: [(s.size+10)/2, (s.size+10)/2],
  });
};

// ─── Stat bar ─────────────────────────────────────────────────────────────
// Counts come from the actual incidents array — never from corridor aggregates
function StatBar({ incidents }) {
  const actNow   = incidents.filter(i => i.priority === 'High').length;
  const clear    = incidents.filter(i => i.priority === 'Low').length;
  const closures = incidents.filter(i => i.requires_road_closure).length;
  const total    = incidents.length;

  const chip = (label, value, color) => (
    <div style={{
      display:'flex', alignItems:'center', gap:6,
      padding:'5px 12px', borderRadius:8,
      background:color+'18', border:`1px solid ${color}30`,
    }}>
      <span style={{fontSize:11, color:'#9ca3af'}}>{label}</span>
      <span style={{fontSize:15, fontWeight:700, color}}>{value}</span>
    </div>
  );

  return (
    <div style={{
      position:'absolute', top:12, left:'50%', transform:'translateX(-50%)',
      zIndex:1000, display:'flex', gap:8, flexWrap:'nowrap',
      background:'rgba(15,20,30,0.88)',
      backdropFilter:'blur(8px)',
      border:'1px solid rgba(255,255,255,0.08)',
      borderRadius:12, padding:'8px 14px',
      boxShadow:'0 4px 24px rgba(0,0,0,0.5)',
      fontFamily:'inherit', whiteSpace:'nowrap',
    }}>
      {chip('Active jams', total,    '#60a5fa')}
      <div style={{width:1, background:'rgba(255,255,255,0.1)'}}/>
      {chip('Act Now',     actNow,   '#ef4444')}
      {chip('Clear',       clear,    '#22c55e')}
      <div style={{width:1, background:'rgba(255,255,255,0.1)'}}/>
      {chip('Road closures', closures, '#a78bfa')}
    </div>
  );
}

// ─── Filter bar ───────────────────────────────────────────────────────────
const FILTERS = [
  { label:'All',      value:'All'  },
  { label:'Act Now',  value:'High' },
  { label:'Clear',    value:'Low'  },
];

function FilterBar({ active, onChange }) {
  const colors = { High:'#ef4444', Low:'#22c55e', All:'#F9E107' }; // Using Flipkart yellow for 'All' to match Gridlock theme
  return (
    <div style={{
      position:'absolute', bottom:28, left:'50%', transform:'translateX(-50%)',
      zIndex:1000, display:'flex', gap:6,
      background:'rgba(15,20,30,0.88)',
      backdropFilter:'blur(8px)',
      border:'1px solid rgba(255,255,255,0.08)',
      borderRadius:20, padding:'5px 8px',
      boxShadow:'0 4px 24px rgba(0,0,0,0.5)',
      fontFamily:'inherit',
    }}>
      {FILTERS.map(f => {
        const isActive = active === f.value;
        const color = colors[f.value];
        return (
          <button key={f.value} onClick={() => onChange(f.value)} style={{
            padding:'4px 16px', borderRadius:14, border:'none', cursor:'pointer',
            fontSize:12, fontWeight: isActive ? 600 : 400,
            background: isActive ? color : 'transparent',
            color: isActive ? (f.value === 'All' ? '#181C21' : '#fff') : '#9ca3af',
            transition:'all 0.15s',
          }}>{f.label}</button>
        );
      })}
    </div>
  );
}

// ─── Loading overlay ──────────────────────────────────────────────────────
function LoadingOverlay() {
  return (
    <div style={{
      position:'absolute', inset:0, zIndex:2000,
      background:'rgba(10,15,25,0.78)',
      backdropFilter:'blur(4px)',
      display:'flex', flexDirection:'column',
      alignItems:'center', justifyContent:'center', gap:14,
    }}>
      <div style={{
        width:36, height:36, borderRadius:'50%',
        border:'3px solid rgba(96,165,250,0.2)',
        borderTopColor:'#60a5fa',
        animation:'spin 0.8s linear infinite',
      }}/>
      <span style={{color:'#9ca3af', fontSize:13}}>Loading live incidents…</span>
    </div>
  );
}

// ─── Popup card ───────────────────────────────────────────────────────────
function IncidentPopup({ inc }) {
  const isHigh = inc.priority === 'High';
  const pc = isHigh ? '#ef4444' : '#22c55e';
  const label = isHigh ? '🚨 Act Now' : '✅ Clear';

  // duration display
  const mins = inc.duration_mins || 45;
  const durationText = mins >= 60
    ? `${(mins / 60).toFixed(1)} hrs`
    : `${mins} mins`;

  // cause: use display version if present, else prettify raw
  const cause = inc.event_cause_display
    || inc.event_cause.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());

  const junction = inc.junction && inc.junction.length < 40
    ? inc.junction
    : 'Unknown junction';

  return (
    <div style={{fontFamily:'inherit', minWidth:190}}>
      <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:6}}>
        <span style={{fontWeight:600, fontSize:13, color:'#f1f5f9', maxWidth:120, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>
          {junction}
        </span>
        <span style={{
          fontSize:10, fontWeight:700, padding:'2px 7px', borderRadius:6,
          background:pc+'22', color:pc, border:`1px solid ${pc}44`,
          whiteSpace:'nowrap',
        }}>{label}</span>
      </div>

      <div style={{fontSize:12, color:'#94a3b8', marginBottom:3}}>
        📍 {inc.corridor}
      </div>
      <div style={{fontSize:12, color:'#94a3b8', marginBottom:3}}>
        🚗 {cause}
        {inc.event_type === 'planned' && (
          <span style={{marginLeft:6, fontSize:10, color:'#818cf8',
            background:'#818cf822', padding:'1px 5px', borderRadius:4}}>Planned</span>
        )}
      </div>
      <div style={{fontSize:12, color:'#94a3b8', marginBottom:6}}>
        ⏱ Expected to clear in {durationText}
      </div>
      {inc.requires_road_closure && (
        <div style={{
          fontSize:11, fontWeight:600, color:'#f87171',
          background:'#ef444415', border:'1px solid #ef444430',
          borderRadius:6, padding:'3px 8px', marginBottom:4,
        }}>⛔ Road closed</div>
      )}
      <div style={{fontSize:11, color:'#64748b', marginTop:4}}>
        🚔 {inc.police_station || 'Unknown station'}
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────
export default function CommandCenterMap({
  className = "h-full w-full rounded-xl overflow-hidden shadow-md border border-border",
}) {
  const { viewport } = useMapStore();
  const [incidents,    setIncidents]    = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState(null);
  const [activeFilter, setActiveFilter] = useState('All');
  const [lastUpdated,  setLastUpdated]  = useState(null);

  const fetchIncidents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getIncidents();
      // Normalise: accept both { incidents: [] } and flat array
      const list = Array.isArray(data) ? data : (data.incidents || []);
      setIncidents(list);
      setLastUpdated(new Date().toLocaleTimeString('en-IN', { hour:'2-digit', minute:'2-digit' }));
    } catch (err) {
      setError('Could not load incidents.');
      console.error('[CommandCenterMap]', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchIncidents(); }, [fetchIncidents]);

  const visible = activeFilter === 'All'
    ? incidents
    : incidents.filter(i => i.priority === activeFilter);

  return (
    <>
      <style>{`
        @keyframes pulseRing {
          0%   { transform:translate(-50%,-50%) scale(0.8); opacity:0.6; }
          100% { transform:translate(-50%,-50%) scale(2.2); opacity:0; }
        }
        @keyframes spin { to { transform:rotate(360deg); } }
        .leaflet-popup-content-wrapper {
          background:#1e293b !important;
          border:1px solid rgba(255,255,255,0.08) !important;
          border-radius:10px !important;
          box-shadow:0 8px 32px rgba(0,0,0,0.6) !important;
          color:#f1f5f9 !important;
        }
        .leaflet-popup-tip { background:#1e293b !important; }
        .leaflet-popup-close-button { color:#64748b !important; }
        .leaflet-popup-content { margin:10px 14px !important; }
      `}</style>

      <div className={className} style={{position:'relative'}}>

        {loading && <LoadingOverlay />}

        {error && (
          <div style={{
            position:'absolute', top:12, left:'50%', transform:'translateX(-50%)',
            zIndex:1001, background:'#7f1d1d', color:'#fca5a5',
            fontSize:12, padding:'6px 16px', borderRadius:8,
            border:'1px solid #ef444440',
          }}>⚠ {error}</div>
        )}

        {!loading && incidents.length > 0 && <StatBar incidents={incidents} />}
        {!loading && incidents.length > 0 && <FilterBar active={activeFilter} onChange={setActiveFilter} />}

        {lastUpdated && (
          <div style={{
            position:'absolute', top:12, right:12, zIndex:1000,
            background:'rgba(15,20,30,0.8)',
            border:'1px solid rgba(255,255,255,0.08)',
            borderRadius:8, padding:'4px 10px',
            fontSize:11, color:'#64748b',
            backdropFilter:'blur(4px)',
          }}>Updated {lastUpdated}</div>
        )}

        <button onClick={fetchIncidents} disabled={loading} style={{
          position:'absolute', bottom:28, right:12, zIndex:1000,
          background:'rgba(15,20,30,0.85)',
          border:'1px solid rgba(255,255,255,0.12)',
          borderRadius:8, padding:'6px 12px',
          color:'#9ca3af', cursor:'pointer', fontSize:12,
          backdropFilter:'blur(4px)',
        }}>↻ Refresh</button>

        <MapContainer
          center={viewport.center}
          zoom={viewport.zoom}
          style={{height:'100%', width:'100%', zIndex:0}}
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
              <Popup><IncidentPopup inc={inc} /></Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </>
  );
}
