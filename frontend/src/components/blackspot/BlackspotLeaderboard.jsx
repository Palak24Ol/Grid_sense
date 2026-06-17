import { useBlackspotStore } from '../../store/useBlackspotStore';
import clsx from 'clsx';
import { Target } from 'lucide-react';

export default function BlackspotLeaderboard() {
  const { blackspots, activeTierFilter, setTierFilter, selectJunction, selectedJunction } = useBlackspotStore();

  const tiers = ['All', 'Chronic', 'Critical', 'At Risk'];

  return (
    <div className="bg-card/90 backdrop-blur-md border border-border rounded-xl shadow-lg flex flex-col h-2/3 overflow-hidden">
      <div className="p-4 border-b border-border bg-muted/30">
        <h2 className="font-semibold flex items-center gap-2 mb-3">
          <Target className="w-5 h-5 text-destructive" />
          Chronic Blackspot Engine
        </h2>
        
        <div className="flex gap-1 bg-muted p-1 rounded-lg">
          {tiers.map(tier => (
            <button
              key={tier}
              onClick={() => setTierFilter(tier)}
              className={clsx(
                "flex-1 py-1 text-xs font-medium rounded-md transition-colors",
                activeTierFilter === tier 
                  ? "bg-card text-foreground shadow-sm" 
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {tier}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1 custom-scrollbar">
        {blackspots.map((b) => (
          <button
            key={b.junction}
            onClick={() => selectJunction(b.junction)}
            className={clsx(
              "w-full text-left p-3 rounded-lg border transition-all duration-200 group flex items-center justify-between",
              selectedJunction?.junction === b.junction
                ? "bg-primary/10 border-primary"
                : "bg-transparent border-transparent hover:bg-muted/50"
            )}
          >
            <div>
              <div className="font-semibold text-sm group-hover:text-primary transition-colors">
                {b.junction}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {b.recurrence_weeks} weeks active • {b.total_incidents} incidents
              </div>
            </div>
            
            <div className={clsx(
              "px-2.5 py-1 rounded-md text-xs font-bold border",
              b.blackspot_tier === 'Chronic' ? "bg-destructive/10 text-destructive border-destructive/20" :
              b.blackspot_tier === 'Critical' ? "bg-amber-500/10 text-amber-500 border-amber-500/20" :
              "bg-muted text-muted-foreground border-border"
            )}>
              {b.blackspot_score.toFixed(1)}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
