import React, { useEffect, useState } from 'react';
import { getReports } from '../services/api';
import * as XLSX from 'xlsx';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

const Reports = () => {
  const [data, setData] = useState([]);
  const [timeframe, setTimeframe] = useState('today'); 
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchReports();
  }, [timeframe]);

  const fetchReports = async () => {
    setLoading(true);
    try {
      const result = await getReports(timeframe);
      setData(result);
    } catch (error) {
      console.error('Error fetching reports:', error);
    }
    setLoading(false);
  };

  const formatDate = (isoString) => {
    if (!isoString) return '-';
    const date = new Date(isoString + (isoString.endsWith('Z') ? '' : 'Z'));
    return date.toLocaleString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
  };

  const getFilename = () => {
    const now = new Date().toISOString().split('T')[0];
    const label = timeframe === 'today' ? 'Daily' : timeframe === 'week' ? 'Weekly' : 'Monthly';
    return `ANPR_${label}_Report_${now}`;
  };

  const exportToExcel = () => {
    if (data.length === 0) return;
    const rows = data.map((r, i) => ({
      'S.No': i + 1,
      'Transaction ID': r.transaction_id,
      'Plate Number': r.plate_number,
      'Entry Time': formatDate(r.entry_time),
      'Exit Time': formatDate(r.exit_time),
      'Status': r.status,
      'Duration Stayed': r.stayed,
    }));
    const ws = XLSX.utils.json_to_sheet(rows);
    ws['!cols'] = [
      { wch: 6 }, { wch: 18 }, { wch: 16 }, { wch: 24 }, { wch: 24 }, { wch: 8 }, { wch: 14 }
    ];
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Report');
    XLSX.writeFile(wb, `${getFilename()}.xlsx`);
  };

  const exportToPDF = () => {
    if (data.length === 0) return;
    const doc = new jsPDF({ orientation: 'landscape' });
    
    // Header
    doc.setFontSize(18);
    doc.setFont('helvetica', 'bold');
    doc.text('ANPR Vehicle Report', 14, 18);
    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(100);
    const label = timeframe === 'today' ? "Today's" : timeframe === 'week' ? '7-Day' : '30-Day';
    doc.text(`${label} Report  |  Generated: ${new Date().toLocaleString('en-IN')}`, 14, 26);
    doc.text(`Total Records: ${data.length}`, 14, 32);
    
    const rows = data.map((r, i) => [
      i + 1,
      r.transaction_id,
      r.plate_number,
      formatDate(r.entry_time),
      formatDate(r.exit_time),
      r.status,
      r.stayed,
    ]);

    autoTable(doc, {
      startY: 38,
      head: [['S.No', 'Transaction ID', 'Plate Number', 'Entry Time', 'Exit Time', 'Status', 'Duration']],
      body: rows,
      styles: { fontSize: 9, cellPadding: 4 },
      headStyles: { fillColor: [15, 23, 42], textColor: 255, fontStyle: 'bold' },
      alternateRowStyles: { fillColor: [248, 250, 252] },
      columnStyles: {
        0: { cellWidth: 12 },
        5: { fontStyle: 'bold' },
      },
    });

    // Footer
    const pageCount = doc.internal.getNumberOfPages();
    for (let i = 1; i <= pageCount; i++) {
      doc.setPage(i);
      doc.setFontSize(8);
      doc.setTextColor(150);
      doc.text(`Page ${i} of ${pageCount}  |  ANPR.OS  |  Confidential`, doc.internal.pageSize.getWidth() / 2, doc.internal.pageSize.getHeight() - 8, { align: 'center' });
    }

    doc.save(`${getFilename()}.pdf`);
  };

  return (
    <div style={{ padding: '32px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><line x1="10" y1="9" x2="8" y2="9"></line></svg>
          </div>
          <h2 style={{ color: '#0f172a', margin: 0, fontSize: '28px', fontWeight: '800', letterSpacing: '-0.5px' }}>
            Vehicle Analytics & Reports
          </h2>
        </div>

        {/* Download Buttons */}
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={exportToExcel}
            disabled={data.length === 0}
            style={{
              padding: '10px 18px', borderRadius: '8px', border: '1px solid #16a34a',
              background: '#ffffff', color: '#16a34a', cursor: data.length === 0 ? 'default' : 'pointer',
              fontWeight: '600', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px',
              opacity: data.length === 0 ? 0.5 : 1, transition: 'all 0.15s',
              boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            Export Excel
          </button>
          <button
            onClick={exportToPDF}
            disabled={data.length === 0}
            style={{
              padding: '10px 18px', borderRadius: '8px', border: '1px solid #dc2626',
              background: '#ffffff', color: '#dc2626', cursor: data.length === 0 ? 'default' : 'pointer',
              fontWeight: '600', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px',
              opacity: data.length === 0 ? 0.5 : 1, transition: 'all 0.15s',
              boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
            Export PDF
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '12px', marginBottom: '32px' }}>
        {['today', 'week', 'month'].map(tf => (
          <button 
            key={tf}
            onClick={() => setTimeframe(tf)}
            style={{ 
              padding: '10px 20px', 
              borderRadius: '8px', 
              border: timeframe === tf ? 'none' : '1px solid #cbd5e1', 
              background: timeframe === tf ? '#0f172a' : '#ffffff', 
              color: timeframe === tf ? '#ffffff' : '#475569', 
              cursor: 'pointer',
              fontWeight: '600',
              fontSize: '14px',
              textTransform: 'capitalize',
              boxShadow: timeframe === tf ? '0 4px 6px -1px rgba(0, 0, 0, 0.1)' : '0 1px 2px rgba(0,0,0,0.05)',
              transition: 'all 0.2s ease'
            }}
          >
            {tf === 'today' ? "Today's Report" : tf === 'week' ? "1 Week Report" : "1 Month Report"}
          </button>
        ))}
      </div>

      <div style={{ background: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: '#64748b', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
            <div style={{ width: '40px', height: '40px', border: '3px solid #f1f5f9', borderTop: '3px solid #3b82f6', borderRadius: '50%', animation: 'spin 1s linear infinite' }}></div>
            <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
            <span style={{ fontWeight: '500' }}>Generating Report Data...</span>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                <tr>
                  <th style={{ padding: '16px 24px', color: '#64748b', fontWeight: '600', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Transaction ID</th>
                  <th style={{ padding: '16px 24px', color: '#64748b', fontWeight: '600', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Plate Number</th>
                  <th style={{ padding: '16px 24px', color: '#64748b', fontWeight: '600', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Entry Time</th>
                  <th style={{ padding: '16px 24px', color: '#64748b', fontWeight: '600', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Exit Time</th>
                  <th style={{ padding: '16px 24px', color: '#64748b', fontWeight: '600', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Status</th>
                  <th style={{ padding: '16px 24px', color: '#64748b', fontWeight: '600', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Duration Stayed</th>
                </tr>
              </thead>
              <tbody>
                {data.length === 0 ? (
                  <tr>
                    <td colSpan="6" style={{ padding: '60px', textAlign: 'center', color: '#94a3b8' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                        <span style={{ fontSize: '15px' }}>No records found for this period.</span>
                      </div>
                    </td>
                  </tr>
                ) : (
                  data.map((row, index) => (
                    <tr key={index} style={{ borderBottom: '1px solid #f1f5f9', transition: 'background-color 0.2s' }}>
                      <td style={{ padding: '16px 24px', fontFamily: 'monospace', color: '#64748b', fontSize: '13px' }}>{row.transaction_id}</td>
                      <td style={{ padding: '16px 24px', fontWeight: '700', color: '#0f172a' }}>{row.plate_number}</td>
                      <td style={{ padding: '16px 24px', color: '#475569', fontSize: '14px' }}>{formatDate(row.entry_time)}</td>
                      <td style={{ padding: '16px 24px', color: '#475569', fontSize: '14px' }}>{formatDate(row.exit_time)}</td>
                      <td style={{ padding: '16px 24px' }}>
                        <span style={{ 
                          padding: '6px 12px', borderRadius: '6px', fontSize: '12px', fontWeight: '700', letterSpacing: '0.5px',
                          background: row.status === 'IN' ? '#ecfdf5' : '#f8fafc',
                          color: row.status === 'IN' ? '#059669' : '#64748b',
                          border: row.status === 'IN' ? '1px solid #a7f3d0' : '1px solid #e2e8f0'
                        }}>
                          {row.status}
                        </span>
                      </td>
                      <td style={{ padding: '16px 24px', fontWeight: '700', color: '#0f172a' }}>{row.stayed}</td>
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

export default Reports;
