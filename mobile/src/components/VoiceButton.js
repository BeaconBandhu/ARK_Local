import { Audio } from 'expo-av';
import React, { useRef, useState } from 'react';
import { ActivityIndicator, Alert, StyleSheet, Text, TouchableOpacity, View } from 'react-native';

export default function VoiceButton({ onTranscript, language, baseUrl }) {
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const recRef = useRef(null);

  async function startRecording() {
    try {
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission needed', 'Microphone access is required for voice answers.');
        return;
      }
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      recRef.current = recording;
      setRecording(true);
    } catch (e) {
      Alert.alert('Error', 'Could not start recording: ' + e.message);
    }
  }

  async function stopRecording() {
    setRecording(false);
    setProcessing(true);
    try {
      await recRef.current.stopAndUnloadAsync();
      const uri = recRef.current.getURI();
      const { transcribeVoice } = await import('../services/api');
      const transcript = await transcribeVoice(uri, language, baseUrl);
      onTranscript(transcript || '');
    } catch (e) {
      Alert.alert('Transcription failed', 'Could not transcribe audio. Please type your answer.');
    } finally {
      setProcessing(false);
    }
  }

  if (processing) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#6366f1" />
        <Text style={styles.processingText}>Transcribing...</Text>
      </View>
    );
  }

  return (
    <TouchableOpacity
      style={[styles.btn, recording && styles.btnActive]}
      onPress={recording ? stopRecording : startRecording}
      activeOpacity={0.8}
    >
      <Text style={styles.icon}>{recording ? '⏹' : '🎙'}</Text>
      <Text style={styles.label}>{recording ? 'Tap to stop' : 'Speak your answer'}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  btn: {
    backgroundColor: '#6366f1',
    borderRadius: 50,
    paddingVertical: 18,
    paddingHorizontal: 30,
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
    elevation: 4,
    shadowColor: '#6366f1',
    shadowOpacity: 0.4,
    shadowRadius: 8,
  },
  btnActive: {
    backgroundColor: '#ef4444',
  },
  icon: { fontSize: 22 },
  label: { color: '#fff', fontWeight: '700', fontSize: 16 },
  center: { alignItems: 'center', gap: 8 },
  processingText: { color: '#6366f1', fontSize: 14 },
});
