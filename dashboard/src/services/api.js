import axios from 'axios';

const BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export async function fetchClassData() {
  const resp = await axios.get(`${BASE}/api/class-data`);
  return resp.data;
}

export async function setTopic(topic, grade = 6) {
  const resp = await axios.post(`${BASE}/api/set-topic`, { topic, grade });
  return resp.data;
}

export async function fetchStatus() {
  const resp = await axios.get(`${BASE}/api/status`);
  return resp.data;
}

export async function clearSession() {
  await axios.delete(`${BASE}/api/session`);
}

export async function obsidianQuery(query, imagePath = null) {
  const resp = await axios.post(`${BASE}/api/obsidian/query`, { query, image_path: imagePath });
  return resp.data.answer;
}

export async function triggerReindex() {
  const resp = await axios.post(`${BASE}/api/obsidian/index`);
  return resp.data;
}

export function createWebSocket() {
  const wsBase = BASE.replace(/^http/, 'ws');
  return new WebSocket(`${wsBase}/ws/dashboard`);
}
