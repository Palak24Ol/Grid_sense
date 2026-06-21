import { useBlackspotStore } from '../../store/useBlackspotStore';
import { X, AlertTriangle } from 'lucide-react';
import clsx from 'clsx';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

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

const CAUSE_LABEL = {
  tree_fall:         'Tree Fall',
  water_logging:     'Water Logging',
  vehicle_breakdown: 'Vehicle Breakdown',
  accident:          'Accident',
  construction:      'Construction',
  protest:           'Protest',
  pot_holes:         'Potholes',
  others:            'Other issue',
  none:              'Unknown cause',
};

export default function JunctionDetailDrawer() {
  const { selectedJunction, clearSelection } = useBlackspotStore();

  if (!selectedJunction) return null;

  // Presence sparkline — weeks active out of last 13
  const weeks = Array.from({ length: 13 }).map((_, i) => ({
    week:   `Week ${i + 1}`,
    active: i < selectedJunction.recurrence_weeks ? 1 : 0,
  }));

  // What's driving the risk — plain labels
  const scoreData = [
    { name: 'Incidents',   value: selectedJunction.total_incidents * 0.4 },
    { name: 'Weeks active',value: selectedJunction.recurrence_weeks * 3  },
    { name: 'Closures',    value: selectedJunction.closures * 5           },
    { name: 'High priority',value: selectedJunction.high_priority * 0.3  },
  ];

  const topCause = CAUSE_LABEL[selectedJunction.top_cause] || selectedJunction.top_cause?.replace(/_/g, ' ') || 'Unknown';

  return (
    <div className="absolute top-0 right-0 h-full w-[400px] bg-card border-l border-border shadow-2xl z-20 flex flex-col transform transition-transform duration-300">

      {/* Header */}
      <div className="p-4 border-b border-border flex items-center justify-between bg-card">
        <div>
          <h2 className="font-bold text-lg text-foreground">{selectedJunction.junction}</h2>
          <p className="text-xs text-muted-foreground">{selectedJunction.corridor}</p>
        </div>
        <button
          onClick={clearSelection}
          className="p-1.5 hover:bg-muted rounded-full text-muted-foreground transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-8">

        {/* Tier + quick stats */}
        <div className="flex items-center justify-between">
          <div>
            <div className="section-label">How bad is it?</div>
            <div className="text-2xl font-bold mt-1 text-foreground">
              {selectedJunction.total_incidents} incidents
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              over {selectedJunction.recurrence_weeks} weeks &bull; {selectedJunction.closures} road closures
            </div>
          </div>
          <span className={clsx(
            'px-3 py-1 text-xs rounded-full border font-bold',
            TIER_BADGE[selectedJunction.blackspot_tier] || 'badge-medium'
          )}>
            {TIER_LABEL[selectedJunction.blackspot_tier] || selectedJunction.blackspot_tier}
          </span>
        </div>

        {/* What's driving it */}
        <div className="space-y-3">
          <h3 className="section-label">What's driving this problem?</h3>
          <div className="h-40 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={scoreData} layout="vertical" margin={{ top: 0, right: 0, left: 10, bottom: 0 }}>
                <XAxis type="number" hide />
                <YAxis
                  dataKey="name"
                  type="category"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: '#888', fontSize: 12 }}
                  width={90}
                />
                <Tooltip
                  cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                  contentStyle={{
                    backgroundColor: 'hsl(220 16% 11%)',
                    border: '1px solid hsl(220 14% 20%)',
                    borderRadius: '8px',
                  }}
                />
                <Bar dataKey="value" fill="hsl(54 95% 51%)" radius={[0, 4, 4, 0]} barSize={16} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 13-week pattern */}
        <div className="space-y-3">
          <h3 className="section-label">Problem pattern — last 13 weeks</h3>
          <div className="flex items-center justify-between gap-1">
            {weeks.map((w, i) => (
              <div
                key={i}
                title={w.week}
                className={clsx(
                  'flex-1 h-8 rounded-sm',
                  w.active ? 'bg-primary' : 'bg-muted'
                )}
              />
            ))}
          </div>
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span>13 weeks ago</span>
            <span className="text-center">
              Jammed in <span className="text-primary font-bold">{selectedJunction.recurrence_weeks}</span> of last 13 weeks
            </span>
            <span>This week</span>
          </div>
        </div>

        {/* Action recommendation */}
        <div className="p-4 rounded-xl border border-primary/25 bg-primary/10 flex gap-3 items-start">
          <AlertTriangle className="w-5 h-5 text-primary shrink-0 mt-0.5" />
          <div>
            <h4 className="font-semibold text-primary mb-1">Action Required</h4>
            <p className="text-sm text-primary/80 leading-relaxed">
              <span className="font-medium">{topCause}</span> has been recurring here for {selectedJunction.recurrence_weeks}+ weeks.
              Raise this with the infrastructure team to fix it permanently.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
