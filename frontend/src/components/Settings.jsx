import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';

const IS_DEV = import.meta.env.DEV;
const API_URL = IS_DEV ? 'http://127.0.0.1:8000' : `${window.location.origin}/api`;

const Settings = () => {
  const { user, token } = useAuth();
  const [newEmail, setNewEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newName, setNewName] = useState('');
  const [regMsg, setRegMsg] = useState('');
  const [regErr, setRegErr] = useState('');
  const [regLoading, setRegLoading] = useState(false);

  const handleRegister = async (e) => {
    e.preventDefault();
    if (!newEmail || !newPassword) { setRegErr('Email and password are required.'); return; }
    setRegLoading(true);
    setRegMsg('');
    setRegErr('');
    try {
      const res = await axios.post(`${API_URL}/auth/register`, {
        email: newEmail,
        password: newPassword,
        name: newName || 'Admin',
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setRegMsg(`Admin "${res.data.name}" (${res.data.email}) registered successfully.`);
      setNewEmail('');
      setNewPassword('');
      setNewName('');
    } catch (err) {
      setRegErr(err.response?.data?.detail || 'Failed to register admin.');
    }
    setRegLoading(false);
  };

  const inputStyle = {
    width: '100%', padding: '12px 14px', background: '#f8fafc',
    border: '1px solid #e2e8f0', borderRadius: '8px', color: '#0f172a',
    fontSize: '14px', outline: 'none', boxSizing: 'border-box',
  };

  const labelStyle = {
    color: '#475569', fontSize: '12px', fontWeight: '600', textTransform: 'uppercase',
    letterSpacing: '0.5px', display: 'block', marginBottom: '6px',
  };

  return (
    <div style={{ padding: '32px', maxWidth: '900px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '32px' }}>
        <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'linear-gradient(135deg, #64748b 0%, #475569 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white' }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
        </div>
        <h2 style={{ color: '#0f172a', margin: 0, fontSize: '28px', fontWeight: '800', letterSpacing: '-0.5px' }}>Settings</h2>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>

        {/* Admin Profile Card */}
        <div style={{ background: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)', overflow: 'hidden' }}>
          <div style={{ padding: '20px 24px', borderBottom: '1px solid #e2e8f0', background: '#f8fafc' }}>
            <h3 style={{ margin: 0, color: '#0f172a', fontSize: '16px', fontWeight: '700' }}>Admin Profile</h3>
          </div>
          <div style={{ padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
              <div style={{ width: '60px', height: '60px', borderRadius: '50%', background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '24px', fontWeight: '700' }}>
                {(user?.name || 'A').charAt(0).toUpperCase()}
              </div>
              <div>
                <div style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>{user?.name || 'Admin'}</div>
                <div style={{ fontSize: '13px', color: '#64748b' }}>{user?.email || '-'}</div>
                <span style={{ background: '#eff6ff', color: '#3b82f6', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '600', marginTop: '4px', display: 'inline-block' }}>{user?.role || 'admin'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* System Info Card */}
        <div style={{ background: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)', overflow: 'hidden' }}>
          <div style={{ padding: '20px 24px', borderBottom: '1px solid #e2e8f0', background: '#f8fafc' }}>
            <h3 style={{ margin: 0, color: '#0f172a', fontSize: '16px', fontWeight: '700' }}>System Information</h3>
          </div>
          <div style={{ padding: '24px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {[
                { label: 'API Endpoint', value: API_URL },
                { label: 'Version', value: 'ANPR.OS v2.0' },
                { label: 'Architecture', value: 'FastAPI + React + PostgreSQL + Redis' },
              ].map((item, idx) => (
                <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: idx < 2 ? '1px solid #f1f5f9' : 'none' }}>
                  <span style={{ color: '#64748b', fontSize: '13px', fontWeight: '500' }}>{item.label}</span>
                  <span style={{ color: '#0f172a', fontSize: '13px', fontWeight: '600', fontFamily: 'monospace' }}>{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Register New Admin */}
      <div style={{ background: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)', overflow: 'hidden', marginTop: '24px' }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #e2e8f0', background: '#f8fafc' }}>
          <h3 style={{ margin: 0, color: '#0f172a', fontSize: '16px', fontWeight: '700' }}>Register New Admin</h3>
          <p style={{ margin: '4px 0 0', color: '#64748b', fontSize: '13px' }}>Only existing authenticated admins can register new administrators.</p>
        </div>
        <form onSubmit={handleRegister} style={{ padding: '24px', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px', alignItems: 'end' }}>
          <div>
            <label style={labelStyle}>Full Name</label>
            <input type="text" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="John Doe" style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>Email Address</label>
            <input type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} placeholder="new.admin@anpr.os" style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>Password</label>
            <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="Min 6 characters" style={inputStyle} />
          </div>
          <div style={{ gridColumn: '1 / -1', display: 'flex', alignItems: 'center', gap: '16px' }}>
            <button type="submit" disabled={regLoading} style={{
              padding: '12px 24px', background: regLoading ? '#94a3b8' : '#0f172a', color: 'white',
              border: 'none', borderRadius: '8px', fontWeight: '600', fontSize: '14px',
              cursor: regLoading ? 'default' : 'pointer', boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
            }}>
              {regLoading ? 'Registering...' : 'Register Admin'}
            </button>
            {regMsg && <span style={{ color: '#059669', fontSize: '13px', fontWeight: '500' }}>{regMsg}</span>}
            {regErr && <span style={{ color: '#dc2626', fontSize: '13px', fontWeight: '500' }}>{regErr}</span>}
          </div>
        </form>
      </div>
    </div>
  );
};

export default Settings;
