import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const NAV_ITEMS = [
  {
    to: '/',
    label: 'Dashboard',
    exact: true,
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1"></rect>
        <rect x="14" y="3" width="7" height="7" rx="1"></rect>
        <rect x="3" y="14" width="7" height="7" rx="1"></rect>
        <rect x="14" y="14" width="7" height="7" rx="1"></rect>
      </svg>
    ),
  },
  {
    to: '/live',
    label: 'Live',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="2"></circle>
        <path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14"></path>
      </svg>
    ),
  },
  {
    to: '/reports',
    label: 'Reports',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
        <line x1="16" y1="13" x2="8" y2="13"></line>
        <line x1="16" y1="17" x2="8" y2="17"></line>
        <line x1="10" y1="9" x2="8" y2="9"></line>
      </svg>
    ),
  },
  {
    to: '/monitor',
    label: 'Monitor',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2"></path>
      </svg>
    ),
  },
];

const ADMIN_ITEMS = [
  {
    to: '/entry',
    label: 'Entry',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path>
        <polyline points="10 17 15 12 10 7"></polyline>
        <line x1="15" y1="12" x2="3" y2="12"></line>
      </svg>
    ),
  },
  {
    to: '/exit',
    label: 'Exit',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
        <polyline points="16 17 21 12 16 7"></polyline>
        <line x1="21" y1="12" x2="9" y2="12"></line>
      </svg>
    ),
  },
];

const BOTTOM_ITEMS = [
  {
    to: '/audit',
    label: 'Audit',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
      </svg>
    ),
  },
  {
    to: '/settings',
    label: 'Settings',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3"></circle>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
      </svg>
    ),
  },
];

const Sidebar = () => {
  const { user, logout } = useAuth();
  const [hoveredItem, setHoveredItem] = useState(null);

  const navLinkStyle = ({ isActive }) => ({
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '10px 0',
    color: isActive ? '#2563eb' : '#64748b',
    textDecoration: 'none',
    borderLeft: isActive ? '2px solid #2563eb' : '2px solid transparent',
    backgroundColor: isActive ? '#eff6ff' : 'transparent',
    fontSize: '10px',
    fontWeight: isActive ? '700' : '500',
    gap: '5px',
    transition: 'all 0.15s ease',
    letterSpacing: '0.3px',
    position: 'relative',
  });

  const renderNavItem = (item, key) => (
    <NavLink
      key={key}
      to={item.to}
      end={item.exact}
      style={navLinkStyle}
      onMouseEnter={() => setHoveredItem(key)}
      onMouseLeave={() => setHoveredItem(null)}
    >
      {({ isActive }) => (
        <>
          <div style={{
            color: isActive ? '#2563eb' : hoveredItem === key ? '#475569' : '#64748b',
            transition: 'color 0.15s',
          }}>
            {item.icon}
          </div>
          <span style={{ textAlign: 'center', lineHeight: 1.2 }}>{item.label}</span>
        </>
      )}
    </NavLink>
  );

  return (
    <aside style={{
      width: '80px',
      backgroundColor: '#ffffff',
      borderRight: '1px solid #e2e8f0',
      display: 'flex',
      flexDirection: 'column',
      boxShadow: '1px 0 0 #e2e8f0',
      zIndex: 10,
      flexShrink: 0,
    }}>
      
      {/* Main Nav */}
      <nav style={{ display: 'flex', flexDirection: 'column', marginTop: '16px', flex: 1, overflowY: 'auto' }}>
        {NAV_ITEMS.map((item, i) => renderNavItem(item, `main-${i}`))}

        <div style={{ height: '1px', backgroundColor: '#f1f5f9', margin: '8px 16px' }}></div>

        {/* Admin section label */}
        <div style={{ textAlign: 'center', fontSize: '8px', fontWeight: '700', color: '#94a3b8', letterSpacing: '1px', padding: '4px 0', textTransform: 'uppercase' }}>
          ADMIN
        </div>

        {ADMIN_ITEMS.map((item, i) => renderNavItem(item, `admin-${i}`))}

        <div style={{ height: '1px', backgroundColor: '#f1f5f9', margin: '8px 16px' }}></div>

        {BOTTOM_ITEMS.map((item, i) => renderNavItem(item, `bottom-${i}`))}
      </nav>

      {/* User Profile & Logout */}
      <div style={{
        padding: '12px 0 16px',
        borderTop: '1px solid #f1f5f9',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '10px',
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '3px' }}>
          <div style={{
            width: '30px', height: '30px', borderRadius: '50%',
            background: 'linear-gradient(135deg, #1e40af 0%, #3b82f6 100%)',
            color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: '800', fontSize: '13px', letterSpacing: '-0.5px',
          }}>
            {user?.name ? user.name.charAt(0).toUpperCase() : 'A'}
          </div>
          <span style={{ fontSize: '9px', color: '#64748b', fontWeight: '600', textAlign: 'center', padding: '0 4px', letterSpacing: '0.2px' }}>
            {(user?.name || 'Admin').split(' ')[0]}
          </span>
        </div>
        <button
          onClick={logout}
          title="Sign Out"
          style={{
            background: 'none', border: 'none',
            color: '#94a3b8', cursor: 'pointer',
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '3px',
            fontSize: '9px', fontWeight: '600', padding: '4px',
            borderRadius: '6px', transition: 'all 0.15s',
            letterSpacing: '0.3px',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = '#ef4444'; e.currentTarget.style.background = '#fef2f2'; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = '#94a3b8'; e.currentTarget.style.background = 'none'; }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
            <polyline points="16 17 21 12 16 7"></polyline>
            <line x1="21" y1="12" x2="9" y2="12"></line>
          </svg>
          Logout
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
