import React from 'react';
import {ActivityIndicator, Pressable, StyleSheet, Text, View} from 'react-native';
import type {StyleProp, ViewStyle} from 'react-native';
import {Icon} from './Icon';
import type {IconName} from './Icon';

export const palette = {
  background: '#F3F6F3', surface: '#FFFFFF', ink: '#182F29', muted: '#62746C',
  green: '#20634F', greenDark: '#143E34', mint: '#E8F2EB', line: '#DFE7E1',
  amber: '#8B5A13', amberBg: '#FFF3DB', red: '#B53D32', redBg: '#FCEEEB',
  slate: '#566D7A', slateBg: '#EDF2F5',
};
export function Card({children, style}: {children: React.ReactNode; style?: StyleProp<ViewStyle>}) {
  return <View style={[ui.card, style]}>{children}</View>;
}
export function Button({title, onPress, icon, disabled = false, loading = false, secondary = false}: {
  title: string; onPress: () => void; icon?: IconName; disabled?: boolean; loading?: boolean; secondary?: boolean;
}) {
  const blocked = disabled || loading;
  const color = secondary ? palette.green : '#FFFFFF';
  return <Pressable onPress={onPress} disabled={blocked} accessibilityRole="button"
    accessibilityState={{disabled: blocked, busy: loading}}
    style={({pressed}) => [ui.button, secondary && ui.secondary, blocked && {opacity: 0.45}, pressed && {opacity: 0.8}]}>
    {loading ? <ActivityIndicator size="small" color={color}/> : icon && <Icon name={icon} size={20} color={color}/>}
    <Text style={[ui.buttonText, {color}]}>{title}</Text>
  </Pressable>;
}
export function Badge({text, tone = 'neutral'}: {text: string; tone?: 'green' | 'amber' | 'red' | 'neutral'}) {
  const color = tone === 'green' ? palette.green : tone === 'amber' ? palette.amber : tone === 'red' ? palette.red : palette.slate;
  const backgroundColor = tone === 'green' ? palette.mint : tone === 'amber' ? palette.amberBg : tone === 'red' ? palette.redBg : palette.slateBg;
  return <View style={[ui.badge, {backgroundColor}]}><View style={[ui.dot, {backgroundColor: color}]}/><Text style={[ui.badgeText, {color}]}>{text}</Text></View>;
}
export function SectionTitle({title, caption, icon}: {title: string; caption?: string; icon?: IconName}) {
  return <View style={ui.sectionTitle}>
    <View style={ui.row}>{icon && <Icon name={icon} size={20}/>}<Text style={ui.sectionHeading}>{title}</Text></View>
    {caption && <Text style={ui.caption}>{caption}</Text>}
  </View>;
}
export function EmptyState({title, body, icon, children}: {title: string; body: string; icon: IconName; children?: React.ReactNode}) {
  return <Card style={ui.empty}><View style={ui.emptyIcon}><Icon name={icon} size={32}/></View>
    <Text style={ui.emptyTitle}>{title}</Text><Text style={ui.emptyBody}>{body}</Text>
    {children && <View style={{alignSelf: 'stretch', marginTop: 22}}>{children}</View>}
  </Card>;
}
export function Notice({text, error = false}: {text: string; error?: boolean}) {
  return <View accessibilityRole={error ? 'alert' : 'text'} style={[ui.notice, error && {backgroundColor: palette.redBg}]}>
    <Icon name={error ? 'warning' : 'info'} size={19} color={error ? palette.red : palette.amber}/>
    <Text style={[ui.noticeText, error && {color: palette.red}]}>{text}</Text>
  </View>;
}
export const ui = StyleSheet.create({
  card: {backgroundColor: palette.surface, borderRadius: 22, borderWidth: 1, borderColor: palette.line, padding: 20, marginBottom: 16},
  row: {flexDirection: 'row', alignItems: 'center', gap: 9},
  between: {flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12},
  sectionTitle: {marginBottom: 16},
  sectionHeading: {fontSize: 17, fontWeight: '700', color: palette.ink, flexShrink: 1},
  body: {fontSize: 14, lineHeight: 22, color: palette.muted},
  caption: {fontSize: 12, lineHeight: 18, color: palette.muted, marginTop: 5},
  label: {fontSize: 13, fontWeight: '600', color: palette.ink, marginBottom: 8},
  input: {minHeight: 52, borderWidth: 1, borderColor: palette.line, borderRadius: 13, backgroundColor: '#F8FAF8', paddingHorizontal: 14, paddingVertical: 12, fontSize: 15, color: palette.ink},
  divider: {height: 1, backgroundColor: palette.line, marginVertical: 18},
  button: {minHeight: 52, borderRadius: 14, backgroundColor: palette.green, paddingHorizontal: 18, paddingVertical: 14, flexDirection: 'row', gap: 10, alignItems: 'center', justifyContent: 'center'},
  secondary: {backgroundColor: palette.mint, borderWidth: 1, borderColor: '#CEDFD3'},
  buttonText: {fontSize: 14, fontWeight: '700', flexShrink: 1, textAlign: 'center'},
  badge: {flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 30, paddingHorizontal: 10, paddingVertical: 7, alignSelf: 'flex-start', flexShrink: 1},
  badgeText: {fontSize: 11, fontWeight: '700', flexShrink: 1},
  dot: {width: 6, height: 6, borderRadius: 3},
  empty: {alignItems: 'center', paddingVertical: 34},
  emptyIcon: {width: 72, height: 72, borderRadius: 24, backgroundColor: palette.mint, alignItems: 'center', justifyContent: 'center', marginBottom: 20},
  emptyTitle: {fontSize: 21, fontWeight: '700', color: palette.ink, textAlign: 'center'},
  emptyBody: {fontSize: 14, lineHeight: 23, color: palette.muted, textAlign: 'center', marginTop: 10, maxWidth: 330},
  notice: {flexDirection: 'row', alignItems: 'flex-start', gap: 9, padding: 14, borderRadius: 13, backgroundColor: palette.amberBg, marginBottom: 16},
  noticeText: {flex: 1, fontSize: 13, lineHeight: 20, color: palette.amber},
});
