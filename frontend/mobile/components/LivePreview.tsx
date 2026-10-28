import React, {useEffect, useRef, useState} from 'react';
import {ActivityIndicator, StyleSheet, Text, View} from 'react-native';
import {Image} from 'expo-image';
import {PreviewStream} from '@driver-monitor/shared';
import type {ApiClient, FrameSource} from '@driver-monitor/shared';
import {Icon} from './Icon';

export function LivePreview({api, enabled, paused = false}: {
  api: ApiClient | null;
  enabled: boolean;
  paused?: boolean;
}) {
  const [source, setSource] = useState<FrameSource | null>(null);
  const [fresh, setFresh] = useState(false);
  const stream = useRef<PreviewStream | null>(null);

  useEffect(() => {
    setSource(null);
    setFresh(false);
    if (!api || !enabled) return;
    const current = new PreviewStream(api, setSource, setFresh);
    stream.current = current;
    current.start();
    return () => {
      current.stop();
      stream.current = null;
    };
  }, [api, enabled]);

  return <View style={s.preview} accessibilityLabel="Ảnh camera từ máy xử lý">
    {enabled && api && source && <Image
      style={[StyleSheet.absoluteFill, {opacity: fresh ? 1 : 0.22}]}
      source={{uri: source.uri, headers: api.headers}}
      cachePolicy="none"
      contentFit="contain"
      transition={0}
      onLoad={event => stream.current?.loaded(event.source.url)}
      onError={() => stream.current?.failed(source.uri)}
      accessibilityLabel="Khung hình camera có chú thích nhận diện"
    />}
    {fresh ? <View style={s.live}>
      <View style={s.liveDot}/><Text style={s.liveText}>Ảnh đang cập nhật</Text>
    </View> : <View style={s.placeholder}>
      <View style={s.icon}>
        {enabled ? <ActivityIndicator color="#BDD6C6"/> : <Icon name="camera" size={30} color="#BDD6C6"/>}
      </View>
      <Text style={s.title}>{paused ? 'Ảnh đang tạm dừng' : enabled ? 'Đang chờ ảnh mới' : 'Chưa có ảnh camera'}</Text>
      <Text style={s.caption}>{paused ? 'Quay lại app để tiếp tục xem.' : enabled
        ? 'Camera và kết nối cần có dữ liệu mới.'
        : 'Ảnh sẽ xuất hiện khi máy xử lý sẵn sàng.'}</Text>
    </View>}
  </View>;
}

const s = StyleSheet.create({
  preview: {aspectRatio: 4 / 3, backgroundColor: '#142D26', overflow: 'hidden'},
  placeholder: {position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, alignItems: 'center', justifyContent: 'center', padding: 24},
  icon: {width: 62, height: 62, borderRadius: 21, backgroundColor: '#254439', alignItems: 'center', justifyContent: 'center'},
  title: {fontSize: 17, lineHeight: 24, fontWeight: '600', color: '#F4F8F5', textAlign: 'center', marginTop: 16},
  caption: {fontSize: 14, lineHeight: 22, color: '#BDD0C5', textAlign: 'center', marginTop: 7, maxWidth: 280},
  live: {position: 'absolute', top: 12, left: 12, borderRadius: 20, backgroundColor: '#143E34E6', paddingHorizontal: 10, paddingVertical: 7, flexDirection: 'row', alignItems: 'center', gap: 6},
  liveDot: {width: 6, height: 6, backgroundColor: '#A5E1B9', borderRadius: 3},
  liveText: {fontSize: 12, fontWeight: '600', color: '#FFFFFF'},
});
