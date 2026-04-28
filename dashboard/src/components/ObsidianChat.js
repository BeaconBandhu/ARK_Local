import React, { useRef, useState } from 'react';
import { obsidianQuery, triggerReindex } from '../services/api';

export default function ObsidianChat() {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const bottomRef = useRef(null);

  async function send() {
    if (!query.trim() || loading) return;
    const q = query.trim();
    setQuery('');
    setMessages(m => [...m, { role: 'user', text: q }]);
    setLoading(true);
    try {
      const answer = await obsidianQuery(q);
      setMessages(m => [...m, { role: 'assistant', text: answer }]);
    } catch {
      setMessages(m => [...m, { role: 'assistant', text: 'Could not reach Ollama. Is the backend running?' }]);
    } finally {
      setLoading(false);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
    }
  }

  async function reindex() {
    setIndexing(true);
    try {
      const r = await triggerReindex();
      setMessages(m => [...m, { role: 'system', text: `Indexed ${r.indexed} vault files.` }]);
    } catch {
      setMessages(m => [...m, { role: 'system', text: 'Reindex failed — check vault path in .env' }]);
    } finally {
      setIndexing(false);
    }
  }

  return (
    <div style={{ background: '#1a1a2e', borderRadius: 16, padding: 20, display: 'flex', flexDirection: 'column', height: 420 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <p style={{ color: '#64748b', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1 }}>
          Obsidian Vault Chat
        </p>
        <button
          onClick={reindex}
          disabled={indexing}
          style={{
            background: '#1e293b', border: '1px solid #334155', borderRadius: 8,
            color: '#94a3b8', fontSize: 12, padding: '5px 12px', cursor: 'pointer',
          }}
        >
          {indexing ? 'Indexing...' : 'Re-index vault'}
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 12 }}>
        {messages.length === 0 && (
          <p style={{ color: '#334155', fontSize: 13, textAlign: 'center', margin: 'auto' }}>
            Ask ECHO anything from your Obsidian notes...
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{
            alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
            background: m.role === 'user' ? '#6366f1' : m.role === 'system' ? '#1e293b' : '#0f172a',
            borderRadius: m.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
            padding: '10px 14px', maxWidth: '80%',
            border: m.role === 'system' ? '1px solid #334155' : 'none',
          }}>
            <p style={{ color: m.role === 'user' ? '#fff' : '#94a3b8', fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
              {m.text}
            </p>
          </div>
        ))}
        {loading && (
          <div style={{ alignSelf: 'flex-start', color: '#6366f1', fontSize: 13 }}>
            ECHO is thinking...
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          placeholder="Ask about your notes, lessons, images..."
          style={{
            flex: 1, background: '#0f0f1a', border: '1px solid #1e293b',
            borderRadius: 10, padding: '10px 14px', color: '#e2e8f0', fontSize: 14,
          }}
        />
        <button
          onClick={send}
          disabled={loading}
          style={{
            background: '#6366f1', border: 'none', borderRadius: 10,
            color: '#fff', fontWeight: 700, padding: '0 20px', cursor: 'pointer',
            opacity: loading ? 0.6 : 1,
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
