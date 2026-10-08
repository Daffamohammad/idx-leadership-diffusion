import "./market-workspace.css";
import {
  Link,
  Navigate,
  RouterProvider,
  createBrowserRouter,
  isRouteErrorResponse,
  Outlet,
  useRouteError,
} from "react-router";
import { useState } from "react";
import AppShell from "./components/AppShell";
import GroupExplorer from "./pages/GroupExplorer";
import Methodology from "./pages/Methodology";
import WhatChanged from "./pages/WhatChanged";
import TickerAnalysis from "./pages/TickerAnalysis";
import StockHeatmap from "./pages/StockHeatmap";
import ForeignFlow from "./pages/ForeignFlow";
import Ownership from "./pages/Ownership";
import MarketOverview from "./pages/MarketOverview";
import MarketMovers from "./pages/MarketMovers";
import RecordedSample from "./pages/RecordedSample";
import PublicHome from "./pages/PublicHome";
import SectorsDashboard from "./pages/SectorsDashboard";
import SubmissionRotationMap from "./components/SubmissionRotationMap";
import MasterGroupTable from "./pages/MasterGroupTable";
import ThemesExplorer from "./pages/ThemesExplorer";
import TickerExplorer from "./pages/TickerExplorer";
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
        background: "var(--surface-subtle)",
        color: "var(--ink)",
      }}
    >
      <section
        style={{
          width: "min(560px, 100%)",
          padding: 28,
          background: "var(--surface)",
          border: "1px solid var(--line)",
          borderTop: "3px solid #d97956",
        }}
      >
        <div className="eyebrow-muted">Market intelligence</div>
        <h1 style={{ margin: "8px 0 10px", fontSize: 24, letterSpacing: "-.03em" }}>
          This view is temporarily unavailable
        </h1>
        <p style={{ margin: 0, color: "var(--muted)", lineHeight: 1.55 }}>
          The data loaded, but this page encountered a rendering problem.
        </p>
        <p style={{ margin: "12px 0 20px", color: "var(--down)", fontFamily: "Geist Mono", fontSize: 11 }}>
          {message}
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <Link
            to="/overview"
            style={{
              padding: "9px 13px",
              background: "var(--ink)",
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
              background: "var(--surface)",
              border: "1px solid #b9c0be",
              color: "var(--ink)",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            Retry
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
      { path: "/movers", Component: MarketMovers },
      { path: "/sources", Component: RecordedSample },
      { path: "/recorded-sample", element: <Navigate to="/sources" replace /> },
      { path: "/sectors", Component: SectorsDashboard },
      { path: "/overview", Component: MarketOverview },
      { path: "/heatmap", Component: StockHeatmap },
      { path: "/foreign", Component: ForeignFlow },
      { path: "/ownership", Component: Ownership },
      { path: "/map", Component: SubmissionRotationMap },
      { path: "/maps/konglo", element: <Navigate to="/map?taxonomy=KONGLO&mode=groups" replace /> },
      { path: "/maps/themes", element: <Navigate to="/map?taxonomy=THEMES&mode=groups" replace /> },
      { path: "/themes", Component: ThemesExplorer },
      { path: "/konglo", Component: ThemesExplorer },
      { path: "/tickers", Component: TickerExplorer },
      { path: "/explorer", Component: GroupExplorer },
      { path: "/groups", Component: MasterGroupTable },
      { path: "/methodology", Component: Methodology },
      { path: "/ticker/:ticker", Component: TickerAnalysis },
    ],
  },
]);

export default function App() {
  return (
    <SnapshotProvider>
      <RouterProvider router={router} />
    </SnapshotProvider>
  );
}
