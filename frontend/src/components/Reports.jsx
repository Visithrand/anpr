import React, { useEffect, useState, useCallback } from 'react';
import * as XLSX from 'xlsx';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

const IS_DEV = import.meta.env.DEV;
const API_URL = IS_DEV ? 'http://127.0.0.1:8000' : `${window.location.protocol}//${window.location.hostname}:8000`;

const Reports = () => {
  const [data, setData] = useState([]);
  const [summary, setSummary] = useState(null);
  const [timeframe, setTimeframe] = useState('today');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PAGE_SIZE = 50;

  const fetchReports = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const token = localStorage.getItem('anpr_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};

      // Fetch both data and summary in parallel
      const params = new URLSearchParams({
        timeframe,
        page,
        page_size: PAGE_SIZE,
        ...(statusFilter ? { status: statusFilter } : {}),
      });

      const [dataRes, summaryRes] = await Promise.all([
        fetch(`${API_URL}/reports?${params}`, { headers }),
        fetch(`${API_URL}/reports/summary?timeframe=${timeframe}`, { headers }),
      ]);

      if (!dataRes.ok) {
        const errText = await dataRes.text();
        throw new Error(`Reports API error ${dataRes.status}: ${errText}`);
      }
      if (!summaryRes.ok) {
        const errText = await summaryRes.text();
        throw new Error(`Summary API error ${summaryRes.status}: ${errText}`);
      }

      const dataJson = await dataRes.json();
      const summaryJson = await summaryRes.json();

      // Handle both old format (array) and new format (object with data key)
      if (Array.isArray(dataJson)) {
        setData(dataJson);
        setTotal(dataJson.length);
        setTotalPages(1);
      } else {
        setData(dataJson.data || []);
        setTotal(dataJson.total || 0);
        setTotalPages(dataJson.total_pages || 1);
      }
      setSummary(summaryJson);
    } catch (err) {
      setError(err.message || 'Failed to load report data. Check network or backend logs.');
      setData([]);
      setSummary(null);
    }
    setLoading(false);
  }, [timeframe, statusFilter, page]);

  useEffect(() => {
    setPage(1);
  }, [timeframe, statusFilter]);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const formatDate = (isoString) => {
    if (!isoString) return '-';
    const date = new Date(isoString.endsWith('Z') ? isoString : isoString + 'Z');
    return date.toLocaleString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  };

  const formatCurrency = (amount) => {
    if (amount == null || amount === '') return '-';
    return `₹${Number(amount).toFixed(2)}`;
  };

  const getFilename = () => {
    const now = new Date().toISOString().split('T')[0];
    const label = timeframe === 'today' ? 'Daily' : timeframe === 'week' ? 'Weekly' : 'Monthly';
    return `ANPR_${label}_Report_${now}`;
  };

  const exportToExcel = () => {
    if (data.length === 0) return;
    const rows = data.map((r) => ({
      'S.No': r.sno,
      'Transaction ID': r.transaction_id,
      'Plate Number': r.plate_number,
      'Entry Time': formatDate(r.entry_time),
      'Exit Time': formatDate(r.exit_time),
      'Duration': r.stayed,
      'Status': r.status,
      'Payment': r.payment_status,
      'Billing Amount': r.billing_amount != null ? r.billing_amount : '',
      'Location': r.location,
    }));
    const ws = XLSX.utils.json_to_sheet(rows);
    ws['!cols'] = [
      { wch: 6 }, { wch: 18 }, { wch: 16 }, { wch: 24 }, { wch: 24 },
      { wch: 12 }, { wch: 8 }, { wch: 10 }, { wch: 14 }, { wch: 16 },
    ];
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Report');
    XLSX.writeFile(wb, `${getFilename()}.xlsx`);
  };

  const exportToPDF = () => {
    if (data.length === 0) return;
    const doc = new jsPDF({ orientation: 'landscape' });

    doc.setFontSize(18);
    doc.setFont('helvetica', 'bold');
    doc.text('ANPR Vehicle Report', 14, 18);
    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(100);
    const label = timeframe === 'today' ? "Today's" : timeframe === 'week' ? '7-Day' : '30-Day';
    doc.text(`${label} Report  |  Generated: ${new Date().toLocaleString('en-IN')}`, 14, 26);
    doc.text(`Total Records: ${total}`, 14, 32);

    if (summary) {
      doc.text(
        `Entries: ${summary.total_entries}  |  Exits: ${summary.total_exits}  |  Inside: ${summary.currently_inside}  |  Revenue: ₹${summary.total_revenue}`,
        14, 38
      );
    }

    autoTable(doc, {
      startY: 44,
      head: [['S.No', 'Transaction ID', 'Plate', 'Entry Time', 'Exit Time', 'Duration', 'Status', 'Payment', 'Amount']],
      body: data.map((r) => [
        r.sno,
        r.transaction_id,
        r.plate_number,
        formatDate(r.entry_time),
        formatDate(r.exit_time),
        r.stayed,
        r.status,
        r.payment_status,
        r.billing_amount != null ? `₹${r.billing_amount}` : '-',
      ]),
      styles: { fontSize: 8, cellPadding: 3 },
      headStyles: { fillColor: [15, 23, 42], textColor: 255, fontStyle: 'bold' },
      alternateRowStyles: { fillColor: [248, 250, 252] },
      columnStyles: { 0: { cellWidth: 10 } },
    });

    const pageCount = doc.internal.getNumberOfPages();
    for (let i = 1; i <= pageCount; i++) {
      doc.setPage(i);
      doc.setFontSize(8);
      doc.setTextColor(150);
      doc.text(
        `Page ${i} of ${pageCount}  |  ANPR.OS  |  Confidential`,
        doc.internal.pageSize.getWidth() / 2,
        doc.internal.pageSize.getHeight() - 8,
        { align: 'center' }
      );
    }
    doc.save(`${getFilename()}.pdf`);
  };

  const exportToCSV = () => {
    const token = localStorage.getItem('anpr_token');
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    fetch(`${API_URL}/reports/export?timeframe=${timeframe}`, { headers })
      .then((res) => {
        if (!res.ok) throw new Error('CSV export failed');
        return res.blob();
      })
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${getFilename()}.csv`;
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch((err) => setError(err.message));
  };

  const statCard = (label, value, color, icon) => (
    <div style={{
      background: '#ffffff', borderRadius: '10px', border: '1px solid #e2e8f0',
      padding: '16px 20px', display: 'flex', alignItems: 'center', gap: '12px',
      boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
    }}>
      <div style={{
        width: '36px', height: '36px', borderRadius: '8px',
        background: `${color}15`, display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '18px', flexShrink: 0,
      }}>{icon}</div>
      <div>
        <div style={{ fontSize: '11px', color: '#64748b', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</div>
        <div style={{ fontSize: '22px', fontWeight: '800', color: color, lineHeight: '1.2', marginTop: '2px' }}>{value}</div>
      </div>
    </div>
  );

  return (
    <div style={{ padding: '28px', maxWidth: '1300px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>
          </div>
          <div>
            <h2 style={{ color: '#0f172a', margin: 0, fontSize: '24px', fontWeight: '800', letterSpacing: '-0.5px' }}>Vehicle Analytics & Reports</h2>
            {total > 0 && <div style={{ color: '#64748b', fontSize: '13px', marginTop: '2px' }}>{total} record{total !== 1 ? 's' : ''} found</div>}
          </div>
        </div>

        {/* Export Buttons */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {[
            { label: 'Export CSV', color: '#2563eb', action: exportToCSV },
            { label: 'Export Excel', color: '#16a34a', action: exportToExcel },
            { label: 'Export PDF', color: '#dc2626', action: exportToPDF },
          ].map(({ label, color, action }) => (
            <button
              key={label}
              onClick={action}
              disabled={data.length === 0}
              style={{
                padding: '9px 16px', borderRadius: '8px', border: `1px solid ${color}`,
                background: '#ffffff', color: color,
                cursor: data.length === 0 ? 'not-allowed' : 'pointer',
                fontWeight: '600', fontSize: '13px',
                opacity: data.length === 0 ? 0.4 : 1,
                transition: 'all 0.15s',
              }}
            >
              ↓ {label}
            </button>
          ))}
          <button
            onClick={fetchReports}
            style={{
              padding: '9px 16px', borderRadius: '8px', border: '1px solid #e2e8f0',
              background: '#f8fafc', color: '#475569',
              cursor: 'pointer', fontWeight: '600', fontSize: '13px',
            }}
          >
            ↻ Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', flexWrap: 'wrap', alignItems: 'center' }}>
        {[
          { key: 'today', label: "Today" },
          { key: 'week', label: "Last 7 Days" },
          { key: 'month', label: "Last 30 Days" },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTimeframe(key)}
            style={{
              padding: '9px 18px', borderRadius: '8px',
              border: timeframe === key ? 'none' : '1px solid #cbd5e1',
              background: timeframe === key ? '#0f172a' : '#ffffff',
              color: timeframe === key ? '#ffffff' : '#475569',
              cursor: 'pointer', fontWeight: '600', fontSize: '13px',
              boxShadow: timeframe === key ? '0 4px 6px -1px rgba(0,0,0,0.1)' : '0 1px 2px rgba(0,0,0,0.05)',
              transition: 'all 0.2s ease',
            }}
          >{label}</button>
        ))}

        <div style={{ marginLeft: '8px', display: 'flex', gap: '8px' }}>
          {[
            { key: '', label: 'All Status' },
            { key: 'IN', label: '🟢 Inside' },
            { key: 'OUT', label: '⚫ Exited' },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setStatusFilter(key)}
              style={{
                padding: '7px 14px', borderRadius: '6px',
                border: statusFilter === key ? '2px solid #3b82f6' : '1px solid #e2e8f0',
                background: statusFilter === key ? '#eff6ff' : '#ffffff',
                color: statusFilter === key ? '#2563eb' : '#64748b',
                cursor: 'pointer', fontWeight: '600', fontSize: '12px',
                transition: 'all 0.15s',
              }}
            >{label}</button>
          ))}
        </div>
      </div>

      {/* Summary Stats */}
      {summary && !loading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginBottom: '24px' }}>
          {statCard('Total Entries', summary.total_entries, '#2563eb', '🚗')}
          {statCard('Total Exits', summary.total_exits, '#059669', '✅')}
          {statCard('Currently Inside', summary.currently_inside, '#d97706', '🏠')}
          {statCard('Revenue', `₹${summary.total_revenue}`, '#7c3aed', '💰')}
          {statCard('Avg Stay', `${summary.avg_stay_minutes}m`, '#0891b2', '⏱️')}
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div style={{
          background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px',
          padding: '14px 16px', marginBottom: '16px',
          color: '#dc2626', fontSize: '13px', fontWeight: '500',
          display: 'flex', alignItems: 'center', gap: '8px',
        }}>
          <span style={{ fontSize: '16px' }}>⚠️</span>
          <span>{error}</span>
          <button onClick={fetchReports} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: '#dc2626', cursor: 'pointer', fontWeight: '700', fontSize: '13px' }}>Retry</button>
        </div>
      )}

      {/* Table */}
      <div style={{ background: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: '#64748b', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
            <div style={{ width: '40px', height: '40px', border: '3px solid #f1f5f9', borderTop: '3px solid #3b82f6', borderRadius: '50%', animation: 'spin 1s linear infinite' }}></div>
            <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
            <span style={{ fontWeight: '500' }}>Loading Report Data...</span>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0' }}>
                <tr>
                  {['#', 'Transaction ID', 'Plate Number', 'Vehicle', 'Plate', 'Entry Time', 'Exit Time', 'Duration', 'Status', 'Payment', 'Amount'].map(col => (
                    <th key={col} style={{ padding: '14px 18px', color: '#475569', fontWeight: '700', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', whiteSpace: 'nowrap' }}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.length === 0 ? (
                  <tr>
                    <td colSpan="11" style={{ padding: '60px', textAlign: 'center', color: '#94a3b8' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                        <div style={{ fontSize: '40px' }}>📋</div>
                        <span style={{ fontSize: '15px', fontWeight: '500' }}>No records found for this period.</span>
                        <span style={{ fontSize: '13px' }}>Records will appear here once vehicles are detected and registered.</span>
                      </div>
                    </td>
                  </tr>
                ) : (
                  data.map((row, index) => (
                    <tr
                      key={row.transaction_id || index}
                      style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s' }}
                      onMouseEnter={e => e.currentTarget.style.background = '#f8fafc'}
                      onMouseLeave={e => e.currentTarget.style.background = ''}
                    >
                      <td style={{ padding: '14px 18px', color: '#94a3b8', fontSize: '12px', fontWeight: '600' }}>{row.sno}</td>
                      <td style={{ padding: '14px 18px', fontFamily: 'monospace', color: '#64748b', fontSize: '12px' }}>{row.transaction_id}</td>
                      <td style={{ padding: '14px 18px' }}>
                        <span style={{ fontWeight: '800', color: '#0f172a', fontSize: '15px', letterSpacing: '0.5px', background: '#f1f5f9', padding: '3px 8px', borderRadius: '4px' }}>
                          {row.plate_number}
                        </span>
                      </td>
                      <td style={{ padding: '14px 18px' }}>
                        {row.vehicle_image_path ? (
                          <img src={`${API_URL}${row.vehicle_image_path}`} alt="Vehicle" style={{ height: '32px', width: '56px', objectFit: 'cover', borderRadius: '4px', border: '1px solid #e2e8f0', cursor: 'pointer' }} onClick={() => window.open(`${API_URL}${row.vehicle_image_path}`, '_blank')} onError={e => e.target.style.display='none'} title="Click to enlarge" />
                        ) : <span style={{ color: '#cbd5e1', fontSize: '12px' }}>-</span>}
                      </td>
                      <td style={{ padding: '14px 18px' }}>
                        {row.plate_image_path ? (
                          <img src={`${API_URL}${row.plate_image_path}`} alt="Plate" style={{ height: '32px', width: '56px', objectFit: 'contain', borderRadius: '4px', border: '1px solid #e2e8f0', background: '#f8fafc', cursor: 'pointer' }} onClick={() => window.open(`${API_URL}${row.plate_image_path}`, '_blank')} onError={e => e.target.style.display='none'} title="Click to enlarge" />
                        ) : <span style={{ color: '#cbd5e1', fontSize: '12px' }}>-</span>}
                      </td>
                      <td style={{ padding: '14px 18px', color: '#475569', fontSize: '13px', whiteSpace: 'nowrap' }}>{formatDate(row.entry_time)}</td>
                      <td style={{ padding: '14px 18px', color: '#475569', fontSize: '13px', whiteSpace: 'nowrap' }}>{formatDate(row.exit_time)}</td>
                      <td style={{ padding: '14px 18px', fontWeight: '600', color: '#0f172a', fontSize: '13px' }}>{row.stayed}</td>
                      <td style={{ padding: '14px 18px' }}>
                        <span style={{
                          padding: '5px 10px', borderRadius: '6px', fontSize: '11px', fontWeight: '700', letterSpacing: '0.5px',
                          background: row.status === 'IN' ? '#ecfdf5' : '#f8fafc',
                          color: row.status === 'IN' ? '#059669' : '#64748b',
                          border: row.status === 'IN' ? '1px solid #a7f3d0' : '1px solid #e2e8f0',
                        }}>
                          {row.status}
                        </span>
                      </td>
                      <td style={{ padding: '14px 18px' }}>
                        <span style={{
                          padding: '4px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '600',
                          background: row.payment_status === 'PAID' ? '#eff6ff' : row.payment_status === 'PENDING' ? '#fffbeb' : '#fef2f2',
                          color: row.payment_status === 'PAID' ? '#2563eb' : row.payment_status === 'PENDING' ? '#d97706' : '#dc2626',
                        }}>
                          {row.payment_status || 'PENDING'}
                        </span>
                      </td>
                      <td style={{ padding: '14px 18px', fontWeight: '700', color: '#0f172a', fontSize: '13px' }}>
                        {formatCurrency(row.billing_amount)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={{ padding: '16px 20px', borderTop: '1px solid #f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ color: '#64748b', fontSize: '13px' }}>
              Page {page} of {totalPages} · {total} total records
            </span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                style={{ padding: '6px 14px', borderRadius: '6px', border: '1px solid #e2e8f0', background: page === 1 ? '#f8fafc' : '#fff', color: page === 1 ? '#94a3b8' : '#475569', cursor: page === 1 ? 'not-allowed' : 'pointer', fontWeight: '600', fontSize: '13px' }}>
                ← Prev
              </button>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                style={{ padding: '6px 14px', borderRadius: '6px', border: '1px solid #e2e8f0', background: page === totalPages ? '#f8fafc' : '#fff', color: page === totalPages ? '#94a3b8' : '#475569', cursor: page === totalPages ? 'not-allowed' : 'pointer', fontWeight: '600', fontSize: '13px' }}>
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Reports;
