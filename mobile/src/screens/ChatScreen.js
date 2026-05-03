import React, { useState } from 'react';
import { SafeAreaView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import ImageChatModal from '../components/ImageChatModal';
import { SERVER_URL } from '../services/api';

export default function ChatScreen({ navigation }) {
  const [modalVisible, setModalVisible] = useState(false);
  const baseUrl = SERVER_URL;

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.back}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>ECHO Chat</Text>
        <View />
      </View>

      <View style={styles.body}>
        <Text style={styles.desc}>Ask ECHO about any image or concept.</Text>
        <Text style={styles.sub}>
          Powered by Ollama on the teacher's PC.{'\n'}
          Upload an image from your textbook and ask questions about it.
        </Text>
        <TouchableOpacity style={styles.btn} onPress={() => setModalVisible(true)}>
          <Text style={styles.btnText}>Open Image Chat</Text>
        </TouchableOpacity>
      </View>

      <ImageChatModal
        visible={modalVisible}
        onClose={() => setModalVisible(false)}
        baseUrl={baseUrl}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f1a' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16 },
  back: { color: '#6366f1', fontSize: 16 },
  title: { color: '#818cf8', fontSize: 18, fontWeight: '900', letterSpacing: 2 },
  body: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  desc: { color: '#e2e8f0', fontSize: 20, fontWeight: '700', textAlign: 'center', marginBottom: 12 },
  sub: { color: '#64748b', fontSize: 14, textAlign: 'center', lineHeight: 22, marginBottom: 32 },
  btn: { backgroundColor: '#6366f1', borderRadius: 16, paddingHorizontal: 32, paddingVertical: 16 },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
});
