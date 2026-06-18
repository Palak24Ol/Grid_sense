import { NavLink } from "react-router-dom";
import {
  Map,
  Stethoscope,
  LineChart,
  ShieldAlert,
  Truck,
  MapPin,
  CloudLightning,
  Radio,
} from "lucide-react";
import clsx from "clsx";

const navItems = [
  { path: "/map",        label: "Command Center",  icon: Map,           sub: "Live overview" },
  { path: "/triage",     label: "Event Triage",    icon: Stethoscope,   sub: "Predict & classify" },
  { path: "/blackspot",  label: "Risk Blackspots",  icon: MapPin,        sub: "Chronic hotspots" },
  { path: "/surge",      label: "Surge Alert",     icon: CloudLightning, sub: "Weather multiplier" },
  { path: "/forecast",   label: "72h Forecast",    icon: LineChart,     sub: "Corridor risk" },
  { path: "/deployment", label: "Deploy Officers", icon: ShieldAlert,   sub: "Manpower planner" },
  { path: "/flipkart",   label: "LCV Logistics",   icon: Truck,         sub: "Fleet incidents" },
];

export default function Sidebar() {
  return (
    <div className="w-60 bg-card border-r border-border flex flex-col h-full shrink-0">

      {/* Logo */}
      <div className="h-16 flex items-center gap-3 px-5 border-b border-border">
        <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shrink-0">
          <Radio className="w-4 h-4 text-primary-foreground" strokeWidth={2.5} />
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-tight text-foreground leading-none">
            GridSense
          </h1>
          <p className="text-[10px] text-muted-foreground mt-0.5 leading-none uppercase tracking-widest">
            Traffic Intel
          </p>
        </div>
      </div>

      {/* Nav label */}
      <div className="px-5 pt-5 pb-2">
        <span className="section-label">Operations</span>
      </div>

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto px-3 space-y-0.5">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group relative",
                  isActive
                    ? "bg-primary/10 text-primary nav-active-bar"
                    : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    className={clsx(
                      "w-4 h-4 shrink-0 transition-colors",
                      isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground"
                    )}
                    strokeWidth={isActive ? 2.5 : 2}
                  />
                  <div className="flex flex-col min-w-0">
                    <span className="leading-tight truncate">{item.label}</span>
                    <span className={clsx(
                      "text-[10px] leading-tight truncate transition-colors",
                      isActive ? "text-primary/60" : "text-muted-foreground/60"
                    )}>
                      {item.sub}
                    </span>
                  </div>
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* System status footer */}
      <div className="p-4 border-t border-border space-y-3">
        <span className="section-label">System</span>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-primary pulse-live shrink-0" />
          <span className="text-xs font-medium text-foreground">Live Data Stream</span>
        </div>
        <div className="bg-muted/40 rounded-lg p-2.5 space-y-1.5">
          <div className="flex justify-between text-[10px]">
            <span className="text-muted-foreground">ML Models</span>
            <span className="text-primary font-medium">Online</span>
          </div>
          <div className="flex justify-between text-[10px]">
            <span className="text-muted-foreground">Corridors</span>
            <span className="text-foreground font-medium">20 active</span>
          </div>
          <div className="flex justify-between text-[10px]">
            <span className="text-muted-foreground">Bengaluru Traffic</span>
            <span className="text-warning font-medium">3 critical</span>
          </div>
        </div>
      </div>
    </div>
  );
}
