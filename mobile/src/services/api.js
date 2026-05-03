import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import * as Network from 'expo-network';

// Fixed server — IP and port are locked, no one can override them
export const SERVER_URL = 'http://10.13.231.31:8000';

export async function getBaseUrl() {
  return SERVER_URL;
}

// No-op — URL is locked to the WiFi IP above
export async function setBaseUrl(_url) {}

export async function isOnline() {
  const state = await Network.getNetworkStateAsync();
  return state.isConnected && state.isInternetReachable;
}

export async function analyseAnswer({ student_id, student_name, topic, answer_text, language }) {
  const online = await isOnline();
  const baseUrl = await getBaseUrl();

  const payload = { student_id, student_name, topic, answer_text, language, offline: !online };

  if (!online) {
    return await offlineAnalyse(payload);
  }

  try {
    const resp = await axios.post(`${baseUrl}/analyse`, payload, { timeout: 60000 });
    return resp.data;
  } catch (err) {
    console.warn('Server unreachable, falling back to offline:', err.message);
    return await offlineAnalyse(payload);
  }
}

async function offlineAnalyse(payload) {
  const cache = await loadOfflineCache();
  const key = `${payload.topic}_${guessFingerprintOffline(payload.answer_text, payload.topic)}`;
  const cached = cache[key];

  const result = {
    student_id: payload.student_id,
    student_name: payload.student_name,
    topic: payload.topic,
    fingerprint: key.split('_').pop() || 'FRAGMENT',
    drift_score: 0.5,
    activated_nodes: [],
    skipped_nodes: [],
    what_they_said: payload.answer_text,
    what_is_wrong: cached?.what_is_wrong || 'Your answer needs more detail.',
    story_fix: cached?.story_fix || 'Think about this topic step by step.',
    follow_up_question: cached?.follow_up_question || 'Can you explain more?',
    peer_suggestion: '',
    language: payload.language,
    timestamp: new Date().toISOString(),
    offline: true,
  };

  await queueForSync(result);
  return result;
}

function guessFingerprintOffline(text, topic) {
  const t = text.toLowerCase();
  if (topic === 'photosynthesis') {
    if (t.includes('release co2') || t.includes('give out co2')) return 'INVERT';
    if (t.includes('sunlight') && !t.includes('co2') && !t.includes('water')) return 'HOLLOW';
  }
  if (topic === 'water_cycle') {
    if (t.includes('evaporation') && t.includes('condensation')) return 'FRAGMENT';
  }
  return 'FRAGMENT';
}

async function loadOfflineCache() {
  try {
    const raw = await AsyncStorage.getItem('echo_offline_cache');
    if (raw) return JSON.parse(raw);
  } catch {}
  return {};
}

export async function syncOfflineQueue() {
  const online = await isOnline();
  if (!online) return { synced: 0 };

  const raw = await AsyncStorage.getItem('echo_sync_queue');
  if (!raw) return { synced: 0 };

  const queue = JSON.parse(raw);
  if (!queue.length) return { synced: 0 };

  const baseUrl = await getBaseUrl();
  let synced = 0;
  const remaining = [];

  for (const item of queue) {
    try {
      await axios.post(`${baseUrl}/analyse`, { ...item, offline: false }, { timeout: 15000 });
      synced++;
    } catch {
      remaining.push(item);
    }
  }

  await AsyncStorage.setItem('echo_sync_queue', JSON.stringify(remaining));
  return { synced };
}

async function queueForSync(result) {
  const raw = await AsyncStorage.getItem('echo_sync_queue');
  const queue = raw ? JSON.parse(raw) : [];
  queue.push(result);
  await AsyncStorage.setItem('echo_sync_queue', JSON.stringify(queue));
}

export async function getCurrentTopic(baseUrl) {
  try {
    const resp = await axios.get(`${baseUrl}/api/current-topic`, { timeout: 5000 });
    return resp.data;
  } catch {
    return null;
  }
}

export async function transcribeVoice(audioUri, language, baseUrl) {
  const formData = new FormData();
  formData.append('audio', { uri: audioUri, type: 'audio/m4a', name: 'answer.m4a' });
  formData.append('language', language);
  const resp = await axios.post(`${baseUrl}/api/voice-transcribe`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000,
  });
  return resp.data.transcript || '';
}

export async function sendImageChat(question, imageUri, baseUrl) {
  const formData = new FormData();
  formData.append('question', question);
  if (imageUri) {
    formData.append('image', { uri: imageUri, type: 'image/jpeg', name: 'image.jpg' });
  }
  const resp = await axios.post(`${baseUrl}/api/image-chat`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 90000,
  });
  return resp.data.answer || '';
}

export async function primeOfflineCache(baseUrl) {
  try {
    const resp = await axios.get(`${baseUrl}/api/offline-cache`, { timeout: 10000 });
    await AsyncStorage.setItem('echo_offline_cache', JSON.stringify(resp.data));
  } catch {}
}
