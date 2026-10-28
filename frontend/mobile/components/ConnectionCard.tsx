import React, {useRef, useState} from 'react';
import {Pressable, StyleSheet, Text, TextInput, View} from 'react-native';
import {ApiClient, normalizeMobileServer} from '@driver-monitor/shared';
import type {Connection} from '@driver-monitor/shared';
import {Icon} from './Icon';
import {Badge, Button, Card, Notice, palette, ui} from './ui';

type Props = {
  connection: Connection | null;
  onConnect: (value: Connection) => Promise<void>;
  onDisconnect: () => Promise<void>;
};
export function ConnectionCard({connection, onConnect, onDisconnect}: Props) {
  const [server, setServer] = useState(connection?.server || '');
  const [token, setToken] = useState(connection?.token || '');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [visible, setVisible] = useState(false);
  const [focused, setFocused] = useState('');
  const tokenInput = useRef<TextInput>(null);
  async function connect() {
    setBusy(true);
    setError('');
    try {
      const value = {server: normalizeMobileServer(server), token: token.trim()};
      await new ApiClient(value).status();
      await onConnect(value);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Không kết nối được');
    } finally { setBusy(false); }
  }
  async function disconnect() {
    try { await onDisconnect(); setToken(''); setError(''); }
    catch (failure) { setError(String(failure)); }
  }
  return <>
    <View style={s.hero}>
      <View style={s.heroGlow}/>
      <View style={s.heroTop}><View style={s.heroMark}><Icon name="shield" color="#CCE6D6" size={29}/></View>
        <Text style={s.eyebrow}>DRIVER MONITOR</Text>
      </View>
      <Text style={s.heroTitle}>Giám sát tài xế{'\n'}trong tầm tay.</Text>
      <Text style={s.heroBody}>Hình ảnh rõ ràng. Trạng thái tức thì.{'\n'}Theo dõi hệ thống ngay trên điện thoại.</Text>
      <View style={s.heroFooter}><View style={s.liveDot}/><Text style={s.heroCaption}>KẾT NỐI VỚI PC / RADXA</Text></View>
    </View>
    <Card>
      <View style={[ui.between, {marginBottom: 24}]}><Text style={ui.sectionHeading}>Thiết lập kết nối</Text>
        <Badge text={connection ? 'Đã lưu' : 'Mạng Wi-Fi'} tone={connection ? 'green' : 'neutral'}/>
      </View>
      <View style={s.step}><Text style={s.number}>1</Text><View style={{flex: 1}}><Text style={ui.label}>Địa chỉ máy chủ</Text>
        <Text style={s.hint}>Máy PC hoặc Radxa chạy hệ thống</Text></View></View>
      <View style={[s.inputBox, focused === 'server' && s.focused]}>
        <Icon name="server" size={20} color={palette.muted}/>
        <TextInput accessibilityLabel="Địa chỉ máy chủ" style={s.input} value={server} onChangeText={setServer}
          placeholder="http://192.168.1.10:8765" placeholderTextColor="#738178"
          autoCapitalize="none" autoCorrect={false} keyboardType="url" returnKeyType="next" editable={!busy}
          onFocus={() => setFocused('server')} onBlur={() => setFocused('')} onSubmitEditing={() => tokenInput.current?.focus()}/>
      </View>
      <View style={[s.step, {marginTop: 24}]}><Text style={s.number}>2</Text><View style={{flex: 1}}><Text style={ui.label}>Mã kết nối</Text>
        <Text style={s.hint}>Lấy từ màn hình khởi động hệ thống</Text></View></View>
      <View style={[s.inputBox, focused === 'token' && s.focused]}>
        <Icon name="lock" size={20} color={palette.muted}/>
        <TextInput ref={tokenInput} accessibilityLabel="Mã kết nối" style={s.input} value={token} onChangeText={setToken}
          placeholder="Nhập mã kết nối" placeholderTextColor="#738178" autoCapitalize="none" autoCorrect={false}
          secureTextEntry={!visible} returnKeyType="go" editable={!busy}
          onFocus={() => setFocused('token')} onBlur={() => setFocused('')}
          onSubmitEditing={() => {if (server.trim() && token.trim() && !busy) void connect();}}/>
        <Pressable accessibilityRole="button" accessibilityLabel={visible ? 'Ẩn mã kết nối' : 'Hiện mã kết nối'}
          style={s.eyeButton} onPress={() => setVisible(!visible)} disabled={busy}>
          <Icon name={visible ? 'eyeOff' : 'eye'} size={20} color={palette.muted}/>
        </Pressable>
      </View>
      <View style={s.secureNote}><Icon name="shield" size={14} color={palette.muted}/><Text style={s.hint}>Mã được lưu bảo mật trên thiết bị.</Text></View>
      {error !== '' && <Notice text={error} error/>}
      <Button title={busy ? 'Đang kiểm tra kết nối…' : 'Kết nối máy chủ'} icon="arrow" loading={busy}
        disabled={!server.trim() || !token.trim()} onPress={() => void connect()}/>
      {connection && <Pressable style={s.disconnect} accessibilityRole="button" disabled={busy} onPress={() => void disconnect()}>
        <Text style={s.disconnectText}>Ngắt giao diện</Text>
      </Pressable>}
    </Card>
    <View style={s.help}><View style={s.helpIcon}><Icon name="wifi" size={21}/></View><View style={s.helpContent}>
      <Text style={s.helpTitle}>Cùng một mạng Wi-Fi</Text><Text style={ui.caption}>Điện thoại và máy xử lý cần kết nối cùng mạng.</Text>
    </View></View>
    <View style={s.help}><View style={s.helpIcon}><Icon name="bell" size={21}/></View><View style={s.helpContent}>
      <Text style={s.helpTitle}>Giữ app mở khi theo dõi</Text><Text style={ui.caption}>Nhận banner và rung cảnh báo khi app đang mở.</Text>
    </View></View>
  </>;
}
const s = StyleSheet.create({
  hero: {backgroundColor: palette.greenDark, borderRadius: 26, padding: 24, marginBottom: 22, overflow: 'hidden'},
  heroGlow: {position: 'absolute', width: 240, height: 240, borderRadius: 120, borderWidth: 35, borderColor: '#214F40', right: -118, top: -88},
  heroTop: {flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 23},
  heroMark: {width: 42, height: 42, borderRadius: 14, backgroundColor: '#285646', alignItems: 'center', justifyContent: 'center'},
  eyebrow: {fontSize: 11, letterSpacing: 2, fontWeight: '700', color: '#C3DDCD'},
  heroTitle: {fontSize: 31, lineHeight: 38, fontWeight: '700', letterSpacing: -0.8, color: '#FFFFFF'},
  heroBody: {fontSize: 14, lineHeight: 22, color: '#C2D8CC', marginTop: 14},
  heroFooter: {flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 25},
  liveDot: {width: 6, height: 6, borderRadius: 3, backgroundColor: '#A9D6B5'},
  heroCaption: {fontSize: 10, fontWeight: '600', letterSpacing: 1.3, color: '#BBD6C7'},
  step: {flexDirection: 'row', alignItems: 'center', gap: 11, marginBottom: 13},
  number: {width: 28, height: 28, borderRadius: 10, backgroundColor: palette.mint, color: palette.green, textAlign: 'center', textAlignVertical: 'center', lineHeight: 28, fontSize: 12, fontWeight: '700', overflow: 'hidden'},
  hint: {fontSize: 12, lineHeight: 18, color: palette.muted},
  inputBox: {flexDirection: 'row', alignItems: 'center', paddingLeft: 14, borderWidth: 1, borderColor: palette.line, borderRadius: 14, backgroundColor: '#F8FAF8', marginBottom: 2},
  focused: {borderColor: '#579176', backgroundColor: '#FFFFFF'},
  input: {flex: 1, minHeight: 54, paddingHorizontal: 11, paddingVertical: 13, fontSize: 14, color: palette.ink},
  eyeButton: {width: 48, minHeight: 52, alignItems: 'center', justifyContent: 'center'},
  secureNote: {flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12, marginBottom: 22},
  disconnect: {minHeight: 48, alignItems: 'center', justifyContent: 'center', marginTop: 10},
  disconnectText: {fontSize: 13, color: palette.green, fontWeight: '600'},
  help: {flexDirection: 'row', alignItems: 'flex-start', gap: 12, paddingHorizontal: 8, marginBottom: 18},
  helpIcon: {width: 40, height: 40, borderRadius: 14, backgroundColor: '#E6EDE7', justifyContent: 'center', alignItems: 'center'},
  helpContent: {flex: 1}, helpTitle: {fontSize: 14, fontWeight: '600', color: palette.ink},
});
