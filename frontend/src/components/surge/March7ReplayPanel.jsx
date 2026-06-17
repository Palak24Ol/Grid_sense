import { useSurgeStore } from '../../store/useSurgeStore';
import { Play, Pause, BarChart2 } from 'lucide-react';
import { useState, useEffect } from 'react';
import clsx from 'clsx';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

export default function March7ReplayPanel() {
  const { replayData, activeHour, setActiveHour } = useSurgeStore();
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    let interval;
    if (isPlaying && replayData) {
      interval = setInterval(() => {
        setActiveHour(prev => {
          const currentIndex = replayData.march7_hourly_timeline.findIndex(t => t.hour_of_day === prev);
          const nextIndex = (currentIndex + 1) % replayData.march7_hourly_timeline.length;
          return replayData.march7_hourly_timeline[nextIndex].hour_of_day;
        });
      }, 2000); // 2 seconds per hour
    }
    return () => clearInterval(interval);
  }, [isPlaying, replayData, setActiveHour]);

  if (!replayData) return null;

  const currentTimelineData = replayData.march7_hourly_timeline.find(t => t.hour_of_day === activeHour) || replayData.march7_hourly_timeline[0];
  const topCause = currentTimelineData.water_logging > currentTimelineData.tree_fall ? 'water_logging' : 'tree_fall';

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm flex flex-col flex-1 overflow-hidden min-h-[400px]">
      <div className="p-4 border-b border-border bg-muted/30 flex items-center justify-between">
        <h2 className="font-semibold flex items-center gap-2">
          <BarChart2 className="w-5 h-5 text-primary" />
          Historical Replay: March 7, 2024
        </h2>
        <div className="flex items-center gap-4">
          <span className="text-xs font-mono text-muted-foreground">
            {activeHour}:00 - {activeHour + 1}:00
          </span>
          <button 
            onClick={() => setIsPlaying(!isPlaying)}
            className="p-1.5 rounded-full bg-primary/20 text-primary hover:bg-primary/30 transition-colors"
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-8">
        
        {/* Main Stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="p-3 bg-muted/20 border border-border rounded-lg text-center">
            <div className="text-xs text-muted-foreground">Total Surge</div>
            <div className="text-2xl font-bold text-destructive mt-1">{replayData.surge_stats.march7_total}</div>
            <div className="text-[10px] text-muted-foreground mt-1">vs {replayData.surge_stats.march6_total} baseline</div>
          </div>
          <div className="p-3 bg-muted/20 border border-border rounded-lg text-center">
            <div className="text-xs text-muted-foreground">Active Hour</div>
            <div className="text-2xl font-bold text-amber-500 mt-1">{currentTimelineData.total}</div>
            <div className="text-[10px] text-muted-foreground mt-1">incidents</div>
          </div>
          <div className="p-3 bg-muted/20 border border-border rounded-lg text-center">
            <div className="text-xs text-muted-foreground">Top Cause</div>
            <div className="text-sm font-bold text-foreground mt-2 capitalize truncate px-1">
              {topCause.replace('_', ' ')}
            </div>
          </div>
        </div>

        {/* Timeline Chart */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-muted-foreground">Incident Timeline</h3>
          <div className="h-32 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={replayData.march7_hourly_timeline} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <XAxis dataKey="hour_of_day" tickFormatter={(v) => `${v}:00`} tick={{fontSize: 10, fill: '#888'}} axisLine={false} tickLine={false} />
                <YAxis hide />
                <Tooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', fontSize: '12px'}} />
                <Bar dataKey="total" radius={[4, 4, 0, 0]}>
                  {replayData.march7_hourly_timeline.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={entry.hour_of_day === activeHour ? '#f59e0b' : '#334155'} 
                      style={{ cursor: 'pointer', transition: 'fill 0.3s ease' }}
                      onClick={() => setActiveHour(entry.hour_of_day)}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Pre-Deployment Plan */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-primary">Generated Pre-Deployment Plan</h3>
          <div className="border border-primary/20 rounded-lg overflow-hidden bg-primary/5">
            <table className="w-full text-left text-sm">
              <thead className="bg-primary/10 text-primary text-xs uppercase">
                <tr>
                  <th className="p-3 font-medium">Station</th>
                  <th className="p-3 font-medium">Surge</th>
                  <th className="p-3 font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-primary/10">
                {replayData.pre_deployment_plan.slice(0, 5).map((plan, i) => (
                  <tr key={i}>
                    <td className="p-3 font-medium">{plan.recommended_station}</td>
                    <td className="p-3 font-mono text-amber-500">+{plan.recommended_officers}</td>
                    <td className="p-3 text-xs text-right text-muted-foreground">{plan.surge_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
}
