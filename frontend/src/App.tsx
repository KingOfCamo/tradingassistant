import { Routes, Route } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import { AuthGuard } from './components/AuthGuard.tsx';
import { Sidebar } from './components/Sidebar.tsx';
import { TopBar } from './components/TopBar.tsx';

const Login = lazy(() => import('./pages/Login.tsx'));
const Dashboard = lazy(() => import('./pages/Dashboard.tsx'));
const Ideas = lazy(() => import('./pages/Ideas.tsx'));
const Confluence = lazy(() => import('./pages/Confluence.tsx'));
const Screener = lazy(() => import('./pages/Screener.tsx'));
const Watchlist = lazy(() => import('./pages/Watchlist.tsx'));
const Portfolio = lazy(() => import('./pages/Portfolio.tsx'));
const RiskMap = lazy(() => import('./pages/RiskMap.tsx'));
const Journal = lazy(() => import('./pages/Journal.tsx'));
const Analysis = lazy(() => import('./pages/Analysis.tsx'));
const Settings = lazy(() => import('./pages/Settings.tsx'));

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="w-6 h-6 border-2 border-accent-green border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

function ProtectedLayout() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen bg-bg-base">
        <Sidebar />
        <div className="flex flex-col flex-1 ml-60">
          <TopBar />
          <main className="flex-1 p-5 overflow-auto">
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route index element={<Dashboard />} />
                <Route path="ideas" element={<Ideas />} />
                <Route path="confluence" element={<Confluence />} />
                <Route path="screener" element={<Screener />} />
                <Route path="watchlist" element={<Watchlist />} />
                <Route path="portfolio" element={<Portfolio />} />
                <Route path="risk" element={<RiskMap />} />
                <Route path="journal" element={<Journal />} />
                <Route path="analysis" element={<Analysis />} />
                <Route path="settings" element={<Settings />} />
              </Routes>
            </Suspense>
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/*" element={<ProtectedLayout />} />
      </Routes>
    </Suspense>
  );
}
