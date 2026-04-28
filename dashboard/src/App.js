import React, { useCallback, useEffect, useRef, useState } from 'react';
import ActionItems from './components/ActionItems';
import GapChart from './components/GapChart';
import MetricCards from './components/MetricCards';
import ObsidianChat from './components/ObsidianChat';
import StudentTable from './components/StudentTable';
import { clearSession, createWebSocket, fetchClassData, fetchStatus, setTopic } from './services/api';

const TOPICS = ['photosynthesis', 'water_cycle', 'food_chain'];

export default function App() {
  const [students, setStudents] = useState([]);
  const [status, setStatus] = useState({});
  const [topic, setTopicState] = useState('photosynthesis');
  const [wsConnected, setWsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const wsRef = useRef(null);

  const loadData = useCallback(async () => {
    try {
      const data = await fetchClassData();
      setStudents(data.students || []);
      setLastUpdate(new Date());
    } catch {}
  }, []);

  useEffect(() => {
    loadData();
    fetchStatus().then(setStatus).catch(() => {});

    function connect() {
      try {
        const ws = createWebSocket();
        wsRef.current = ws;
        ws.onopen = () => setWsConnected(true);
        ws.onclose = () => { setWsConnected(false); setTimeout(connect, 3000); };
        ws.onerror = () => ws.close();
        ws.onmessage = (e) => {
          const msg = JSON.parse(e.data);
          if (msg.type === 'init') {
            setStudents(msg.students || []);
          } else if (msg.type === 'new_result') {
            setStudents(prev => {
              const idx = prev.findIndex(s => s.student_id === msg.data.student_id);
              if (idx >= 0) { const next = [...prev]; next[idx] = msg.data; return next; }
              return [...prev, msg.data];
            });
            setLastUpdate(new Date());
          }
        };
      } catch {}
    }

    connect();
    const poll = setInterval(loadData, 10000);
    return () => { clearInterval(poll); wsRef.current?.close(); };
  }, [loadData]);

  async function handleTopicChange(t) {
    setTopicState(t);
    try { await setTopic(t); } catch {}
  }

  async function handleClear() {
    if (!window.confirm('Clear all student data for this session?')) return;
    await clearSession();
    setStudents([]);
  }

  function exportCSV() {
    const header = ['ID', 'Name', 'Topic', 'Fingerprint', 'Drift', 'Language', 'Timestamp'].join(',');
    const rows = students.map(s =>
      [s.student_id, s.student_name, s.topic, s.fingerprint, s.drift_score, s.language, s.timestamp].join(',')
    );
    const blob = new Blob([[header, ...rows].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'echo_session.csv'; a.click();
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0a0a14' }}>
      {/* Nav */}
      <nav style={{
        background: '#1a1a2e', borderBottom: '1px solid #1e293b',
        padding: '0 24px', display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', height: 60, position: 'sticky', top: 0, zIndex: 100,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ color: '#818cf8', fontSize: 20, fontWeight: 900, letterSpacing: 3 }}>ECHO</span>
          <span style={{ color: '#334155', fontSize: 14 }}>Teacher Dashboard</span>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: wsConnected ? '#10b981' : '#f59e0b',
          }} title={wsConnected ? 'Live' : 'Polling'} />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <select
            value={topic}
            onChange={e => handleTopicChange(e.target.value)}
            style={{
              background: '#0f0f1a', border: '1px solid #1e293b', borderRadius: 10,
              color: '#e2e8f0', padding: '6px 12px', fontSize: 14, cursor: 'pointer',
            }}
          >
            {TOPICS.map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
          </select>
          <button onClick={exportCSV} style={navBtn}>Export CSV</button>
          <button onClick={handleClear} style={{ ...navBtn, borderColor: '#ef4444', color: '#ef4444' }}>
            Clear session
          </button>
        </div>
      </nav>

      <div style={{ padding: '24px', maxWidth: 1400, margin: '0 auto' }}>
        {/* Status bar */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
          {lastUpdate && (
            <span style={{ color: '#475569', fontSize: 12 }}>
              Last update: {lastUpdate.toLocaleTimeString()}
            </span>
          )}
          {status.ollama !== undefined && (
            <StatusPill label="Ollama" ok={status.ollama} />
          )}
          {status.mongo !== undefined && (
            <StatusPill label="MongoDB" ok={status.mongo} />
          )}
          {status.redis !== undefined && (
            <StatusPill label="Redis" ok={status.redis} />
          )}
          {status.obsidian_configured !== undefined && (
            <StatusPill label="Obsidian vault" ok={status.obsidian_configured} />
          )}
        </div>

        {/* Metric cards */}
        <MetricCards students={students} />

        {/* Two-column: chart + actions */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
          <GapChart students={students} />
          <ActionItems students={students} />
        </div>

        {/* Obsidian chat + student table */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: 16, marginBottom: 20 }}>
          <ObsidianChat />
          <StudentTable students={students} />
        </div>
      </div>
    </div>
  );
}

function StatusPill({ label, ok }) {
  return (
    <span style={{
      fontSize: 11, padding: '3px 10px', borderRadius: 20,
      background: ok ? '#10b98122' : '#ef444422',
      color: ok ? '#10b981' : '#ef4444',
      border: `1px solid ${ok ? '#10b981' : '#ef4444'}`,
    }}>
      {label}: {ok ? 'OK' : 'offline'}
    </span>
  );
}

const navBtn = {
  background: 'transparent', border: '1px solid #334155', borderRadius: 8,
  color: '#94a3b8', fontSize: 13, padding: '6px 14px', cursor: 'pointer',
};
