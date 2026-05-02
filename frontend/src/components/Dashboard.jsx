import React, { useEffect, useState } from 'react';
import { getDashboard } from '../services/api';

const Dashboard = () => {
  const [data, setData] = useState({
    vehicles_inside: 0,
    total_revenue: 0,
    active_vehicles: []
  });

  useEffect(() => {
    fetchDashboard();

    // WebSocket for real-time updates
    const ws = new WebSocket('ws://127.0.0.1:8000/ws/dashboard');
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'REFRESH_DASHBOARD') {
        fetchDashboard();
      }
    };
    ws.onerror = () => console.warn('WS error, falling back to polling');

    // Fallback polling every 30s if WS is unavailable
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
    const date = new Date(dateString + 'Z');
    return new Intl.DateTimeFormat('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(date);
  };

  return (
    <div>
      <h2 className="page-heading">Parking Operations Dashboard</h2>

      <div className="form-panel" style={{ display: 'flex', gap: '40px', padding: '16px 24px', marginBottom: '16px' }}>
        <div>
          <span style={{ color: '#555', fontSize: '13px' }}>Vehicles Inside : </span>
          <strong>{data.vehicles_inside}</strong>
        </div>
        <div>
          <span style={{ color: '#555', fontSize: '13px' }}>Total Revenue : </span>
          <strong>₹{data.total_revenue?.toFixed(2) || '0.00'}</strong>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '8px' }}>
        <div style={{ fontSize: '12px' }}>
          <strong>{data.active_vehicles.length}</strong> Results
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-gray" onClick={fetchDashboard}>Refresh</button>
        </div>
      </div>

      <div className="gov-table-container">
        <table className="gov-table">
          <thead>
            <tr>
              <th style={{ width: '60px' }}>S.No.</th>
              <th>Vehicle Plate Number</th>
              <th>Entry Date and Time</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {data.active_vehicles.length === 0 ? (
              <tr>
                <td colSpan="4" style={{ padding: '20px' }}>No active vehicles found.</td>
              </tr>
            ) : (
              data.active_vehicles.map((v, index) => (
                <tr key={index}>
                  <td>{String(index + 1).padStart(2, '0')}</td>
                  <td>
                    <strong>{v.plate_number}</strong>
                  </td>
                  <td>
                    {formatDate(v.entry_time).split(',')[0]}<br/>
                    {formatDate(v.entry_time).split(',')[1]}
                  </td>
                  <td style={{ color: 'green', fontWeight: 'bold' }}>IN</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Dashboard;
