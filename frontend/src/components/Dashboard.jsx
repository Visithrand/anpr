import React, { useEffect, useState, useMemo } from 'react';
import { getDashboard, recordExit } from '../services/api';

const Dashboard = () => {
  const [data, setData] = useState({
    vehicles_inside: 0,
    total_revenue: 0,
    total_entries_today: 0,
    total_exits_today: 0,
    avg_stay_minutes: 0,
    active_vehicles: [],
    recent_activity: [],
  });

  const [searchQuery, setSearchQuery] = useState('');
  const [sortOrder, setSortOrder] = useState('newest'); // 'newest' | 'oldest'

  const [selectedVehicle, setSelectedVehicle] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  const calculateDuration = (entryTime) => {
    if (!entryTime) return 0;
    const entry = new Date(entryTime + (entryTime.endsWith('Z') ? '' : 'Z'));
    const now = new Date();
    const diffMs = now - entry;
    return Math.max(0, Math.floor(diffMs / 60000));
  };

  const handleRowClick = (v) => {
    setSelectedVehicle(v);
    setIsModalOpen(true);
  };

  const handleForceExit = async (bypassPayment, triggerGate) => {
    if (!selectedVehicle) return;
    setIsProcessing(true);
    try {
      const res = await recordExit(selectedVehicle.plate_number, bypassPayment, triggerGate);
      alert(res.message || "Action processed successfully!");
      setIsModalOpen(false);
      fetchDashboard();
    } catch (e) {
      const errorDetail = e.response?.data?.detail;
      const errorMsg = typeof errorDetail === 'object' 
        ? (errorDetail.message || errorDetail.reason || JSON.stringify(errorDetail)) 
        : (errorDetail || e.message);
      alert(`Override failed: ${errorMsg}`);
    }
    setIsProcessing(false);
  };

  useEffect(() => {
    fetchDashboard();

    const isDev = import.meta.env.DEV;
    const wsUrl = isDev 
      ? 'ws://127.0.0.1:8000/ws/dashboard' 
      : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/dashboard`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'REFRESH_DASHBOARD') {
        fetchDashboard();
      }
    };
    ws.onerror = () => console.warn('WS error, falling back to polling');

    const interval = setInterval(fetchDashboard, 30000);

    return () => {
      ws.close();
      clearInterval(interval);
    };
  }, []);

  const fetchDashboard = async () => {
    try {
      const result = await getDashboard();
      setData(result);
    } catch (error) {
      console.error('Error fetching dashboard:', error);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    const date = new Date(dateString + (dateString.endsWith('Z') ? '' : 'Z'));
    return new Intl.DateTimeFormat('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(date);
  };

  const fmtActivity = (ts) => {
    if (!ts) return '-';
    const d = new Date(ts + (ts.endsWith?.('Z') ? '' : 'Z'));
    const now = new Date();
    const diffMs = now - d;
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHrs = Math.floor(diffMins / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    return formatDate(ts);
  };

  const kpiCards = [
    {
      title: 'Vehicles Inside',
      value: data.vehicles_inside,
      iconBg: '#eff6ff',
      iconColor: '#3b82f6',
      icon: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>,
    },
    {
      title: 'Entries Today',
      value: data.total_entries_today,
      iconBg: '#eef2ff',
      iconColor: '#6366f1',
      icon: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path><polyline points="10 17 15 12 10 7"></polyline><line x1="15" y1="12" x2="3" y2="12"></line></svg>,
    },
    {
      title: 'Exits Today',
      value: data.total_exits_today,
      iconBg: '#fffbeb',
      iconColor: '#f59e0b',
      icon: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>,
    },
  ];

  const filteredVehicles = useMemo(() => {
    let result = [...(data.active_vehicles || [])];
    
    if (searchQuery) {
      result = result.filter(v => v.plate_number.toLowerCase().includes(searchQuery.toLowerCase()));
    }
    
    result.sort((a, b) => {
      const tA = new Date(a.entry_time + (a.entry_time.endsWith('Z') ? '' : 'Z')).getTime();
      const tB = new Date(b.entry_time + (b.entry_time.endsWith('Z') ? '' : 'Z')).getTime();
      return sortOrder === 'newest' ? tB - tA : tA - tB;
    });

    return result;
  }, [data.active_vehicles, searchQuery, sortOrder]);

  const handleExport = () => {
    if (!filteredVehicles.length) return;
    const headers = ['Registration Number', 'Entry Time', 'Status'];
    const csvContent = [
      headers.join(','),
      ...filteredVehicles.map(v => `"${v.plate_number}","${formatDate(v.entry_time)}","PARKED"`)
    ].join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `active_vehicles_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ padding: '32px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>
          </div>
          <h2 style={{ color: '#0f172a', margin: 0, fontSize: '28px', fontWeight: '800', letterSpacing: '-0.5px' }}>
            Operations Overview
          </h2>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', padding: '6px 12px', borderRadius: '8px', color: '#475569', fontSize: '12px', fontWeight: '500' }}>
            Avg Stay: <strong style={{ color: '#0f172a' }}>{data.avg_stay_minutes || 0} min</strong>
          </div>
          <button onClick={fetchDashboard} style={{ background: '#ffffff', border: '1px solid #cbd5e1', padding: '8px 16px', borderRadius: '8px', color: '#475569', fontWeight: '600', fontSize: '13px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
            Refresh
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px', marginBottom: '28px' }}>
        {kpiCards.map((card, i) => (
          <div key={i} style={{ background: '#ffffff', padding: '24px', borderRadius: '16px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)', display: 'flex', alignItems: 'center', gap: '20px', transition: 'transform 0.15s, box-shadow 0.15s' }}>
            <div style={{ width: '56px', height: '56px', borderRadius: '12px', background: card.iconBg, color: card.iconColor, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              {card.icon}
            </div>
            <div>
              <div style={{ color: '#64748b', fontSize: '12px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '4px' }}>{card.title}</div>
              <div style={{ color: '#0f172a', fontSize: '28px', fontWeight: '800', lineHeight: '1' }}>{card.value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Bottom Grid: Active Vehicles + Activity Feed */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
        
        {/* Active Vehicles */}
        <div style={{ background: '#ffffff', borderRadius: '16px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)', overflow: 'hidden' }}>
          <div style={{ padding: '16px 24px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <h3 style={{ margin: 0, color: '#0f172a', fontSize: '16px', fontWeight: '700' }}>Active Parked Vehicles</h3>
              <span style={{ background: '#f1f5f9', color: '#475569', padding: '2px 10px', borderRadius: '20px', fontSize: '12px', fontWeight: '600' }}>{filteredVehicles.length}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input 
                type="text" 
                placeholder="Search plate..." 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ padding: '6px 12px', border: '1px solid #e2e8f0', borderRadius: '6px', fontSize: '13px', outline: 'none', width: '140px' }}
              />
              <select 
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)}
                style={{ padding: '6px 10px', border: '1px solid #e2e8f0', borderRadius: '6px', fontSize: '13px', outline: 'none', background: '#fff', cursor: 'pointer' }}
              >
                <option value="newest">Newest First</option>
                <option value="oldest">Oldest First</option>
              </select>
              <button 
                onClick={handleExport}
                style={{ padding: '6px 12px', border: '1px solid #e2e8f0', borderRadius: '6px', fontSize: '13px', background: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', color: '#0f172a', fontWeight: '500' }}
                title="Export to CSV"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                Export
              </button>
            </div>
          </div>
          <div style={{ overflowX: 'auto', maxHeight: '320px', overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead style={{ background: '#f8fafc', position: 'sticky', top: 0, zIndex: 1 }}>
                <tr>
                  <th style={{ padding: '14px 24px', color: '#64748b', fontWeight: '600', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', width: '60px' }}>S.No.</th>
                  <th style={{ padding: '14px 24px', color: '#64748b', fontWeight: '600', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Registration No.</th>
                  <th style={{ padding: '14px 24px', color: '#64748b', fontWeight: '600', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Entry Time</th>
                  <th style={{ padding: '14px 24px', color: '#64748b', fontWeight: '600', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', textAlign: 'right' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredVehicles.length === 0 ? (
                  <tr>
                    <td colSpan="4" style={{ padding: '48px', textAlign: 'center', color: '#94a3b8' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
                        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                        <span style={{ fontSize: '14px' }}>No active vehicles found.</span>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredVehicles.map((v, index) => (
                    <tr 
                      key={index} 
                      onClick={() => handleRowClick(v)}
                      style={{ 
                        borderBottom: '1px solid #f1f5f9',
                        cursor: 'pointer',
                        transition: 'background-color 0.15s ease'
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f8fafc'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                    >
                      <td style={{ padding: '14px 24px', color: '#64748b', fontSize: '13px', fontWeight: '500' }}>{String(index + 1).padStart(2, '0')}</td>
                      <td style={{ padding: '14px 24px', fontWeight: '700', color: '#0f172a', fontSize: '14px' }}>{v.plate_number}</td>
                      <td style={{ padding: '14px 24px', color: '#475569', fontSize: '13px' }}>
                        <span style={{ fontWeight: '500', color: '#0f172a' }}>{formatDate(v.entry_time).split(',')[0]}</span>
                        <span style={{ marginLeft: '6px', color: '#64748b' }}>{formatDate(v.entry_time).split(',')[1]}</span>
                      </td>
                      <td style={{ padding: '14px 24px', textAlign: 'right' }}>
                        <span style={{ background: '#ecfdf5', color: '#059669', padding: '4px 10px', borderRadius: '6px', fontSize: '11px', fontWeight: '700', letterSpacing: '0.5px' }}>PARKED</span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Activity Feed */}
        <div style={{ background: '#ffffff', borderRadius: '16px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)', overflow: 'hidden' }}>
          <div style={{ padding: '20px 24px', borderBottom: '1px solid #e2e8f0' }}>
            <h3 style={{ margin: 0, color: '#0f172a', fontSize: '16px', fontWeight: '700' }}>Activity Feed</h3>
          </div>
          <div style={{ overflowY: 'auto', maxHeight: '320px' }}>
            {(!data.recent_activity || data.recent_activity.length === 0) ? (
              <div style={{ padding: '48px 24px', textAlign: 'center', color: '#94a3b8' }}>
                <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" style={{ margin: '0 auto 10px' }}><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                <p style={{ fontSize: '14px' }}>No recent activity.</p>
              </div>
            ) : (
              data.recent_activity.map((item, i) => {
                const isEntry = (item.action || '').toUpperCase().includes('ENTRY');
                return (
                  <div key={i} style={{ padding: '14px 24px', borderBottom: '1px solid #f1f5f9', display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                    <div style={{
                      width: '8px', height: '8px', borderRadius: '50%', marginTop: '6px', flexShrink: 0,
                      background: isEntry ? '#10b981' : '#ef4444',
                    }}></div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '13px', fontWeight: '600', color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {item.plate_number}
                        <span style={{ fontWeight: '400', color: '#64748b', marginLeft: '6px' }}>— {item.action}</span>
                      </div>
                      <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>{fmtActivity(item.timestamp)}</div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
      {/* Administrative Override Modal */}
      {isModalOpen && selectedVehicle && (
        <>
          {/* Backdrop */}
          <div 
            onClick={() => setIsModalOpen(false)} 
            style={{ 
              position: 'fixed', inset: 0, background: 'rgba(15, 23, 42, 0.4)', 
              backdropFilter: 'blur(4px)', zIndex: 1000, 
              animation: 'fadeIn 0.2s ease-out' 
            }}
          />
          
          {/* Modal Content */}
          <div style={{ 
            position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
            width: '90vw', maxWidth: '540px', background: '#ffffff', borderRadius: '16px', 
            zIndex: 1001, boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.15)',
            display: 'flex', flexDirection: 'column', overflow: 'hidden',
            border: '1px solid #e2e8f0', animation: 'modalIn 0.25s ease-out'
          }}>
            {/* Header */}
            <div style={{ padding: '20px 24px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f8fafc' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: '#ef4444', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white' }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                </div>
                <h3 style={{ margin: 0, color: '#0f172a', fontSize: '16px', fontWeight: '700' }}>Admin Vehicle Override</h3>
              </div>
              <button 
                onClick={() => setIsModalOpen(false)} 
                style={{ background: '#f1f5f9', border: 'none', borderRadius: '6px', width: '30px', height: '30px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#64748b' }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
              </button>
            </div>

            {/* Body */}
            <div style={{ padding: '24px' }}>
              <div style={{ background: '#f8fafc', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '16px', marginBottom: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                  <span style={{ color: '#64748b', fontSize: '13px', fontWeight: '500' }}>Registration Number</span>
                  <span style={{ color: '#0f172a', fontSize: '15px', fontWeight: '700', letterSpacing: '1px' }}>{selectedVehicle.plate_number}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                  <span style={{ color: '#64748b', fontSize: '13px', fontWeight: '500' }}>Entry Time</span>
                  <span style={{ color: '#334155', fontSize: '13px', fontWeight: '600' }}>{formatDate(selectedVehicle.entry_time)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#64748b', fontSize: '13px', fontWeight: '500' }}>Duration Inside</span>
                  <span style={{ color: '#ef4444', fontSize: '13px', fontWeight: '700' }}>{calculateDuration(selectedVehicle.entry_time)} mins</span>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <button 
                  onClick={() => handleForceExit(true, true)}
                  disabled={isProcessing}
                  style={{ 
                    padding: '12px', background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)', 
                    color: 'white', border: 'none', borderRadius: '8px', cursor: isProcessing ? 'default' : 'pointer', 
                    fontWeight: '700', fontSize: '13px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                    boxShadow: '0 4px 6px -1px rgba(239, 68, 68, 0.25)', opacity: isProcessing ? 0.6 : 1
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
                  Force Exit (Open Barrier & Mark OUT)
                </button>

                <button 
                  onClick={() => handleForceExit(true, false)}
                  disabled={isProcessing}
                  style={{ 
                    padding: '12px', background: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', 
                    borderRadius: '8px', cursor: isProcessing ? 'default' : 'pointer', 
                    fontWeight: '700', fontSize: '13px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                    opacity: isProcessing ? 0.6 : 1
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                  Purge Active Status (Mark OUT Only, No Gate)
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      <style>
        {`
          @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
          }
          @keyframes modalIn {
            from { opacity: 0; transform: translate(-50%, -48%); }
            to { opacity: 1; transform: translate(-50%, -50%); }
          }
        `}
      </style>
    </div>
  );
};

export default Dashboard;
