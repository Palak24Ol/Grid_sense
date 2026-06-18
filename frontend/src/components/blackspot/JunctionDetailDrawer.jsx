import { useBlackspotStore } from '../../store/useBlackspotStore';
import { X, Activity, AlertTriangle } from 'lucide-react';
import clsx from 'clsx';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function JunctionDetailDrawer() {
  const { selectedJunction, clearSelection } = useBlackspotStore();

  if (!selectedJunction) return null;

  // Since we don't have the raw weekly timeline in the basic mock, 
  // we simulate a 13-week presence array for the sparkline based on recurrence_weeks
  const weeks = Array.from({ length: 13 }).map((_, i) => ({
    week: `W${i + 1}`,
    active: i < selectedJunction.recurrence_weeks ? 1 : 0
  }));

  // Score breakdown (simulated based on formula for visualization)
  const scoreData = [
    { name: 'Incidents', value: selectedJunction.total_incidents * 0.4 },
    { name: 'Recurrence', value: selectedJunction.recurrence_weeks * 3 },
    { name: 'Closures', value: selectedJunction.closures * 5 },
    { name: 'Priority', value: selectedJunction.high_priority * 0.3 }
  ];

  return (
    <div className="absolute top-0 right-0 h-full w-[400px] bg-card border-l border-border shadow-2xl z-20 flex flex-col transform transition-transform duration-300">
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
        
        {/* Header Stats */}
        <div className="flex items-center justify-between">
          <div>
            <div className="section-label">Blackspot Score</div>
            <div className="text-4xl font-bold font-mono mt-1 text-foreground">
              {selectedJunction.blackspot_score.toFixed(1)}
            </div>
          </div>
          <div className={clsx(
            "px-3 py-1 text-xs",
            selectedJunction.blackspot_tier === 'Chronic' ? "badge-critical" :
            selectedJunction.blackspot_tier === 'Critical' ? "badge-warning" :
            "badge-medium"
          )}>
            {selectedJunction.blackspot_tier}
          </div>
        </div>

        {/* Score Breakdown Chart */}
        <div className="space-y-3">
          <h3 className="section-label flex items-center gap-2">
            <Activity className="w-4 h-4" /> Score Components
          </h3>
          <div className="h-40 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={scoreData} layout="vertical" margin={{ top: 0, right: 0, left: 10, bottom: 0 }}>
                <XAxis type="number" hide />
                <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{fill: '#888', fontSize: 12}} width={70} />
                <Tooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{backgroundColor: 'hsl(220 16% 11%)', border: '1px solid hsl(220 14% 20%)', borderRadius: '8px'}} />
                <Bar dataKey="value" fill="hsl(54 95% 51%)" radius={[0, 4, 4, 0]} barSize={16} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 13-Week Sparkline */}
        <div className="space-y-3">
          <h3 className="section-label">13-Week Recurrence</h3>
          <div className="flex items-center justify-between gap-1">
            {weeks.map((w, i) => (
              <div 
                key={i} 
                title={w.week}
                className={clsx(
                  "flex-1 h-8 rounded-sm",
                  w.active ? "bg-primary" : "bg-muted"
                )}
              />
            ))}
          </div>
          <p className="text-xs text-center text-muted-foreground">
            Active in {selectedJunction.recurrence_weeks} out of last 13 weeks
          </p>
        </div>

        {/* Action Recommendation */}
        <div className="p-4 rounded-xl border border-primary/25 bg-primary/10 flex gap-3 items-start">
          <AlertTriangle className="w-5 h-5 text-primary shrink-0 mt-0.5" />
          <div>
            <h4 className="font-semibold text-primary mb-1">Intervention Required</h4>
            <p className="text-sm text-primary/80 leading-relaxed">
              {selectedJunction.top_cause.replace('_', ' ')} recurring for {selectedJunction.recurrence_weeks}+ weeks. 
              Flag to infrastructure teams for permanent resolution to eliminate this node.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
