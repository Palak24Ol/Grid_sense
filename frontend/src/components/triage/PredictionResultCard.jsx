import { AlertTriangle, Clock, CheckCircle, Info } from 'lucide-react';

// Map known backend reason patterns to plain English
const REASON_MAP = [
  { match: /rush hour|peak traffic|deploy within/i,           plain: "Happened during peak rush hour — roads are busier" },
  { match: /vehicle type/i,                                   plain: "The type of vehicle involved adds to the risk" },
  { match: /incident cause type|cause type/i,                 plain: "This type of incident commonly causes delays" },
  { match: /station.*high.priority|high.priority.*station/i,  plain: "This area has a history of serious incidents" },
  { match: /corridor.*density|density.*corridor/i,            plain: "This is a high-traffic road" },
  { match: /closure rate|cause.*closure/i,                    plain: "This type of incident often leads to road closure" },
  { match: /corridor incident|corridor.*incident/i,           plain: "This corridor sees frequent incidents" },
  { match: /geographic zone|zone/i,                           plain: "This zone has a pattern of incidents" },
  { match: /high.priority corridor|known.*corridor/i,         plain: "This is a known high-priority road" },
  { match: /rush hour|is_rush/i,                              plain: "Happened during peak rush hour" },
  { match: /daytime/i,                                        plain: "Happened during daytime when traffic is heavy" },
  { match: /day of week|day.*week/i,                          plain: "This day of the week is usually busier" },
  { match: /time of day|hour/i,                               plain: "Time of day affects traffic badly here" },
  { match: /other.*incident.*road|road.*incident/i,           plain: "Other problems reported on this road recently" },
  { match: /location|geographic|lat|lon/i,                    plain: "Location is a known trouble area" },
  { match: /planned event|is_planned/i,                       plain: "This is a known planned event" },
];

function toPlainReason(raw) {
  if (!raw) return null;

  // Completely strip anything with importance= or value= — these are internal ML numbers
  if (/importance\s*=\s*[\d.]+/i.test(raw)) {
    // Extract just the label part before the comma + importance
    const labelPart = raw.split(',')[0]
      .replace(/^[↑↓\s]+/, '')
      .replace(/^(Risk|Priority):\s*/i, '')
      .trim();

    // Try to map the label part
    for (const { match, plain } of REASON_MAP) {
      if (match.test(labelPart)) return plain;
    }

    // If we can't map it, skip this reason entirely (return null)
    return null;
  }

  // No importance= — try to map the whole string
  const clean = raw
    .replace(/^[↑↓\s]+/, '')
    .replace(/^(Risk|Priority):\s*/i, '')
    .replace(/\s*\(.*?\)/g, '')
    .replace(/—\s*$/, '')
    .trim();

  for (const { match, plain } of REASON_MAP) {
    if (match.test(clean)) return plain;
  }

  // If it reads like a plain sentence already, use it
  if (clean.includes(' ') && !clean.includes('_') && !clean.includes('=')) {
    return clean.replace(/—\s*$/, '').trim();
  }

  return null; // skip unreadable ones
}

export default function PredictionResultCard({ result }) {
  if (!result) return null;

  const durationMins = Math.round(result.predicted_duration_mins);
  const durationText = durationMins >= 60
    ? `About ${(durationMins / 60).toFixed(1)} hours`
    : `About ${durationMins} minutes`;

  const priorityLabel = result.predicted_priority === 'High' ? 'High — Act Now' : 'Low — Monitor';

  // Build clean, deduplicated plain-language reasons
  const cleanReasons = (result.top_reasons || [])
    .map(toPlainReason)
    .filter(Boolean)
    .filter((r, i, arr) => arr.indexOf(r) === i) // deduplicate
    .slice(0, 4);

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden flex flex-col h-full">
      <div className="p-4 border-b border-border bg-muted/30">
        <h2 className="font-semibold">What to Do</h2>
      </div>

      <div className="p-6 flex-1 overflow-y-auto space-y-6">

        {/* Priority + Road Closure */}
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-xl p-4 border border-border bg-muted/20 flex flex-col items-center justify-center text-center gap-1">
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Priority</span>
            <span className={`text-2xl font-bold ${result.predicted_priority === 'High' ? 'text-destructive' : 'text-primary'}`}>
              {priorityLabel}
            </span>
          </div>
          <div className="rounded-xl p-4 border border-border bg-muted/20 flex flex-col items-center justify-center text-center gap-1">
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Road Closure?</span>
            <span className={`text-2xl font-bold ${result.closure_flag ? 'text-destructive' : 'text-primary'}`}>
              {result.closure_flag ? 'Likely' : 'Unlikely'}
            </span>
            <div className="w-full bg-muted rounded-full h-1.5 mt-2 overflow-hidden">
              <div
                className={`h-full rounded-full ${result.closure_flag ? 'bg-destructive' : 'bg-primary'}`}
                style={{ width: `${Math.min(100, Math.max(0, result.closure_probability * 100))}%` }}
              />
            </div>
          </div>
        </div>

        {/* Duration */}
        <div className="p-4 rounded-xl border border-border bg-muted/20 flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center shrink-0 border border-primary/25">
            <Clock className="w-6 h-6 text-primary" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-lg">{durationText} to clear</h3>
            <p className="text-sm text-muted-foreground">
              Could be anywhere from {Math.round(result.duration_p25)} to {Math.round(result.duration_p75)} minutes
            </p>
          </div>
        </div>

        {/* Manual check — plain language only, no ML mention */}
        {result.disagreement_flag && (
          <div className="p-4 rounded-xl border border-warning/30 bg-warning/10 flex gap-3 items-start">
            <AlertTriangle className="w-5 h-5 text-warning shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-warning mb-1">Manual Check Needed</h4>
              <p className="text-sm text-warning/80 leading-relaxed">
                Our system is unsure about this one — please have an officer verify the situation on ground before deciding.
              </p>
            </div>
          </div>
        )}

        {/* Plain reasons — only show if we have clean ones */}
        {cleanReasons.length > 0 && (
          <div className="p-4 rounded-xl border border-border bg-muted/10 space-y-2">
            <h4 className="font-semibold text-sm flex items-center gap-2">
              <Info className="w-4 h-4 text-primary" />
              Why this recommendation?
            </h4>
            <ul className="space-y-1.5">
              {cleanReasons.map((reason, idx) => (
                <li key={idx} className="text-sm text-muted-foreground flex items-start gap-2">
                  <CheckCircle className="w-3.5 h-3.5 text-primary/70 mt-0.5 shrink-0" />
                  <span>{reason}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

      </div>
    </div>
  );
}