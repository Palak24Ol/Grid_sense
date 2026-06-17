import { NavLink } from "react-router-dom";
import { 
  Map, 
  Stethoscope, 
  LineChart, 
  ShieldAlert, 
  Truck, 
  MapPin, 
  CloudLightning 
} from "lucide-react";
import clsx from "clsx";

const navItems = [
  { path: "/map", label: "Command Center", icon: Map },
  { path: "/triage", label: "Triage & Predict", icon: Stethoscope },
  { path: "/blackspot", label: "Blackspots", icon: MapPin },
  { path: "/surge", label: "Weather Surge", icon: CloudLightning },
  { path: "/forecast", label: "Forecast", icon: LineChart },
  { path: "/deployment", label: "Deployment", icon: ShieldAlert },
  { path: "/flipkart", label: "LCV Logistics", icon: Truck },
];

export default function Sidebar() {
  return (
    <div className="w-64 bg-card border-r border-border flex flex-col h-full shrink-0">
      <div className="h-16 flex items-center px-6 border-b border-border">
        <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
          GridSense
        </h1>
      </div>
      
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                isActive 
                  ? "bg-primary/10 text-primary shadow-[inset_4px_0_0_0_hsl(var(--primary))]" 
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <Icon className="w-5 h-5" />
              {item.label}
            </NavLink>
          );
        })}
      </nav>

      <div className="p-4 border-t border-border">
        <div className="text-xs text-muted-foreground">System Status</div>
        <div className="flex items-center gap-2 mt-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-sm font-medium">All Systems Normal</span>
        </div>
      </div>
    </div>
  );
}
