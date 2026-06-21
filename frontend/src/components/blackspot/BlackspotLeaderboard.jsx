import { useBlackspotStore } from '../../store/useBlackspotStore';
import clsx from 'clsx';
import { MapPin } from 'lucide-react';

const TIER_LABEL = {
  Chronic:  'Always Jams',
  Critical: 'Often Jams',
  'At Risk': 'Watch This',
};

const TIER_BADGE = {
  Chronic:  'badge-critical',
  Critical: 'badge-warning',
  'At Risk': 'badge-medium',
};

const FILTER_TABS = ['All', 'Chronic', 'Critical', 'At Risk'];

export default function BlackspotLeaderboard() {
  const {
    blackspots,
    activeTierFilter,
    setTierFilter,
    selectJunction,
    selectedJunction,
  } = useBlackspotStore();

  return (
    <div className="bg-card/90 backdrop-blur-md border border-border rounded-xl shadow-lg flex flex-col h-2/3 overflow-hidden">
      <div className="p-4 border-b border-border bg-card">
        <h2 className="text-sm font-bold text-foreground flex items-center gap-2 mb-3">
          <MapPin className="w-4 h-4 text-primary" />
          Recurring Problem Junctions
        </h2>
        <p className="text-[10px] text-muted-foreground mb-3">
          These junctions jam up regularly — keep an eye on them
        </p>

        {/* Filter tabs */}
        <div className="flex gap-1 bg-muted p-1 rounded-lg">
          {FILTER_TABS.map(tab => (
            <button
              key={tab}
              onClick={() => setTierFilter(tab)}
              className={clsx(
                'flex-1 py-1 text-xs font-medium rounded-md transition-colors',
                activeTierFilter === tab
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {tab === 'Chronic' ? 'Always' : tab === 'Critical' ? 'Often' : tab === 'At Risk' ? 'Watch' : tab}
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
              'w-full text-left p-3 rounded-lg border transition-all duration-200 group flex items-center justify-between',
              selectedJunction?.junction === b.junction
                ? 'bg-primary/10 border-primary'
                : 'bg-transparent border-transparent hover:bg-muted/50'
            )}
          >
            <div>
              <div className="font-semibold text-sm group-hover:text-primary transition-colors">
                {b.junction}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {b.recurrence_weeks} weeks in a row &bull; {b.total_incidents} incidents
              </div>
            </div>

            <span className={clsx(
              'px-2.5 py-1 rounded-md text-xs font-bold border',
              TIER_BADGE[b.blackspot_tier] || 'badge-medium'
            )}>
              {TIER_LABEL[b.blackspot_tier] || b.blackspot_tier}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
