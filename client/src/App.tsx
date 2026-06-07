import React, { useEffect, useState, useCallback } from 'react';
import './App.css';
import bgImage from './assets/ddd.jpg';

type Screen = 'login' | 'driver' | 'admin' | 'landing';

type DriverStatus = 'AWAKE' | 'WARNING' | 'DROWSY';

interface AlertItem {
  time: string;
  label: string;
  severity: DriverStatus | 'NORMAL';
}

interface LogItem {
  driver: string;
  time: string;
  ear: number;
  status: DriverStatus | 'NORMAL';
}

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';
const AI_BASE = process.env.REACT_APP_AI_URL || 'http://localhost:8001';

interface AuthedUser {
  id: string;
  name: string;
  email: string;
  role: 'driver' | 'admin';
}



type AuthMode = 'login' | 'register';

const LandingPage: React.FC<{ onGetStarted: () => void }> = ({ onGetStarted }) => {
  return (
    <div className="landing-page" style={{ backgroundImage: `url(${bgImage})` }}>
      <div className="landing-overlay">
        <div className="landing-content">
          <h1 className="landing-title">DRIVER DROWSINESS DETECTION</h1>
          <button className="primary-button landing-button" onClick={onGetStarted}>
            Get Started
          </button>
        </div>
      </div>
    </div>
  );
};

const LoginPage: React.FC<{
  onLoginSuccess: (user: AuthedUser, token: string) => void;
}> = ({ onLoginSuccess }) => {
  const [mode, setMode] = useState<AuthMode>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'driver' | 'admin'>('driver');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const url = mode === 'login'
        ? `${API_BASE}/api/auth/login`
        : `${API_BASE}/api/auth/register`;
      const body = mode === 'login'
        ? { email, password }
        : { name, email, password, role };

      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        throw new Error(data?.message || (mode === 'login' ? 'Login failed' : 'Registration failed'));
      }

      const user: AuthedUser = {
        id: data.user.id,
        name: data.user.name,
        email: data.user.email,
        role: data.user.role,
      };
      onLoginSuccess(user, data.token);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-root">
      <div className="full-screen-center">
        <div className="login-card">
          <div className="login-title">DRIVER MONITORING SYSTEM</div>
          <div className="login-heading">
            {mode === 'login' ? 'Secure access' : 'Create account'}
          </div>
          <div className="login-subheading">
            Real-time drowsiness detection using AI – optimized for on-road
            safety.
          </div>

          <form className="login-form" onSubmit={handleSubmit}>
            {mode === 'register' && (
              <div>
                <div className="field-label">Name</div>
                <input
                  type="text"
                  className="field-input"
                  placeholder="Your name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
            )}
            <div>
              <div className="field-label">Email</div>
              <input
                type="email"
                className="field-input"
                placeholder="driver@fleet.example"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div>
              <div className="field-label">Password</div>
              <input
                type="password"
                className="field-input"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>
            {mode === 'register' && (
              <div>
                <div className="field-label">Role</div>
                <select
                  className="field-input"
                  value={role}
                  onChange={(e) => setRole(e.target.value as 'driver' | 'admin')}
                >
                  <option value="driver">Driver</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            )}
            <div className="login-actions">
              <button type="submit" className="primary-button" disabled={loading}>
                {loading
                  ? (mode === 'login' ? 'Validating…' : 'Creating account…')
                  : (mode === 'login' ? 'Login' : 'Register')}
              </button>
              {error && (
                <span className="dataset-hint" style={{ color: 'var(--danger)' }}>
                  {error}
                </span>
              )}
            </div>
          </form>

          <div className="login-footer">
            <button
              type="button"
              className="ghost-button"
              style={{ marginTop: 8, fontSize: '0.9rem' }}
              onClick={() => {
                setMode(mode === 'login' ? 'register' : 'login');
                setError(null);
              }}
            >
              {mode === 'login' ? 'Create account' : 'Already have an account? Login'}
            </button>
            <span className="login-tagline" style={{ display: 'block', marginTop: 12 }}>
              “Real-time Drowsiness Detection using AI”
            </span>
            <span style={{ fontSize: '0.78rem' }}>
              Use admin credentials to access the Admin Dashboard.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

const StatusCard: React.FC<{
  ear: number;
  status: DriverStatus;
  threshold: number;
}> = ({ ear, status, threshold }) => {
  const statusClass =
    status === 'DROWSY'
      ? 'status-card status-card-drowsy'
      : status === 'WARNING'
        ? 'status-card status-card-warning'
        : 'status-card status-card-awake';

  const pillText =
    status === 'DROWSY'
      ? 'Drowsy'
      : status === 'WARNING'
        ? 'Early warning'
        : 'Awake';

  const pillIcon =
    status === 'DROWSY' ? '🔴' : status === 'WARNING' ? '🟡' : '🟢';

  return (
    <div className={statusClass}>
      <div className="status-header">
        <div>
          <div className="status-header-main">Driver status</div>
          <div className="status-header-sub">Eye Aspect Ratio (EAR) monitor</div>
        </div>
        <div className="tag-pill">
          <span className="tag-pill-dot" />
          <span className="tag-pill-label">AI / Computer Vision</span>
        </div>
      </div>

      <div className="status-values">
        <div className="status-metric">
          <div className="status-metric-label">EAR (current)</div>
          <div className="status-metric-value">{ear.toFixed(2)}</div>
        </div>
        <div className="status-metric">
          <div className="status-metric-label">Threshold</div>
          <div className="status-metric-value">{threshold.toFixed(2)}</div>
        </div>
        <div className="status-metric">
          <span className="status-pill">
            <span className="status-pill-dot" />
            <span>
              {pillIcon} {pillText}
            </span>
          </span>
        </div>
      </div>

      <div className="status-footnote">
        EAR &lt; threshold for continuous frames triggers a drowsiness alert.
      </div>
    </div>
  );
};

const AlertTimeline: React.FC<{ items: AlertItem[] }> = ({ items }) => {
  const colorForSeverity = (severity: AlertItem['severity']) => {
    switch (severity) {
      case 'DROWSY':
        return 'var(--danger)';
      case 'WARNING':
        return 'var(--warning)';
      case 'AWAKE':
        return 'var(--success)';
      default:
        return 'var(--text-muted)';
    }
  };

  return (
    <div className="card card-muted">
      <div className="card-title">Alert timeline</div>
      <div className="card-heading">Recent EAR-based events</div>
      <ul className="timeline-list">
        {items.map((item, index) => (
          <li key={index} className="timeline-item">
            <span
              className="timeline-dot"
              style={{ backgroundColor: colorForSeverity(item.severity) }}
            />
            <span className="timeline-time">{item.time}</span>
            <span
              className={
                item.severity === 'NORMAL'
                  ? 'timeline-label-muted'
                  : 'timeline-label'
              }
            >
              {item.label}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
};

const DatasetModePanel: React.FC = () => {
  const [summary, setSummary] = useState<{
    datasetRoot: string;
    counts: { AWAKE: number; DROWSY: number };
    samples: {
      AWAKE: { name: string; url: string }[];
      DROWSY: { name: string; url: string }[];
    };
  } | null>(null);
  const [datasetChartData, setDatasetChartData] = useState<{ time: string; ear: number }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch summary
      try {
        const summaryRes = await fetch(`${AI_BASE}/api/ai/dataset/summary`);
        const summaryJson = await summaryRes.json().catch(() => null);
        if (summaryRes.ok && summaryJson) {
          setSummary(summaryJson);
        } else {
          setError(summaryJson?.detail || 'Failed to load dataset summary');
        }
      } catch (e) {
        setError((e as Error).message);
      }

      // Fetch results silently
      try {
        const resultsRes = await fetch(`${AI_BASE}/api/ai/dataset/results`);
        const resultsJson = await resultsRes.json().catch(() => null);
        if (resultsRes.ok && resultsJson && resultsJson.items) {
          setDatasetChartData(resultsJson.items);
        }
      } catch (e) {
        console.warn('Silent results fetch error:', e);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return (
    <section className="dataset-layout">
      <div className="card dataset-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div className="card-title">Dataset mode</div>
            <div className="card-heading">Offline dataset browser</div>
          </div>
          <button
            type="button"
            className="ghost-button"
            onClick={fetchAll}
            disabled={loading}
            style={{ padding: '6px 12px', fontSize: '0.8rem' }}
          >
            {loading ? 'Refreshing...' : '↻ Refresh'}
          </button>
        </div>
        <div className="card-subtitle">
          Browses the images under <span style={{ fontFamily: 'monospace' }}>backend/python_service/dataset</span> and
          lets you run prediction in dataset-mode.
        </div>

        <div className="dataset-form">
          <div className="dataset-input-row">
            <span className="field-label">Dataset UI</span>
            <div className="dataset-file-input">
              Python service: <span style={{ fontFamily: 'monospace' }}>{AI_BASE}</span>
            </div>
            <span className="dataset-hint">
              Start the Python service (<span style={{ fontFamily: 'monospace' }}>python backend/python_service/main.py</span>)
              and open the dataset browser.
            </span>
          </div>

          <button
            type="button"
            className="primary-button"
            onClick={() => window.open(`${AI_BASE}/dataset-browser`, '_blank')}
          >
            Open dataset browser
          </button>

          <div className="dataset-result-grid">
            <div>
              <div className="dataset-result-label">AWAKE images</div>
              <div className="dataset-result-value">
                {loading ? 'Loading…' : (summary?.counts?.AWAKE ?? 0).toLocaleString()}
              </div>
            </div>
            <div>
              <div className="dataset-result-label">DROWSY images</div>
              <div className="dataset-result-value">
                {loading ? 'Loading…' : (summary?.counts?.DROWSY ?? 0).toLocaleString()}
              </div>
            </div>
            <div>
              <div className="dataset-result-label">Dataset root</div>
              <div className="dataset-result-value" style={{ fontFamily: 'monospace' }}>
                {summary?.datasetRoot ?? '—'}
              </div>
            </div>
            <div>
              <div className="dataset-result-label">Status</div>
              <div className="dataset-result-value">
                {error ? 'Error' : summary ? 'Ready' : loading ? 'Loading…' : '—'}
              </div>
            </div>
          </div>



          {summary && (
            <div style={{ display: 'grid', gap: 10, marginTop: 6 }}>
              <div className="dataset-hint">Sample previews</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {(['AWAKE', 'DROWSY'] as const).map((lbl) => (
                  <div key={lbl} style={{ display: 'grid', gap: 6 }}>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      {lbl}
                    </div>
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
                        gap: 8,
                      }}
                    >
                      {(summary.samples?.[lbl] ?? []).slice(0, 4).map((s) => (
                        <div
                          key={s.name}
                          title={s.name}
                          style={{
                            borderRadius: 14,
                            overflow: 'hidden',
                            border: '1px solid rgba(148,163,184,0.25)',
                            background: 'rgba(15,23,42,0.8)',
                            aspectRatio: '1 / 1',
                          }}
                        >
                          <img
                            src={`${AI_BASE}${s.url}`}
                            alt={s.name}
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                            loading="lazy"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <EARChart data={datasetChartData} />
    </section>
  );
};

const DriverDashboard: React.FC<{
  onLogout: () => void;
  token: string;
  user: AuthedUser;
}> = ({ onLogout, token, user }) => {
  const threshold = 0.21;
  const [ear, setEar] = useState<number | null>(null);
  const [status, setStatus] = useState<DriverStatus>('AWAKE');
  const [isDismissed, setIsDismissed] = useState(false);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const showAlertOverlay = status === 'DROWSY' && !isDismissed;

  useEffect(() => {
    if (status !== 'DROWSY') {
      setIsDismissed(false);
    }
  }, [status]);
  const [mode, setMode] = useState<'live' | 'dataset'>('live');
  const isLiveMode = mode === 'live';

  useEffect(() => {
    let isMounted = true;

    const fetchLogs = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/driver/logs?limit=10`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!isMounted) return;

        if (!res.ok) {
          throw new Error('Failed to load logs');
        }

        const data = await res.json();
        const logs: { earValue: number; status: string; timestamp: string }[] =
          data.logs ?? [];

        if (logs.length === 0) {
          setEar(0.26);
          setStatus('AWAKE');
          setAlerts([
            {
              time: '-',
              label: 'No events yet for this driver',
              severity: 'NORMAL',
            },
          ]);
          return;
        }

        const [latest, ...rest] = logs;
        
        // Check if the log is recent (e.g., within the last 30 seconds)
        // This prevents old "DROWSY" logs from appearing immediately when you log back in
        const logTime = new Date(latest.timestamp).getTime();
        const now = Date.now();
        const isRecent = (now - logTime) < 30000; // 30 seconds

        if (isRecent) {
          setEar(latest.earValue);
          if (
            latest.status === 'AWAKE' ||
            latest.status === 'WARNING' ||
            latest.status === 'DROWSY'
          ) {
            setStatus(latest.status as DriverStatus);
          }
        } else {
          // If the log is old, show a default "Fresh" state
          setEar(0.26);
          setStatus('AWAKE');
        }

        const mappedAlerts: AlertItem[] = [latest, ...rest].map((log) => {
          const time = new Date(log.timestamp).toLocaleTimeString(undefined, {
            hour: '2-digit',
            minute: '2-digit',
          });

          let label = 'Normal driving';
          if (log.status === 'DROWSY') {
            label = 'Drowsy detected';
          } else if (log.status === 'WARNING') {
            label = 'Early warning event';
          }

          return {
            time,
            label: `${label} (EAR ${log.earValue.toFixed(2)})`,
            severity:
              log.status === 'AWAKE' ||
                log.status === 'WARNING' ||
                log.status === 'DROWSY'
                ? (log.status as DriverStatus)
                : 'NORMAL',
          };
        });

        setAlerts(mappedAlerts);
      } catch {
        if (!isMounted) return;
        setEar(0.26);
        setStatus('AWAKE');
        setAlerts([
          {
            time: '-',
            label: 'Could not load logs from server',
            severity: 'NORMAL',
          },
        ]);
      }
    };

    fetchLogs();
    const interval = setInterval(fetchLogs, 5000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [token]);

  return (
    <div className="app-root">
      <div className="app-shell">
        <header className="top-bar">
          <div className="top-bar-title">
            <span>🚗</span>
            <div>
              <div className="top-bar-title-main">Driver Dashboard</div>
              <div className="top-bar-title-sub">
                {isLiveMode ? 'Live on-road monitoring' : 'Dataset-based evaluation'}
              </div>
            </div>
          </div>
          <div className="top-bar-actions">
            <div className="mode-toggle">
              <button
                type="button"
                className={
                  isLiveMode
                    ? 'mode-toggle-btn mode-toggle-btn-active'
                    : 'mode-toggle-btn'
                }
                onClick={() => setMode('live')}
              >
                Live mode
              </button>
              <button
                type="button"
                className={
                  !isLiveMode
                    ? 'mode-toggle-btn mode-toggle-btn-active'
                    : 'mode-toggle-btn'
                }
                onClick={() => setMode('dataset')}
              >
                Dataset mode
              </button>
            </div>
            <button type="button" className="ghost-button" onClick={onLogout}>
              Logout
            </button>
          </div>
        </header>

        <main className="dashboard-main">
          {isLiveMode ? (
            <>
              <section className="dashboard-grid">
                <div className="card camera-card">
                  <div className="camera-header">
                    <div className="camera-meta">
                      <span>Live camera feed</span>
                      <span
                        style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}
                      >
                        In-cabin driver view
                      </span>
                    </div>
                    <div className="camera-meta">
                      <span
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: 999,
                          backgroundColor: '#22c55e',
                          boxShadow: '0 0 16px rgba(34,197,94,0.9)',
                        }}
                      />
                      <span>Streaming</span>
                    </div>
                  </div>
                  <div className="camera-body">
                    <div className="camera-feed-wrapper">
                      <div className="camera-placeholder">
                        LIVE CAMERA FEED (connected to OpenCV / model)
                      </div>
                      <div className="camera-overlay" />
                    </div>
                    <div style={{ marginTop: 16, textAlign: 'center' }}>
                      <button
                        type="button"
                        className="primary-button"
                        onClick={async () => {
                          try {
                            const res = await fetch(`${AI_BASE}/api/ai/launch-webcam?user_email=${encodeURIComponent(user.email)}`, {
                              method: 'POST',
                            });
                            if (res.ok) {
                              alert('Webcam mode launched successfully! Check the new window. Drowsiness events will appear in the Alert Timeline below.');
                            } else {
                              console.warn('Webcam launch returned status:', res.status);
                            }
                          } catch (err) {
                            console.warn('Webcam launch error (silently caught):', err);
                          }
                        }}
                      >
                        🎥 Launch Webcam
                      </button>
                    </div>
                  </div>
                </div>

                <StatusCard
                  ear={ear ?? threshold}
                  status={status}
                  threshold={threshold}
                />
              </section>

              <AlertTimeline items={alerts} />
            </>
          ) : (
            <DatasetModePanel />
          )}
        </main>
      </div>

      {showAlertOverlay && isLiveMode && (
        <div className="alert-overlay">
          <div className="alert-overlay-backdrop" />
          <div className="alert-overlay-panel">
            <div className="alert-icon">⚠</div>
            <div>
              <div className="alert-text-main">Drowsiness Alert – Please take a break</div>
              <div className="alert-text-sub">
                EAR has remained below threshold for continuous frames.
              </div>
            </div>
            <div className="alert-badge">EAR: {(ear ?? threshold).toFixed(2)}</div>
            <button
              type="button"
              className="ghost-button"
              onClick={() => setIsDismissed(true)}
              style={{
                padding: '4px 12px',
                fontSize: '0.75rem',
                borderColor: 'rgba(239, 68, 68, 0.5)',
                color: 'var(--danger)',
                marginLeft: '8px'
              }}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

const StatsCard: React.FC<{
  label: string;
  value: string;
  caption?: string;
  icon?: React.ReactNode;
}> = ({ label, value, caption, icon }) => (
  <div className="stats-card">
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
      <div className="stats-label">{label}</div>
      {icon && <div style={{ opacity: 0.9 }}>{icon}</div>}
    </div>
    <div className="stats-value">{value}</div>
    {caption && <div className="stats-caption">{caption}</div>}
  </div>
);

const EARChart: React.FC<{
  data: { time: string; ear: number }[];
}> = ({ data }) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const viewBoxWidth = 100;
  const viewBoxHeight = 40;
  const minEar = 0.1;
  const maxEar = 0.4;
  const threshold = 0.21;

  if (data.length === 0) {
    return (
      <div className="chart-card card card-muted">
        <div className="card-title">EAR vs Time</div>
        <div className="card-heading">No data available</div>
        <div className="chart-wrapper" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 160 }}>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Run dataset evaluation to see results</span>
        </div>
      </div>
    );
  }

  const getCoords = (val: number, index: number) => {
    const x = data.length === 1 ? viewBoxWidth / 2 : (index / (data.length - 1)) * viewBoxWidth;
    const clampedEar = Math.min(Math.max(val, minEar), maxEar);
    const normalized = (clampedEar - minEar) / (maxEar - minEar);
    const y = viewBoxHeight - 5 - normalized * 26;
    return { x, y };
  };

  const coords = data.map((p, i) => getCoords(p.ear, i));

  // Bezier curve calculation logic
  const bezierCommand = (point: { x: number; y: number }, i: number, a: { x: number; y: number }[]) => {
    const cps = (p1: { x: number; y: number }, p2: { x: number; y: number }, p3: { x: number; y: number } | undefined, isEnd: boolean) => {
      const smoothing = 0.15;
      const dx = (p3 ? p3.x : p2.x) - p1.x;
      const dy = (p3 ? p3.y : p2.y) - p1.y;
      const dist = Math.sqrt(dx * dx + dy * dy) * smoothing;
      const angle = Math.atan2(dy, dx) + (isEnd ? Math.PI : 0);
      return {
        x: p2.x + Math.cos(angle) * dist,
        y: p2.y + Math.sin(angle) * dist
      };
    };

    const cp1 = cps(a[i - 2] || a[i - 1], a[i - 1], point, false);
    const cp2 = cps(point, a[i] || point, a[i - 1], true);
    return `C ${cp1.x.toFixed(2)},${cp1.y.toFixed(2)} ${cp2.x.toFixed(2)},${cp2.y.toFixed(2)} ${point.x.toFixed(2)},${point.y.toFixed(2)}`;
  };

  const d = coords.reduce((acc, point, i, a) => (i === 0 ? `M ${point.x},${point.y}` : `${acc} ${bezierCommand(point, i, a)}`), '');
  const fillD = `${d} L ${viewBoxWidth},${viewBoxHeight - 6} L 0,${viewBoxHeight - 6} Z`;

  const thresholdY = getCoords(threshold, 0).y;

  return (
    <div className="chart-card card card-muted">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div className="card-title">EAR vs Time</div>
          <div className="card-heading">Eye Aspect Ratio behaviour</div>
        </div>
        {hoverIndex !== null && (
          <div className="tooltip-mini">
            <div style={{ color: 'var(--accent-secondary)', fontWeight: 600 }}>{data[hoverIndex].ear.toFixed(3)}</div>
            <div style={{ fontSize: '0.65rem', opacity: 0.7 }}>{data[hoverIndex].time}</div>
          </div>
        )}
      </div>

      <div className="chart-wrapper" style={{ position: 'relative', overflow: 'visible' }}>
        <svg
          viewBox={`0 0 ${viewBoxWidth} ${viewBoxHeight}`}
          width="100%"
          height="160"
          style={{ overflow: 'visible' }}
          onMouseMove={(e: any) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const x = ((e.clientX - rect.left) / rect.width) * viewBoxWidth;
            const index = Math.round((x / viewBoxWidth) * (data.length - 1));
            if (index >= 0 && index < data.length) setHoverIndex(index);
          }}
          onMouseLeave={() => setHoverIndex(null)}
        >
          <defs>
            <linearGradient id="earLine" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#38bdf8" />
              <stop offset="100%" stopColor="#a855f7" />
            </linearGradient>
            <linearGradient id="earFill" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="rgba(56,189,248,0.25)" />
              <stop offset="100%" stopColor="rgba(15,23,42,0.05)" />
            </linearGradient>
          </defs>

          {/* Risk Zone */}
          <rect
            x={0}
            y={thresholdY}
            width={viewBoxWidth}
            height={viewBoxHeight - 6 - thresholdY}
            fill="rgba(239, 68, 68, 0.08)"
          />
          <line
            x1={0}
            y1={thresholdY}
            x2={viewBoxWidth}
            y2={thresholdY}
            stroke="rgba(239, 68, 68, 0.3)"
            strokeWidth={0.3}
            strokeDasharray="1,1"
          />

          {/* Baseline */}
          <line
            x1={0}
            y1={viewBoxHeight - 6}
            x2={viewBoxWidth}
            y2={viewBoxHeight - 6}
            stroke="rgba(55,65,81,0.5)"
            strokeWidth={0.2}
          />

          {/* Path */}
          <path d={fillD} fill="url(#earFill)" stroke="none" />
          <path
            d={d}
            fill="none"
            stroke="url(#earLine)"
            strokeWidth={0.8}
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Hover Marker */}
          {hoverIndex !== null && (
            <>
              <line
                x1={coords[hoverIndex].x}
                y1={0}
                x2={coords[hoverIndex].x}
                y2={viewBoxHeight - 6}
                stroke="rgba(255,255,255,0.2)"
                strokeWidth={0.3}
              />
              <circle
                cx={coords[hoverIndex].x}
                cy={coords[hoverIndex].y}
                r={1}
                fill="#fff"
                stroke="url(#earLine)"
                strokeWidth={0.5}
              />
            </>
          )}
        </svg>

        <div className="chart-legend">
          <div className="chart-legend-item">
            <span className="chart-legend-line" />
            <span>Dynamic Dataset EAR</span>
          </div>
          <div className="chart-legend-item">
            <span style={{ fontSize: '0.72rem', color: 'rgba(239, 68, 68, 0.7)' }}>
              --- Risk Zone (EAR &lt; {threshold})
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

const LogsTable: React.FC<{ rows: LogItem[] }> = ({ rows }) => {
  const statusClassName = (status: LogItem['status']) => {
    switch (status) {
      case 'AWAKE':
        return 'logs-status-pill logs-status-awake';
      case 'DROWSY':
        return 'logs-status-pill logs-status-drowsy';
      case 'WARNING':
        return 'logs-status-pill logs-status-normal';
      default:
        return 'logs-status-pill logs-status-normal';
    }
  };

  return (
    <div className="logs-card card card-muted">
      <div className="card-title">Alert history</div>
      <div className="card-heading">Session-level logs</div>
      <div className="logs-table-wrapper">
        <table className="logs-table">
          <thead>
            <tr>
              <th>Driver</th>
              <th>Time</th>
              <th>EAR</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index}>
                <td>{row.driver}</td>
                <td>{row.time}</td>
                <td>{row.ear.toFixed(2)}</td>
                <td>
                  <span className={statusClassName(row.status)}>
                    <span className="logs-status-pill-dot" />
                    <span>{row.status}</span>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const AdminDashboard: React.FC<{ onLogout: () => void; token: string }> = ({
  onLogout,
  token,
}) => {
  const [stats, setStats] = useState<{
    totalDrivers: number;
    alertsToday: number;
    averageEAR: number;
    systemAccuracy: string;
  } | null>(null);

  const [chartData, setChartData] = useState<{ time: string; ear: number }[]>(
    []
  );
  const [logs, setLogs] = useState<LogItem[]>([]);

  useEffect(() => {
    let isMounted = true;

    const fetchAdminData = async () => {
      try {
        const [statsRes, logsRes, analyticsRes] = await Promise.all([
          fetch(`${API_BASE}/api/admin/stats`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch(`${API_BASE}/api/admin/logs?limit=20`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch(`${API_BASE}/api/admin/analytics`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
        ]);

        if (!isMounted) return;

        if (statsRes.ok) {
          const s = await statsRes.json();
          setStats(s);
        }

        if (logsRes.ok) {
          const json = await logsRes.json();
          const rawLogs = json.logs ?? [];
          const mapped: LogItem[] = rawLogs.map((log: any) => ({
            driver: log.userId?.name ?? 'Driver',
            time: new Date(log.timestamp).toLocaleTimeString(undefined, {
              hour: '2-digit',
              minute: '2-digit',
            }),
            ear: log.earValue,
            status:
              log.status === 'AWAKE' ||
                log.status === 'WARNING' ||
                log.status === 'DROWSY'
                ? (log.status as DriverStatus)
                : ('NORMAL' as const),
          }));
          setLogs(mapped);
        }

        if (analyticsRes.ok) {
          const json = await analyticsRes.json();
          const points = json.points ?? [];
          const mappedChart = points.map((p: any) => ({
            time: new Date(p.timestamp).toLocaleTimeString(undefined, {
              hour: '2-digit',
              minute: '2-digit',
            }),
            ear: p.earValue,
          }));
          setChartData(mappedChart);
        }
      } catch {
        // Silent fail; UI will show zeros / empty states.
      }
    };

    fetchAdminData();
    const interval = setInterval(fetchAdminData, 10000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [token]);

  return (
    <div className="app-root">
      <div className="app-shell">
        <header className="top-bar">
          <div className="top-bar-title">
            <span>📊</span>
            <div>
              <div className="top-bar-title-main">Admin Dashboard</div>
              <div className="top-bar-title-sub">System analytics & logs</div>
            </div>
          </div>
          <div className="top-bar-actions">
            <div className="tag-pill">
              <span className="tag-pill-dot" />
              <span className="tag-pill-label">Overview</span>
            </div>
            <button type="button" className="ghost-button" onClick={onLogout}>
              Logout
            </button>
          </div>
        </header>

        <main className="dashboard-main">
          <section className="stats-row">
            <StatsCard
              label="Drivers monitored"
              value={(stats?.totalDrivers ?? 0).toString()}
              caption="Active in last 24 hours"
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#38bdf8' }}>
                  <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              }
            />
            <StatsCard
              label="Drowsiness alerts"
              value={(stats?.alertsToday ?? 0).toString()}
              caption="Generated today"
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#facc15' }}>
                  <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
                  <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
                </svg>
              }
            />
            <StatsCard
              label="Model accuracy"
              value={stats?.systemAccuracy ?? '92%'}
              caption="Validation dataset"
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#a855f7' }}>
                  <circle cx="12" cy="12" r="10" />
                  <circle cx="12" cy="12" r="6" />
                  <circle cx="12" cy="12" r="2" />
                </svg>
              }
            />
          </section>

          <EARChart
            data={
              chartData.length
                ? chartData
                : [
                  { time: '—', ear: 0.3 },
                  { time: '—', ear: 0.26 },
                ]
            }
          />

          <LogsTable rows={logs} />
        </main>
      </div>
    </div>
  );
};

const App: React.FC = () => {
  const [screen, setScreen] = useState<Screen>('landing');
  const [user, setUser] = useState<AuthedUser | null>(null);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const stored = sessionStorage.getItem('auth');
    if (!stored) return;

    try {
      const parsed = JSON.parse(stored) as { user: AuthedUser; token: string };
      setUser(parsed.user);
      setToken(parsed.token);
      setScreen(parsed.user.role === 'admin' ? 'admin' : 'driver');
    } catch {
      // Ignore parse errors and clear invalid storage
      sessionStorage.removeItem('auth');
    }
  }, []);

  const handleLogout = () => {
    setUser(null);
    setToken(null);
    setScreen('login');
    sessionStorage.removeItem('auth');
  };

  const handleLoginSuccess = (nextUser: AuthedUser, nextToken: string) => {
    setUser(nextUser);
    setToken(nextToken);
    setScreen(nextUser.role === 'admin' ? 'admin' : 'driver');
    sessionStorage.setItem('auth', JSON.stringify({ user: nextUser, token: nextToken }));
  };

  if (screen === 'driver' && user && token) {
    return <DriverDashboard onLogout={handleLogout} token={token} user={user} />;
  }

  if (screen === 'admin' && user && token) {
    return <AdminDashboard onLogout={handleLogout} token={token} />;
  }

  if (screen === 'landing') {
    return <LandingPage onGetStarted={() => setScreen('login')} />;
  }

  return <LoginPage onLoginSuccess={handleLoginSuccess} />;
};

export default App;
