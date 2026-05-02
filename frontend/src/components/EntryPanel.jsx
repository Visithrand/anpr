import React, { useState } from 'react';
import { recordEntry } from '../services/api';

const EntryPanel = () => {
  const [plate, setPlate] = useState('');
  const [status, setStatus] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!plate.trim()) return;

    setStatus(null);
    try {
      const response = await recordEntry(plate.trim().toUpperCase());
      setStatus({ type: 'success', message: `${response.message} (${response.plate_number})` });
      setPlate('');
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'An unexpected error occurred.';
      if (errorMsg === "Vehicle already inside") {
        setStatus({ type: 'error', message: 'This vehicle is already parked inside.' });
      } else {
        setStatus({ type: 'error', message: errorMsg });
      }
    }
  };

  return (
    <div>
      <h2 className="page-heading">Manual Vehicle Entry Portal</h2>
      
      {status && (
        <div className={`alert ${status.type === 'success' ? 'alert-success' : 'alert-error'}`}>
          {status.message}
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
            <button type="submit" className="btn btn-gray" disabled={!plate.trim()}>Authorize Entry</button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default EntryPanel;
