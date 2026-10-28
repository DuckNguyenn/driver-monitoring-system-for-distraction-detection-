import React, {useEffect, useMemo, useState} from 'react';
import {ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View} from 'react-native';
import {File, Paths} from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import {ApiClient, HistoryReader, label, numberText, sourceLabel, timeText} from '@driver-monitor/shared';
import type {Event, MonitorSnapshot, Session} from '@driver-monitor/shared';
import {Icon} from './Icon';
import {SignalChart} from './SignalChart';
import {Badge, Button, Card, EmptyState, Notice, palette, SectionTitle, ui} from './ui';

type Props = {api: ApiClient | null; onConnect: () => void; onNavigate?: () => void};
export function History({api, onConnect, onNavigate}: Props) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selected, setSelected] = useState<Session | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [samples, setSamples] = useState<MonitorSnapshot[]>([]);
  const [error, setError] = useState('');
  const [listing, setListing] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [from, setFrom] = useState('');
  const [until, setUntil] = useState('');
  const [filter, setFilter] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [offset, setOffset] = useState(0);
  const [next, setNext] = useState<number | null>(null);
  const busy = listing || detailLoading || sharing;
  const reader = useMemo(() => api ? new HistoryReader(api) : null, [api]);

  async function load(cursor = 0) {
    if (!reader) return;
    setListing(true);
    setError('');
    try {
      const query = new URLSearchParams({offset: String(cursor), limit: '20'});
      if (from) query.set('start', new Date(from + 'T00:00:00').toISOString());
      if (until) query.set('end', new Date(until + 'T23:59:59').toISOString());
      const page = await reader.list('?' + query);
      if (!page) return;
      setSessions(page.items);
      setOffset(cursor);
      setNext(page.next_offset);
      setListing(false);
    } catch (failure) {
      setError(failure instanceof RangeError ? 'Nhập ngày theo định dạng YYYY-MM-DD.' : String(failure));
      setListing(false);
    }
  }
  useEffect(() => {
    setSessions([]); setSelected(null); setEvents([]); setSamples([]);
    setListing(false); setDetailLoading(false);
    void load();
    return () => reader?.invalidate();
  }, [reader]);

  async function open(session: Session) {
    if (!reader) return;
    setSelected(session); setDetailLoading(true); setError(''); setEvents([]); setSamples([]);
    onNavigate?.();
    try {
      const data = await reader.load(session.id);
      if (!data) return;
      setSamples(data.samples); setEvents(data.events); setDetailLoading(false);
    } catch (failure) { setError(String(failure)); setDetailLoading(false); }
  }
  function back() {
    reader?.invalidate(); setDetailLoading(false); setSelected(null); setError(''); onNavigate?.();
  }
  async function share() {
    if (!api || !selected) return;
    setSharing(true); setError('');
    try {
      const text = await api.csv(selected.id);
      const file = new File(Paths.cache, selected.id.replace(/[^a-zA-Z0-9_-]/g, '_') + '.csv');
      file.create({overwrite: true}); file.write(text);
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(file.uri, {mimeType: 'text/csv', UTI: 'public.comma-separated-values-text'});
      } else setError('Thiết bị chưa hỗ trợ chia sẻ file.');
    } catch (failure) { setError(String(failure)); }
    finally { setSharing(false); }
  }
  if (!api) return <EmptyState icon="history" title="Nhật ký ở một nơi" body="Kết nối với máy xử lý để xem lại các phiên giám sát và sự kiện đã ghi nhận.">
    <Button title="Thiết lập kết nối" icon="link" onPress={onConnect}/>
  </EmptyState>;

  if (selected) return <>
    <Pressable accessibilityRole="button" onPress={back} disabled={sharing} style={s.back}>
      <Icon name="back" size={20}/><Text style={s.link}>Tất cả phiên</Text>
    </Pressable>
    {error !== '' && <Notice text={error} error/>}
    <Card>
      <View style={ui.between}><Text style={ui.sectionHeading}>Chi tiết phiên</Text>
        <Badge text={label(selected.lifecycle)} tone={selected.lifecycle === 'error' ? 'red' : 'neutral'}/>
      </View>
      <Text style={s.detailDate}>{timeText(selected.started_at)}</Text>
      <Text style={ui.body}>{sourceLabel(selected.source_kind)}</Text>
      {!!selected.source && <Text style={ui.caption} selectable>Nguồn: {selected.source}</Text>}
      <Text style={[ui.caption, {marginTop: 10}]} selectable>{selected.id}</Text>
      <View style={s.summary}>
        {[[String(selected.summary.frames ?? '—'), 'Khung hình'], [numberText(selected.summary.fps), 'FPS'], [numberText(selected.summary.latency_p95_ms, 0), 'p95 · ms']].map(([value, caption]) =>
          <View style={s.metric} key={caption}><Text style={s.metricValue}>{value}</Text><Text style={ui.caption}>{caption}</Text></View>)}
      </View>
      {selected.summary.fault && <Notice text={selected.summary.fault} error/>}
      <Button title="Xuất / Chia sẻ CSV" icon="download" secondary loading={sharing} disabled={busy} onPress={() => void share()}/>
    </Card>
    {detailLoading ? <Loading text="Đang tải chi tiết phiên…"/> : <>
      <Card><SectionTitle title="Tín hiệu cuối phiên" caption="Ba tín hiệu trong 60 giây cuối" icon="pulse"/><SignalChart samples={samples}/></Card>
      <Card><SectionTitle title="Dòng sự kiện" caption={events.length ? events.length + ' sự kiện đã ghi nhận' : undefined} icon="history"/>
        {!events.length && !error && <Text style={ui.body}>Chưa có sự kiện được ghi nhận.</Text>}
        {events.map((event, index) => <View key={event.id} style={s.event}>
          <View style={s.timeline}><View style={[s.eventDot, event.kind === 'alert' && {backgroundColor: palette.red}]}/>
            {index < events.length - 1 && <View style={s.eventLine}/>}</View>
          <View style={s.eventContent}><Text style={s.eventTitle}>{label(event.kind)}</Text><Text style={ui.caption}>{timeText(event.utc)}</Text>
            <Text style={s.eventBody}>{event.payload.reasons?.map(label).join(' · ') || event.payload.error || event.payload.fault || ''}</Text>
          </View>
        </View>)}
      </Card>
    </>}
  </>;

  const shown = sessions.filter(value => !filter || (value.id + ' ' + value.source).toLowerCase().includes(filter.toLowerCase()));
  return <>
    <Card>
      <View style={s.search}><Icon name="search" size={20} color={palette.muted}/>
        <TextInput accessibilityLabel="Tìm phiên" placeholder="Tìm phiên trong trang…" placeholderTextColor={palette.muted}
          style={s.searchInput} value={filter} onChangeText={setFilter} autoCapitalize="none"/>
      </View>
      <View style={[ui.between, {marginTop: 8}]}>
        <Pressable accessibilityRole="button" accessibilityState={{expanded: showFilters}} style={s.filterButton} onPress={() => setShowFilters(!showFilters)}>
          <Icon name="filter" size={19}/><Text style={s.link}>Bộ lọc ngày</Text>
        </Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel="Làm mới lịch sử" disabled={busy} style={s.refresh} onPress={() => void load(0)}>
          <Icon name="refresh" size={20}/>
        </Pressable>
      </View>
      {showFilters && <View style={s.filters}>
        <View style={s.dateRow}>
          <DateField title="Từ ngày" value={from} onChange={setFrom}/>
          <DateField title="Đến ngày" value={until} onChange={setUntil}/>
        </View>
        <Text style={[ui.caption, {marginBottom: 14}]}>Tìm kiếm theo mã / nguồn chỉ áp dụng trong trang hiện tại.</Text>
        <Button title="Áp dụng bộ lọc" icon="filter" disabled={busy} onPress={() => void load(0)}/>
      </View>}
    </Card>
    {error !== '' && <Notice text={error} error/>}
    <View style={[ui.between, {marginBottom: 14}]}><Text style={ui.sectionHeading}>Các phiên giám sát</Text><Text style={ui.caption}>Trang {Math.floor(offset / 20) + 1}</Text></View>
    {listing && <Loading text="Đang tải nhật ký…"/>}
    {!listing && !shown.length && !error && <EmptyState icon="calendar" title="Chưa có phiên phù hợp" body="Thử đổi từ khóa, khoảng ngày hoặc làm mới danh sách."/>}
    {shown.map(session => <Pressable key={session.id} accessibilityRole="button" accessibilityLabel={'Xem phiên ' + session.id}
      onPress={() => void open(session)} style={({pressed}) => [s.session, pressed && {backgroundColor: '#EAF1EB'}]}>
      <View style={s.sessionIcon}><Icon name={session.source_kind === 'camera' ? 'camera' : 'history'} size={23}/></View>
      <View style={s.sessionContent}><Text style={s.sessionDate}>{timeText(session.started_at)}</Text>
        <Text style={ui.caption}>{sourceLabel(session.source_kind)} · {label(session.lifecycle)}</Text>
        <Text style={s.sessionId} numberOfLines={1}>{session.id}</Text>
        {!!session.source && <Text style={ui.caption} numberOfLines={1}>Nguồn: {session.source}</Text>}
      </View><Icon name="chevron" size={19} color={palette.muted}/>
    </Pressable>)}
    <View style={s.pagination}>
      <View style={{flex: 1}}><Button title="Trang trước" icon="back" secondary disabled={offset === 0 || busy} onPress={() => void load(Math.max(0, offset - 20))}/></View>
      <View style={{flex: 1}}><Button title="Trang sau" icon="arrow" secondary disabled={next === null || busy} onPress={() => void load(next!)}/></View>
    </View>
  </>;
}
function DateField({title, value, onChange}: {title: string; value: string; onChange: (value: string) => void}) {
  return <View style={{flex: 1}}><Text style={ui.label}>{title}</Text>
    <TextInput accessibilityLabel={title} style={ui.input} placeholder="YYYY-MM-DD" placeholderTextColor={palette.muted}
      value={value} onChangeText={onChange} autoCapitalize="none"/>
  </View>;
}
function Loading({text}: {text: string}) {
  return <View style={s.loading}><ActivityIndicator color={palette.green}/><Text style={ui.caption}>{text}</Text></View>;
}
const s = StyleSheet.create({
  search: {flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#F4F7F4', borderRadius: 13, paddingHorizontal: 12},
  searchInput: {flex: 1, minHeight: 50, paddingVertical: 12, color: palette.ink, fontSize: 14},
  filterButton: {flexDirection: 'row', alignItems: 'center', gap: 8, minHeight: 48},
  refresh: {width: 48, minHeight: 48, alignItems: 'center', justifyContent: 'center'},
  filters: {borderTopWidth: 1, borderColor: palette.line, paddingTop: 16, marginTop: 5},
  dateRow: {flexDirection: 'row', gap: 10, marginBottom: 10},
  link: {color: palette.green, fontSize: 13, fontWeight: '600'},
  session: {flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: '#FFFFFF', borderRadius: 19, borderWidth: 1, borderColor: palette.line, padding: 17, marginBottom: 12},
  sessionIcon: {width: 46, height: 46, borderRadius: 15, backgroundColor: palette.mint, alignItems: 'center', justifyContent: 'center'},
  sessionContent: {flex: 1}, sessionDate: {fontSize: 14, fontWeight: '700', color: palette.ink},
  sessionId: {fontSize: 11, color: palette.muted, marginTop: 8},
  pagination: {flexDirection: 'row', gap: 12, marginTop: 10, marginBottom: 15},
  loading: {alignItems: 'center', paddingVertical: 24, gap: 7},
  back: {flexDirection: 'row', alignItems: 'center', gap: 9, minHeight: 48, marginBottom: 12},
  detailDate: {fontSize: 19, fontWeight: '700', color: palette.ink, marginTop: 18, marginBottom: 6},
  summary: {flexDirection: 'row', backgroundColor: '#F4F7F4', borderRadius: 15, paddingVertical: 18, marginVertical: 20},
  metric: {flex: 1, alignItems: 'center'}, metricValue: {fontSize: 23, fontWeight: '700', color: palette.ink},
  event: {flexDirection: 'row', gap: 13}, timeline: {alignItems: 'center', width: 12, paddingTop: 6},
  eventDot: {width: 9, height: 9, borderRadius: 5, backgroundColor: palette.green},
  eventLine: {width: 1, flex: 1, backgroundColor: palette.line, marginTop: 5},
  eventContent: {flex: 1, paddingBottom: 22}, eventTitle: {fontSize: 14, fontWeight: '700', color: palette.ink},
  eventBody: {fontSize: 13, lineHeight: 20, color: palette.muted, marginTop: 5},
});
