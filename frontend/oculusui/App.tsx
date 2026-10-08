import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import Navbar from './Navbar';

// Each page is lazy-loaded, so every page is its own chunk.
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Rankings = lazy(() => import('./pages/Rankings'));
const Sectors = lazy(() => import('./pages/Sectors'));
const Company = lazy(() => import('./pages/Company'));

export default function App() {
  return (
    <div className="mt-app">
      <Navbar />
      <div className="mt-main">
        <Suspense fallback={<div className="mt-empty">Loading…</div>}>
          <Routes>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/rankings" element={<Rankings />} />
            <Route path="/sectors" element={<Sectors />} />
            <Route path="/company/:ticker" element={<Company />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Suspense>
      </div>
    </div>
  );
}
