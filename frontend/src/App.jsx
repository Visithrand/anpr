import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import EntryPanel from './components/EntryPanel';
import ExitPanel from './components/ExitPanel';
import LiveDashboard from './components/LiveDashboard';
import Reports from './components/Reports';
import AuditTrail from './components/AuditTrail';
import Settings from './components/Settings';
import Monitor from './components/Monitor';
import LoginPage from './components/LoginPage';

function AppShell() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#f8fafc', fontFamily: "'Inter', system-ui, -apple-system, sans-serif" }}>
        <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
          <div style={{ width: '44px', height: '44px', borderRadius: '12px', background: 'linear-gradient(135deg, #1e40af 0%, #3b82f6 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 4px 16px rgba(59, 130, 246, 0.3)' }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"></rect><path d="M8 21h8M12 17v4"></path></svg>
          </div>
          <div>
            <div style={{ color: '#0f172a', fontSize: '20px', fontWeight: '800', letterSpacing: '-0.5px' }}>ANPR<span style={{ color: '#3b82f6' }}>.OS</span></div>
            <div style={{ color: '#94a3b8', fontSize: '12px', fontWeight: '500', marginTop: '4px' }}>Loading...</div>
          </div>
          <div style={{ width: '180px', height: '2px', background: '#e2e8f0', borderRadius: '2px', overflow: 'hidden' }}>
            <div style={{ height: '100%', background: 'linear-gradient(90deg, #2563eb, #3b82f6)', animation: 'loadBar 1.5s ease-in-out infinite', width: '60%', borderRadius: '2px' }}></div>
          </div>
          <style>{`@keyframes loadBar { 0% { transform: translateX(-100%); } 100% { transform: translateX(280%); } }`}</style>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column',
      height: '100vh', 
      width: '100vw', 
      overflow: 'hidden', 
      fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
      backgroundColor: '#f8fafc',
      color: '#0f172a'
    }}>
      {/* Persistent Global Header */}
      <header style={{
        height: '60px',
        backgroundColor: '#ffffff',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        zIndex: 100,
        flexShrink: 0,
      }}>
        <div>
          <div style={{ fontWeight: '800', fontSize: '16px', color: '#0f172a', letterSpacing: '-0.3px', lineHeight: '1.2', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>EYROVIZ</span>
            <span style={{ color: '#64748b', fontWeight: '400', fontSize: '12px' }}>TECHNOLOGIES</span>
          </div>
          <div style={{ fontSize: '9px', color: '#94a3b8', fontWeight: '600', marginTop: '2px', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
            © EYROVIZ · All Rights Reserved
          </div>
        </div>

        {/* Brand System Status Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '11px',
            fontWeight: '700',
            color: '#0f172a',
            backgroundColor: '#f1f5f9',
            padding: '4px 10px',
            borderRadius: '20px',
            border: '1px solid #e2e8f0',
          }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#10b981', display: 'inline-block' }}></span>
            ANPR.OS ONLINE
          </span>
        </div>
      </header>

      {/* Main Workspace (Sidebar + Routes) */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Global Sidebar */}
        <Sidebar />

        {/* Page Content */}
        <main style={{ flex: 1, overflowY: 'auto' }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/live" element={<LiveDashboard />} />
            <Route path="/entry" element={<EntryPanel />} />
            <Route path="/exit" element={<ExitPanel />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/audit" element={<AuditTrail />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/monitor" element={<Monitor />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppShell />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
