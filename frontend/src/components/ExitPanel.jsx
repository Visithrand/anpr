import React, { useState } from 'react';
import { recordExit } from '../services/api';

const ExitPanel = () => {
  const [plate, setPlate] = useState('');
  const [status, setStatus] = useState(null);
  const [billData, setBillData] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!plate.trim()) return;

    setStatus(null);
    setBillData(null);
    try {
      const response = await recordExit(plate.trim().toUpperCase());
      setStatus({ type: 'success', message: 'Vehicle exit processed successfully.' });
      setBillData(response);
      setPlate('');
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'An unexpected error occurred.';
      setStatus({ type: 'error', message: errorMsg });
    }
  };

  return (
    <div>
      <h2 className="page-heading">Manual Vehicle Exit Portal</h2>
      
      {status && !billData && (
        <div className={`alert ${status.type === 'success' ? 'alert-success' : 'alert-error'}`}>
          {status.message}
        </div>
      )}

      {billData && (
        <div style={{ marginBottom: '24px' }}>
          <div className="alert alert-success">
            <strong>Success:</strong> Billing receipt generated for {billData.plate_number}.
          </div>
          <table className="gov-table" style={{ width: '50%' }}>
            <tbody>
              <tr>
                <td style={{ backgroundColor: '#f9f9f9', width: '150px', textAlign: 'left', fontWeight: 'bold' }}>Plate Number:</td>
                <td style={{ textAlign: 'left' }}>{billData.plate_number}</td>
              </tr>
              <tr>
                <td style={{ backgroundColor: '#f9f9f9', textAlign: 'left', fontWeight: 'bold' }}>Duration:</td>
                <td style={{ textAlign: 'left' }}>{billData.duration_minutes ? (billData.duration_minutes / 60).toFixed(2) : 0} Hours</td>
              </tr>
              <tr>
                <td style={{ backgroundColor: '#f9f9f9', textAlign: 'left', fontWeight: 'bold' }}>Amount Due:</td>
                <td style={{ textAlign: 'left', color: '#006400', fontWeight: 'bold', fontSize: '16px' }}>₹{billData.amount?.toFixed(2)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      <div className="form-panel">
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <div className="form-label">Plate Number :</div>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. MH12AB1234"
              value={plate}
              onChange={(e) => setPlate(e.target.value.toUpperCase())}
              required
            />
          </div>
          
          <div className="button-group">
            <button type="button" className="btn btn-red" onClick={() => setPlate('')}>Reset</button>
            <button type="submit" className="btn btn-gray" disabled={!plate.trim()}>Process Checkout</button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ExitPanel;
