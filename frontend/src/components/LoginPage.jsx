import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

const LoginPage = () => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!email || !password) {
      setError('Please enter both email and password.');
      return;
    }
    setIsLoading(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(err.response?.data?.detail || 'Authentication failed. Please try again.');
    }
    setIsLoading(false);
  };

  const inputStyle = {
    width: '100%',
    padding: '12px 16px',
    background: '#ffffff',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    color: '#111827',
    fontSize: '16px',
    outline: 'none',
    boxSizing: 'border-box',
    transition: 'border-color 0.2s, box-shadow 0.2s',
    fontFamily: "'Inter', sans-serif",
  };

  const labelStyle = {
    color: '#374151',
    fontSize: '14px',
    fontWeight: '500',
    display: 'block',
    marginBottom: '8px',
  };

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      width: '100vw',
      background: '#ffffff',
      fontFamily: "'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif",
      position: 'relative',
    }}>
      
      {/* Top Left Branding Header with Copyright */}
      <div style={{
        position: 'absolute',
        top: '28px',
        left: '28px',
        zIndex: 100,
        pointerEvents: 'none',
      }}>
        <div style={{
          fontWeight: '800',
          fontSize: '18px',
          color: '#ffffff',
          letterSpacing: '-0.3px',
          lineHeight: '1.2',
        }}>
          EYROVIZ <span style={{ color: '#94a3b8', fontWeight: '400' }}>TECHNOLOGIES</span>
        </div>
        <div style={{
          fontSize: '9px',
          color: '#64748b',
          fontWeight: '600',
          marginTop: '2px',
          letterSpacing: '0.5px',
          textTransform: 'uppercase',
        }}>
          © EYROVIZ · All Rights Reserved
        </div>
      </div>

      {/* Left Panel - EYROVIZ Brand Showcase */}
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)',
        padding: '60px 40px',
        overflow: 'hidden',
        position: 'relative',
      }}>
        {/* Animated background glow */}
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', width: '400px', height: '400px', borderRadius: '50%', background: 'radial-gradient(circle, rgba(59,130,246,0.08) 0%, transparent 70%)', animation: 'pulseGlow 4s ease-in-out infinite' }} />
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', width: '300px', height: '300px', borderRadius: '50%', border: '1px solid rgba(59,130,246,0.1)', animation: 'ringExpand 6s ease-in-out infinite' }} />
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', width: '220px', height: '220px', borderRadius: '50%', border: '1px solid rgba(59,130,246,0.06)', animation: 'ringExpand 6s ease-in-out infinite 1s' }} />

        <div style={{ textAlign: 'center', position: 'relative', zIndex: 2, maxWidth: '420px' }}>
          {/* Logo Mark */}
          <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '80px', height: '80px', borderRadius: '20px', background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)', boxShadow: '0 20px 40px rgba(59,130,246,0.3)', marginBottom: '32px' }}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
              <circle cx="12" cy="12" r="3"/>
            </svg>
          </div>

          {/* Brand Name */}
          <h1 style={{ color: '#ffffff', fontSize: '42px', fontWeight: '900', letterSpacing: '-1px', margin: '0 0 4px', lineHeight: '1' }}>
            EYROVIZ
          </h1>
          <div style={{ color: '#64748b', fontSize: '13px', fontWeight: '600', letterSpacing: '6px', textTransform: 'uppercase', marginBottom: '28px' }}>
            TECHNOLOGIES
          </div>

          {/* Divider */}
          <div style={{ width: '48px', height: '2px', background: 'linear-gradient(90deg, transparent, #3b82f6, transparent)', margin: '0 auto 28px' }} />

          {/* Tagline */}
          <p style={{ color: '#94a3b8', fontSize: '16px', fontWeight: '400', lineHeight: '1.7', margin: '0 0 40px' }}>
            Intelligent Vehicle Surveillance<br />& Access Control Platform
          </p>

          {/* Feature Chips */}
          <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', flexWrap: 'wrap' }}>
            {['ANPR Engine', 'Multi-Camera', 'Real-Time OCR', 'Gate Control'].map((feat) => (
              <span key={feat} style={{
                padding: '6px 14px',
                borderRadius: '20px',
                border: '1px solid rgba(148,163,184,0.2)',
                color: '#94a3b8',
                fontSize: '11px',
                fontWeight: '600',
                letterSpacing: '0.5px',
                background: 'rgba(255,255,255,0.03)',
                backdropFilter: 'blur(4px)',
              }}>
                {feat}
              </span>
            ))}
          </div>

          {/* Copyright */}
          <div style={{ marginTop: '48px', color: '#475569', fontSize: '10px', fontWeight: '600', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
            © 2026 EYROVIZ · All Rights Reserved
          </div>
        </div>
      </div>

      {/* Right Panel - Login Form */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#ffffff',
        padding: '40px',
      }}>
        <div style={{ width: '100%', maxWidth: '400px' }}>
          
          <div style={{ textAlign: 'center', marginBottom: '40px' }}>
            <h1 style={{ fontSize: '32px', fontWeight: '700', color: '#111827', margin: '0 0 8px 0' }}>
              Welcome back
            </h1>
            <p style={{ color: '#6b7280', fontSize: '16px', margin: 0 }}>
              Sign in to the ANPR.OS Command Center
            </p>
          </div>

          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '24px' }}>
              <label style={labelStyle}>Email address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={inputStyle}
                placeholder="admin@anpr.os"
                onFocus={(e) => { e.target.style.borderColor = '#0f172a'; e.target.style.boxShadow = '0 0 0 3px rgba(15, 23, 42, 0.08)'; }}
                onBlur={(e) => { e.target.style.borderColor = '#d1d5db'; e.target.style.boxShadow = 'none'; }}
                required
              />
            </div>

            <div style={{ marginBottom: '32px' }}>
              <label style={labelStyle}>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={inputStyle}
                placeholder="••••••••"
                onFocus={(e) => { e.target.style.borderColor = '#0f172a'; e.target.style.boxShadow = '0 0 0 3px rgba(15, 23, 42, 0.08)'; }}
                onBlur={(e) => { e.target.style.borderColor = '#d1d5db'; e.target.style.boxShadow = 'none'; }}
                required
              />
            </div>

            {error && (
              <div style={{
                background: '#fef2f2', border: '1px solid #fecaca',
                borderRadius: '6px', padding: '12px 16px', marginBottom: '24px',
                color: '#b91c1c', fontSize: '14px',
                display: 'flex', alignItems: 'center', gap: '8px',
              }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="15" y1="9" x2="9" y2="15"></line>
                  <line x1="9" y1="9" x2="15" y2="15"></line>
                </svg>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              style={{
                width: '100%',
                padding: '12px',
                border: 'none',
                borderRadius: '6px',
                background: isLoading ? '#9ca3af' : '#0f172a',
                color: 'white',
                fontSize: '16px',
                fontWeight: '500',
                cursor: isLoading ? 'default' : 'pointer',
                transition: 'background-color 0.2s',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                fontFamily: "'Inter', sans-serif",
              }}
              onMouseOver={(e) => { if (!isLoading) e.currentTarget.style.backgroundColor = '#1e293b'; }}
              onMouseOut={(e) => { if (!isLoading) e.currentTarget.style.backgroundColor = '#0f172a'; }}
            >
              {isLoading ? (
                <>
                  <div style={{ width: '16px', height: '16px', border: '2px solid rgba(255,255,255,0.3)', borderTop: '2px solid white', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }}></div>
                  Signing in...
                </>
              ) : (
                'Continue'
              )}
            </button>
          </form>

          <p style={{ textAlign: 'center', color: '#9ca3af', fontSize: '12px', marginTop: '24px' }}>
            ANPR.OS v2.0 · Secured by JWT
          </p>
        </div>
      </div>

      <style>
        {`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
          @keyframes pulseGlow {
            0%, 100% { opacity: 0.4; transform: translate(-50%, -50%) scale(1); }
            50% { opacity: 1; transform: translate(-50%, -50%) scale(1.15); }
          }
          @keyframes ringExpand {
            0%, 100% { opacity: 0.3; transform: translate(-50%, -50%) scale(0.9); }
            50% { opacity: 0.8; transform: translate(-50%, -50%) scale(1.1); }
          }
        `}
      </style>
    </div>
  );
};

export default LoginPage;
