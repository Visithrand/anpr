import React, { useEffect, useState, useRef } from 'react';
import { getMonitoringMetrics, getCameras } from '../services/api';

const Monitor = () => {
  const [metrics, setMetrics] = useState({
    active_cameras: 0,
    queue_size: 0,
    last_ocr_latency: 0.0,
    last_det_latency: 0.0,
    last_total_latency: 0.0,
    last_detection_time: null,
  });
  const [cameraList, setCameraList] = useState([]);
  const [loading, setLoading] = useState(true);
  const pollRef = useRef(null);

  const fetchMetrics = async () => {
    try {
      const data = await getMonitoringMetrics();
      setMetrics(data);
      const cams = await getCameras();
      setCameraList(cams);
    } catch (e) {
      console.warn('Failed to fetch monitor metrics:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    // Poll every 2 seconds for real-time monitoring feel
    pollRef.current = setInterval(fetchMetrics, 2000);
    return () => clearInterval(pollRef.current);
  }, []);

  const formatLatency = (ms) => {
    if (!ms) return '0 ms';
    return `${ms.toFixed(1)} ms`;
  };

  const getQueueColor = (size) => {
    if (size === 0) return '#10b981'; // Green
    if (size < 20) return '#f59e0b';  // Orange
    return '#ef4444';                  // Red
  };

  const fmtTime = (iso) => {
    if (!iso) return '-';
    const d = new Date(iso + (iso.endsWith('Z') ? '' : 'Z'));
    return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const kpis = [
    {
      title: 'Active Cameras',
      value: `${metrics.active_cameras} Active`,
      desc: 'Cameras capturing frames',
      color: metrics.active_cameras > 0 ? '#10b981' : '#64748b',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
      )
    },
    {
      title: 'OCR Queue Depth',
      value: `${metrics.queue_size} Frames`,
      desc: 'Pending OCR processing',
      color: getQueueColor(metrics.queue_size),
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/><line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/></svg>
      )
    },
    {
      title: 'OCR Latency',
      value: formatLatency(metrics.last_ocr_latency),
      desc: 'Text extraction inference',
      color: '#3b82f6',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      )
    },
    {
      title: 'Last Detection',
      value: fmtTime(metrics.last_detection_time),
      desc: 'Plate registration time',
      color: '#8b5cf6',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
      )
    }
  ];

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b' }}>
        <span>Loading monitor metrics...</span>
      </div>
    );
  }

  return (
    <div style={{ padding: '32px', maxWidth: '1200px', margin: '0 auto' }}>
      
      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '28px' }}>
        <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white' }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect><rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect><line x1="6" y1="6" x2="6.01" y2="6"></line><line x1="6" y1="18" x2="6.01" y2="18"></line></svg>
        </div>
        <div>
          <h2 style={{ color: '#0f172a', margin: 0, fontSize: '28px', fontWeight: '800', letterSpacing: '-0.5px' }}>System Performance Monitor</h2>
          <p style={{ margin: '4px 0 0', color: '#64748b', fontSize: '13px' }}>Real-time hardware pipeline status and OCR worker diagnostics.</p>
        </div>
      </div>

      {/* ── KPIs ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', marginBottom: '28px' }}>
        {kpis.map((kpi, i) => (
          <div key={i} style={{ background: '#ffffff', padding: '20px', borderRadius: '16px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: '#f8fafc', color: kpi.color, display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid #f1f5f9', flexShrink: 0 }}>
              {kpi.icon}
            </div>
            <div>
              <div style={{ color: '#64748b', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '4px' }}>{kpi.title}</div>
              <div style={{ color: '#0f172a', fontSize: '22px', fontWeight: '800', lineHeight: '1.2' }}>{kpi.value}</div>
              <div style={{ color: '#94a3b8', fontSize: '11px', marginTop: '4px', fontWeight: '500' }}>{kpi.desc}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Two Column Details ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.8fr 1.2fr', gap: '24px' }}>
        
        {/* Left: Camera Feeds Diagnostics */}
        <div style={{ background: '#ffffff', borderRadius: '16px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)', overflow: 'hidden' }}>
          <div style={{ padding: '16px 24px', borderBottom: '1px solid #e2e8f0', background: '#f8fafc' }}>
            <h3 style={{ margin: 0, color: '#0f172a', fontSize: '16px', fontWeight: '700' }}>Camera Channel Health</h3>
          </div>
          <div style={{ padding: '20px' }}>
            {cameraList.length === 0 ? (
              <div style={{ textAlign: 'center', color: '#94a3b8', padding: '20px' }}>No cameras configured.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {cameraList.map((cam) => (
                  <div key={cam.id} style={{ border: '1px solid #f1f5f9', borderRadius: '10px', padding: '14px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: cam.running ? '#fdfdfd' : '#f8fafc' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: cam.running ? '#10b981' : '#cbd5e1' }}></div>
                      <div>
                        <div style={{ fontWeight: '700', color: '#0f172a', fontSize: '14px' }}>{cam.label}</div>
                        <div style={{ fontSize: '11px', color: '#94a3b8', fontFamily: 'monospace', marginTop: '2px' }}>ID: {cam.id} | Source: {cam.source || 'None'}</div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '24px', alignItems: 'center' }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ color: '#94a3b8', fontSize: '9px', fontWeight: '700', textTransform: 'uppercase' }}>Uptime</div>
                        <div style={{ color: '#475569', fontSize: '12px', fontWeight: '600', marginTop: '2px' }}>{cam.running ? `${(cam.uptime / 60).toFixed(1)}m` : '-'}</div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ color: '#94a3b8', fontSize: '9px', fontWeight: '700', textTransform: 'uppercase' }}>Detections</div>
                        <div style={{ color: '#475569', fontSize: '12px', fontWeight: '600', marginTop: '2px' }}>{cam.detection_count}</div>
                      </div>
                      <span style={{ 
                        fontSize: '11px', fontWeight: '700', padding: '4px 8px', borderRadius: '6px',
                        background: cam.running ? '#ecfdf5' : '#f1f5f9',
                        color: cam.running ? '#059669' : '#64748b'
                      }}>
                        {cam.running ? 'ONLINE' : 'OFFLINE'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Pipeline Latency Breakdown */}
        <div style={{ background: '#ffffff', borderRadius: '16px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)', overflow: 'hidden' }}>
          <div style={{ padding: '16px 24px', borderBottom: '1px solid #e2e8f0', background: '#f8fafc' }}>
            <h3 style={{ margin: 0, color: '#0f172a', fontSize: '16px', fontWeight: '700' }}>Pipeline Latency Diagnostics</h3>
          </div>
          <div style={{ padding: '24px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ color: '#475569', fontSize: '13px', fontWeight: '500' }}>1. Plate Detection (OpenVINO)</span>
                  <span style={{ color: '#0f172a', fontSize: '13px', fontWeight: '700' }}>{formatLatency(metrics.last_det_latency)}</span>
                </div>
                <div style={{ width: '100%', height: '6px', background: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{ width: `${Math.min(100, (metrics.last_det_latency / 200) * 100)}%`, height: '100%', background: '#3b82f6', borderRadius: '3px' }}></div>
                </div>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ color: '#475569', fontSize: '13px', fontWeight: '500' }}>2. OCR Extraction (PaddleOCR)</span>
                  <span style={{ color: '#0f172a', fontSize: '13px', fontWeight: '700' }}>{formatLatency(metrics.last_ocr_latency)}</span>
                </div>
                <div style={{ width: '100%', height: '6px', background: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{ width: `${Math.min(100, (metrics.last_ocr_latency / 500) * 100)}%`, height: '100%', background: '#8b5cf6', borderRadius: '3px' }}></div>
                </div>
              </div>

              <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: '16px', marginTop: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <span style={{ color: '#0f172a', fontSize: '14px', fontWeight: '700' }}>Total Pipeline Latency</span>
                    <div style={{ color: '#94a3b8', fontSize: '11px', marginTop: '2px' }}>Capture to publish delay</div>
                  </div>
                  <span style={{ color: '#10b981', fontSize: '18px', fontWeight: '800' }}>{formatLatency(metrics.last_total_latency)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>

    </div>
  );
};

export default Monitor;
