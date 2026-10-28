import React from 'react';
import {StyleSheet, Text, View} from 'react-native';
import {label, numberText, percent, sourceLabel, stateLabels, timeText} from '@driver-monitor/shared';
import type {ApiClient, Device, DriverState, MonitorSnapshot} from '@driver-monitor/shared';
import {Icon} from './Icon';
import type {IconName} from './Icon';
import {LivePreview} from './LivePreview';
import {SignalChart} from './SignalChart';
import {Badge, Button, Card, EmptyState, Notice, palette, SectionTitle, ui} from './ui';

interface MonitorProps {
  api: ApiClient | null;
  snapshot: MonitorSnapshot | null;
  samples: MonitorSnapshot[];
  active: boolean;
  onConnect: () => void;
}
const states: Record<DriverState, {color: string; background: string; icon: IconName}> = {
  NORMAL: {color: '#FFFFFF', background: palette.greenDark, icon: 'shield'},
  WARNING: {color: palette.amber, background: palette.amberBg, icon: 'warning'},
  ALERT: {color: palette.red, background: palette.redBg, icon: 'warning'},
  UNKNOWN: {color: palette.slate, background: palette.slateBg, icon: 'eyeOff'},
};

export function Monitor({api, snapshot, samples, active, onConnect}: MonitorProps) {
  if (!api) return <EmptyState icon="monitor" title="Sẵn sàng giám sát"
    body="Kết nối với PC hoặc Radxa để xem camera, trạng thái tài xế và nhật ký trong cùng một nơi.">
    <Button title="Kết nối máy xử lý" icon="link" onPress={onConnect}/>
  </EmptyState>;

  const fresh = active && !!snapshot?.connected;
  const state = snapshot?.state ?? 'UNKNOWN';
  const appearance = fresh ? states[state] : states.UNKNOWN;
  const reasons = snapshot?.reasons.length ? snapshot.reasons.map(label).join(' · ')
    : label(snapshot?.lifecycle ?? 'unavailable');
  const showReasons = !fresh || state !== 'NORMAL' || !!snapshot?.reasons.length
    || snapshot?.lifecycle !== 'running';
  const age = snapshot && Number.isFinite(snapshot.age_ms)
    ? numberText(Math.max(0, snapshot.age_ms) / 1000, 1) + ' giây' : '—';

  return <>
    <View style={[s.stateCard, {backgroundColor: appearance.background}]}>
      <View style={s.stateTop}>
        <View style={{flex: 1}}>
          <Text style={[s.stateEyebrow, {color: appearance.color}]}>{fresh ? 'TRẠNG THÁI TÀI XẾ' : 'TRẠNG THÁI GẦN NHẤT'}</Text>
          <Text style={[s.stateTitle, {color: appearance.color}]}>{stateLabels[state]}</Text>
        </View>
        <View style={[s.stateIcon, {borderColor: appearance.color + '40'}]}>
          <Icon name={appearance.icon} size={25} color={appearance.color}/>
        </View>
      </View>
      {showReasons && <Text style={[s.reasons, {color: appearance.color}]}>{reasons}</Text>}
      <View style={[s.stateFooter, {borderColor: appearance.color + '30'}]}>
        <Text style={[s.stateCode, {color: appearance.color}]}>{state}</Text>
        <Text style={[s.source, {color: appearance.color}]}>{sourceLabel(snapshot?.source_kind ?? 'unknown')}</Text>
      </View>
    </View>
    {!fresh && <Notice text={!active ? 'App đang tạm dừng cập nhật.' : snapshot
      ? 'Đang thử kết nối lại. Các số liệu dưới đây thuộc lần cập nhật trước.'
      : 'Đang chờ dữ liệu đầu tiên từ máy xử lý.'}/>}

    <Card style={s.cameraCard}>
      <View style={s.cameraHeading}>
        <View style={ui.row}><Icon name="camera" size={20}/><Text style={ui.sectionHeading}>Camera tài xế</Text></View>
        <Text style={s.cameraKind}>{snapshot?.source_kind === 'video' ? 'PHÁT LẠI' : snapshot?.source_kind === 'camera' ? 'TRỰC TIẾP' : 'CHỜ NGUỒN'}</Text>
      </View>
      <LivePreview api={api} enabled={fresh} paused={!active}/>
      <View style={[s.cameraFooter, !fresh && {opacity: 0.5}]}>
        <Performance label="Tốc độ AI" value={numberText(snapshot?.performance.fps)} unit="FPS"/>
        <View style={s.performanceDivider}/>
        <Performance label="Độ trễ" value={numberText(snapshot?.performance.latency_ms, 0)} unit="ms"/>
      </View>
      <Text style={s.updateTime}>Cập nhật: {timeText(snapshot?.utc)}</Text>
    </Card>

    <View style={!fresh ? {opacity: 0.5} : undefined}>
    <View style={s.counts}>
      <Count icon="eye" title="Chớp hai mắt" value={snapshot?.counts.blink_total}
        detail={(snapshot?.counts.blink_5s ?? '—') + ' lần / 5 giây'}/>
      <Count icon="mouth" title="Ngáp xác nhận" value={snapshot?.counts.yawn_60s} detail="lần / 60 giây"/>
    </View>
    <Card>
      <SectionTitle icon="pulse" title="Tín hiệu nhận diện" caption="Xác suất từ model, được máy xử lý cung cấp."/>
      <SignalChart samples={samples}/>
    </Card>

    <Card>
      <SectionTitle icon="chip" title="Thiết bị & chất lượng" caption="Trạng thái nhận từ máy xử lý."/>
      <DeviceRow icon="camera" name="Camera" device={snapshot?.devices.camera}/>
      <DeviceRow icon="chip" name="Model AI" device={snapshot?.devices.models}/>
      <DeviceRow icon="bell" name="ESP32 → Buzzer" device={snapshot?.devices.esp32}/>
      {snapshot?.devices.esp32.configured && <Text style={s.ack}>
        ACK gần nhất: {numberText(snapshot.devices.esp32.ack_age_seconds)} giây
      </Text>}
      <View style={ui.divider}/>
      <Detail name="Chất lượng ảnh" value={label(snapshot?.quality.image ?? 'unavailable')}/>
      <Detail name="Quan sát mắt" value={label(snapshot?.quality.eyes ?? 'unavailable')}/>
      <Detail name="Vòng đời phiên" value={label(snapshot?.lifecycle ?? 'unavailable')}/>
      <Detail name="Tuổi dữ liệu máy chủ" value={age}/>
      <Detail name="Thời gian nguồn" value={numberText(snapshot?.source_timestamp) + ' s'}/>
      <Detail name="P(ngáp) thô" value={percent(snapshot?.probabilities.yawn_raw)}/>
      <Detail name="Chu kỳ một mắt" value={String(snapshot?.counts.eye_cycles ?? '—')}/>
      <Text style={s.explanation}>Chu kỳ một mắt được ghi riêng, không tính là một lần chớp hai mắt. Dấu — nghĩa là chưa có dữ liệu.</Text>
    </Card>
    </View>
    {!fresh && <Button title="Kiểm tra kết nối" icon="wifi" onPress={onConnect} secondary/>}
  </>;
}

function Performance({label: title, value, unit}: {label: string; value: string; unit: string}) {
  return <View style={s.performance}>
    <Text style={s.performanceLabel}>{title}</Text>
    <Text style={s.performanceValue}>{value} <Text style={s.unit}>{unit}</Text></Text>
  </View>;
}
function Count({icon, title, value, detail}: {icon: IconName; title: string; value?: number | null; detail: string}) {
  return <View style={s.count}>
    <View style={s.countIcon}><Icon name={icon} size={21}/></View>
    <Text style={s.countTitle}>{title}</Text>
    <Text style={s.countValue}>{value ?? '—'}</Text>
    <Text style={s.countDetail}>{detail}</Text>
  </View>;
}
function DeviceRow({icon, name, device}: {icon: IconName; name: string; device?: Device}) {
  const tone = device?.state === 'error' || device?.error ? 'red'
    : ['connected', 'ready'].includes(device?.state ?? '') ? 'green'
    : device?.state === 'unconfirmed' ? 'amber' : 'neutral';
  return <View style={s.device}>
    <View style={s.deviceHeading}>
      <View style={s.deviceName}><Icon name={icon} size={18}/><Text style={s.deviceText}>{name}</Text></View>
      <Badge text={label(device?.state ?? 'unavailable')} tone={tone}/>
    </View>
    {!!device?.error && <Text accessibilityRole="alert" style={s.deviceError}>{device.error}</Text>}
  </View>;
}
function Detail({name, value}: {name: string; value: string}) {
  return <View style={s.detail}><Text style={s.detailName}>{name}</Text><Text style={s.detailValue}>{value}</Text></View>;
}

const s = StyleSheet.create({
  stateCard: {borderRadius: 24, padding: 18, marginBottom: 16},
  stateTop: {flexDirection: 'row', alignItems: 'center', gap: 13},
  stateEyebrow: {fontSize: 11, lineHeight: 17, fontWeight: '600', letterSpacing: 1},
  stateTitle: {fontSize: 26, lineHeight: 32, fontWeight: '700', marginTop: 7, letterSpacing: -0.5},
  stateIcon: {width: 44, height: 44, borderRadius: 15, borderWidth: 1, alignItems: 'center', justifyContent: 'center'},
  reasons: {fontSize: 14, lineHeight: 23, marginTop: 13},
  stateFooter: {borderTopWidth: 1, paddingTop: 10, marginTop: 10, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 14},
  stateCode: {fontSize: 11, fontWeight: '700', letterSpacing: 1},
  source: {fontSize: 13, lineHeight: 20, textAlign: 'right', flexShrink: 1},
  cameraCard: {padding: 0, overflow: 'hidden'},
  cameraHeading: {paddingHorizontal: 18, paddingVertical: 17, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap'},
  cameraKind: {fontSize: 10, fontWeight: '700', color: palette.muted, letterSpacing: 0.5},
  cameraFooter: {flexDirection: 'row', alignItems: 'center', paddingTop: 17, paddingHorizontal: 20, gap: 20},
  performance: {flex: 1},
  performanceLabel: {fontSize: 12, color: palette.muted, lineHeight: 18},
  performanceValue: {fontSize: 22, lineHeight: 30, fontWeight: '700', color: palette.ink, marginTop: 2, fontVariant: ['tabular-nums']},
  unit: {fontSize: 12, fontWeight: '500', color: palette.muted},
  performanceDivider: {width: 1, height: 35, backgroundColor: palette.line},
  updateTime: {fontSize: 12, color: palette.muted, lineHeight: 19, paddingHorizontal: 20, paddingTop: 10, paddingBottom: 17},
  counts: {flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 16},
  count: {flex: 1, minWidth: 128, padding: 18, backgroundColor: palette.surface, borderRadius: 20, borderWidth: 1, borderColor: palette.line},
  countIcon: {width: 36, height: 36, backgroundColor: palette.mint, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginBottom: 13},
  countTitle: {fontSize: 13, lineHeight: 20, fontWeight: '600', color: palette.muted},
  countValue: {fontSize: 34, lineHeight: 44, fontWeight: '700', color: palette.ink, marginTop: 4, fontVariant: ['tabular-nums']},
  countDetail: {fontSize: 12, lineHeight: 19, color: palette.muted, marginTop: 3},
  device: {borderTopWidth: 1, borderColor: palette.line, paddingVertical: 13},
  deviceHeading: {flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 10},
  deviceName: {flexDirection: 'row', alignItems: 'center', gap: 9},
  deviceText: {fontSize: 14, color: palette.ink, fontWeight: '600'},
  deviceError: {fontSize: 13, lineHeight: 21, color: palette.red, marginTop: 8},
  ack: {fontSize: 12, lineHeight: 19, color: palette.muted},
  detail: {flexDirection: 'row', justifyContent: 'space-between', gap: 18, paddingVertical: 7},
  detailName: {flex: 1, fontSize: 13, lineHeight: 21, color: palette.muted},
  detailValue: {flex: 1, fontSize: 13, lineHeight: 21, color: palette.ink, fontWeight: '600', textAlign: 'right'},
  explanation: {fontSize: 12, lineHeight: 20, color: palette.muted, marginTop: 13},
});
