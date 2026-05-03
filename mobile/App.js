import AsyncStorage from '@react-native-async-storage/async-storage';
import * as ImagePicker from 'expo-image-picker';
import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator, Alert, Dimensions, FlatList, Image,
  KeyboardAvoidingView, Platform, ScrollView, StatusBar, StyleSheet,
  Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import axios from 'axios';

const { width } = Dimensions.get('window');

const FP_COLORS = {
  INVERT: '#ef4444', GHOST: '#f59e0b',
  HOLLOW: '#3b82f6', FRAGMENT: '#10b981', ORPHAN: '#8b5cf6',
};
const FP_DESC = {
  INVERT: 'Flipped understanding', GHOST: 'Wrong belief',
  HOLLOW: 'Right words, no meaning', FRAGMENT: 'Partial understanding', ORPHAN: 'Missing foundation',
};
const TOPICS = ['photosynthesis', 'water_cycle', 'food_chain'];
const LANGUAGES = ['english', 'kannada', 'hindi'];

// ── Screen IDs ────────────────────────────────────────────────────
const SCREEN = { SETUP: 'setup', HOME: 'home', RESULT: 'result', CHAT: 'chat' };

export default function App() {
  const [screen, setScreen] = useState(SCREEN.SETUP);
  const [serverUrl, setServerUrl] = useState('http://192.168.31.18:8000');
  const [studentId, setStudentId] = useState('');
  const [studentName, setStudentName] = useState('');
  const [topic, setTopic] = useState('photosynthesis');
  const [language, setLanguage] = useState('english');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [serverOk, setServerOk] = useState(null);

  useEffect(() => { loadSaved(); }, []);

  async function loadSaved() {
    const id = await AsyncStorage.getItem('ark_student_id');
    const name = await AsyncStorage.getItem('ark_student_name');
    const url = await AsyncStorage.getItem('ark_server_url');
    if (id) setStudentId(id);
    if (name) setStudentName(name);
    if (url) setServerUrl(url);
    if (id && name) setScreen(SCREEN.HOME);
  }

  async function saveAndContinue() {
    if (!studentId.trim() || !studentName.trim() || !serverUrl.trim()) {
      Alert.alert('Required', 'Fill in all fields before continuing.'); return;
    }
    await AsyncStorage.multiSet([
      ['ark_student_id', studentId.trim()],
      ['ark_student_name', studentName.trim()],
      ['ark_server_url', serverUrl.trim()],
    ]);
    pingServer(serverUrl.trim());
    setScreen(SCREEN.HOME);
  }

  async function pingServer(url) {
    try {
      await axios.get(`${url}/api/status`, { timeout: 4000 });
      setServerOk(true);
    } catch { setServerOk(false); }
  }

  async function submitAnswer() {
    if (!answer.trim()) { Alert.alert('Required', 'Please type your answer.'); return; }
    setLoading(true);
    try {
      const url = await AsyncStorage.getItem('ark_server_url') || serverUrl;
      const resp = await axios.post(`${url}/analyse`, {
        student_id: studentId,
        student_name: studentName,
        topic, answer_text: answer.trim(), language,
      }, { timeout: 60000 });
      setResult(resp.data);
      setAnswer('');
      setScreen(SCREEN.RESULT);
    } catch (e) {
      Alert.alert('Server unreachable',
        `Make sure the PC backend is running.\nURL: ${serverUrl}\n\nError: ${e.message}`);
    } finally { setLoading(false); }
  }

  // ── SETUP SCREEN ─────────────────────────────────────────────
  if (screen === SCREEN.SETUP) return (
    <KeyboardAvoidingView style={s.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <StatusBar barStyle="light-content" backgroundColor="#0a0a14" />
      <ScrollView contentContainerStyle={s.center}>
        <Text style={s.logo}>ARK</Text>
        <Text style={s.subtitle}>Student Setup</Text>

        <Text style={s.label}>Student ID</Text>
        <TextInput style={s.input} value={studentId} onChangeText={setStudentId}
          placeholder="e.g. S12" placeholderTextColor="#475569" autoCapitalize="characters" />

        <Text style={s.label}>Your Name</Text>
        <TextInput style={s.input} value={studentName} onChangeText={setStudentName}
          placeholder="e.g. Priya R." placeholderTextColor="#475569" />

        <Text style={s.label}>Server URL (PC's IP address)</Text>
        <TextInput style={s.input} value={serverUrl} onChangeText={setServerUrl}
          placeholder="http://192.168.x.x:8000" placeholderTextColor="#475569"
          autoCapitalize="none" keyboardType="url" />
        <Text style={{ color: '#475569', fontSize: 11, marginBottom: 16, alignSelf: 'flex-start' }}>
          Find your PC IP: run "ipconfig" → look for IPv4 Address
        </Text>

        <TouchableOpacity style={s.btn} onPress={saveAndContinue}>
          <Text style={s.btnText}>Start →</Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );

  // ── HOME SCREEN ───────────────────────────────────────────────
  if (screen === SCREEN.HOME) return (
    <KeyboardAvoidingView style={s.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <StatusBar barStyle="light-content" backgroundColor="#0a0a14" />
      <ScrollView contentContainerStyle={{ padding: 20, paddingBottom: 40 }}>

        {/* Header */}
        <View style={s.header}>
          <Text style={s.logo}>ARK</Text>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {LANGUAGES.map(l => (
              <TouchableOpacity key={l} style={[s.pill, language === l && s.pillActive]}
                onPress={() => setLanguage(l)}>
                <Text style={[s.pillText, language === l && s.pillTextActive]}>
                  {l === 'english' ? 'EN' : l === 'kannada' ? 'KN' : 'HI'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          {serverOk !== null && (
            <View style={[s.dot, { backgroundColor: serverOk ? '#10b981' : '#ef4444' }]} />
          )}
        </View>

        {/* Student info */}
        <View style={s.card}>
          <Text style={s.cardLabel}>Student</Text>
          <Text style={{ color: '#e2e8f0', fontSize: 15, fontWeight: '600' }}>{studentName}</Text>
          <Text style={{ color: '#64748b', fontSize: 12 }}>{studentId}</Text>
        </View>

        {/* Topic selector */}
        <View style={s.card}>
          <Text style={s.cardLabel}>Topic</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {TOPICS.map(t => (
              <TouchableOpacity key={t} style={[s.pill, topic === t && s.pillActive]}
                onPress={() => setTopic(t)}>
                <Text style={[s.pillText, topic === t && s.pillTextActive]}>
                  {t.replace('_', ' ')}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Question */}
        <View style={s.card}>
          <Text style={s.cardLabel}>Question</Text>
          <Text style={{ color: '#e2e8f0', fontSize: 16, lineHeight: 24 }}>
            {topic === 'photosynthesis' && 'Explain how plants make their own food using sunlight.'}
            {topic === 'water_cycle' && 'Describe how water moves from earth to sky and back again.'}
            {topic === 'food_chain' && 'Explain how energy moves from the sun through living things.'}
          </Text>
        </View>

        {/* Answer */}
        <View style={s.card}>
          <Text style={s.cardLabel}>Your Answer</Text>
          <TextInput
            style={s.answerInput}
            multiline value={answer} onChangeText={setAnswer}
            placeholder="Type your answer here..."
            placeholderTextColor="#475569"
            textAlignVertical="top"
          />
        </View>

        {/* Submit */}
        <TouchableOpacity style={[s.btn, loading && { opacity: 0.6 }]}
          onPress={submitAnswer} disabled={loading}>
          {loading
            ? <ActivityIndicator color="#fff" />
            : <Text style={s.btnText}>Analyse my answer →</Text>}
        </TouchableOpacity>

        {/* Image chat */}
        <TouchableOpacity style={s.outlineBtn} onPress={() => setScreen(SCREEN.CHAT)}>
          <Text style={s.outlineBtnText}>Image Chat (ask about a photo)</Text>
        </TouchableOpacity>

        {/* Change settings */}
        <TouchableOpacity onPress={() => setScreen(SCREEN.SETUP)} style={{ alignItems: 'center', marginTop: 16 }}>
          <Text style={{ color: '#475569', fontSize: 13 }}>Change server / profile</Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );

  // ── RESULT SCREEN ─────────────────────────────────────────────
  if (screen === SCREEN.RESULT && result) {
    const color = FP_COLORS[result.fingerprint] || '#6366f1';
    const pct = Math.round((result.drift_score || 0) * 100);
    return (
      <ScrollView style={s.container} contentContainerStyle={{ padding: 20, paddingBottom: 40 }}>
        <StatusBar barStyle="light-content" backgroundColor="#0a0a14" />

        <View style={s.header}>
          <Text style={s.logo}>ARK</Text>
          <Text style={{ color: '#64748b', fontSize: 13 }}>{result.student_name}</Text>
        </View>

        {/* Fingerprint */}
        <View style={[s.card, { borderLeftWidth: 4, borderLeftColor: color }]}>
          <Text style={s.cardLabel}>Understanding type</Text>
          <View style={[s.badge, { backgroundColor: color + '22', borderColor: color }]}>
            <Text style={[s.badgeText, { color }]}>{result.fingerprint}</Text>
          </View>
          <Text style={{ color: '#94a3b8', fontSize: 13, marginTop: 6 }}>
            {FP_DESC[result.fingerprint]}
          </Text>
          <View style={{ marginTop: 14 }}>
            <Text style={{ color: '#64748b', fontSize: 12, marginBottom: 6 }}>
              Drift score — {pct}%
            </Text>
            <View style={{ height: 8, backgroundColor: '#0f172a', borderRadius: 4, overflow: 'hidden' }}>
              <View style={{ height: '100%', width: `${pct}%`, backgroundColor: color, borderRadius: 4 }} />
            </View>
          </View>
        </View>

        {/* You said */}
        <View style={s.card}>
          <Text style={s.cardLabel}>You said</Text>
          <Text style={{ color: '#94a3b8', fontSize: 14, fontStyle: 'italic', lineHeight: 22 }}>
            {result.what_they_said}
          </Text>
        </View>

        {/* What's wrong */}
        {!!result.what_is_wrong && (
          <View style={[s.card, { borderLeftWidth: 3, borderLeftColor: '#ef4444' }]}>
            <Text style={s.cardLabel}>What needs correcting</Text>
            <Text style={{ color: '#fca5a5', fontSize: 14, lineHeight: 22 }}>{result.what_is_wrong}</Text>
          </View>
        )}

        {/* Story fix */}
        {!!result.story_fix && (
          <View style={[s.card, { borderLeftWidth: 3, borderLeftColor: '#8b5cf6' }]}>
            <Text style={s.cardLabel}>Think of it this way</Text>
            <Text style={{ color: '#c4b5fd', fontSize: 14, lineHeight: 22 }}>{result.story_fix}</Text>
          </View>
        )}

        {/* Follow-up */}
        {!!result.follow_up_question && (
          <View style={[s.card, { borderLeftWidth: 3, borderLeftColor: '#3b82f6' }]}>
            <Text style={s.cardLabel}>Question for you</Text>
            <Text style={{ color: '#7dd3fc', fontSize: 15, lineHeight: 22, fontStyle: 'italic' }}>
              {result.follow_up_question}
            </Text>
          </View>
        )}

        {/* Nodes */}
        {(result.activated_nodes?.length > 0 || result.skipped_nodes?.length > 0) && (
          <View style={s.card}>
            <Text style={s.cardLabel}>Concept nodes</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
              {(result.activated_nodes || []).map(n => (
                <View key={n} style={[s.chip, { borderColor: '#10b981', backgroundColor: '#10b98122' }]}>
                  <Text style={{ color: '#10b981', fontSize: 11 }}>{n.replace(/_/g, ' ')}</Text>
                </View>
              ))}
              {(result.skipped_nodes || []).map(n => (
                <View key={n} style={[s.chip, { borderColor: '#ef4444', backgroundColor: '#ef444422' }]}>
                  <Text style={{ color: '#ef4444', fontSize: 11 }}>{n.replace(/_/g, ' ')}</Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* Peer suggestion */}
        {!!result.peer_suggestion && (
          <View style={[s.card, { borderLeftWidth: 3, borderLeftColor: '#10b981' }]}>
            <Text style={s.cardLabel}>Peer help</Text>
            <Text style={{ color: '#6ee7b7', fontSize: 14 }}>{result.peer_suggestion}</Text>
          </View>
        )}

        {/* Actions */}
        <View style={{ flexDirection: 'row', gap: 12, marginTop: 8 }}>
          <TouchableOpacity style={[s.outlineBtn, { flex: 1 }]} onPress={() => setScreen(SCREEN.HOME)}>
            <Text style={s.outlineBtnText}>Try again</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[s.btn, { flex: 1 }]} onPress={() => { setAnswer(''); setScreen(SCREEN.HOME); }}>
            <Text style={s.btnText}>Next question</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    );
  }

  // ── IMAGE CHAT SCREEN ─────────────────────────────────────────
  if (screen === SCREEN.CHAT) return (
    <ImageChatScreen serverUrl={serverUrl} onBack={() => setScreen(SCREEN.HOME)} />
  );

  return null;
}

// ══════════════════════════════════════════════════════════════════
// IMAGE CHAT SCREEN (separate component)
// ══════════════════════════════════════════════════════════════════
function ImageChatScreen({ serverUrl, onBack }) {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [image, setImage] = useState(null);
  const [loading, setLoading] = useState(false);

  async function pickImage() {
    const res = await ImagePicker.launchImageLibraryAsync({ quality: 0.7 });
    if (!res.canceled) setImage(res.assets[0].uri);
  }
  async function captureImage() {
    const res = await ImagePicker.launchCameraAsync({ quality: 0.7 });
    if (!res.canceled) setImage(res.assets[0].uri);
  }

  async function send() {
    const q = question.trim();
    if (!q) return;
    setQuestion('');
    setMessages(m => [...m, { role: 'user', text: q, img: image }]);
    setLoading(true);
    try {
      const form = new FormData();
      form.append('question', q);
      if (image) form.append('image', { uri: image, type: 'image/jpeg', name: 'photo.jpg' });
      const resp = await axios.post(`${serverUrl}/api/image-chat`, form,
        { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 90000 });
      setMessages(m => [...m, { role: 'ai', text: resp.data.answer || 'No response.' }]);
    } catch (e) {
      setMessages(m => [...m, { role: 'ai', text: 'Could not reach PC. Make sure backend is running.' }]);
    } finally { setLoading(false); }
  }

  return (
    <KeyboardAvoidingView style={s.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <StatusBar barStyle="light-content" backgroundColor="#0a0a14" />
      <View style={[s.header, { padding: 16, paddingTop: 50 }]}>
        <TouchableOpacity onPress={onBack}><Text style={{ color: '#6366f1', fontSize: 16 }}>← Back</Text></TouchableOpacity>
        <Text style={s.logo}>ARK Chat</Text>
        <View />
      </View>

      <View style={{ flexDirection: 'row', gap: 8, padding: 12 }}>
        <TouchableOpacity style={s.outlineBtn} onPress={pickImage}>
          <Text style={s.outlineBtnText}>Gallery</Text>
        </TouchableOpacity>
        <TouchableOpacity style={s.outlineBtn} onPress={captureImage}>
          <Text style={s.outlineBtnText}>Camera</Text>
        </TouchableOpacity>
        {image && (
          <TouchableOpacity onPress={() => setImage(null)}>
            <Text style={{ color: '#ef4444', fontSize: 13, marginTop: 10 }}>Clear</Text>
          </TouchableOpacity>
        )}
      </View>

      {image && <Image source={{ uri: image }} style={{ width: '100%', height: 160 }} resizeMode="cover" />}

      <FlatList
        style={{ flex: 1, padding: 12 }}
        data={messages}
        keyExtractor={(_, i) => String(i)}
        renderItem={({ item }) => (
          <View style={{ alignSelf: item.role === 'user' ? 'flex-end' : 'flex-start', marginBottom: 10, maxWidth: '85%' }}>
            {item.img && <Image source={{ uri: item.img }} style={{ width: 120, height: 80, borderRadius: 8, marginBottom: 4 }} />}
            <View style={{ backgroundColor: item.role === 'user' ? '#6366f1' : '#1e293b', borderRadius: 12, padding: 12 }}>
              <Text style={{ color: '#fff', fontSize: 14, lineHeight: 20 }}>{item.text}</Text>
            </View>
          </View>
        )}
        ListFooterComponent={loading ? <ActivityIndicator color="#6366f1" style={{ margin: 16 }} /> : null}
      />

      <View style={{ flexDirection: 'row', gap: 8, padding: 12 }}>
        <TextInput
          style={[s.input, { flex: 1, marginBottom: 0 }]}
          value={question} onChangeText={setQuestion}
          placeholder="Ask about the image or topic..."
          placeholderTextColor="#475569"
          onSubmitEditing={send}
        />
        <TouchableOpacity style={s.btn} onPress={send} disabled={loading}>
          <Text style={s.btnText}>Send</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

// ══════════════════════════════════════════════════════════════════
// STYLES
// ══════════════════════════════════════════════════════════════════
const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a14' },
  center: { flexGrow: 1, justifyContent: 'center', padding: 24 },
  logo: { color: '#818cf8', fontSize: 26, fontWeight: '900', letterSpacing: 4 },
  subtitle: { color: '#64748b', fontSize: 14, marginBottom: 28, marginTop: 4 },
  label: { color: '#94a3b8', fontSize: 12, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 },
  input: { backgroundColor: '#1a1a2e', borderRadius: 12, padding: 14, color: '#e2e8f0', fontSize: 15, marginBottom: 16, borderWidth: 1, borderColor: '#1e293b', width: '100%' },
  btn: { backgroundColor: '#6366f1', borderRadius: 14, padding: 16, alignItems: 'center', justifyContent: 'center' },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  outlineBtn: { backgroundColor: 'transparent', borderRadius: 14, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#334155', marginTop: 10 },
  outlineBtnText: { color: '#94a3b8', fontSize: 15, fontWeight: '600' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  card: { backgroundColor: '#1a1a2e', borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: '#1e293b' },
  cardLabel: { color: '#64748b', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 },
  answerInput: { backgroundColor: '#0f0f1a', borderRadius: 12, padding: 14, color: '#e2e8f0', fontSize: 15, minHeight: 120 },
  pill: { backgroundColor: '#1e293b', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 7 },
  pillActive: { backgroundColor: '#6366f1' },
  pillText: { color: '#64748b', fontSize: 12, fontWeight: '600', textTransform: 'capitalize' },
  pillTextActive: { color: '#fff' },
  dot: { width: 10, height: 10, borderRadius: 5 },
  badge: { alignSelf: 'flex-start', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 5, borderWidth: 1, marginTop: 6 },
  badgeText: { fontWeight: '700', fontSize: 14, letterSpacing: 1 },
  chip: { borderRadius: 20, paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1 },
});
