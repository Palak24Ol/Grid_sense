import { useSurgeStore } from '../../store/useSurgeStore';
import { CloudLightning, AlertTriangle, ShieldAlert } from 'lucide-react';
import clsx from 'clsx';

export default function SurgeDashboard() {
  const { vulnerability } = useSurgeStore();

  if (!vulnerability || !vulnerability.corridors) return null;

  const overallRisk = vulnerability.critical_count > 0 ? 'critical' : 'high';
  const topActualCorridor = vulnerability.corridors.find(c => c.corridor !== "Non-corridor");
  const topCorridor = topActualCorridor?.corridor || 'Unknown';
  const topMultiplier = topActualCorridor ? Math.max(1, topActualCorridor.vulnerability_score / 10).toFixed(1) : "1.0";

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm flex flex-col shrink-0 overflow-hidden">
      <div className="p-4 border-b border-border bg-card flex items-center justify-between">
        <h2 className="text-sm font-bold text-foreground flex items-center gap-2">
          <CloudLightning className="w-4 h-4 text-warning" />
          Live Weather Vulnerability
        </h2>
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
          {new Date().toLocaleTimeString()}
        </span>
      </div>

      <div className="p-6 space-y-6">
        
        {/* Trigger Card */}
        <div className={clsx(
          "p-4 rounded-xl border flex gap-4 items-start",
          overallRisk === 'critical' ? "bg-destructive/10 border-destructive/30" : "bg-warning/10 border-warning/30"
        )}>
          {overallRisk === 'critical' ? (
            <ShieldAlert className="w-8 h-8 text-destructive shrink-0 mt-1" />
          ) : (
            <AlertTriangle className="w-8 h-8 text-warning shrink-0 mt-1" />
          )}
          
          <div>
            <h3 className={clsx(
              "font-bold text-lg mb-1 uppercase tracking-wider",
              overallRisk === 'critical' ? "text-destructive" : "text-warning"
            )}>
              {overallRisk} SURGE RISK DETECTED
            </h3>
            <p className="text-sm text-foreground/80 leading-relaxed">
              Current weather conditions match historical patterns for mass incidents. 
              Top vulnerable corridor: <span className="font-bold text-foreground">{topCorridor}</span>. 
              Expect up to <span className="font-bold text-warning">{topMultiplier}x more incidents</span> than a normal day.
              System recommends immediate execution of city-wide pre-deployment plan.
            </p>
          </div>
        </div>

        {/* Vulnerable Corridors Table */}
        <div className="space-y-3">
          <h3 className="section-label">Corridor Vulnerability Index</h3>
          <div className="border border-border rounded-lg overflow-hidden bg-muted/10">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted text-muted-foreground text-xs uppercase">
                <tr>
                  <th className="p-3 font-medium">Corridor</th>
                  <th className="p-3 font-medium">Risk Cause</th>
                  <th className="p-3 font-medium">Multiplier</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {vulnerability.corridors
                  .filter(c => c.corridor !== "Non-corridor")
                  .slice(0, 5)
                  .map((c) => {
                  const primaryCause = c.water_logging_count > c.tree_fall_count ? 'water_logging' : 'tree_fall';
                  const multiplier = Math.max(1, c.vulnerability_score / 10).toFixed(1);
                  return (
                  <tr key={c.corridor}>
                    <td className="p-3 font-medium">{c.corridor}</td>
                    <td className="p-3 capitalize text-muted-foreground">{primaryCause.replace('_', ' ')}</td>
                    <td className="p-3">
                      <span className={clsx(
                        "px-2 py-0.5 rounded-full text-xs font-bold",
                        multiplier >= 4 ? "badge-critical" : "badge-warning"
                      )}>
                        {multiplier}x
                      </span>
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
}
