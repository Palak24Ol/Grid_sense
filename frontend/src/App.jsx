import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import CommandCenterMap from "./components/map/CommandCenterMap";
import TriageScreen from "./components/triage/TriageScreen";
import BlackspotScreen from "./components/blackspot/BlackspotScreen";
import SurgeScreen from "./components/surge/SurgeScreen";
import DeploymentScreen from "./components/deployment/DeploymentScreen";
import ForecastScreen from "./components/forecast/ForecastScreen";
import FlipkartScreen from "./components/flipkart/FlipkartScreen";

const MapPage = () => <div className="p-4 h-full"><CommandCenterMap /></div>;

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<Navigate to="/map" replace />} />
          <Route path="map" element={<MapPage />} />
          <Route path="triage" element={<TriageScreen />} />
          <Route path="forecast" element={<ForecastScreen />} />
          <Route path="deployment" element={<DeploymentScreen />} />
          <Route path="flipkart" element={<FlipkartScreen />} />
          <Route path="blackspot" element={<BlackspotScreen />} />
          <Route path="surge" element={<SurgeScreen />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
