import * as ImagePicker from 'expo-image-picker';
import React, { useState } from 'react';
import {
  ActivityIndicator, Image, KeyboardAvoidingView, Modal, Platform,
  ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { sendImageChat } from '../services/api';

export default function ImageChatModal({ visible, onClose, baseUrl }) {
  const [image, setImage] = useState(null);
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  async function pickImage() {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });
    if (!result.canceled) setImage(result.assets[0].uri);
  }

  async function captureImage() {
    const result = await ImagePicker.launchCameraAsync({ quality: 0.8 });
    if (!result.canceled) setImage(result.assets[0].uri);
  }

  async function send() {
    if (!question.trim()) return;
    const q = question.trim();
    setQuestion('');
    setMessages(m => [...m, { role: 'user', text: q, imageUri: image }]);
    setLoading(true);
    try {
      const answer = await sendImageChat(q, image, baseUrl);
      setMessages(m => [...m, { role: 'assistant', text: answer }]);
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', text: 'Could not reach Ollama. Make sure the server is running.' }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={styles.header}>
          <Text style={styles.title}>Image Chat</Text>
          <TouchableOpacity onPress={onClose}><Text style={styles.close}>✕</Text></TouchableOpacity>
        </View>

        <View style={styles.imageRow}>
          <TouchableOpacity style={styles.imgBtn} onPress={pickImage}>
            <Text style={styles.imgBtnText}>Gallery</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.imgBtn} onPress={captureImage}>
            <Text style={styles.imgBtnText}>Camera</Text>
          </TouchableOpacity>
          {image && (
            <TouchableOpacity onPress={() => setImage(null)}>
              <Text style={styles.clearImg}>Clear image</Text>
            </TouchableOpacity>
          )}
        </View>

        {image && <Image source={{ uri: image }} style={styles.preview} resizeMode="cover" />}

        <ScrollView style={styles.messages} contentContainerStyle={{ paddingBottom: 8 }}>
          {messages.map((m, i) => (
            <View key={i} style={[styles.bubble, m.role === 'user' ? styles.userBubble : styles.aiBubble]}>
              {m.imageUri && <Image source={{ uri: m.imageUri }} style={styles.msgImage} />}
              <Text style={m.role === 'user' ? styles.userText : styles.aiText}>{m.text}</Text>
            </View>
          ))}
          {loading && <ActivityIndicator style={{ margin: 16 }} color="#6366f1" />}
        </ScrollView>

        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            value={question}
            onChangeText={setQuestion}
            placeholder="Ask about the image or topic..."
            multiline
            returnKeyType="send"
            onSubmitEditing={send}
          />
          <TouchableOpacity style={styles.sendBtn} onPress={send} disabled={loading}>
            <Text style={styles.sendText}>Send</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f1a' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, backgroundColor: '#1a1a2e' },
  title: { color: '#fff', fontSize: 18, fontWeight: '700' },
  close: { color: '#aaa', fontSize: 22 },
  imageRow: { flexDirection: 'row', gap: 8, padding: 12, alignItems: 'center' },
  imgBtn: { backgroundColor: '#6366f1', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 8 },
  imgBtnText: { color: '#fff', fontWeight: '600' },
  clearImg: { color: '#ef4444', fontSize: 13 },
  preview: { width: '100%', height: 180 },
  messages: { flex: 1, padding: 12 },
  bubble: { borderRadius: 12, padding: 12, marginBottom: 8, maxWidth: '90%' },
  userBubble: { backgroundColor: '#6366f1', alignSelf: 'flex-end' },
  aiBubble: { backgroundColor: '#1e293b', alignSelf: 'flex-start' },
  userText: { color: '#fff', fontSize: 14 },
  aiText: { color: '#e2e8f0', fontSize: 14, lineHeight: 20 },
  msgImage: { width: '100%', height: 120, borderRadius: 8, marginBottom: 6 },
  inputRow: { flexDirection: 'row', padding: 12, gap: 8, borderTopWidth: 1, borderColor: '#1e293b' },
  input: { flex: 1, backgroundColor: '#1e293b', borderRadius: 12, padding: 12, color: '#fff', maxHeight: 100 },
  sendBtn: { backgroundColor: '#6366f1', borderRadius: 12, paddingHorizontal: 16, justifyContent: 'center' },
  sendText: { color: '#fff', fontWeight: '700' },
});
