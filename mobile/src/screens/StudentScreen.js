import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { useEffect, useRef, useState } from 'react';
import {
  Alert, KeyboardAvoidingView, Platform, ScrollView, StyleSheet,
  Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import VoiceButton from '../components/VoiceButton';
import { analyseAnswer, getCurrentTopic, isOnline, syncOfflineQueue } from '../services/api';

const LANGUAGES = ['english', 'kannada', 'hindi'];
const TOPICS = ['photosynthesis', 'water_cycle', 'food_chain'];

export default function StudentScreen({ navigation }) {
  const [studentId, setStudentId] = useState('');
  const [studentName, setStudentName] = useState('');
  const [topic, setTopic] = useState('photosynthesis');
  const [answer, setAnswer] = useState('');
  const [language, setLanguage] = useState('english');
  const [loading, setLoading] = useState(false);
  const [online, setOnline] = useState(true);
  const [baseUrl] = useState('http://10.13.231.31:8000');
  const [setupDone, setSetupDone] = useState(false);

  useEffect(() => {
    bootstrap();
    const interval = setInterval(syncOfflineQueue, 30000);
    return () => clearInterval(interval);
  }, []);

  async function bootstrap() {
    const [storedId, storedName] = await Promise.all([
      AsyncStorage.getItem('echo_student_id'),
      AsyncStorage.getItem('echo_student_name'),
    ]);
    if (storedId) setStudentId(storedId);
    if (storedName) setStudentName(storedName);

    const connected = await isOnline();
    setOnline(connected);

    if (connected) {
      const topicData = await getCurrentTopic(url);
      if (topicData?.topic) setTopic(topicData.topic);
    }
  }

  async function handleSubmit() {
    if (!studentId.trim() || !studentName.trim()) {
      Alert.alert('Required', 'Please enter your Student ID and Name first.');
      return;
    }
    if (!answer.trim()) {
      Alert.alert('Required', 'Please write or speak your answer.');
      return;
    }

    await AsyncStorage.multiSet([
      ['echo_student_id', studentId.trim()],
      ['echo_student_name', studentName.trim()],
    ]);

    setLoading(true);
    try {
      const result = await analyseAnswer({
        student_id: studentId.trim(),
        student_name: studentName.trim(),
        topic,
        answer_text: answer.trim(),
        language,
      });
      navigation.navigate('Result', { result });
    } catch (e) {
      Alert.alert('Error', 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  if (!setupDone && !studentId) {
    return (
      <View style={styles.setup}>
        <Text style={styles.logo}>ECHO</Text>
        <Text style={styles.setupTitle}>Set up your profile</Text>
        <TextInput
          style={styles.setupInput}
          placeholder="Student ID (e.g. S12)"
          placeholderTextColor="#64748b"
          value={studentId}
          onChangeText={setStudentId}
          autoCapitalize="characters"
        />
        <TextInput
          style={styles.setupInput}
          placeholder="Your name"
          placeholderTextColor="#64748b"
          value={studentName}
          onChangeText={setStudentName}
        />
        <TouchableOpacity style={styles.btn} onPress={() => setSetupDone(true)}>
          <Text style={styles.btnText}>Continue</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.scroll}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.logo}>ECHO</Text>
          <View style={styles.langRow}>
            {LANGUAGES.map(l => (
              <TouchableOpacity
                key={l}
                style={[styles.langBtn, language === l && styles.langActive]}
                onPress={() => setLanguage(l)}
              >
                <Text style={[styles.langText, language === l && styles.langTextActive]}>
                  {l === 'english' ? 'EN' : l === 'kannada' ? 'KN' : 'HI'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <View style={[styles.dot, online ? styles.online : styles.offline]} />
        </View>

        {/* Identity */}
        <View style={styles.card}>
          <Text style={styles.label}>Student ID</Text>
          <TextInput style={styles.input} value={studentId} onChangeText={setStudentId} placeholderTextColor="#64748b" placeholder="S12" />
          <Text style={styles.label}>Name</Text>
          <TextInput style={styles.input} value={studentName} onChangeText={setStudentName} placeholderTextColor="#64748b" placeholder="Your name" />
        </View>

        {/* Topic selector */}
        <View style={styles.card}>
          <Text style={styles.label}>Topic</Text>
          <View style={styles.topicRow}>
            {TOPICS.map(t => (
              <TouchableOpacity
                key={t}
                style={[styles.topicBtn, topic === t && styles.topicActive]}
                onPress={() => setTopic(t)}
              >
                <Text style={[styles.topicText, topic === t && styles.topicTextActive]}>
                  {t.replace('_', ' ')}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Question */}
        <View style={styles.card}>
          <Text style={styles.questionTitle}>Question</Text>
          <Text style={styles.question}>
            {topic === 'photosynthesis' && 'Explain how plants make their own food using sunlight.'}
            {topic === 'water_cycle' && 'Describe how water moves from the earth to the sky and back again.'}
            {topic === 'food_chain' && 'Explain how energy moves from the sun through living things in a field.'}
          </Text>
        </View>

        {/* Answer area */}
        <View style={styles.card}>
          <Text style={styles.label}>Your Answer</Text>
          <TextInput
            style={styles.answerInput}
            multiline
            value={answer}
            onChangeText={setAnswer}
            placeholder="Type your answer here..."
            placeholderTextColor="#64748b"
            textAlignVertical="top"
          />
          <View style={{ marginTop: 12 }}>
            <VoiceButton onTranscript={setAnswer} language={language} baseUrl={baseUrl} />
          </View>
        </View>

        {/* Submit */}
        <TouchableOpacity
          style={[styles.submitBtn, loading && styles.btnDisabled]}
          onPress={handleSubmit}
          disabled={loading}
        >
          <Text style={styles.submitText}>{loading ? 'Analysing...' : 'Analyse my answer'}</Text>
        </TouchableOpacity>

        {/* Image chat link */}
        <TouchableOpacity style={styles.chatLink} onPress={() => navigation.navigate('Chat')}>
          <Text style={styles.chatLinkText}>Ask about an image or topic →</Text>
        </TouchableOpacity>

        {!online && (
          <View style={styles.offlineBanner}>
            <Text style={styles.offlineText}>Offline mode — answers saved and will sync when connected</Text>
          </View>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f1a' },
  scroll: { padding: 16, paddingBottom: 40 },
  setup: { flex: 1, backgroundColor: '#0f0f1a', alignItems: 'center', justifyContent: 'center', padding: 24 },
  setupTitle: { color: '#e2e8f0', fontSize: 18, marginBottom: 24 },
  setupInput: { width: '100%', backgroundColor: '#1e293b', borderRadius: 12, padding: 14, color: '#fff', marginBottom: 12, fontSize: 15 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 },
  logo: { color: '#818cf8', fontSize: 24, fontWeight: '900', letterSpacing: 3 },
  langRow: { flexDirection: 'row', gap: 6 },
  langBtn: { backgroundColor: '#1e293b', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5 },
  langActive: { backgroundColor: '#6366f1' },
  langText: { color: '#94a3b8', fontSize: 12, fontWeight: '600' },
  langTextActive: { color: '#fff' },
  dot: { width: 10, height: 10, borderRadius: 5 },
  online: { backgroundColor: '#10b981' },
  offline: { backgroundColor: '#f59e0b' },
  card: { backgroundColor: '#1a1a2e', borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: '#1e293b' },
  label: { color: '#94a3b8', fontSize: 12, fontWeight: '600', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 },
  input: { backgroundColor: '#0f0f1a', borderRadius: 10, padding: 12, color: '#fff', fontSize: 15, marginBottom: 10 },
  topicRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  topicBtn: { backgroundColor: '#0f0f1a', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8 },
  topicActive: { backgroundColor: '#6366f1' },
  topicText: { color: '#94a3b8', fontSize: 13, fontWeight: '600', textTransform: 'capitalize' },
  topicTextActive: { color: '#fff' },
  questionTitle: { color: '#818cf8', fontWeight: '700', fontSize: 13, marginBottom: 6 },
  question: { color: '#e2e8f0', fontSize: 16, lineHeight: 24 },
  answerInput: { backgroundColor: '#0f0f1a', borderRadius: 12, padding: 14, color: '#fff', fontSize: 15, minHeight: 120 },
  submitBtn: { backgroundColor: '#6366f1', borderRadius: 16, padding: 18, alignItems: 'center', marginTop: 8 },
  btnDisabled: { opacity: 0.6 },
  submitText: { color: '#fff', fontSize: 17, fontWeight: '700' },
  btn: { backgroundColor: '#6366f1', borderRadius: 14, padding: 16, width: '100%', alignItems: 'center', marginTop: 8 },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  chatLink: { alignItems: 'center', marginTop: 16 },
  chatLinkText: { color: '#6366f1', fontSize: 14 },
  offlineBanner: { backgroundColor: '#7c3aed22', borderRadius: 10, padding: 12, marginTop: 12, borderWidth: 1, borderColor: '#7c3aed' },
  offlineText: { color: '#a78bfa', fontSize: 13, textAlign: 'center' },
});
