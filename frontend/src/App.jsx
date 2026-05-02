import React from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import EntryPanel from './components/EntryPanel';
import ExitPanel from './components/ExitPanel';

function App() {
  return (
    <BrowserRouter>
      {/* Top Government Banner */}
      <div className="top-banner">
        National e-Government Parking Procurement Portal of the Government
      </div>

      {/* Header with Logo and Navigation */}
      <header className="header-container">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ 
            width: '60px', height: '60px', borderRadius: '50%', 
            background: 'linear-gradient(to right, red, green)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'white', fontWeight: 'bold', fontSize: '12px'
          }}>
            ANPR
          </div>
        </div>
        
        <nav className="header-nav">
          <NavLink to="/" className={({ isActive }) => isActive ? 'active' : ''} end>Home Page</NavLink>
          <span>|</span>
          <NavLink to="/entry" className={({ isActive }) => isActive ? 'active' : ''}>Manual Entry</NavLink>
          <span>|</span>
          <NavLink to="/exit" className={({ isActive }) => isActive ? 'active' : ''}>Manual Exit</NavLink>
        </nav>
      </header>

      {/* Main Grid Layout */}
      <div className="main-container">
        <Sidebar />
        <main>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/entry" element={<EntryPanel />} />
            <Route path="/exit" element={<ExitPanel />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
