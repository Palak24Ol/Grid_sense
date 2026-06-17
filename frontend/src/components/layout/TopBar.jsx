import { Bell, Clock, Search, AlertTriangle, MapPin, CheckCircle2, AlertCircle } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import clsx from "clsx";

const MOCK_CORRIDORS = [
  "ORR South", "ORR East 1", "ORR East 2", "Bellary Road 1", "Bellary Road 2",
  "Mysore Road", "Tumkur Road", "Bannerghata Road", "Hosur Road", "CBD 1", "CBD 2",
  "West of Chord Road", "Old Madras Road"
];

const MOCK_NOTIFICATIONS = [
  { id: 1, type: 'critical', title: 'High Surge Risk', message: 'ORR South has a 4.4x vulnerability multiplier.', time: '2 mins ago' },
  { id: 2, type: 'warning', title: 'Tree Fall Reported', message: 'Mysore Road junction blocked.', time: '15 mins ago' },
  { id: 3, type: 'info', title: 'Deployment Active', message: '8 officers dispatched to Bellary Road 1.', time: '1 hr ago' },
];

export default function TopBar() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  
  const searchRef = useRef(null);
  const notifRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (searchRef.current && !searchRef.current.contains(event.target)) {
        setIsSearchFocused(false);
      }
      if (notifRef.current && !notifRef.current.contains(event.target)) {
        setShowNotifications(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filteredCorridors = MOCK_CORRIDORS.filter(c => c.toLowerCase().includes(searchQuery.toLowerCase()));
  return (
    <div className="h-16 bg-card border-b border-border flex items-center justify-between px-6 shrink-0 z-10">
      <div className="flex items-center gap-4 flex-1">
        <div className="relative w-72" ref={searchRef}>
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input 
            type="text" 
            placeholder="Search junctions, corridors..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => setIsSearchFocused(true)}
            className="w-full bg-muted/50 border border-border rounded-md pl-9 pr-4 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary/50"
          />
          
          {/* Search Dropdown */}
          {isSearchFocused && searchQuery && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-card border border-border rounded-md shadow-lg overflow-hidden z-50">
              {filteredCorridors.length > 0 ? (
                <ul className="max-h-60 overflow-y-auto py-1">
                  {filteredCorridors.map((corridor, idx) => (
                    <li 
                      key={idx}
                      className="px-4 py-2 hover:bg-muted cursor-pointer text-sm flex items-center gap-2 text-foreground"
                      onClick={() => {
                        setSearchQuery(corridor);
                        setIsSearchFocused(false);
                      }}
                    >
                      <MapPin className="w-4 h-4 text-muted-foreground" />
                      {corridor}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="p-4 text-sm text-muted-foreground text-center">
                  No results found.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock className="w-4 h-4" />
          <span>Live Data Stream</span>
        </div>
        
        <div className="flex gap-4">
          <div className="flex flex-col items-end">
            <span className="text-xs text-muted-foreground uppercase tracking-wider">Active Incidents</span>
            <span className="text-lg font-bold text-destructive">24</span>
          </div>
          <div className="w-px h-8 bg-border" />
          <div className="flex flex-col items-end">
            <span className="text-xs text-muted-foreground uppercase tracking-wider">Critical Corridors</span>
            <span className="text-lg font-bold text-amber-500">3</span>
          </div>
        </div>

        <div className="relative" ref={notifRef}>
          <button 
            onClick={() => setShowNotifications(!showNotifications)}
            className="relative p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-full transition-colors"
          >
            <Bell className="w-5 h-5" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-destructive rounded-full border border-card" />
          </button>

          {/* Notifications Dropdown */}
          {showNotifications && (
            <div className="absolute top-full right-0 mt-2 w-80 bg-card border border-border rounded-lg shadow-xl overflow-hidden z-50">
              <div className="p-3 border-b border-border bg-muted/30 flex justify-between items-center">
                <span className="font-semibold text-sm">Notifications</span>
                <span className="text-xs text-primary cursor-pointer hover:underline">Mark all read</span>
              </div>
              <div className="max-h-80 overflow-y-auto">
                {MOCK_NOTIFICATIONS.map(n => (
                  <div key={n.id} className="p-3 border-b border-border hover:bg-muted/50 transition-colors flex gap-3 cursor-pointer">
                    <div className="mt-0.5">
                      {n.type === 'critical' && <AlertTriangle className="w-4 h-4 text-destructive" />}
                      {n.type === 'warning' && <AlertCircle className="w-4 h-4 text-amber-500" />}
                      {n.type === 'info' && <CheckCircle2 className="w-4 h-4 text-primary" />}
                    </div>
                    <div className="flex-1 space-y-1">
                      <div className="flex justify-between items-start">
                        <p className={clsx("text-sm font-medium", 
                          n.type === 'critical' && "text-destructive",
                          n.type === 'warning' && "text-amber-500",
                          n.type === 'info' && "text-primary"
                        )}>
                          {n.title}
                        </p>
                        <span className="text-[10px] text-muted-foreground whitespace-nowrap">{n.time}</span>
                      </div>
                      <p className="text-xs text-muted-foreground leading-tight">{n.message}</p>
                    </div>
                  </div>
                ))}
              </div>
              <div className="p-2 text-center bg-muted/30 border-t border-border">
                <button className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                  View all notifications
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
