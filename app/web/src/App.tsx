import {
  Link,
  RouterProvider,
  createBrowserRouter,
  isRouteErrorResponse,
  Outlet,
  useRouteError,
} from "react-router";
import { useState } from "react";
import AppShell from "./components/AppShell";
import CustomCursor from "./components/CustomCursor";
import PublicHome from "./pages/PublicHome";
import LeadershipMap from "./pages/LeadershipMap";
import GroupExplorer from "./pages/GroupExplorer";
import Methodology from "./pages/Methodology";
import WhatChanged from "./pages/WhatChanged";
import ChartDemo from "./pages/ChartDemo";
import TickerAnalysis from "./pages/TickerAnalysis";
import MarketOverview from "./pages/MarketOverview";
import TaxonomyMapPage from "./pages/TaxonomyMapPage";
import MasterGroupTable from "./pages/MasterGroupTable";
import ThemesExplorer from "./pages/ThemesExplorer";
import { SnapshotProvider, useSnapshot } from "./data/SnapshotProvider";
function WorkspaceLayout() {
  const [taxonomy, setTaxonomy] = useState<"Sector" | "Industry">("Sector");
  const snap = useSnapshot();
  return (
    <AppShell taxonomy={taxonomy} onTaxonomyChange={setTaxonomy} snap={snap}>
      <Outlet />
    </AppShell>
  );
}

function RouteErrorElement() {
  const error = useRouteError();
  const message = isRouteErrorResponse(error)
    ? `${error.status}: ${error.statusText || "Page unavailable"}`
    : error instanceof Error
      ? error.message
      : "The page could not be rendered.";

  return (
    <main
      aria-live="polite"
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: 32,
        background: "#faf9f6",
        color: "#202325",
      }}
    >
      <section
        style={{
          width: "min(560px, 100%)",
          padding: 28,
          background: "#fff",
          border: "1px solid #dfe2e1",
          borderTop: "3px solid #d97956",
        }}
      >
        <div className="eyebrow-muted">Market intelligence</div>
        <h1 style={{ margin: "8px 0 10px", fontSize: 24, letterSpacing: "-.03em" }}>
          This view is temporarily unavailable
        </h1>
        <p style={{ margin: 0, color: "#686e73", lineHeight: 1.55 }}>
          The snapshot loaded, but this page encountered a rendering problem.
        </p>
        <p style={{ margin: "12px 0 20px", color: "#8f2424", fontFamily: "Geist Mono", fontSize: 11 }}>
          {message}
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <Link
            to="/overview"
            style={{
              padding: "9px 13px",
              background: "#202325",
              color: "#fff",
              textDecoration: "none",
              fontSize: 12,
            }}
          >
            Return to overview
          </Link>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{
              padding: "8px 12px",
              background: "#fff",
              border: "1px solid #b9c0be",
              color: "#202325",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            Reload snapshot
          </button>
        </div>
      </section>
    </main>
  );
}

const router = createBrowserRouter([
  { path: "/", Component: PublicHome, errorElement: <RouteErrorElement /> },
  {
    Component: WorkspaceLayout,
    errorElement: <RouteErrorElement />,
    children: [
      { path: "/what-changed", Component: WhatChanged },
      { path: "/overview", Component: MarketOverview },
      { path: "/map", Component: LeadershipMap },
      { path: "/maps/konglo", Component: TaxonomyMapPage },
      { path: "/maps/themes", Component: TaxonomyMapPage },
      { path: "/themes", Component: ThemesExplorer },
      { path: "/explorer", Component: GroupExplorer },
      { path: "/groups", Component: MasterGroupTable },
      { path: "/methodology", Component: Methodology },
      { path: "/chart-demo", Component: ChartDemo },
      { path: "/ticker/:ticker", Component: TickerAnalysis },
    ],
  },
]);

export default function App() {
  return (
    <SnapshotProvider>
      <CustomCursor />
      <RouterProvider router={router} />
    </SnapshotProvider>
  );
}
