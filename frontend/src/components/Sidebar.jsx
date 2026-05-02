import React from 'react';
import { NavLink } from 'react-router-dom';

const Sidebar = () => {
  return (
    <aside>
      <div className="sidebar-box" style={{ marginBottom: '0' }}>
        <div className="sidebar-box-header green">
          ^ Navigation Links
        </div>
        <div className="sidebar-box-content" style={{ padding: '0' }}>
          <ul className="sidebar-menu">
            <li><NavLink to="/" end>Dashboard</NavLink></li>
            <li><NavLink to="/entry">Manual Entry</NavLink></li>
            <li><NavLink to="/exit">Manual Exit</NavLink></li>
          </ul>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
