import { useState } from 'react';
import { useBlackspotStore } from '../../store/useBlackspotStore';
import { ShieldAlert, AlertTriangle, CheckCircle, ChevronDown, ChevronUp } from 'lucide-react';
import clsx from 'clsx';

const CAUSE_LABEL = {
  tree_fall:         'Tree Fall',
  water_logging:     'Water Logging',
  vehicle_breakdown: 'Vehicle Breakdown',
  accident:          'Accident',
  construction:      'Construction',
  protest:           'Protest',
  pot_holes:         'Potholes',
  others:            'Others',
  none:              '—',
};

function RateBar({ rate }) {
  const pct = Math.round(rate * 100);
  const color =
    pct >= 30 ? 'bg-red-500'
    : pct >= 15 ? 'bg-orange-500'
    : pct >= 5  ? 'bg-yellow-500'
    : 'bg-emerald-500';

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full', color)} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className={clsx(
        'text-xs font-bold w-10 text-right',
        pct >= 30 ? 'text-red-400' : pct >= 15 ? 'text-orange-400' : pct >= 5 ? 'text-yellow-400' : 'text-emerald-400'
      )}>
        {pct}%
      </span>
    </div>
  );
}

export default function NeglectStationCard() {
  const { neglectIndex } = useBlackspotStore();
  const [expanded, setExpanded] = useState(false);

  if (!neglectIndex || neglectIndex.length === 0) return null;

  const sorted   = [...neglectIndex].sort((a, b) => b.neglect_rate - a.neglect_rate);
  const active   = sorted.filter(s => s.neglect_rate > 0);
  const clean    = sorted.filter(s => s.neglect_rate === 0).length;
  const critical = active.filter(s => s.neglect_rate >= 0.30).length;
  const showing  = expanded ? active : active.slice(0, 5);

  return (
    <div className="bg-card/90 backdrop-blur-md border border-border rounded-xl shadow-lg overflow-hidden flex flex-col">

      {/* Header */}
      <div className="p-4 border-b border-border bg-card/80">
        <h2 className="text-sm font-bold text-foreground flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-red-400" />
          Station Accountability Index
        </h2>
        <p className="text-xs text-muted-foreground mt-1">
          Stations consistently slow to resolve high-risk incidents
        </p>

        {/* Summary stats */}
        <div className="grid grid-cols-3 gap-2 mt-3">
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-2 text-center">
            <p className="text-lg font-bold text-red-400">{critical}</p>
            <p className="text-[10px] text-muted-foreground leading-tight">Critical<br/>(&gt;30%)</p>
          </div>
          <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-2 text-center">
            <p className="text-lg font-bold text-orange-400">{active.length}</p>
            <p className="text-[10px] text-muted-foreground leading-tight">Flagged<br/>Stations</p>
          </div>
          <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-2 text-center">
            <p className="text-lg font-bold text-emerald-400">{clean}</p>
            <p className="text-[10px] text-muted-foreground leading-tight">Clean<br/>Stations</p>
          </div>
        </div>
      </div>

      {/* Station list */}
      <div className="overflow-y-auto p-4 space-y-3 max-h-[320px]">
        {showing.map((station, idx) => {
          const pct = Math.round(station.neglect_rate * 100);
          const isCritical = pct >= 30;
          return (
            <div
              key={station.police_station}
              className={clsx(
                'rounded-lg border p-3 space-y-2',
                isCritical
                  ? 'border-red-500/30 bg-red-500/5'
                  : 'border-border bg-muted/10'
              )}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-xs text-muted-foreground shrink-0">#{idx + 1}</span>
                  {isCritical && <AlertTriangle className="w-3 h-3 text-red-400 shrink-0" />}
                  <span className="text-xs font-semibold truncate">{station.police_station}</span>
                </div>
                <span className={clsx(
                  'text-xs font-bold shrink-0 ml-2',
                  pct >= 30 ? 'text-red-400' : pct >= 15 ? 'text-orange-400' : 'text-yellow-400'
                )}>
                  {station.neglected_count} unresolved
                </span>
              </div>

              <RateBar rate={station.neglect_rate} />

              <div className="flex justify-between text-[10px] text-muted-foreground">
                <span>{station.total_incidents} total incidents</span>
                <span className="text-primary/80">
                  Top cause: {CAUSE_LABEL[station.top_neglected_cause] || station.top_neglected_cause}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Expand / collapse */}
      {active.length > 5 && (
        <button
          onClick={() => setExpanded(e => !e)}
          className="w-full p-2.5 border-t border-border text-xs text-muted-foreground hover:text-foreground hover:bg-muted/20 transition-colors flex items-center justify-center gap-1"
        >
          {expanded
            ? <><ChevronUp className="w-3 h-3" />Show less</>
            : <><ChevronDown className="w-3 h-3" />Show all {active.length} flagged stations</>
          }
        </button>
      )}

      {/* Clean station note */}
      {clean > 0 && !expanded && (
        <div className="px-4 pb-3 flex items-center gap-1.5 text-[10px] text-emerald-400/70">
          <CheckCircle className="w-3 h-3" />
          {clean} stations with zero neglect rate
        </div>
      )}
    </div>
  );
}
