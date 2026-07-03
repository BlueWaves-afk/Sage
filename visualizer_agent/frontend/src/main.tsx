import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "./index.css";
import "maplibre-gl/dist/maplibre-gl.css";

import AppShell from "./components/layout/AppShell";
import Landing from "./screens/Landing";
import CommandCenter from "./screens/CommandCenter";
import GlobalIntelligence from "./screens/GlobalIntelligence";
import SimulationLab from "./screens/SimulationLab";
import ResponsePlanner from "./screens/ResponsePlanner";
import StrategicCopilot from "./screens/StrategicCopilot";

const router = createBrowserRouter([
  { path: "/", element: <Landing /> },
  {
    element: <AppShell />,
    children: [
      { path: "/command", element: <CommandCenter /> },
      { path: "/intelligence", element: <GlobalIntelligence /> },
      { path: "/simulation", element: <SimulationLab /> },
      { path: "/response", element: <ResponsePlanner /> },
      { path: "/copilot", element: <StrategicCopilot /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
