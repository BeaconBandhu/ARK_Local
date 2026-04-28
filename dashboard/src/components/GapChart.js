import { ArcElement, BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, Tooltip } from 'chart.js';
import React from 'react';
import { Bar } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Tooltip, Legend);

const FP_COLORS = {
  INVERT:   '#ef4444',
  GHOST:    '#f59e0b',
  HOLLOW:   '#3b82f6',
  FRAGMENT: '#10b981',
  ORPHAN:   '#8b5cf6',
};

const LABELS = ['INVERT', 'GHOST', 'HOLLOW', 'FRAGMENT', 'ORPHAN'];

export default function GapChart({ students }) {
  const counts = LABELS.map(fp => students.filter(s => s.fingerprint === fp).length);

  const data = {
    labels: LABELS,
    datasets: [{
      label: 'Students',
      data: counts,
      backgroundColor: LABELS.map(fp => FP_COLORS[fp] + 'cc'),
      borderColor: LABELS.map(fp => FP_COLORS[fp]),
      borderWidth: 2,
      borderRadius: 8,
    }],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: ctx => ` ${ctx.raw} students` } },
    },
    scales: {
      x: { grid: { color: '#1e293b' }, ticks: { color: '#94a3b8' } },
      y: { grid: { color: '#1e293b' }, ticks: { color: '#94a3b8', stepSize: 1 }, beginAtZero: true },
    },
  };

  return (
    <div style={{ background: '#1a1a2e', borderRadius: 16, padding: 20, height: 260 }}>
      <p style={{ color: '#64748b', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
        Gap distribution
      </p>
      <Bar data={data} options={options} height={180} />
    </div>
  );
}
