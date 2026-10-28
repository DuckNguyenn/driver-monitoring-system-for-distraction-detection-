export type DriverState = 'NORMAL' | 'WARNING' | 'ALERT' | 'UNKNOWN';
export interface MonitorSnapshot {
  schema_version: 1; session_id: string; sequence: number; utc: string; source_timestamp: number | null;
  source_kind: 'camera' | 'video' | 'unknown'; source: string; backend: string | null;
  lifecycle: 'initializing' | 'running' | 'finished' | 'error'; state: DriverState; alert: boolean;
  alert_episode_id: string | null; reasons: string[]; connected: boolean; age_ms: number;
  probabilities: {eye_1_closed: number | null; eye_2_closed: number | null; yawn: number | null; yawn_raw: number | null};
  counts: {blink_total: number | null; blink_5s: number | null; yawn_60s: number | null; eye_cycles: number | null};
  quality: {image: string; eyes: string; metrics: Record<string, number | string | null>};
  performance: {fps: number | null; latency_ms: number | null; processing_ms: number | null};
  devices: {camera: Device; models: Device; esp32: Device & {configured: boolean; ack_age_seconds: number | null}};
}
export interface Device {state: string; error: string | null}
export interface Session {
  id: string; started_at: string; ended_at: string | null; source: string; source_kind: string;
  backend: string | null; lifecycle: string;
  summary: {frames?: number; fps?: number; latency_p95_ms?: number | null; fault?: string | null};
}
export interface Event {id: string; session_id: string; utc: string; kind: string; payload: {state?: string; reasons?: string[]; error?: string; fault?: string}}
export interface Page<T> {items: T[]; next_offset: number | null}
export interface Connection {server: string; token: string}

export const stateLabels: Record<DriverState, string> = {NORMAL: 'Bình thường', WARNING: 'Cần chú ý', ALERT: 'Cảnh báo', UNKNOWN: 'Chưa xác định'};
const labels: Record<string, string> = {
  prolonged_eye_closure: 'Hai mắt nhắm kéo dài', frequent_yawning: 'Ngáp nhiều lần', increased_blinking: 'Chớp mắt tăng',
  eyes_closed_too_long: 'Hai mắt nhắm kéo dài', blink_rate_increasing: 'Chớp mắt tăng', recovering: 'Đang xác nhận hồi phục',
  invalid_probabilities: 'Xác suất chưa hợp lệ', driver_changed: 'Vị trí tài xế thay đổi',
  blurry: 'Ảnh mờ', dark: 'Thiếu sáng', no_face: 'Không thấy mặt', multiple_faces: 'Nhiều khuôn mặt',
  uncertain_eyes: 'Mắt chưa xác định', stale_frame: 'Frame quá cũ', frame_gap: 'Gián đoạn frame',
  eye_motion: 'Đầu đang chuyển động', eye_motion_settling: 'Chờ góc mặt ổn định', eye_quality: 'Mắt chưa đủ rõ',
  eye_model_changed: 'Đang xác nhận lại trạng thái mắt', head_motion: 'Chờ góc mặt ổn định',
  eyewear_fault: 'Nhận diện kính gặp lỗi; đang dùng nhánh mắt gốc', eye_routing_enabled: 'Bật tự nhận kính',
  camera_timeout: 'Camera không trả ảnh', camera_error: 'Lỗi camera', runtime_fault: 'Lỗi xử lý',
  usable: 'Đủ chất lượng', unavailable: 'Chưa có dữ liệu', overexposed: 'Cháy sáng', face_too_small: 'Mặt quá nhỏ',
  connected: 'Đã kết nối', ready: 'Sẵn sàng', not_configured: 'Chưa cấu hình', unconfirmed: 'Chưa nhận ACK',
  inactive: 'Đã dừng', initializing: 'Đang khởi động', running: 'Đang chạy', finished: 'Đã kết thúc', error: 'Có lỗi',
  state: 'Đổi trạng thái', alert: 'Bật cảnh báo', blink: 'Chớp mắt', yawn: 'Ngáp', serial_fault: 'Lỗi ESP32',
  startup: 'Khởi động', session_start: 'Bắt đầu phiên', session_end: 'Kết thúc phiên', telemetry_fault: 'Lỗi xuất dữ liệu',
};
export const label = (value: string) => labels[value] ?? value.replaceAll('_', ' ');
export const percent = (value: number | null | undefined) => value == null ? '—' : `${Math.round(value * 100)}%`;
export const numberText = (value: number | null | undefined, digits = 1) => value == null ? '—' : value.toFixed(digits);
export const timeText = (value: string | null | undefined) => value ? new Date(value).toLocaleString('vi-VN') : '—';
export const sourceLabel = (kind: string) => kind === 'video' ? 'Phát lại video' : kind === 'camera' ? 'Camera trực tiếp' : 'Chưa xác định nguồn';
export const probabilitySignals = [
  {key:'eye_1_closed',label:'Mắt 1',description:'Xác suất nhắm mắt',color:'#278b73'},
  {key:'eye_2_closed',label:'Mắt 2',description:'Xác suất nhắm mắt',color:'#4e85bb'},
  {key:'yawn',label:'Ngáp',description:'Xác suất đã lọc',color:'#d49733'},
] as const;

export function normalizeServer(value: string): string {
  const url = new URL(value.includes('://') ? value.trim() : `http://${value.trim()}`);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== '/')
    throw new Error('Nhập địa chỉ máy chủ, ví dụ http://192.168.1.10:8765');
  return url.origin;
}

export function normalizeMobileServer(value: string): string {
  const server=normalizeServer(value), hostname=new URL(server).hostname.toLowerCase();
  if(hostname==='localhost' || hostname==='localhost.' || hostname.endsWith('.localhost') ||
     hostname==='[::1]' || hostname==='[::]' || hostname==='0.0.0.0' || hostname.startsWith('127.'))
    throw new Error('Trên điện thoại, hãy nhập IPv4 Wi-Fi của PC / Radxa đang chạy serve. Địa chỉ 127.0.0.1/localhost trỏ vào chính điện thoại.');
  return server;
}

export class ApiClient {
  readonly server: string;
  readonly token: string;
  constructor(connection: Connection) {this.server = normalizeServer(connection.server); this.token = connection.token.trim();}
  get headers() {return {Authorization: `Bearer ${this.token}`};}
  frameUrl(sequence: number, after?: string) {return `${this.server}/api/v1/frame.jpg?t=${sequence}${after===undefined?'':`&after=${encodeURIComponent(after)}`}`;}
  async frameMetadata(nonce: number, signal: AbortSignal, after?: string): Promise<FrameSource> {
    const uri=this.frameUrl(nonce,after);
    const response=await fetch(uri,{method:'HEAD',headers:this.headers,signal,cache:'no-store'});
    const sequence=response.headers.get('X-Frame-Sequence');
    if(!response.ok || sequence===null)throw new Error('Camera chưa có ảnh mới');
    return {uri,sequence};
  }
  async request<T>(path: string, text = false): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(`${this.server}/api/v1/${path}`, {headers: this.headers, signal: controller.signal, cache: 'no-store'}).catch(()=>{
        throw new Error(`Không kết nối được ${this.server}${controller.signal.aborted?' trong 8 giây':''}. Kiểm tra serve trên PC, cùng Wi-Fi và quyền truy cập mạng cục bộ.`);
      });
      if (!response.ok) throw new Error(response.status === 401 ? 'Mã kết nối không hợp lệ' : `Yêu cầu thất bại (${response.status})`);
      return await (text ? response.text() : response.json()) as T;
    } finally {clearTimeout(timeout);}
  }
  status() {return this.request<MonitorSnapshot | null>('status');}
  sessions(query = '') {return this.request<Page<Session>>(`sessions${query}`);}
  session(id: string) {return this.request<Session>(`sessions/${encodeURIComponent(id)}`);}
  series(id: string, offset = 0) {return this.request<Page<MonitorSnapshot>>(`sessions/${encodeURIComponent(id)}/series?offset=${offset}`);}
  events(id: string, offset = 0) {return this.request<Page<Event>>(`sessions/${encodeURIComponent(id)}/events?offset=${offset}`);}
  csv(id: string) {return this.request<string>(`sessions/${encodeURIComponent(id)}/export.csv`, true);}
}

export function effectiveConnection(connected: boolean, serverAge: number, receivedAt: number, now: number) {
  return connected && serverAge + Math.max(0, now - receivedAt) <= 2000;
}

type SocketFactory = (url: string) => WebSocket;
export class LiveConnection {
  private socket: WebSocket | null = null;
  private stopped = true;
  private retry: ReturnType<typeof setTimeout> | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private attempt = 0;
  private receivedAt = 0;
  private value: MonitorSnapshot | null = null;
  private api: ApiClient;
  private onSnapshot: (value: MonitorSnapshot | null) => void;
  private onError: (message: string) => void;
  private factory: SocketFactory;
  constructor(api: ApiClient, onSnapshot: (value: MonitorSnapshot | null) => void,
              onError: (message: string) => void, factory: SocketFactory = url => new WebSocket(url)) {
    this.api = api; this.onSnapshot = onSnapshot; this.onError = onError; this.factory = factory;
  }
  start() {
    this.stopped = false;
    this.open();
    this.timer = setInterval(() => {
      if (this.value && !effectiveConnection(this.value.connected, this.value.age_ms, this.receivedAt, Date.now()))
        this.onSnapshot({...this.value, connected: false});
    }, 250);
  }
  private open() {
    if (this.stopped) return;
    let socket: WebSocket;
    try {socket = this.factory(`${this.api.server.replace(/^http/, 'ws')}/api/v1/ws`);}
    catch {this.onError('Mất kết nối. Đang thử lại…');this.retry = setTimeout(() => this.open(), Math.min(5000, 500 * 2 ** this.attempt++));return;}
    this.socket = socket;
    socket.onopen = () => {if (!this.stopped) socket.send(JSON.stringify({type: 'auth', token: this.api.token}));};
    socket.onmessage = event => {
      if (this.stopped || socket !== this.socket) return;
      try {
        const message = JSON.parse(String(event.data));
        if (message.type !== 'snapshot') return;
        const value = message.snapshot as MonitorSnapshot | null;
        if (value !== null && (value.schema_version !== 1 || !Object.hasOwn(stateLabels, value.state))) return;
        this.attempt = 0; this.receivedAt = Date.now(); this.value = value;
        this.onError(''); this.onSnapshot(value);
      } catch {this.onError('Dữ liệu máy chủ không hợp lệ');}
    };
    socket.onerror = () => {if (!this.stopped) this.onError('Mất kết nối. Đang thử lại…');};
    socket.onclose = event => {
      if (this.stopped || socket !== this.socket) return;
      if (this.value) this.onSnapshot({...this.value, connected: false});
      if (event.code === 1008) {this.onError('Mã kết nối bị từ chối. Kiểm tra lại trong mục Kết nối.'); return;}
      this.onError('Mất kết nối. Đang thử lại…');
      this.retry = setTimeout(() => this.open(), Math.min(5000, 500 * 2 ** this.attempt++));
    };
  }
  stop() {
    this.stopped = true;
    if (this.retry) clearTimeout(this.retry);
    if (this.timer) clearInterval(this.timer);
    this.socket?.close(); this.socket = null;
  }
}

export class AlertMemory {
  private ids: string[];
  constructor(ids: string[] = []) {this.ids = ids.slice(-64);}
  accept(value: {alert: boolean; connected: boolean; source_kind: string; alert_episode_id: string | null}): boolean {
    const id = value.alert_episode_id;
    if (!value.connected || !value.alert || !id || value.source_kind !== 'camera' || this.ids.includes(id)) return false;
    this.ids.push(id); this.ids = this.ids.slice(-64);
    return true;
  }
  export() {return [...this.ids];}
}

export interface Point {x: number; y: number | null}
export function chartSegments(points: Point[]): {x: number; y: number}[][] {
  const segments: {x: number; y: number}[][] = [];
  let current: {x: number; y: number}[] = [];
  for (const point of points) {
    if (point.y == null || !Number.isFinite(point.y) || !Number.isFinite(point.x)) {if (current.length) segments.push(current); current = [];}
    else {
      const previous=current.at(-1);
      if(previous && (point.x-previous.x>2000 || point.x<previous.x)){segments.push(current);current=[];}
      current.push({x: point.x, y: point.y});
    }
  }
  if (current.length) segments.push(current);
  return segments;
}
export function appendSample(samples: MonitorSnapshot[], next: MonitorSnapshot): MonitorSnapshot[] {
  if (samples.at(-1)?.session_id === next.session_id && samples.at(-1)?.sequence === next.sequence) return samples;
  const cutoff = Date.parse(next.utc) - 60000;
  return [...samples.filter(s => s.session_id === next.session_id && Date.parse(s.utc) >= cutoff), next].slice(-400);
}

export class HistoryReader {
  private listVersion=0;
  private detailVersion=0;
  private api: Pick<ApiClient,'sessions'|'series'|'events'>;
  constructor(api: Pick<ApiClient,'sessions'|'series'|'events'>){this.api=api;}
  invalidate(){this.listVersion++;this.detailVersion++;}
  async list(query: string): Promise<Page<Session>|null> {
    const version=++this.listVersion;
    try{const page=await this.api.sessions(query);return version===this.listVersion?page:null;}
    catch(error){if(version===this.listVersion)throw error;return null;}
  }
  async load(id: string): Promise<{samples: MonitorSnapshot[];events: Event[]}|null> {
    const version=++this.detailVersion;
    try{
      let cursor:number|null=0;const samples:MonitorSnapshot[]=[],events:Event[]=[];
      do{const page=await this.api.series(id,cursor);if(version!==this.detailVersion)return null;samples.push(...page.items);cursor=page.next_offset;}while(cursor!==null);
      cursor=0;do{const page=await this.api.events(id,cursor);if(version!==this.detailVersion)return null;events.push(...page.items);cursor=page.next_offset;}while(cursor!==null);
      const last=samples.at(-1);
      return {samples:last?samples.filter(value=>Date.parse(value.utc)>=Date.parse(last.utc)-60000):[],events:events.reverse()};
    }catch(error){if(version===this.detailVersion)throw error;return null;}
  }
}

export interface FrameSource {uri: string;sequence: string}
export class PreviewStream {
  private stopped=true;
  private source:FrameSource|null=null;
  private loadedSequence:string|null=null;
  private loadedAt=-Infinity;
  private requestedAt=-Infinity;
  private poll:ReturnType<typeof setTimeout>|null=null;
  private watchdog:ReturnType<typeof setInterval>|null=null;
  private request:AbortController|null=null;
  private api: Pick<ApiClient,'frameMetadata'>;
  private onSource:(value:FrameSource)=>void;
  private onFresh:(fresh:boolean)=>void;
  constructor(api: Pick<ApiClient,'frameMetadata'>,onSource:(value:FrameSource)=>void,onFresh:(fresh:boolean)=>void){this.api=api;this.onSource=onSource;this.onFresh=onFresh;}
  start(){
    this.stopped=false;this.onFresh(false);
    this.watchdog=setInterval(()=>{if(Date.now()-this.loadedAt>2000)this.onFresh(false);},250);
    void this.tick();
  }
  private async tick(){
    if(this.stopped)return;
    if(this.source && this.loadedSequence!==this.source.sequence && Date.now()-this.requestedAt<1500){
      this.poll=setTimeout(()=>{void this.tick();},1000/30);
      return;
    }
    const began=Date.now(),request=new AbortController();this.request=request;
    const timeout=setTimeout(()=>request.abort(),1500);
    try{
      const frame=await this.api.frameMetadata(began,request.signal,this.loadedSequence??undefined);
      if(this.stopped)return;
      // Replace an image request that never completes; repeat headers cannot extend freshness.
      if(frame.sequence!==this.source?.sequence || (this.loadedSequence!==frame.sequence && Date.now()-this.requestedAt>=1500)){
        this.source=frame;this.requestedAt=Date.now();this.onSource(frame);
      }
    }catch{if(!this.stopped)this.onFresh(false);}
    finally{clearTimeout(timeout);if(this.request===request)this.request=null;}
    if(!this.stopped)this.poll=setTimeout(()=>{void this.tick();},Math.max(0,1000/30-(Date.now()-began)));
  }
  loaded(uri: string){
    if(this.stopped || !this.source || uri!==this.source.uri)return;
    if(this.source.sequence!==this.loadedSequence){this.loadedSequence=this.source.sequence;this.loadedAt=Date.now();}
    this.onFresh(Date.now()-this.loadedAt<=2000);
  }
  failed(uri: string){if(!this.stopped && uri===this.source?.uri){this.requestedAt=-Infinity;this.onFresh(false);}}
  stop(){
    this.stopped=true;this.request?.abort();
    if(this.poll)clearTimeout(this.poll);if(this.watchdog)clearInterval(this.watchdog);
    this.onFresh(false);
  }
}
