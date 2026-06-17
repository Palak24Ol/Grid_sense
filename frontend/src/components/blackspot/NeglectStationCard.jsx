import { useBlackspotStore } from '../../store/useBlackspotStore';
import { Clock } from 'lucide-react';

export default function NeglectStationCard() {
  const { neglectIndex } = useBlackspotStore();

  if (!neglectIndex || neglectIndex.length === 0) return null;

  const topStations = neglectIndex.slice(0, 3);

  return (
    <div className="bg-card/90 backdrop-blur-md border border-border rounded-xl shadow-lg flex-1 overflow-hidden flex flex-col">
      <div className="p-4 border-b border-border bg-muted/30">
        <h2 className="font-semibold flex items-center gap-2">
          <Clock className="w-5 h-5 text-amber-500" />
          Resolution Neglect Index
        </h2>
        <p className="text-xs text-muted-foreground mt-1">
          Stations with incidents open 5x longer than median.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {topStations.map((station, idx) => (
          <div key={station.police_station} className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="font-medium text-sm flex items-center gap-2">
                <span className="text-xs text-muted-foreground">{idx + 1}.</span>
                {station.police_station}
              </span>
              <span className="text-destructive text-sm font-bold">
                {(station.neglect_rate * 100).toFixed(1)}%
              </span>
            </div>
            
            <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
              <div 
                className="h-full bg-destructive" 
                style={{ width: `${station.neglect_rate * 100}%` }}
              />
            </div>
            
            <div className="text-xs text-muted-foreground flex justify-between">
              <span>{station.neglected_count} neglected</span>
              <span className="capitalize text-amber-500/80 text-right max-w-[150px] truncate">
                Top: {station.top_neglected_cause.replace('_', ' ')}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
