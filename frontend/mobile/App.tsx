import React, {useEffect, useMemo, useRef, useState} from 'react';
import {AppState, KeyboardAvoidingView, Platform, Pressable, ScrollView, StatusBar, StyleSheet, Text, View} from 'react-native';
import {SafeAreaProvider, SafeAreaView} from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import * as SecureStore from 'expo-secure-store';
import {AlertMemory, ApiClient, appendSample, label, LiveConnection, normalizeMobileServer} from '@driver-monitor/shared';
import type {Connection, MonitorSnapshot} from '@driver-monitor/shared';
import {ConnectionCard} from './components/ConnectionCard';
import {History} from './components/History';
import {Monitor} from './components/Monitor';
import {Icon} from './components/Icon';
import type {IconName} from './components/Icon';
import {Badge, Notice, palette} from './components/ui';

type Tab = 'monitor' | 'history' | 'connection';
const tabs: {key: Tab; title: string; icon: IconName}[] = [
  {key: 'monitor', title: 'Giám sát', icon: 'monitor'},
  {key: 'history', title: 'Lịch sử', icon: 'history'},
  {key: 'connection', title: 'Kết nối', icon: 'link'},
];
export default function App() { return <SafeAreaProvider><Application/></SafeAreaProvider>; }
function Application() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [tab, setTab] = useState<Tab>('connection');
  const [snapshot, setSnapshot] = useState<MonitorSnapshot | null>(null);
  const [samples, setSamples] = useState<MonitorSnapshot[]>([]);
  const [error, setError] = useState('');
  const [banner, setBanner] = useState('');
  const [active, setActive] = useState(AppState.currentState === 'active');
  const [restored, setRestored] = useState(false);
  const alerts = useRef(new AlertMemory());
  const scroll = useRef<ScrollView>(null);
  const api = useMemo(() => connection ? new ApiClient(connection) : null, [connection]);
  const scrollTop = () => scroll.current?.scrollTo({y: 0, animated: false});
  function go(next: Tab) { setTab(next); scrollTop(); }
  useEffect(() => {
    let canceled = false;
    (async () => {
      try {
        const seen = await SecureStore.getItemAsync('dm-alerts');
        if (seen) alerts.current = new AlertMemory(JSON.parse(seen));
        const saved = await SecureStore.getItemAsync('dm-connection');
        if (!canceled && saved) {
          const value = JSON.parse(saved);
          normalizeMobileServer(value.server); setConnection(value); setTab('monitor');
        }
      } catch {
        if (!canceled) setError('Không đọc được kết nối đã lưu. Nhập lại địa chỉ và mã.');
      } finally { if (!canceled) setRestored(true); }
    })();
    return () => { canceled = true; };
  }, []);
  useEffect(() => {
    const listener = AppState.addEventListener('change', state => setActive(state === 'active'));
    return () => listener.remove();
  }, []);
  useEffect(() => {
    if (!api || !active || !restored) {
      setSnapshot(value => value ? {...value, connected: false} : null);
      return;
    }
    const live = new LiveConnection(api, value => {
      setSnapshot(value);
      if (!value) return;
      if (value.lifecycle === 'running') setSamples(current => appendSample(current, value));
      if (alerts.current.accept(value)) {
        setBanner(value.reasons.map(label).join(' · ') || 'Tài xế cần chú ý ngay');
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error).catch(() => {});
        SecureStore.setItemAsync('dm-alerts', JSON.stringify(alerts.current.export())).catch(() => {});
      }
    }, setError);
    live.start();
    return () => live.stop();
  }, [api, active, restored]);
  useEffect(() => { setSnapshot(null); setSamples([]); }, [api]);
  useEffect(() => {
    if (!banner) return;
    const timer = setTimeout(() => setBanner(''), 10000);
    return () => clearTimeout(timer);
  }, [banner]);
  async function connect(value: Connection) {
    await SecureStore.setItemAsync('dm-connection', JSON.stringify(value));
    setConnection(value); setError(''); go('monitor');
  }
  async function disconnect() {
    await SecureStore.deleteItemAsync('dm-connection');
    setConnection(null); setError(''); setBanner('');
  }
  const connected = !!snapshot?.connected;
  return <SafeAreaView style={s.safe}>
    <StatusBar barStyle="dark-content"/>
    <View style={s.header}>
      <View style={s.brand}><View style={s.mark}><Icon name="shield" size={24} color="#FFFFFF"/></View>
        <View style={{flexShrink: 1}}><Text style={s.brandName}>Driver Monitor</Text><Text style={s.brandCaption}>Đồng hành cùng sự tập trung</Text></View>
      </View>
      <Badge text={connected ? 'Trực tuyến' : connection ? 'Ngoại tuyến' : 'Chưa kết nối'} tone={connected ? 'green' : 'neutral'}/>
    </View>
    {banner !== '' && <View style={s.banner} accessibilityRole="alert">
      <View style={s.alertIcon}><Icon name="warning" size={23} color="#FFFFFF"/></View>
      <View style={{flex: 1}}><Text style={s.bannerTitle}>Cảnh báo tài xế</Text><Text style={s.bannerText}>{banner}</Text></View>
      <Pressable accessibilityRole="button" accessibilityLabel="Ẩn cảnh báo" style={s.dismiss} onPress={() => setBanner('')}>
        <Icon name="close" size={21} color="#FFFFFF"/>
      </Pressable>
    </View>}
    <KeyboardAvoidingView style={{flex: 1}} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView ref={scroll} contentContainerStyle={s.content} keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag" showsVerticalScrollIndicator={false}>
        {tab !== 'connection' && <View style={[s.pageHeading, tab === 'monitor' && {marginTop: 4, marginBottom: 17}]}>
          {tab === 'history' && <Text style={s.eyebrow}>NHẬT KÝ GIÁM SÁT</Text>}
          <Text style={s.title}>{tab === 'monitor' ? 'Giám sát tài xế' : 'Lịch sử phiên'}</Text>
          {tab === 'history' && <Text style={s.description}>Xem lại các phiên và sự kiện đã ghi nhận.</Text>}
        </View>}
        {error !== '' && <Notice text={error}/>}
        {tab === 'connection' && <ConnectionCard connection={connection} onConnect={connect} onDisconnect={disconnect}/>}
        {tab === 'monitor' && <Monitor api={api} snapshot={snapshot} samples={samples} active={active} onConnect={() => go('connection')}/>}
        {tab === 'history' && <History api={api} onConnect={() => go('connection')} onNavigate={scrollTop}/>}
        <View style={s.footnote}><Icon name="shield" size={14} color={palette.muted}/><Text style={s.footnoteText}>Camera, AI và còi hoạt động tại PC / Radxa.</Text></View>
      </ScrollView>
    </KeyboardAvoidingView>
    <View style={s.tabs}>{tabs.map(item => <Pressable key={item.key} accessibilityRole="button" accessibilityLabel={item.title}
      accessibilityState={{selected: tab === item.key}} style={s.tab} onPress={() => go(item.key)}>
      <View key={tab === item.key ? 'active' : 'inactive'} style={[s.tabIcon, tab === item.key && s.tabIconActive]}><Icon name={item.icon} size={23} color={tab === item.key ? '#FFFFFF' : '#6E8076'}/></View>
      <Text style={[s.tabLabel, tab === item.key && s.tabLabelActive]}>{item.title}</Text>
    </Pressable>)}</View>
  </SafeAreaView>;
}
const s = StyleSheet.create({
  safe: {flex: 1, backgroundColor: palette.background},
  header: {paddingHorizontal: 20, paddingVertical: 15, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12},
  brand: {flexDirection: 'row', alignItems: 'center', gap: 10, flexShrink: 1},
  mark: {width: 42, height: 42, borderRadius: 14, backgroundColor: palette.greenDark, alignItems: 'center', justifyContent: 'center'},
  brandName: {fontSize: 16, fontWeight: '800', letterSpacing: -0.4, color: palette.ink},
  brandCaption: {fontSize: 10, color: palette.muted, marginTop: 3},
  content: {paddingHorizontal: 20, paddingTop: 10, paddingBottom: 26},
  pageHeading: {marginTop: 10, marginBottom: 23},
  eyebrow: {fontSize: 10, letterSpacing: 1.8, fontWeight: '700', color: palette.green, marginBottom: 9},
  title: {fontSize: 30, lineHeight: 37, letterSpacing: -0.8, fontWeight: '700', color: palette.ink},
  description: {fontSize: 13, lineHeight: 21, color: palette.muted, marginTop: 7},
  footnote: {flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 6, marginTop: 12},
  footnoteText: {fontSize: 11, lineHeight: 18, color: palette.muted, flexShrink: 1, textAlign: 'center'},
  tabs: {flexDirection: 'row', backgroundColor: '#FFFFFF', borderTopWidth: 1, borderColor: palette.line, paddingTop: 9, paddingBottom: 8},
  tab: {flex: 1, minHeight: 60, alignItems: 'center', justifyContent: 'center', gap: 4},
  tabIcon: {width: 55, height: 33, borderRadius: 13, backgroundColor: '#FFFFFF', overflow: 'hidden', alignItems: 'center', justifyContent: 'center'},
  tabIconActive: {backgroundColor: palette.green},
  tabLabel: {fontSize: 11, fontWeight: '500', color: palette.muted}, tabLabelActive: {color: palette.green, fontWeight: '700'},
  banner: {flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: palette.red, marginHorizontal: 20, marginBottom: 7, padding: 14, borderRadius: 18},
  alertIcon: {width: 38, height: 38, borderRadius: 13, backgroundColor: '#C1594D', alignItems: 'center', justifyContent: 'center'},
  bannerTitle: {fontSize: 15, color: '#FFFFFF', fontWeight: '700'}, bannerText: {fontSize: 13, lineHeight: 19, color: '#FFF0EA', marginTop: 3},
  dismiss: {width: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center'},
});
