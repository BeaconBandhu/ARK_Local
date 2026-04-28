import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

const COLORS = {
  INVERT:   { bg: '#ef4444', text: '#fff' },
  GHOST:    { bg: '#f59e0b', text: '#fff' },
  HOLLOW:   { bg: '#3b82f6', text: '#fff' },
  FRAGMENT: { bg: '#10b981', text: '#fff' },
  ORPHAN:   { bg: '#8b5cf6', text: '#fff' },
};

const DESCRIPTIONS = {
  INVERT:   'Flipped understanding',
  GHOST:    'Wrong belief',
  HOLLOW:   'Right words, no meaning',
  FRAGMENT: 'Partial understanding',
  ORPHAN:   'Missing foundation',
};

export default function FingerprintBadge({ type, large }) {
  const colors = COLORS[type] || { bg: '#6b7280', text: '#fff' };
  return (
    <View style={[styles.badge, { backgroundColor: colors.bg }, large && styles.large]}>
      <Text style={[styles.type, { color: colors.text }, large && styles.largeType]}>{type}</Text>
      {large && (
        <Text style={[styles.desc, { color: colors.text }]}>{DESCRIPTIONS[type]}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
    alignSelf: 'flex-start',
  },
  large: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 12,
  },
  type: {
    fontWeight: '700',
    fontSize: 13,
    letterSpacing: 1,
  },
  largeType: {
    fontSize: 18,
  },
  desc: {
    fontSize: 12,
    marginTop: 2,
    opacity: 0.9,
  },
});
