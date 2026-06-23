import { client } from "./client";
import mockData from "./mocks/incidents.json";

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";
const TOMTOM_KEY = import.meta.env.VITE_TOMTOM_KEY;

// Bengaluru bounding box
const BBOX = "77.35,12.75,77.80,13.20";

// How many pins to show max — keeps map readable
const TOP_N = 100;

// ─── TomTom icon category → event_cause ──────────────────────────────────
// Category 6 is TomTom's catch-all for slow traffic in India — we remap it
// by magnitudeOfDelay in tomtomToIncident() so it shows meaningful labels.
const CATEGORY_MAP = {
  0:  { cause: "others",               display: "Traffic Congestion" },
  1:  { cause: "accident",             display: "Accident"           },
  2:  { cause: "fog",                  display: "Fog / Poor Visibility" },
  3:  { cause: "dangerous_conditions", display: "Dangerous Conditions" },
  4:  { cause: "road_conditions",      display: "Slippery Road"      },
  5:  { cause: "road_conditions",      display: "Ice on Road"        },
  6:  { cause: "others",               display: "Traffic Jam"        }, // remapped below by magnitude
  7:  { cause: "construction",         display: "Construction Works" },
  8:  { cause: "others",               display: "Lane Restriction"   },
  9:  { cause: "others",               display: "Road Closure"       },
  10: { cause: "others",               display: "Road Blocked"       },
  11: { cause: "others",               display: "Road Works"         },
  14: { cause: "accident",             display: "Accident / Breakdown"},
};

// For category 6 (traffic jam), use magnitude to give a more useful label
const CAT6_DISPLAY = {
  0: "Light Traffic",
  1: "Minor Slowdown",
  2: "Moderate Jam",
  3: "Heavy Congestion",
  4: "Road Blocked",
};

// ─── TomTom magnitudeOfDelay → priority + closure ────────────────────────
// 0=unknown 1=minor 2=moderate 3=major 4=road closed
const PRIORITY_MAP = {
  0: { priority: "Low",  requires_road_closure: false },
  1: { priority: "Low",  requires_road_closure: false },
  2: { priority: "Low",  requires_road_closure: false },
  3: { priority: "High", requires_road_closure: false },
  4: { priority: "High", requires_road_closure: true  },
};

// ─── Map raw TomTom incident → your incident shape ────────────────────────
function tomtomToIncident(raw, index) {
  const props = raw.properties || {};
  const geo   = raw.geometry  || {};

  let lat = null;
  let lon = null;
  if (geo.type === "Point" && Array.isArray(geo.coordinates)) {
    [lon, lat] = geo.coordinates;
  } else if (geo.type === "LineString" && Array.isArray(geo.coordinates) && geo.coordinates.length > 0) {
    const mid = Math.floor(geo.coordinates.length / 2);
    [lon, lat] = geo.coordinates[mid];
  }

  if (!lat || !lon) return null;
  if (lat < 12.75 || lat > 13.20 || lon < 77.35 || lon > 77.80) return null;

  const catId    = props.iconCategory    ?? 0;
  const magDelay = props.magnitudeOfDelay ?? 0;

  const catInfo = CATEGORY_MAP[catId]    || CATEGORY_MAP[0];
  const priInfo = PRIORITY_MAP[magDelay] || PRIORITY_MAP[0];

  // For category 6 (generic jam), override display with magnitude-aware label
  const displayLabel = catId === 6
    ? (CAT6_DISPLAY[magDelay] || "Traffic Jam")
    : catInfo.display;

  const delayMins = props.delay != null ? Math.round(props.delay / 60) : null;
  // Use actual delay if > 0, else fallback based on magnitude
  const MAGNITUDE_DURATION = { 0: 5, 1: 10, 2: 20, 3: 40, 4: 60 };
  const duration = (delayMins && delayMins > 0)
    ? delayMins
    : (MAGNITUDE_DURATION[magDelay] || 15);

  // Junction: "From Road → To Road", truncate only if truly too long
  let junction = "Traffic Point";
  if (props.from && props.to) {
    const full = `${props.from} → ${props.to}`;
    junction = full.length > 50 ? props.from : full;
  } else if (props.from) {
    junction = props.from;
  } else if (props.roadNumbers && props.roadNumbers.length > 0) {
    junction = props.roadNumbers.join(" / ");
  }

  // Corridor: road number if available, else derive from junction
  const corridor = props.roadNumbers && props.roadNumbers.length > 0
    ? props.roadNumbers[0]
    : (props.from || "Non-corridor");

  return {
    id:                   `TT-${props.id || index}`,
    event_type:           "unplanned",
    event_cause:          catInfo.cause,
    event_cause_display:  displayLabel,
    latitude:             lat,
    longitude:            lon,
    corridor,
    junction,
    police_station:       null,
    priority:             priInfo.priority,
    requires_road_closure: priInfo.requires_road_closure,
    start_datetime:       props.startTime || new Date().toISOString(),
    duration_mins:        duration,
    status:               "active",
    is_stale_active:      false,
    source:               "tomtom",
    // Internal severity score — road closures first, then magnitude, then delay seconds
    _severity: (priInfo.requires_road_closure ? 100000 : 0)
             + (magDelay * 1000)
             + (props.delay || 0),
  };
}

// ─── Pick top N with guaranteed buckets ──────────────────────────────────
// Splits the 100 pins into 3 buckets so the stat bar never shows zeroes:
//   • 15 road closures  (magnitudeOfDelay 4)
//   • 60 High priority  (magnitudeOfDelay 3, no closure)
//   • 25 Low / Clear    (magnitudeOfDelay 0-2)
// Within each bucket, worst delay first.
function pickTopN(list) {
  const byDelay = (a, b) => b._severity - a._severity;

  const closures = list
    .filter(i => i.requires_road_closure)
    .sort(byDelay)
    .slice(0, 15);

  const highNoClosure = list
    .filter(i => i.priority === 'High' && !i.requires_road_closure)
    .sort(byDelay)
    .slice(0, 60);

  const low = list
    .filter(i => i.priority === 'Low')
    .sort(byDelay)
    .slice(0, 25);

  // If any bucket is short, backfill from the next tier
  const combined = [...closures, ...highNoClosure, ...low];

  // Dedupe by id just in case, then cap at TOP_N
  const seen = new Set();
  return combined.filter(i => {
    if (seen.has(i.id)) return false;
    seen.add(i.id);
    return true;
  }).slice(0, TOP_N);
}

// ─── Fetch live incidents from TomTom ─────────────────────────────────────
async function fetchTomTomIncidents() {
  if (!TOMTOM_KEY) {
    console.warn("[incidents] VITE_TOMTOM_KEY not set — falling back to backend");
    return null;
  }

  const fields = "{incidents{type,geometry{type,coordinates},properties{id,iconCategory,magnitudeOfDelay,startTime,delay,from,to,roadNumbers,timeValidity}}}";

  const url =
    `https://api.tomtom.com/traffic/services/5/incidentDetails` +
    `?key=${TOMTOM_KEY}` +
    `&bbox=${BBOX}` +
    `&fields=${fields}` +
    `&language=en-GB` +
    `&categoryFilter=0,1,2,3,4,5,6,7,8,9,10,11,14` +
    `&timeValidityFilter=present` +
    `&t=1111`;

  const res = await fetch(url);

  if (!res.ok) {
    console.error("[incidents] TomTom API error:", res.status, res.statusText);
    return null;
  }

  const json    = await res.json();
  const rawList = json.incidents || [];

  const allMapped = rawList
    .map((raw, i) => tomtomToIncident(raw, i))
    .filter(Boolean);

  // Keep only the worst TOP_N — map stays clean, worst spots always visible
  const top = pickTopN(allMapped);

  console.log(
    `[incidents] TomTom: ${rawList.length} raw → ${allMapped.length} valid → showing top ${top.length}`
  );
  return top;
}

// ─── Public API ───────────────────────────────────────────────────────────

export const getIncidents = async (filters = {}) => {
  if (USE_MOCK) return mockData;

  const tomtomIncidents = await fetchTomTomIncidents();
  if (tomtomIncidents && tomtomIncidents.length > 0) {
    return {
      total:     tomtomIncidents.length,
      filtered:  tomtomIncidents.length,
      incidents: tomtomIncidents,
    };
  }

  console.warn("[incidents] TomTom empty/failed — falling back to backend");
  const response = await client.get("/incidents", {
    params: { exclude_stale: true, limit: 300, ...filters },
  });

  const data   = response.data;
  const all    = Array.isArray(data) ? data : (data.incidents || []);
  const active = all.filter(
    (i) =>
      i.status     === "active"  &&
      i.latitude   >= 12.75 && i.latitude   <= 13.20 &&
      i.longitude  >= 77.35 && i.longitude  <= 77.80
  );

  return { total: active.length, filtered: active.length, incidents: active };
};

export const getIncidentSummary = async () => {
  if (USE_MOCK) {
    const { incidents } = mockData;
    return {
      total:    incidents.length,
      high:     incidents.filter(i => i.priority === "High").length,
      low:      incidents.filter(i => i.priority === "Low").length,
      closures: incidents.filter(i => i.requires_road_closure).length,
    };
  }

  const tomtomIncidents = await fetchTomTomIncidents();
  if (tomtomIncidents && tomtomIncidents.length > 0) {
    return {
      total:    tomtomIncidents.length,
      high:     tomtomIncidents.filter(i => i.priority === "High").length,
      low:      tomtomIncidents.filter(i => i.priority === "Low").length,
      closures: tomtomIncidents.filter(i => i.requires_road_closure).length,
    };
  }

  const response = await client.get("/incidents/summary");
  return response.data;
};