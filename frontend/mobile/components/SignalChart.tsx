import React, {useState} from 'react';
import {StyleSheet, Text, View} from 'react-native';
import Svg, {Circle, Line, Polyline, Text as SvgText} from 'react-native-svg';
import {chartSegments, percent, probabilitySignals} from '@driver-monitor/shared';
import type {MonitorSnapshot} from '@driver-monitor/shared';
import {palette} from './ui';

const lineColors = {eye_1_closed: '#20634F', eye_2_closed: '#326D98', yawn: '#94621A'};

export function SignalChart({samples}: {samples: MonitorSnapshot[]}) {
  const [width, setWidth] = useState(300);
  const current = samples.at(-1);
  const parsedEnd = current ? Date.parse(current.utc) : Date.now();
  const end = Number.isFinite(parsedEnd) ? parsedEnd : Date.now();
  const start = end - 60000;
  const left = 40, right = Math.max(left + 1, width - 8);
  const x = (time: number) => left + (time - start) / 60000 * (right - left);
  const y = (value: number) => 72 - value * 60;

  return <View onLayout={event => setWidth(Math.max(160, event.nativeEvent.layout.width))}>
    {probabilitySignals.map(({key, label: title, description}) => {
      const color = lineColors[key];
      const segments = chartSegments(samples
        .filter(sample => Date.parse(sample.utc) >= start && Date.parse(sample.utc) <= end)
        .map(sample => ({x: Date.parse(sample.utc), y: sample.probabilities[key]})));
      return <View key={key} style={s.signal}>
        <View style={s.heading}>
          <View style={s.label}>
            <View style={[s.marker, {backgroundColor: color}]}/>
            <View style={{flex: 1}}><Text style={s.title}>{title}</Text><Text style={s.description}>{description}</Text></View>
          </View>
          <Text style={[s.value, {color}]}>{percent(current?.probabilities[key])}</Text>
        </View>
        <View accessible accessibilityLabel={title + ': ' + percent(current?.probabilities[key]) + ', biểu đồ 60 giây'}>
          <Svg width="100%" height={84} viewBox={'0 0 ' + width + ' 84'} accessible={false}>
            {[0, 0.5, 1].map(value => <React.Fragment key={value}>
              <Line x1={left} x2={right} y1={y(value)} y2={y(value)} stroke="#DDE6E0"/>
              <SvgText x={0} y={y(value) + 4} fill={palette.muted} fontSize={12}>{value * 100}%</SvgText>
            </React.Fragment>)}
            {[left, (left + right) / 2, right].map(position => <Line key={position}
              x1={position} x2={position} y1={12} y2={72} stroke="#E1E8E3" strokeDasharray="3 4"/>)}
            {segments.map((segment, index) => segment.length === 1
              ? <Circle key={index} cx={x(segment[0].x)} cy={y(segment[0].y)} r={2.5} fill={color}/>
              : <Polyline key={index} points={segment.map(point => x(point.x) + ',' + y(point.y)).join(' ')}
                fill="none" stroke={color} strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round"/>)}
          </Svg>
        </View>
      </View>;
    })}
    <View style={s.axis}>{['−60 giây', '−30 giây', 'Hiện tại'].map(text => <Text key={text} style={s.axisText}>{text}</Text>)}</View>
    <Text style={s.note}>Cùng trục 60 giây · Đường ngắt khi thiếu dữ liệu</Text>
  </View>;
}

const s = StyleSheet.create({
  signal: {borderTopWidth: 1, borderColor: palette.line, paddingTop: 15, marginBottom: 10},
  heading: {flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 7},
  label: {flexDirection: 'row', gap: 9, alignItems: 'center', flex: 1},
  marker: {width: 4, height: 32, borderRadius: 2},
  title: {fontSize: 14, fontWeight: '700', color: palette.ink},
  description: {fontSize: 12, lineHeight: 18, color: palette.muted, marginTop: 2},
  value: {fontSize: 23, fontWeight: '700', fontVariant: ['tabular-nums']},
  axis: {flexDirection: 'row', justifyContent: 'space-between', paddingLeft: 40, paddingRight: 8},
  axisText: {fontSize: 12, color: palette.muted},
  note: {fontSize: 12, lineHeight: 19, color: palette.muted, marginTop: 13},
});
