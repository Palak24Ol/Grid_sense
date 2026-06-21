import { useSurgeStore } from '../../store/useSurgeStore';
import { CloudLightning, AlertTriangle, ShieldAlert } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Cloud, Droplets, Wind, Thermometer } from 'lucide-react';
import clsx from 'clsx';

function roadStatusLabel(multiplier) {
  if (multiplier >= 4)   return { label: 'Very Bad',  cls: 'badge-critical', dot: 'bg-red-400'      };
  if (multiplier >= 2.5) return { label: 'Bad',       cls: 'badge-warning',  dot: 'bg-orange-400'   };
  if (multiplier >= 1.5) return { label: 'Getting Worse', cls: 'badge-medium', dot: 'bg-yellow-400' };
  return                        { label: 'Manageable', cls: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20', dot: 'bg-emerald-400' };
}
async function fetchBengaluruWeather(apiKey) {
  const res = await fetch(
    `https://api.openweathermap.org/data/2.5/weather?q=Bengaluru,IN&appid=${apiKey}&units=metric`
  );
  const data = await res.json();
  if (data.cod !== 200) return null;  // ← add this
  return data;
}

export default function SurgeDashboard() {


  const { vulnerability } = useSurgeStore();
   const [weather, setWeather] = useState(null);
const [isRaining, setIsRaining] = useState(false);

useEffect(() => {
  const key = import.meta.env.VITE_WEATHER_KEY;
  if (!key) return;
  fetchBengaluruWeather(key).then(data => {
  if (!data) return;  // ← add this
  setWeather(data);
  const rain = data.weather?.[0]?.main?.toLowerCase();
  setIsRaining(rain === 'rain' || rain === 'drizzle' || rain === 'thunderstorm');
});
}, []);

  if (!vulnerability || !vulnerability.corridors) return null;

  const overallRisk   = vulnerability.critical_count > 0 ? 'critical' : 'high';
  const topActual     = vulnerability.corridors.find(c => c.corridor !== 'Non-corridor');
  const topCorridor   = topActual?.corridor   || 'Unknown';
  const topMultiplier = topActual
    ? Math.max(1, topActual.vulnerability_score / 10).toFixed(1)
    : '1.0';

 

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm flex flex-col shrink-0 overflow-hidden">
      <div className="p-4 border-b border-border bg-card flex items-center justify-between">
        <h2 className="text-sm font-bold text-foreground flex items-center gap-2">
          <CloudLightning className="w-4 h-4 text-warning" />
          Rain & Surge Alert
        </h2>
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
          {new Date().toLocaleTimeString()}
        </span>
      </div>

      <div className="p-6 space-y-6">

        {weather && (
  <div className="p-4 rounded-xl border border-border bg-muted/20 flex items-center justify-between">
    <div className="flex items-center gap-3">
      <img 
        src={`https://openweathermap.org/img/wn/${weather.weather[0].icon}@2x.png`}
        alt="weather"
        className="w-12 h-12"
      />
      <div>
        <p className="font-bold text-foreground capitalize">
          {weather.weather[0].description}
        </p>
        <p className="text-xs text-muted-foreground">Bengaluru right now</p>
      </div>
    </div>
    <div className="flex gap-4 text-xs text-muted-foreground">
      <div className="flex items-center gap-1">
        <Thermometer className="w-3 h-3" />
        {Math.round(weather.main.temp)}°C
      </div>
      <div className="flex items-center gap-1">
        <Droplets className="w-3 h-3" />
        {weather.main.humidity}%
      </div>
      <div className="flex items-center gap-1">
        <Wind className="w-3 h-3" />
        {Math.round(weather.wind.speed)} m/s
      </div>
    </div>
    {isRaining && (
      <span className="px-3 py-1 bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded-full text-xs font-bold animate-pulse">
        🌧️ RAIN DETECTED
      </span>
    )}
  </div>
)}

        {/* Main alert banner — plain language */}
        <div className={clsx(
          'p-4 rounded-xl border flex gap-4 items-start',
          overallRisk === 'critical'
            ? 'bg-destructive/10 border-destructive/30'
            : 'bg-warning/10 border-warning/30'
        )}>
          {overallRisk === 'critical'
            ? <ShieldAlert className="w-8 h-8 text-destructive shrink-0 mt-1" />
            : <AlertTriangle className="w-8 h-8 text-warning shrink-0 mt-1" />
          }
          <div>
            <h3 className={clsx(
              'font-bold text-lg mb-1',
              overallRisk === 'critical' ? 'text-destructive' : 'text-warning'
            )}>
              {overallRisk === 'critical' ? '🔴 Serious Jam Risk' : '🟡 Traffic Getting Worse'}
            </h3>
            <p className="text-sm text-foreground/80 leading-relaxed">
              Rain is making traffic much worse than usual.{' '}
              <span className="font-bold text-foreground">{topCorridor}</span> is the worst road right now —
              expect about <span className="font-bold text-warning">{topMultiplier}x more jams</span> than a normal day.
              Deploy extra officers immediately.
            </p>
          </div>
        </div>

        {/* Road status table — red/yellow/green */}
        <div className="space-y-3">
          <h3 className="section-label">Road conditions right now</h3>
          <div className="border border-border rounded-lg overflow-hidden bg-muted/10">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted text-muted-foreground text-xs uppercase">
                <tr>
                  <th className="p-3 font-medium">Road</th>
                  <th className="p-3 font-medium">Main problem</th>
                  <th className="p-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {vulnerability.corridors
                  .filter(c => c.corridor !== 'Non-corridor')
                  .slice(0, 5)
                  .map((c) => {
                    const multiplier   = Math.max(1, c.vulnerability_score / 10).toFixed(1);
                    const primaryCause = c.water_logging_count > c.tree_fall_count
                      ? 'Water Logging'
                      : 'Tree Fall';
                    const status = roadStatusLabel(Number(multiplier));

                    return (
                      <tr key={c.corridor}>
                        <td className="p-3 font-medium">{c.corridor}</td>
                        <td className="p-3 text-muted-foreground">{primaryCause}</td>
                        <td className="p-3">
                          <span className={clsx('px-2 py-0.5 rounded-full text-xs font-bold flex items-center gap-1.5 w-fit', status.cls)}>
                            <span className={clsx('w-1.5 h-1.5 rounded-full', status.dot)} />
                            {status.label}
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
