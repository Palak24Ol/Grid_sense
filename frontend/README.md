# GridSense Frontend

The frontend for **GridSense**, an AI-powered traffic intelligence and command center designed to predict, triage, and manage mass traffic incidents across Bengaluru.

## 🛠 Tech Stack
- **Framework:** React + Vite
- **Styling:** Tailwind CSS + Lucide Icons
- **Mapping:** React-Leaflet + CARTO dark basemaps
- **State Management:** Zustand
- **Charts/Visuals:** Recharts

## 🚀 Getting Started

### 1. Environment Setup
The frontend requires two environment variables to communicate with the FastAPI backend. In production or Docker, these are provided automatically. If running locally, create a `.env` file in the `frontend` directory:

```env
VITE_API_URL=http://localhost:8000/api/v1
VITE_USE_MOCK=false
```
*Note: Setting `VITE_USE_MOCK=false` ensures the Live Map and UI components pull actual live data from the PostgreSQL database rather than static fallback JSON.*

### 2. Running Locally (Without Docker)
If you want to run the frontend independently of the `docker-compose` setup for rapid UI development:

```bash
# Install dependencies
npm install

# Start the Vite dev server with hot-reloading
npm run dev
```

### 3. Running with Docker
The recommended way to run the full stack (Frontend, Backend, and Database) is using Docker from the root directory:

```bash
cd ..
docker-compose up -d --build
```
*Note: The frontend is mapped via a volume in `docker-compose.yml`, so any edits to the `src/` files will instantly hot-reload in the browser without needing a container rebuild!*

## 🗺 Application Structure
- **/components/map**: Contains `CommandCenterMap.jsx`, handling the live Leaflet map and dynamic tooltips.
- **/components/triage**: Incident check form — predicts closure risk, priority, and expected clearance time in plain language for field officers.
- **/components/surge**: Rain & Surge Alert dashboard highlighting vulnerable corridors with red/yellow/green road status.
- **/components/events**: Planned event deployment planner for rallies, matches, and festivals.
- **/components/forecast**: 3-day ahead traffic trouble forecast per corridor.
- **/components/deployment**: Officer posting recommender — how many officers, where to send them.
- **/components/blackspot**: Recurring problem junctions map and slow-response station tracker.
- **/components/logistics**: Heavy vehicle trouble zones and risk breakdown.
- **/components/learning**: Post-event learning system (accessible via `/learning` URL — not shown in the officer sidebar by design).
- **/api**: Axios client wrappers to fetch data from the FastAPI endpoints.
- **/store**: Zustand global stores managing UI state across the dashboards.
