import React, { useState } from 'react';

const FP_COLORS = {
  INVERT:   '#ef4444',
  GHOST:    '#f59e0b',
  HOLLOW:   '#3b82f6',
  FRAGMENT: '#10b981',
  ORPHAN:   '#8b5cf6',
};

function Badge({ type }) {
  const color = FP_COLORS[type] || '#6b7280';
  return (
    <span style={{
      background: color + '22', color, border: `1px solid ${color}`,
      borderRadius: 6, padding: '2px 8px', fontSize: 11, fontWeight: 700, letterSpacing: 1,
    }}>
      {type}
    </span>
  );
}

function DriftBar({ score }) {
  const color = score >= 0.7 ? '#ef4444' : score >= 0.4 ? '#f59e0b' : '#10b981';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width: 80, height: 6, background: '#0f0f1a', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${score * 100}%`, height: '100%', background: color, borderRadius: 3 }} />
      </div>
      <span style={{ color: '#94a3b8', fontSize: 12 }}>{score.toFixed(2)}</span>
    </div>
  );
}

function initials(name) {
  return name.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase();
}

export default function StudentTable({ students }) {
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState(null);

  const filtered = students.filter(s =>
    s.student_name?.toLowerCase().includes(search.toLowerCase()) ||
    s.student_id?.toLowerCase().includes(search.toLowerCase()) ||
    s.fingerprint?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div style={{ background: '#1a1a2e', borderRadius: 16, padding: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <p style={{ color: '#64748b', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1 }}>
          Student results ({filtered.length})
        </p>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search name, ID or fingerprint..."
          style={{
            background: '#0f0f1a', border: '1px solid #1e293b', borderRadius: 10,
            padding: '8px 14px', color: '#e2e8f0', fontSize: 13, width: 260,
          }}
        />
      </div>

      {filtered.length === 0 && (
        <p style={{ color: '#475569', fontSize: 14, textAlign: 'center', padding: 32 }}>
          No students yet. Waiting for submissions...
        </p>
      )}

      {filtered.map(student => (
        <div key={student.student_id}>
          <div
            style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0',
              borderBottom: '1px solid #1e293b', cursor: 'pointer',
            }}
            onClick={() => setExpanded(expanded === student.student_id ? null : student.student_id)}
          >
            <div style={{
              width: 36, height: 36, borderRadius: '50%',
              background: (FP_COLORS[student.fingerprint] || '#6366f1') + '33',
              border: `2px solid ${FP_COLORS[student.fingerprint] || '#6366f1'}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: FP_COLORS[student.fingerprint] || '#6366f1',
              fontSize: 13, fontWeight: 700, flexShrink: 0,
            }}>
              {initials(student.student_name || 'S?')}
            </div>

            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ color: '#e2e8f0', fontWeight: 600, fontSize: 14 }}>{student.student_name}</p>
              <p style={{ color: '#475569', fontSize: 11 }}>{student.student_id} · {student.topic}</p>
            </div>

            <Badge type={student.fingerprint} />
            <DriftBar score={student.drift_score || 0} />

            <span style={{ color: '#475569', fontSize: 18 }}>
              {expanded === student.student_id ? '▲' : '▼'}
            </span>
          </div>

          {expanded === student.student_id && (
            <div style={{
              background: '#0f0f1a', borderRadius: 12, padding: 20, margin: '8px 0 16px',
              border: '1px solid #1e293b', fontSize: 13,
            }}>
              <Row label="What they said" value={student.what_they_said} italic />
              <Row label="What is wrong" value={student.what_is_wrong} color="#fca5a5" />
              <Row label="Story fix" value={student.story_fix} color="#c4b5fd" />
              <Row label="Follow-up question" value={student.follow_up_question} color="#7dd3fc" />
              {student.peer_suggestion && <Row label="Peer suggestion" value={student.peer_suggestion} color="#6ee7b7" />}
              <Row label="Activated nodes" value={(student.activated_nodes || []).join(', ') || '—'} />
              <Row label="Skipped nodes" value={(student.skipped_nodes || []).join(', ') || '—'} color="#fca5a5" />
              <Row label="Language" value={student.language} />
              <Row label="Time" value={student.timestamp ? new Date(student.timestamp).toLocaleTimeString() : '—'} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function Row({ label, value, color, italic }) {
  return (
    <div style={{ display: 'flex', gap: 12, marginBottom: 10 }}>
      <span style={{ color: '#475569', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, width: 130, flexShrink: 0 }}>
        {label}
      </span>
      <span style={{ color: color || '#94a3b8', lineHeight: 1.5, fontStyle: italic ? 'italic' : 'normal' }}>
        {value || '—'}
      </span>
    </div>
  );
}
