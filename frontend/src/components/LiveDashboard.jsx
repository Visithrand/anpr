import React, { useEffect, useState, useRef, useCallback } from 'react';
import Zoom from 'react-medium-image-zoom';
import 'react-medium-image-zoom/dist/styles.css';
import {
  startLiveFeed, stopLiveFeed, stopAllFeeds, getLiveDetections, clearLiveDetections,
  registerLiveEntry, approveExit, getCameras, getStreamUrl
} from '../services/api';

const IS_DEV = import.meta.env.DEV;
const API_BASE = IS_DEV ? 'http://127.0.0.1:8000' : window.location.origin;

const LiveDashboard = () => {
  const [cameras, setCameras] = useState([]);
  const [detections, setDetections] = useState([]);
  const [selectedDetection, setSelectedDetection] = useState(null);
  const [editablePlate, setEditablePlate] = useState('');
  const [isRegistering, setIsRegistering] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [filterCam, setFilterCam] = useState(null);
  const [addCamOpen, setAddCamOpen] = useState(false);
  const [newSource, setNewSource] = useState('sample.mp4');
  const [newLabel, setNewLabel] = useState('');
  const pollRef = useRef(null);

  const refreshCameras = useCallback(async () => {
    try { setCameras(await getCameras()); } catch(e) { console.warn('cam poll err', e); }
  }, []);

  const refreshDetections = useCallback(async () => {
    try {
      const det = await getLiveDetections(50, filterCam);
      setDetections(det);
      if (det.length > 0 && !selectedDetection) {
        setSelectedDetection(det[0]);
        setEditablePlate(det[0].plate_text);
      }
    } catch(e) { console.warn('det poll err', e); }
  }, [selectedDetection, filterCam]);

  useEffect(() => {
    refreshCameras();
    refreshDetections();
    pollRef.current = setInterval(() => { refreshCameras(); refreshDetections(); }, 2500);
    const wsUrl = IS_DEV 
      ? 'ws://127.0.0.1:8000/ws/dashboard' 
      : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/dashboard`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = () => { refreshCameras(); refreshDetections(); };
    ws.onerror = () => {};
    return () => { clearInterval(pollRef.current); ws.close(); };
  }, [refreshCameras, refreshDetections]);

  const handleStartCam = async (camId, source, label) => {
    try {
      await startLiveFeed(source, camId, label);
      await refreshCameras();
    } catch(e) { alert(`Failed to start camera ${camId}: ${e.message}`); }
  };

  const handleStopCam = async (camId) => {
    try { await stopLiveFeed(camId); await refreshCameras(); } catch(e) { console.error(e); }
  };

  const handleStopAll = async () => {
    try { await stopAllFeeds(); await refreshCameras(); } catch(e) { console.error(e); }
  };

  const handleClear = async () => {
    try {
      await clearLiveDetections(filterCam);
      setDetections([]); setSelectedDetection(null); setEditablePlate('');
    } catch(e) { console.error(e); }
  };

  const handleAddCamera = async () => {
    const slot = cameras.find(c => !c.running);
    if (!slot) { alert('All 4 camera slots are in use.'); return; }
    await handleStartCam(slot.id, newSource, newLabel || `Camera ${slot.id}`);
    setAddCamOpen(false); setNewSource('sample.mp4'); setNewLabel('');
  };

  const handleRowClick = (d) => { setSelectedDetection(d); setEditablePlate(d.plate_text); setIsModalOpen(true); };

  const handleEntry = async () => {
    if (!selectedDetection || !editablePlate) return;
    setIsRegistering(true);
    try {
      await registerLiveEntry(editablePlate, selectedDetection.image_url, selectedDetection.vehicle_image_url);
      alert(`Entry registered for ${editablePlate}`);
      setSelectedDetection({ ...selectedDetection, is_inside: true, status: 'IN', billing_status: 'Pending' });
    } catch(e) { alert(`Failed: ${e.response?.data?.detail || e.message}`); }
    setIsRegistering(false);
  };

  const handleExit = async () => {
    if (!selectedDetection || !editablePlate) return;
    setIsRegistering(true);
    try {
      const res = await approveExit(editablePlate);
      alert(`Exit approved! Amount: ₹${res.amount}. ${res.billing_notes}`);
      setSelectedDetection({ ...selectedDetection, is_inside: false, status: 'OUT', billing_status: 'Paid' });
    } catch(e) {
      const d = e.response?.data?.detail;
      alert(`Failed: ${typeof d === 'object' ? (d.message || JSON.stringify(d)) : (d || e.message)}`);
    }
    setIsRegistering(false);
  };

  const fmtTime = (iso) => {
    if (!iso) return '-';
    const d = new Date(iso + (iso.endsWith('Z') ? '' : 'Z'));
    return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const fmtDate = (iso) => {
    if (!iso) return '-';
    const d = new Date(iso + (iso.endsWith('Z') ? '' : 'Z'));
    return d.toISOString().split('T')[0] + ' ' + d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  };

  const activeCams = cameras.filter(c => c.running);
  const gridCols = activeCams.length <= 1 ? '1fr' : '1fr 1fr';

  // Inline styles
  const S = {
    btn: { padding: '8px 16px', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '600', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' },
    input: { padding: '8px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '13px', outline: 'none', fontFamily: "'Inter', sans-serif" },
  };

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', height: '100%', boxSizing: 'border-box' }}>

      {/* ── Header Bar ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <h2 style={{ color: '#0f172a', margin: 0, fontSize: '24px', fontWeight: '700', letterSpacing: '-0.5px' }}>Live Monitoring</h2>
          <span style={{ background: '#f1f5f9', border: '1px solid #e2e8f0', borderRadius: '20px', padding: '4px 10px', fontSize: '11px', fontWeight: '700', color: '#0f172a' }}>
            {activeCams.length}/4 Cameras
          </span>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={() => setAddCamOpen(!addCamOpen)} style={{ ...S.btn, background: '#3b82f6', color: 'white' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            Add Camera
          </button>
          <button onClick={handleStopAll} style={{ ...S.btn, background: '#ef4444', color: 'white' }}>Stop All</button>
          <button onClick={handleClear} style={{ ...S.btn, background: '#fff', color: '#475569', border: '1px solid #cbd5e1' }}>Clear Log</button>
        </div>
      </div>

      {/* ── Add Camera Dialog ── */}
      {addCamOpen && (
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '16px', padding: '14px 18px', background: '#f8fafc', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
          <input value={newSource} onChange={e => setNewSource(e.target.value)} placeholder="RTSP URL, file path, or webcam index (0)" style={{ ...S.input, flex: 1 }} />
          <input value={newLabel} onChange={e => setNewLabel(e.target.value)} placeholder="Label (e.g. Entry Gate 1)" style={{ ...S.input, width: '200px' }} />
          <button onClick={handleAddCamera} style={{ ...S.btn, background: '#0f172a', color: 'white' }}>Connect</button>
          <button onClick={() => setAddCamOpen(false)} style={{ ...S.btn, background: '#f1f5f9', color: '#64748b', border: '1px solid #e2e8f0' }}>Cancel</button>
        </div>
      )}

      {/* ── Main Content ── */}
      <div style={{ display: 'flex', gap: '20px', flex: 1, overflow: 'hidden' }}>

        {/* LEFT — Camera Grid */}
        <div style={{ flex: '1.8', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {activeCams.length === 0 ? (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: '#0f172a', borderRadius: '12px', color: '#64748b', gap: '12px' }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
              <span style={{ fontSize: '14px', fontWeight: '500' }}>No cameras active. Click "Add Camera" to begin.</span>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: gridCols, gap: '12px', flex: 1, overflow: 'hidden' }}>
              {activeCams.map(cam => (
                <div key={cam.id} style={{ position: 'relative', background: '#0f172a', borderRadius: '10px', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '200px' }}>
                  <img src={getStreamUrl(cam.id)} alt={cam.label} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                  {/* Overlay: top-left status */}
                  <div style={{ position: 'absolute', top: 10, left: 10, display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <div style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#22c55e', boxShadow: '0 0 6px #22c55e' }} />
                    <span style={{ background: 'rgba(15,23,42,0.75)', backdropFilter: 'blur(4px)', color: 'white', padding: '3px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: '700', letterSpacing: '0.5px' }}>
                      CAM {cam.id} — {cam.label}
                    </span>
                  </div>
                  {/* Overlay: top-right stop */}
                  <button onClick={() => handleStopCam(cam.id)} style={{ position: 'absolute', top: 10, right: 10, background: 'rgba(239,68,68,0.85)', color: 'white', border: 'none', borderRadius: '4px', padding: '4px 8px', fontSize: '10px', fontWeight: '700', cursor: 'pointer' }}>
                    STOP
                  </button>
                  {/* Overlay: bottom-right detection count */}
                  <div style={{ position: 'absolute', bottom: 10, right: 10, background: 'rgba(15,23,42,0.75)', color: '#94a3b8', padding: '3px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: '600' }}>
                    {cam.detection_count} detections
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* RIGHT — Detections List */}
        <div style={{ flex: '1', display: 'flex', flexDirection: 'column', background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <div style={{ padding: '14px 18px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f8fafc' }}>
            <span style={{ fontWeight: '700', color: '#0f172a', fontSize: '15px' }}>Recent Plates</span>
            <select value={filterCam || ''} onChange={e => setFilterCam(e.target.value ? Number(e.target.value) : null)} style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#fff', color: '#334155', fontSize: '12px', fontWeight: '600', cursor: 'pointer' }}>
              <option value="">All Cameras</option>
              {cameras.filter(c => c.running).map(c => (
                <option key={c.id} value={c.id}>CAM {c.id}: {c.label}</option>
              ))}
            </select>
          </div>

          <div style={{ overflowY: 'auto', flex: 1 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead style={{ position: 'sticky', top: 0, background: '#f1f5f9', zIndex: 1, boxShadow: '0 1px 0 #e2e8f0' }}>
                <tr>
                  {['#','Plate','CAM','Plate Img','Time'].map(h => (
                    <th key={h} style={{ padding: '12px 10px', textAlign: 'left', color: '#64748b', fontWeight: '600', textTransform: 'uppercase', fontSize: '10px', letterSpacing: '0.5px' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {detections.length === 0 ? (
                  <tr><td colSpan="5" style={{ padding: '50px 20px', textAlign: 'center', color: '#94a3b8' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                      <span>No detections yet.</span>
                    </div>
                  </td></tr>
                ) : (
                  detections.map((d, i) => {
                    const isSel = selectedDetection && selectedDetection.id === d.id;
                    return (
                      <tr key={d.id} onClick={() => handleRowClick(d)} style={{ borderBottom: '1px solid #f1f5f9', cursor: 'pointer', background: isSel ? '#eff6ff' : 'transparent', transition: 'background 0.15s' }}>
                        <td style={{ padding: '8px 10px', color: '#64748b', fontSize: '12px' }}>{i+1}</td>
                        <td style={{ padding: '8px 10px', fontWeight: '700', color: isSel ? '#2563eb' : '#0f172a', fontSize: '12px' }}>{d.plate_text}</td>
                        <td style={{ padding: '8px 10px' }}>
                          <span style={{ background: '#eff6ff', color: '#3b82f6', padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: '700' }}>CAM {d.camera_id}</span>
                        </td>
                        <td style={{ padding: '4px 10px' }}>
                          <img src={`${API_BASE}${d.image_url}`} alt="Plate" style={{ height: '24px', borderRadius: '3px', objectFit: 'contain', background: '#fff', border: '1px solid #e2e8f0' }} />
                        </td>
                        <td style={{ padding: '8px 10px', color: '#475569', fontWeight: '500', fontSize: '11px' }}>{fmtTime(d.timestamp)}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ── Detail Modal ── */}
      {isModalOpen && selectedDetection && (
        <>
          <div onClick={() => setIsModalOpen(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', zIndex: 100, animation: 'fadeIn 0.2s ease-out' }} />
          <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: '90vw', maxWidth: '1100px', maxHeight: '90vh', background: '#fff', borderRadius: '16px', zIndex: 101, boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)', display: 'flex', flexDirection: 'column', overflow: 'hidden', animation: 'modalIn 0.25s ease-out' }}>
            {/* Header */}
            <div style={{ padding: '18px 24px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f8fafc', flexShrink: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'linear-gradient(135deg,#16a34a,#059669)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                </div>
                <h3 style={{ margin: 0, color: '#0f172a', fontSize: '18px', fontWeight: '700' }}>Vehicle Intelligence Details</h3>
                <span style={{ background: '#eff6ff', color: '#3b82f6', padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '700' }}>CAM {selectedDetection.camera_id}</span>
              </div>
              <button onClick={() => setIsModalOpen(false)} style={{ background: '#f1f5f9', border: '1px solid #e2e8f0', borderRadius: '8px', width: '36px', height: '36px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#64748b' }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>

            {/* Body */}
            <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
              {/* Left — Vehicle Image */}
              <div style={{ flex: '1.2', background: '#0f172a', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', position: 'relative', padding: '16px' }}>
                <Zoom><img src={`${API_BASE}${selectedDetection.vehicle_image_url}`} alt="Vehicle" style={{ maxWidth: '100%', maxHeight: '340px', objectFit: 'contain', borderRadius: '8px' }} onError={e => e.target.style.display='none'} /></Zoom>
                <div style={{ position: 'absolute', top: 12, left: 12, background: 'rgba(0,0,0,0.5)', color: 'white', padding: '4px 10px', borderRadius: '4px', fontSize: '11px', fontWeight: '600' }}>CAPTURED VEHICLE IMAGE</div>
              </div>

              {/* Right — Details */}
              <div style={{ flex: '1', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                <div style={{ flex: 1, overflowY: 'auto', padding: '24px 28px' }}>
                  <div style={{ marginBottom: '28px' }}>
                    <div style={{ color: '#64748b', fontSize: '11px', fontWeight: '700', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>License Plate</div>
                    <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
                      <div style={{ border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden', background: '#f8fafc', width: '160px', height: '70px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <Zoom><img src={`${API_BASE}${selectedDetection.image_url}`} alt="Plate" style={{ width: '100%', height: '100%', objectFit: 'contain' }} onError={e => e.target.style.display='none'} /></Zoom>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <div style={{ color: '#475569', fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Registration Number</div>
                        <input type="text" value={editablePlate} onChange={e => setEditablePlate(e.target.value)} style={{ fontSize: '22px', fontWeight: '800', color: '#0f172a', letterSpacing: '2px', background: '#f8fafc', padding: '6px 12px', borderRadius: '6px', border: '2px solid #3b82f6', width: '180px', textAlign: 'center', outline: 'none' }} />
                      </div>
                    </div>
                  </div>

                  <div style={{ color: '#64748b', fontSize: '11px', fontWeight: '700', marginBottom: '14px', textTransform: 'uppercase', letterSpacing: '1px' }}>Transaction Details</div>
                  <div style={{ background: '#f8fafc', borderRadius: '10px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
                    {[
                      { label: 'Date/Time', value: fmtDate(selectedDetection.timestamp) },
                      { label: 'Camera', value: `CAM ${selectedDetection.camera_id} — ${selectedDetection.camera_label}` },
                      { label: 'Location', value: selectedDetection.location },
                      { label: 'Transaction ID', value: selectedDetection.id, mono: true },
                      { label: 'Status', value: selectedDetection.status, color: selectedDetection.status === 'IN' ? '#10b981' : '#ef4444' },
                      { label: 'Billing', value: selectedDetection.billing_status },
                    ].map((item, idx) => (
                      <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderBottom: idx < 5 ? '1px solid #e2e8f0' : 'none' }}>
                        <span style={{ color: '#64748b', fontSize: '13px', fontWeight: '500' }}>{item.label}</span>
                        <span style={{ color: item.color || '#0f172a', fontSize: '13px', fontWeight: item.color ? '700' : '600', fontFamily: item.mono ? 'monospace' : 'inherit' }}>{item.value}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Action Buttons */}
                <div style={{ padding: '20px 28px', borderTop: '1px solid #e2e8f0', background: '#f8fafc', display: 'flex', gap: '12px', flexShrink: 0 }}>
                  <button onClick={handleEntry} disabled={isRegistering || selectedDetection?.status === 'IN'} style={{ flex: 1, padding: '14px', background: (isRegistering || selectedDetection?.status === 'IN') ? '#d1d5db' : 'linear-gradient(135deg,#059669,#10b981)', color: 'white', border: 'none', borderRadius: '8px', cursor: (isRegistering || selectedDetection?.status === 'IN') ? 'default' : 'pointer', fontWeight: '700', fontSize: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', opacity: (isRegistering || selectedDetection?.status === 'IN') ? 0.6 : 1 }}>
                    Register Entry & Open Gate
                  </button>
                  <button onClick={handleExit} disabled={isRegistering || selectedDetection?.status === 'OUT'} style={{ flex: 1, padding: '14px', background: (isRegistering || selectedDetection?.status === 'OUT') ? '#d1d5db' : 'linear-gradient(135deg,#dc2626,#ef4444)', color: 'white', border: 'none', borderRadius: '8px', cursor: (isRegistering || selectedDetection?.status === 'OUT') ? 'default' : 'pointer', fontWeight: '700', fontSize: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', opacity: (isRegistering || selectedDetection?.status === 'OUT') ? 0.6 : 1 }}>
                    Process Exit
                  </button>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      <style>{`
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes modalIn { from { opacity: 0; transform: translate(-50%, -48%); } to { opacity: 1; transform: translate(-50%, -50%); } }
      `}</style>
    </div>
  );
};

export default LiveDashboard;
