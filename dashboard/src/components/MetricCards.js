import React from 'react';

function Card({ label, value, sub, color }) {
  return (
    <div style={{
      background: '#1a1a2e', borderRadius: 16, padding: '20px 24px',
      borderLeft: `4px solid ${color}`, flex: '1 1 160px', minWidth: 140,
    }}>
      <p style={{ color: '#64748b', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>{label}</p>
      <p style={{ fontSize: 32, fontWeight: 800, color, lineHeight: 1 }}>{value}</p>
      {sub && <p style={{ color: '#64748b', fontSize: 13, marginTop: 6 }}>{sub}</p>}
    </div>
  );
}

export default function MetricCards({ students, totalExpected = 30 }) {
  const answered = students.length;
  const understood = students.filter(s => s.drift_score < 0.3).length;
  const critical = students.filter(s => s.drift_score >= 0.7).length;
  const avgDrift = answered
    ? (students.reduce((a, s) => a + s.drift_score, 0) / answered).toFixed(2)
    : '—';

  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 24 }}>
      <Card label="Students answered" value={`${answered}/${totalExpected}`} color="#6366f1" />
      <Card label="Fully understood" value={understood} sub="drift < 0.3" color="#10b981" />
      <Card label="Critical gaps" value={critical} sub="drift ≥ 0.7" color="#ef4444" />
      <Card label="Average drift" value={avgDrift} sub="0 = perfect, 1 = lost" color="#f59e0b" />
    </div>
  );
}
