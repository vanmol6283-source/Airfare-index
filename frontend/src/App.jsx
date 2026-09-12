import { BrowserRouter, Routes, Route } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import Overview from "./pages/Overview";
import DataExplorer from "./pages/DataExplorer";
import RoutesPage from "./pages/Routes";
import RouteDetail from "./pages/RouteDetail";
import Methodology from "./pages/Methodology";
import DataQuality from "./pages/DataQuality";
import ApiDocs from "./pages/ApiDocs";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<Overview />} />
          <Route path="/explorer" element={<DataExplorer />} />
          <Route path="/routes" element={<RoutesPage />} />
          <Route path="/route/:id" element={<RouteDetail />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="/data-quality" element={<DataQuality />} />
          <Route path="/api-docs" element={<ApiDocs />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}