import React from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import FingerprintBadge from '../components/FingerprintBadge';

export default function ResultScreen({ route, navigation }) {
  const { result } = route.params;

  const driftPercent = Math.round(result.drift_score * 100);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scroll}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.logo}>ECHO</Text>
        <Text style={styles.student}>{result.student_name} · {result.student_id}</Text>
        {result.offline && (
          <View style={styles.offlinePill}>
            <Text style={styles.offlinePillText}>Offline result</Text>
          </View>
        )}
      </View>

      {/* Fingerprint */}
      <View style={styles.fpCard}>
        <Text style={styles.fpLabel}>Your understanding type</Text>
        <FingerprintBadge type={result.fingerprint} large />
        <View style={styles.driftRow}>
          <Text style={styles.driftLabel}>Drift score</Text>
          <View style={styles.driftBar}>
            <View style={[styles.driftFill, { width: `${driftPercent}%`, backgroundColor: driftColor(result.drift_score) }]} />
          </View>
          <Text style={styles.driftValue}>{driftPercent}%</Text>
        </View>
      </View>

      {/* What you said */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>You said</Text>
        <Text style={styles.saidText}>{result.what_they_said}</Text>
      </View>

      {/* What's wrong */}
      {result.what_is_wrong ? (
        <View style={[styles.card, styles.wrongCard]}>
          <Text style={styles.cardTitle}>What needs correcting</Text>
          <Text style={styles.wrongText}>{result.what_is_wrong}</Text>
        </View>
      ) : null}

      {/* Story analogy */}
      {result.story_fix ? (
        <View style={[styles.card, styles.storyCard]}>
          <Text style={styles.cardTitle}>Think of it this way</Text>
          <Text style={styles.storyText}>{result.story_fix}</Text>
        </View>
      ) : null}

      {/* Follow-up */}
      {result.follow_up_question ? (
        <View style={[styles.card, styles.questionCard]}>
          <Text style={styles.cardTitle}>Question for you</Text>
          <Text style={styles.questionText}>{result.follow_up_question}</Text>
        </View>
      ) : null}

      {/* Nodes */}
      {(result.activated_nodes?.length > 0 || result.skipped_nodes?.length > 0) && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Concept nodes</Text>
          <View style={styles.nodesRow}>
            {result.activated_nodes.map(n => (
              <View key={n} style={styles.nodeGreen}>
                <Text style={styles.nodeText}>{n.replace(/_/g, ' ')}</Text>
              </View>
            ))}
            {result.skipped_nodes.map(n => (
              <View key={n} style={styles.nodeRed}>
                <Text style={styles.nodeText}>{n.replace(/_/g, ' ')}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {/* Peer suggestion */}
      {result.peer_suggestion ? (
        <View style={[styles.card, styles.peerCard]}>
          <Text style={styles.cardTitle}>Peer help</Text>
          <Text style={styles.peerText}>{result.peer_suggestion}</Text>
        </View>
      ) : null}

      {/* Actions */}
      <View style={styles.actions}>
        <TouchableOpacity style={styles.tryBtn} onPress={() => navigation.goBack()}>
          <Text style={styles.tryText}>Try again</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.nextBtn} onPress={() => navigation.navigate('Student')}>
          <Text style={styles.nextText}>Next question</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

function driftColor(score) {
  if (score >= 0.7) return '#ef4444';
  if (score >= 0.4) return '#f59e0b';
  return '#10b981';
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f1a' },
  scroll: { padding: 16, paddingBottom: 40 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 },
  logo: { color: '#818cf8', fontSize: 20, fontWeight: '900', letterSpacing: 3 },
  student: { color: '#94a3b8', fontSize: 13 },
  offlinePill: { backgroundColor: '#7c3aed33', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3, borderWidth: 1, borderColor: '#7c3aed' },
  offlinePillText: { color: '#a78bfa', fontSize: 11 },
  fpCard: { backgroundColor: '#1a1a2e', borderRadius: 16, padding: 20, marginBottom: 12, borderWidth: 1, borderColor: '#1e293b' },
  fpLabel: { color: '#64748b', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 },
  driftRow: { flexDirection: 'row', alignItems: 'center', marginTop: 16, gap: 8 },
  driftLabel: { color: '#64748b', fontSize: 12, width: 70 },
  driftBar: { flex: 1, height: 8, backgroundColor: '#0f0f1a', borderRadius: 4, overflow: 'hidden' },
  driftFill: { height: '100%', borderRadius: 4 },
  driftValue: { color: '#e2e8f0', fontSize: 13, fontWeight: '700', width: 36 },
  card: { backgroundColor: '#1a1a2e', borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: '#1e293b' },
  cardTitle: { color: '#64748b', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 },
  saidText: { color: '#94a3b8', fontSize: 14, fontStyle: 'italic', lineHeight: 20 },
  wrongCard: { borderColor: '#ef444433' },
  wrongText: { color: '#fca5a5', fontSize: 15, lineHeight: 22 },
  storyCard: { borderColor: '#6366f133', backgroundColor: '#1a1a2e' },
  storyText: { color: '#c4b5fd', fontSize: 14, lineHeight: 22 },
  questionCard: { borderColor: '#0ea5e933' },
  questionText: { color: '#7dd3fc', fontSize: 15, lineHeight: 22, fontStyle: 'italic' },
  nodesRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  nodeGreen: { backgroundColor: '#10b98122', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1, borderColor: '#10b981' },
  nodeRed: { backgroundColor: '#ef444422', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1, borderColor: '#ef4444' },
  nodeText: { color: '#e2e8f0', fontSize: 12 },
  peerCard: { borderColor: '#10b98133' },
  peerText: { color: '#6ee7b7', fontSize: 14, lineHeight: 20 },
  actions: { flexDirection: 'row', gap: 12, marginTop: 8 },
  tryBtn: { flex: 1, backgroundColor: '#1e293b', borderRadius: 14, padding: 16, alignItems: 'center' },
  tryText: { color: '#94a3b8', fontSize: 15, fontWeight: '600' },
  nextBtn: { flex: 1, backgroundColor: '#6366f1', borderRadius: 14, padding: 16, alignItems: 'center' },
  nextText: { color: '#fff', fontSize: 15, fontWeight: '700' },
});
