import React from 'react';

const FP_ACTIONS = {
  INVERT:   'Spend 5 min on the partner analogy — explain that plants and humans swap gases (plants in CO2, out O2).',
  GHOST:    'These students have a strong but wrong belief. Direct contradiction with evidence works best — show a real experiment.',
  HOLLOW:   'Students know the words but not the steps. Make them draw the process or act it out physically.',
  FRAGMENT: 'Identify which one link is missing per student. Peer-pair them with students who have that node activated.',
  ORPHAN:   'The problem is upstream — go back to the prerequisite concept before re-teaching this topic.',
};

const FP_COLORS = {
  INVERT:   '#ef4444',
  GHOST:    '#f59e0b',
  HOLLOW:   '#3b82f6',
  FRAGMENT: '#10b981',
  ORPHAN:   '#8b5cf6',
};

export default function ActionItems({ students }) {
  const grouped = {};
  for (const s of students) {
    const fp = s.fingerprint;
    if (!grouped[fp]) grouped[fp] = [];
    grouped[fp].push(s);
  }

  const ready = students.filter(s => s.drift_score < 0.3);
  const sorted = Object.entries(grouped).sort((a, b) => b[1].length - a[1].length);

  return (
    <div style={{ background: '#1a1a2e', borderRadius: 16, padding: 20 }}>
      <p style={{ color: '#64748b', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
        Action items
      </p>

      {sorted.length === 0 && (
        <p style={{ color: '#475569', fontSize: 14 }}>No student data yet. Waiting for submissions...</p>
      )}

      {sorted.map(([fp, group]) => (
        <div key={fp} style={{
          borderLeft: `3px solid ${FP_COLORS[fp]}`,
          background: FP_COLORS[fp] + '11',
          borderRadius: '0 12px 12px 0',
          padding: '12px 16px',
          marginBottom: 10,
        }}>
          <p style={{ color: FP_COLORS[fp], fontWeight: 700, fontSize: 13, marginBottom: 4 }}>
            {group.length} student{group.length !== 1 ? 's' : ''} — {fp}
          </p>
          <p style={{ color: '#94a3b8', fontSize: 13, lineHeight: 1.5 }}>{FP_ACTIONS[fp]}</p>
          <p style={{ color: '#475569', fontSize: 11, marginTop: 6 }}>
            {group.map(s => s.student_name).join(', ')}
          </p>
        </div>
      ))}

      {ready.length > 0 && (
        <div style={{
          borderLeft: '3px solid #10b981',
          background: '#10b98111',
          borderRadius: '0 12px 12px 0',
          padding: '12px 16px',
        }}>
          <p style={{ color: '#10b981', fontWeight: 700, fontSize: 13, marginBottom: 4 }}>
            {ready.length} student{ready.length !== 1 ? 's' : ''} ready — assign as peer helpers
          </p>
          <p style={{ color: '#475569', fontSize: 11 }}>
            {ready.map(s => s.student_name).join(', ')}
          </p>
        </div>
      )}
    </div>
  );
}
