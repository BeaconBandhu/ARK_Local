'use strict';

const IDB_NAME  = 'ark_offline';
const IDB_VER   = 1;
const IDB_STORE = 'pending_queue';
const SYNC_TAG  = 'ark-sync';

// ── IndexedDB helpers ────────────────────────────────────────────────────────

function openIDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_NAME, IDB_VER);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(IDB_STORE)) {
        db.createObjectStore(IDB_STORE, { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = e => resolve(e.target.result);
    req.onerror   = e => reject(e.target.error);
  });
}

function idbGetAll(db) {
  return new Promise((resolve, reject) => {
    const req = db.transaction(IDB_STORE, 'readonly').objectStore(IDB_STORE).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror   = () => reject(req.error);
  });
}

function idbDelete(db, id) {
  return new Promise((resolve, reject) => {
    const req = db.transaction(IDB_STORE, 'readwrite').objectStore(IDB_STORE).delete(id);
    req.onsuccess = () => resolve();
    req.onerror   = () => reject(req.error);
  });
}

// ── Flush queue → /analyse ───────────────────────────────────────────────────

async function flushQueue() {
  const db    = await openIDB();
  const items = await idbGetAll(db);
  let   sent  = 0;

  for (const item of items) {
    try {
      const res = await fetch('/analyse', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(item.data),
      });
      if (res.ok) {
        await idbDelete(db, item.id);
        sent++;
      }
    } catch (_) {
      // Network still down — keep item, retry on next sync event
    }
  }

  const remaining = items.length - sent;

  // Notify all open ARK tabs
  const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  clients.forEach(c => c.postMessage({ type: 'ARK_SYNC_DONE', sent, remaining }));
}

// ── Lifecycle ────────────────────────────────────────────────────────────────

self.addEventListener('install',  ()  => self.skipWaiting());
self.addEventListener('activate', e   => e.waitUntil(self.clients.claim()));

// Background Sync API — fires when browser regains connectivity
self.addEventListener('sync', evt => {
  if (evt.tag === SYNC_TAG) evt.waitUntil(flushQueue());
});
