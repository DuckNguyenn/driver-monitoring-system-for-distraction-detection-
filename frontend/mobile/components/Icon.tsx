import React from 'react';
import Svg, {Path} from 'react-native-svg';

const paths = {
  shield: 'M12 3 4.5 6v5c0 4.5 3 7.6 7.5 10 4.5-2.4 7.5-5.5 7.5-10V6L12 3Z M8.5 12l2.3 2.3 4.7-4.8',
  monitor: 'M4 4h16v12H4V4Z M8 21h8 M12 16v5 M7 10h3l2-3 2 6 2-3h2',
  history: 'M4 11a8 8 0 1 1 2 6 M4 4v7h7 M12 7v5l3 2',
  link: 'm10 13 4-4 M8.5 16.5l-1 1a4.2 4.2 0 0 1-6-6l4-4a4.2 4.2 0 0 1 6 0 M15.5 7.5l1-1a4.2 4.2 0 0 1 6 6l-4 4a4.2 4.2 0 0 1-6 0',
  camera: 'M3 7h4l2-3h6l2 3h4v13H3V7Z M16 13a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
  eye: 'M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z',
  eyeOff: 'm3 3 18 18 M10 6c6-1 10 4 12 6a19 19 0 0 1-4 4 M14 18C7 20 3 14 2 12a20 20 0 0 1 4-4',
  arrow: 'M4 12h16 m-6-6 6 6-6 6',
  back: 'M20 12H4 m6-6-6 6 6 6',
  chevron: 'm9 5 7 7-7 7',
  lock: 'M6 10h12v11H6V10Z M8 10V7a4 4 0 0 1 8 0v3 M12 14v3',
  server: 'M4 3h16v7H4V3Z M4 14h16v7H4v-7Z M8 6.5h.1 M8 17.5h.1 M15 6.5h2 M15 17.5h2',
  wifi: 'M2 8a16 16 0 0 1 20 0 M5 12a11 11 0 0 1 14 0 M9 16a5 5 0 0 1 6 0 M12 20h.01',
  info: 'M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18Z M12 11v5 M12 7h.01',
  bell: 'M5 17h14l-2-4V9a5 5 0 0 0-10 0v4l-2 4Z M10 21h4',
  warning: 'm12 3 10 18H2L12 3Z M12 9v5 M12 17h.01',
  close: 'm6 6 12 12 M18 6 6 18',
  pulse: 'M2 12h5l3-8 4 16 3-8h5',
  filter: 'M4 6h16 M7 12h10 M10 18h4',
  search: 'M11 3a8 8 0 1 1 0 16 8 8 0 0 1 0-16Z m6 14 4 4',
  download: 'M12 3v12 m-5-5 5 5 5-5 M4 16v5h16v-5',
  refresh: 'M20 8a8 8 0 0 0-14-3L3 8 M3 3v5h5 M4 16a8 8 0 0 0 14 3l3-3 M21 21v-5h-5',
  chip: 'M6 6h12v12H6V6Z M9 9h6v6H9V9Z M9 2v4 M15 2v4 M9 18v4 M15 18v4 M2 9h4 M2 15h4 M18 9h4 M18 15h4',
  mouth: 'M5 6c4-3 10-3 14 0v6a7 7 0 0 1-14 0V6Z M8 8h8',
  calendar: 'M4 5h16v16H4V5Z M8 2v6 M16 2v6 M4 11h16 M8 15h2 M14 15h2',
};
export type IconName = keyof typeof paths;
export function Icon({name, size = 22, color = '#174D42'}: {name: IconName; size?: number; color?: string}) {
  return <Svg width={size} height={size} viewBox="0 0 24 24" accessible={false}>
    <Path d={paths[name]} fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round"/>
  </Svg>;
}
