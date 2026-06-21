import {
  Bell, Search, AlertTriangle, MapPin,
  CheckCircle2, AlertCircle, Zap, Activity,
} from "lucide-react";
import { useState, useRef, useEffect } from "react";
import clsx from "clsx";
import { useMapStore } from "../../store/useMapStore";
import { getIncidents } from "../../api/incidents";

const CORRIDOR_COORDS = {
  "ORR South":             [12.9139, 77.5659, 14],
  "ORR East 1":            [12.9502, 77.6992, 14],
  "ORR East 2":            [12.9954, 77.6829, 14],
  "ORR North 1":           [13.0388, 77.6211, 14],
  "ORR North 2":           [13.0451, 77.5816, 14],
  "ORR West 1":            [12.9139, 77.5659, 14],
  "Bellary Road 1":        [13.0208, 77.5880, 14],
  "Bellary Road 2":        [13.0804, 77.5962, 14],
  "Mysore Road":           [12.9663, 77.6071, 14],
  "Tumkur Road":           [13.0429, 77.5128, 14],
  "Bannerghata Road":      [12.9094, 77.5982, 14],
  "Hosur Road":            [12.9055, 77.6310, 14],
  "CBD 1":                 [12.9808, 77.6028, 14],
  "CBD 2":                 [12.9808, 77.6028, 14],
  "West of Chord Road":    [12.9879, 77.5443, 14],
  "Old Madras Road":       [12.9808, 77.6246, 14],
  "IRR(Thanisandra road)": [12.9275, 77.6213, 14],
};

const MOCK_CORRIDORS = Object.keys(CORRIDOR_COORDS);

const MOCK_NOTIFICATIONS = [
  { id: 1, type: "critical", title: "ORR South — Jam Alert",    message: "Heavy rain is making traffic much worse than usual. Send extra officers.", time: "2m ago" },
  { id: 2, type: "warning",  title: "Tree Fall on Mysore Road", message: "Junction blocked, only one lane open. Divert traffic.",                     time: "15m ago" },
  { id: 3, type: "info",     title: "Officers Dispatched",      message: "8 officers sent to Bellary Road 1.",                                         time: "1h ago" },
];

function LivePulse() {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/25">
      <span className="w-1.5 h-1.5 rounded-full bg-primary pulse-live" />
      <span className="text-xs font-semibold text-primary tracking-wide uppercase">Live</span>
    </div>
  );
}

export default function TopBar() {
  const [searchQuery,       setSearchQuery]       = useState("");
  const [isSearchFocused,   setIsSearchFocused]   = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications,     setNotifications]     = useState(MOCK_NOTIFICATIONS);
  const [activeProblems,    setActiveProblems]    = useState(null);
  const [urgentNow,         setUrgentNow]         = useState(null);
  const searchRef = useRef(null);
  const notifRef  = useRef(null);
  const { setViewport } = useMapStore();

  // Pull real incident counts from API
  useEffect(() => {
    getIncidents()
      .then(data => {
        const list = Array.isArray(data) ? data : (data.incidents || []);
        setActiveProblems(list.length);
        setUrgentNow(list.filter(i => i.priority === 'High').length);
      })
      .catch(() => {
        // leave as null — won't show stale hardcoded numbers
      });
  }, []);

  useEffect(() => {
    const handler = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) setIsSearchFocused(false);
      if (notifRef.current  && !notifRef.current.contains(e.target))  setShowNotifications(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = MOCK_CORRIDORS.filter(c =>
    c.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleCorridorSelect = (corridor) => {
    setSearchQuery(corridor);
    setIsSearchFocused(false);
    const coords = CORRIDOR_COORDS[corridor];
    if (coords) setViewport({ center: [coords[0], coords[1]], zoom: coords[2] });
  };

  return (
    <div className="h-16 bg-card border-b border-border flex items-center justify-between px-6 shrink-0 z-20">

      {/* Left: search */}
      <div className="flex items-center gap-4 flex-1">
        <div className="relative w-64" ref={searchRef}>
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search a road or area…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => setIsSearchFocused(true)}
            className="w-full bg-muted/40 border border-border rounded-lg pl-8 pr-4 py-1.5 text-sm focus:outline-none focus:border-primary/50 focus:bg-muted/60 transition-colors placeholder:text-muted-foreground/50"
          />
          {isSearchFocused && searchQuery && (
            <div className="absolute top-full left-0 right-0 mt-1.5 bg-card border border-border rounded-lg shadow-2xl overflow-hidden z-50">
              {filtered.length > 0 ? (
                <ul className="max-h-56 overflow-y-auto py-1">
                  {filtered.map((corridor, i) => (
                    <li
                      key={i}
                      onClick={() => handleCorridorSelect(corridor)}
                      className="px-3 py-2 hover:bg-muted/60 cursor-pointer text-sm flex items-center gap-2 text-foreground transition-colors"
                    >
                      <MapPin className="w-3.5 h-3.5 text-primary shrink-0" />
                      {corridor}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="p-3 text-sm text-muted-foreground text-center">No roads found.</p>
              )}
            </div>
          )}
        </div>
        <LivePulse />
      </div>

      {/* Right: live stats + bell */}
      <div className="flex items-center gap-5">

        {/* Active Problems — real data */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20">
          <Activity className="w-3.5 h-3.5 text-red-400" />
          <span className="text-xs text-muted-foreground">Active Problems</span>
          <span className="text-sm font-bold text-red-400">
            {activeProblems !== null ? activeProblems : '—'}
          </span>
        </div>

        {/* Urgent Now — real data */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-warning/10 border border-warning/20">
          <Zap className="w-3.5 h-3.5 text-warning" />
          <span className="text-xs text-muted-foreground">Urgent Now</span>
          <span className="text-sm font-bold text-warning">
            {urgentNow !== null ? urgentNow : '—'}
          </span>
        </div>

        <div className="w-px h-6 bg-border" />

        {/* Notifications */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className={clsx(
              "relative p-2 rounded-lg transition-colors",
              showNotifications
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
            )}
          >
            <Bell className="w-4 h-4" />
            {notifications.length > 0 && (
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-primary rounded-full border border-card" />
            )}
          </button>

          {showNotifications && (
            <div className="absolute top-full right-0 mt-2 w-80 bg-card border border-border rounded-xl shadow-2xl overflow-hidden z-50">
              <div className="px-4 py-3 border-b border-border flex justify-between items-center">
                <span className="font-semibold text-sm text-foreground">Alerts</span>
                {notifications.length > 0 && (
                  <span
                    onClick={() => setNotifications([])}
                    className="text-xs text-primary cursor-pointer hover:underline"
                  >Clear all</span>
                )}
              </div>
              <div className="max-h-72 overflow-y-auto divide-y divide-border">
                {notifications.length === 0 ? (
                  <p className="p-6 text-xs text-muted-foreground text-center">No alerts</p>
                ) : notifications.map((n) => (
                  <div key={n.id} className="p-3 hover:bg-muted/40 transition-colors flex gap-3 cursor-pointer group">
                    <div className="mt-0.5 shrink-0">
                      {n.type === "critical" && <AlertTriangle className="w-4 h-4 text-destructive" />}
                      {n.type === "warning"  && <AlertCircle   className="w-4 h-4 text-warning" />}
                      {n.type === "info"     && <CheckCircle2  className="w-4 h-4 text-primary" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-start gap-2">
                        <p className={clsx("text-xs font-semibold truncate",
                          n.type === "critical" && "text-destructive",
                          n.type === "warning"  && "text-warning",
                          n.type === "info"     && "text-primary",
                        )}>{n.title}</p>
                        <span className="text-[10px] text-muted-foreground whitespace-nowrap">{n.time}</span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5 leading-snug">{n.message}</p>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); setNotifications(prev => prev.filter(x => x.id !== n.id)); }}
                      className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-foreground text-xs px-1 transition-opacity shrink-0"
                    >✕</button>
                  </div>
                ))}
              </div>
              <div className="px-4 py-2 border-t border-border bg-muted/20 text-center">
                <button
                  onClick={() => setShowNotifications(false)}
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  View all alerts
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}