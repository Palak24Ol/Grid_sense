import { useSurgeStore } from '../../store/useSurgeStore';
import { Play, Pause, BarChart2 } from 'lucide-react';
import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

function hourLabel(h) {
  const ampm = h < 12 ? 'AM' : 'PM';
  const hh   = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${hh} ${ampm}`;
}

export default function March7ReplayPanel() {
  const { replayData, activeHour, setActiveHour } = useSurgeStore();
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    let interval;
    if (isPlaying && replayData) {
      interval = setInterval(() => {
        setActiveHour(prev => {
          const currentIndex = replayData.march7_hourly_timeline.findIndex(t => t.hour_of_day === prev);
          const nextIndex    = (currentIndex + 1) % replayData.march7_hourly_timeline.length;
          return replayData.march7_hourly_timeline[nextIndex].hour_of_day;
        });
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [isPlaying, replayData, setActiveHour]);

  if (!replayData) return null;

  const current  = replayData.march7_hourly_timeline.find(t => t.hour_of_day === activeHour)
                || replayData.march7_hourly_timeline[0];
  const topCause = current.water_logging > current.tree_fall ? 'Water Logging' : 'Tree Fall';

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm flex flex-col flex-1 overflow-hidden min-h-[400px]">
      <div className="p-4 border-b border-border bg-card flex items-center justify-between">
        <h2 className="text-sm font-bold text-foreground flex items-center gap-2">
          <BarChart2 className="w-4 h-4 text-primary" />
          Replay: Worst Day on Record (7 March 2024)
        </h2>
        <div className="flex items-center gap-4">
          <span className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">
            {hourLabel(activeHour)} – {hourLabel(activeHour + 1)}
          </span>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="p-1.5 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors glow-yellow"
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-8">

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="p-3 bg-muted/20 border border-border rounded-xl text-center flex flex-col items-center justify-center gap-1">
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Incidents That Day</span>
            <div className="text-2xl font-bold text-destructive mt-1">{replayData.surge_stats.march7_total}</div>
            <div className="text-[10px] text-muted-foreground mt-1">vs {replayData.surge_stats.march6_total} day before</div>
          </div>
          <div className="p-3 bg-muted/20 border border-border rounded-xl text-center flex flex-col items-center justify-center gap-1">
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">This Hour</span>
            <div className="text-2xl font-bold text-warning mt-1">{current.total}</div>
            <div className="text-[10px] text-muted-foreground mt-1">incidents</div>
          </div>
          <div className="p-3 bg-muted/20 border border-border rounded-xl text-center flex flex-col items-center justify-center gap-1">
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Main Problem</span>
            <div className="text-sm font-bold text-foreground mt-2 truncate px-1">{topCause}</div>
          </div>
        </div>

        {/* Timeline Chart */}
        <div className="space-y-3">
          <h3 className="section-label">Incidents hour by hour — click any bar</h3>
          <div className="h-32 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={replayData.march7_hourly_timeline}
                margin={{ top: 0, right: 0, left: -20, bottom: 0 }}
              >
                <XAxis
                  dataKey="hour_of_day"
                  tickFormatter={(v) => hourLabel(v)}
                  tick={{ fontSize: 10, fill: '#888' }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis hide />
                <Tooltip
                  cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    border: 'none',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  labelFormatter={(v) => `${hourLabel(v)} – ${hourLabel(v + 1)}`}
                  formatter={(value) => [value, 'Incidents']}
                />
                <Bar dataKey="total" radius={[4, 4, 0, 0]}>
                  {replayData.march7_hourly_timeline.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.hour_of_day === activeHour ? 'hsl(54 95% 51%)' : 'hsl(220 14% 16%)'}
                      style={{ cursor: 'pointer', transition: 'fill 0.3s ease' }}
                      onClick={() => setActiveHour(entry.hour_of_day)}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Deployment plan */}
        <div className="space-y-3">
          <h3 className="section-label text-primary">What should have been done</h3>
          <div className="border border-primary/20 rounded-lg overflow-hidden bg-primary/5">
            <table className="w-full text-left text-sm">
              <thead className="bg-primary/10 text-primary text-xs uppercase">
                <tr>
                  <th className="p-3 font-medium">Station</th>
                  <th className="p-3 font-medium">Extra Officers</th>
                  <th className="p-3 font-medium text-right">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-primary/10">
                {replayData.pre_deployment_plan.slice(0, 5).map((plan, i) => (
                  <tr key={i}>
                    <td className="p-3 font-medium">{plan.recommended_station}</td>
                    <td className="p-3 font-mono text-warning">+{plan.recommended_officers}</td>
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
