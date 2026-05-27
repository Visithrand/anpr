import React, { useEffect, useState, useMemo } from 'react';
import { getAuditLogs, clearAuditLogs } from '../services/api';

const AuditTrail = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [actionFilter, setActionFilter] = useState('ALL');
  const [sortOrder, setSortOrder] = useState('newest'); // 'newest' | 'oldest'

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await getAuditLogs(100);
      setLogs(data);
    } catch (err) {
      console.error('Failed to fetch audit logs:', err);
    }
    setLoading(false);
  };

  const handleClearLogs = async () => {
    if (window.confirm("WARNING: This will permanently delete all audit logs. Are you sure you want to proceed?")) {
      try {
        await clearAuditLogs();
        fetchLogs();
      } catch (err) {
        console.error('Failed to clear logs:', err);
        alert('Failed to clear logs. See console for details.');
      }
    }
  };

  const fmtDate = (ts) => {
    if (!ts) return '-';
    const d = new Date(ts + (ts.endsWith?.('Z') ? '' : 'Z'));
    return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const actionBadge = (action) => {
    const a = (action || '').toUpperCase();
    let bg, color, border;
    if (a.includes('ENTRY') || a.includes('REGISTER')) { bg = '#ecfdf5'; color = '#059669'; border = '#a7f3d0'; }
    else if (a.includes('EXIT') || a.includes('APPROVE')) { bg = '#fef2f2'; color = '#dc2626'; border = '#fecaca'; }
    else { bg = '#f8fafc'; color = '#64748b'; border = '#e2e8f0'; }
    return (
      <span style={{ background: bg, color, border: `1px solid ${border}`, padding: '4px 10px', borderRadius: '6px', fontSize: '11px', fontWeight: '700', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
        {action}
      </span>
    );
  };

  const filteredLogs = useMemo(() => {
    let result = [...logs];

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(log => 
        (log.plate_number || '').toLowerCase().includes(q) || 
        (log.operator || '').toLowerCase().includes(q) ||
        (log.details || '').toLowerCase().includes(q)
      );
    }

    if (actionFilter !== 'ALL') {
      result = result.filter(log => (log.action || '').toUpperCase().includes(actionFilter));
    }

    result.sort((a, b) => {
      const tA = new Date(a.timestamp + (a.timestamp.endsWith('Z') ? '' : 'Z')).getTime();
      const tB = new Date(b.timestamp + (b.timestamp.endsWith('Z') ? '' : 'Z')).getTime();
      return sortOrder === 'newest' ? tB - tA : tA - tB;
    });

    return result;
  }, [logs, searchQuery, actionFilter, sortOrder]);

  const handleExport = () => {
    if (!filteredLogs.length) return;
    const headers = ['ID', 'Action', 'Plate Number', 'Operator', 'Timestamp', 'Details'];
    const csvContent = [
      headers.join(','),
      ...filteredLogs.map(log => 
        `"${log.id}","${log.action}","${log.plate_number}","${log.operator}","${fmtDate(log.timestamp)}","${(log.details || '').replace(/"/g, '""')}"`
      )
    ].join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit_logs_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ padding: '32px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
          </div>
          <h2 style={{ color: '#0f172a', margin: 0, fontSize: '28px', fontWeight: '800', letterSpacing: '-0.5px' }}>Audit Trail</h2>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button onClick={handleClearLogs} style={{ background: '#fef2f2', border: '1px solid #fecaca', padding: '8px 16px', borderRadius: '8px', color: '#dc2626', fontWeight: '600', fontSize: '13px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            Clear Logs
          </button>
          <button onClick={fetchLogs} style={{ background: '#ffffff', border: '1px solid #cbd5e1', padding: '8px 16px', borderRadius: '8px', color: '#475569', fontWeight: '600', fontSize: '13px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
            Refresh
          </button>
        </div>
      </div>

      <div style={{ background: '#ffffff', borderRadius: '16px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)', overflow: 'hidden' }}>
        
        {/* Toolbar */}
        <div style={{ padding: '16px 24px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ color: '#475569', fontSize: '13px', fontWeight: '600' }}>Showing {filteredLogs.length} logs</span>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input 
              type="text" 
              placeholder="Search plate, operator..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ padding: '6px 12px', border: '1px solid #e2e8f0', borderRadius: '6px', fontSize: '13px', outline: 'none', width: '200px' }}
            />
            <select 
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              style={{ padding: '6px 10px', border: '1px solid #e2e8f0', borderRadius: '6px', fontSize: '13px', outline: 'none', background: '#fff', cursor: 'pointer' }}
            >
              <option value="ALL">All Actions</option>
              <option value="ENTRY">Entry</option>
              <option value="EXIT">Exit</option>
              <option value="REGISTER">Register</option>
              <option value="APPROVE">Approve</option>
            </select>
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

        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: '#64748b', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
            <div style={{ width: '40px', height: '40px', border: '3px solid #f1f5f9', borderTop: '3px solid #6366f1', borderRadius: '50%', animation: 'spin 1s linear infinite' }}></div>
            <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
            <span style={{ fontWeight: '500' }}>Loading audit logs...</span>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                <tr>
                  <th style={{ padding: '14px 20px', color: '#64748b', fontWeight: '600', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>ID</th>
                  <th style={{ padding: '14px 20px', color: '#64748b', fontWeight: '600', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Action</th>
                  <th style={{ padding: '14px 20px', color: '#64748b', fontWeight: '600', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Plate Number</th>
                  <th style={{ padding: '14px 20px', color: '#64748b', fontWeight: '600', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Operator</th>
                  <th style={{ padding: '14px 20px', color: '#64748b', fontWeight: '600', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Timestamp</th>
                  <th style={{ padding: '14px 20px', color: '#64748b', fontWeight: '600', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Details</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.length === 0 ? (
                  <tr>
                    <td colSpan="6" style={{ padding: '60px', textAlign: 'center', color: '#94a3b8' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                        <span style={{ fontSize: '15px' }}>No audit logs found matching criteria.</span>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredLogs.map((log) => (
                    <tr key={log.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '14px 20px', color: '#94a3b8', fontSize: '12px', fontFamily: 'monospace' }}>#{log.id}</td>
                      <td style={{ padding: '14px 20px' }}>{actionBadge(log.action)}</td>
                      <td style={{ padding: '14px 20px', fontWeight: '700', color: '#0f172a', fontSize: '14px' }}>{log.plate_number}</td>
                      <td style={{ padding: '14px 20px', color: '#475569', fontSize: '13px' }}>{log.operator}</td>
                      <td style={{ padding: '14px 20px', color: '#475569', fontSize: '13px' }}>{fmtDate(log.timestamp)}</td>
                      <td style={{ padding: '14px 20px', color: '#64748b', fontSize: '12px', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={log.details}>{log.details || '-'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default AuditTrail;
