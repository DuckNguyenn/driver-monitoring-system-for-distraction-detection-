import {useEffect, useMemo, useRef, useState} from 'react';
import {AlertMemory, ApiClient, appendSample, chartSegments, label, LiveConnection, normalizeServer, numberText, percent, probabilitySignals, sourceLabel, stateLabels, timeText} from '@driver-monitor/shared';
import type {Connection, Event, MonitorSnapshot, Session} from '@driver-monitor/shared';

type Tab = 'monitor' | 'history' | 'connection';
function savedConnection(): Connection | null {try {return JSON.parse(sessionStorage.getItem('dm-connection') || 'null');} catch {return null;}}
function savedAlerts(): string[] {try {return JSON.parse(sessionStorage.getItem('dm-alerts') || '[]');} catch {return [];}}
function metricNumber(value: number | string | null | undefined): number | null {if(value==null || value==='')return null;const number=Number(value);return Number.isFinite(number)?number:null;}

export function App() {
  const [connection, setConnection] = useState<Connection | null>(savedConnection);
  const [tab, setTab] = useState<Tab>(connection ? 'monitor' : 'connection');
  const [snapshot, setSnapshot] = useState<MonitorSnapshot | null>(null);
  const [samples, setSamples] = useState<MonitorSnapshot[]>([]);
  const [error, setError] = useState('');
  const [banner, setBanner] = useState('');
  const alerts = useRef(new AlertMemory(savedAlerts()));
  const api = useMemo(() => connection ? new ApiClient(connection) : null, [connection]);
  useEffect(() => {
    setSnapshot(null); setSamples([]);
    if (!api) return;
    const live = new LiveConnection(api, value => {
      setSnapshot(value);
      if (value) {
        if (value.lifecycle === 'running') setSamples(previous => appendSample(previous, value));
        if (alerts.current.accept(value)) {
          setBanner(value.reasons.map(label).join(' · ') || 'Tài xế cần chú ý ngay');
          sessionStorage.setItem('dm-alerts', JSON.stringify(alerts.current.export()));
        }
      }
    }, setError);
    live.start();
    return () => live.stop();
  }, [api]);
  useEffect(() => {if (!banner) return; const id = setTimeout(() => setBanner(''), 10000); return () => clearTimeout(id);}, [banner]);
  function connect(value: Connection) {
    sessionStorage.setItem('dm-connection', JSON.stringify(value));
    setConnection(value); setTab('monitor'); setError('');
  }
  const linked = snapshot?.connected === true;
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-symbol">◉</span><div>DRIVER<span>MONITOR</span></div></div>
      <div className="nav-caption">KHÔNG GIAN GIÁM SÁT</div>
      <nav aria-label="Điều hướng">
        {([['monitor','◈','Giám sát'],['history','◷','Lịch sử phiên'],['connection','⌁','Kết nối']] as const).map(([key,icon,text]) =>
          <button key={key} className={tab===key?'nav active':'nav'} onClick={()=>setTab(key)}><span aria-hidden="true">{icon}</span>{text}</button>)}
      </nav>
      <div className="sidebar-bottom"><span className={linked?'dot online':'dot'}/><strong>{linked?'Máy xử lý trực tuyến':'Chờ máy xử lý'}</strong><small>Cùng mạng Wi-Fi · Chỉ giám sát</small><span className="version">LAN / v1.0</span></div>
    </aside>
    <main>
      <header><div><div className="eyebrow">HỆ THỐNG GIÁM SÁT TÀI XẾ</div><h1>{tab==='monitor'?'Giám sát trực tiếp':tab==='history'?'Lịch sử phiên':'Kết nối thiết bị'}</h1><p>{tab==='monitor'?'Theo dõi trạng thái từ camera và bộ xử lý tại chỗ.':tab==='history'?'Sự kiện và số liệu từ nhật ký của máy xử lý.':'Kết nối PC hoặc Radxa trong cùng mạng Wi-Fi.'}</p></div><div className="connection-chip"><span className={linked?'dot online':'dot'}/>{linked?'Đã kết nối':connection?'Mất kết nối':'Chưa kết nối'}</div></header>
      {banner && <div className="alert-banner" role="alert"><strong>Cảnh báo tài xế</strong><span>{banner}</span><button aria-label="Ẩn thông báo" onClick={()=>setBanner('')}>×</button></div>}
      {error && <div className="notice" role="status">{error}</div>}
      {tab==='connection' && <Connect current={connection} onConnect={connect} onDisconnect={()=>{setConnection(null);sessionStorage.removeItem('dm-connection');}}/>}
      {tab==='monitor' && <Monitor api={api} snapshot={snapshot} samples={samples} onConnect={()=>setTab('connection')}/>}
      {tab==='history' && <History api={api} onConnect={()=>setTab('connection')}/>}
      <footer>DRIVER MONITOR <span>Quyết định do máy xử lý cung cấp · Camera và còi hoạt động tại PC / Radxa</span></footer>
    </main>
  </div>;
}

function Connect({current,onConnect,onDisconnect}:{current:Connection|null;onConnect:(c:Connection)=>void;onDisconnect:()=>void}) {
  const [server,setServer] = useState(current?.server || (location.port==='5173'?'http://127.0.0.1:8765':location.origin));
  const [token,setToken] = useState(current?.token || '');
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  return <section className="connect-layout"><div className="card connect-card"><div className="card-kicker">MÁY CHỦ TRONG MẠNG NỘI BỘ</div><h2>Một kết nối, cùng dữ liệu</h2><p>Nhập địa chỉ và mã được hiển thị khi chạy lệnh <code>serve</code> trên máy xử lý.</p>
    <form onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');try{const value={server:normalizeServer(server),token:token.trim()};await new ApiClient(value).status();onConnect(value);}catch(error){setError(error instanceof Error?error.message:'Không kết nối được máy chủ');}finally{setBusy(false);}}}>
      <label htmlFor="server">Địa chỉ máy chủ</label><input id="server" value={server} onChange={e=>setServer(e.target.value)} placeholder="http://192.168.1.10:8765" autoComplete="url" required/>
      <label htmlFor="token">Mã kết nối</label><input id="token" type="password" value={token} onChange={e=>setToken(e.target.value)} placeholder="Mã từ máy xử lý" autoComplete="off" required/>
      <p className="helper">Mã chỉ được giữ trong phiên trình duyệt này.</p>{error && <div className="form-error" role="alert">{error}</div>}
      <button className="primary" disabled={busy}>{busy?'Đang kiểm tra…':'Kết nối máy chủ'}</button>{current && <button type="button" className="secondary" onClick={onDisconnect}>Ngắt giao diện</button>}
    </form></div><div className="connection-guide"><div className="guide-icon">⌁</div><h2>Cùng mạng Wi-Fi</h2><p>Máy xử lý phục vụ cả dashboard và app iPhone. Dùng địa chỉ IPv4 của máy xử lý, cổng mặc định <strong>8765</strong>.</p><div className="guide-step"><span>01</span><div><strong>Chạy hệ thống tại PC / Radxa</strong><p>Camera và ESP32 nối vào máy xử lý.</p></div></div><div className="guide-step"><span>02</span><div><strong>Mở web hoặc app iPhone</strong><p>Nhập cùng địa chỉ máy chủ và mã kết nối.</p></div></div><div className="guide-step"><span>03</span><div><strong>Theo dõi trạng thái và lịch sử</strong><p>Ảnh chỉ truyền khi bạn mở mục Giám sát.</p></div></div></div></section>;
}

function Monitor({api,snapshot,samples,onConnect}:{api:ApiClient|null;snapshot:MonitorSnapshot|null;samples:MonitorSnapshot[];onConnect:()=>void}) {
  const state = snapshot?.state || 'UNKNOWN';
  const stale = !snapshot?.connected;
  return <>
    <section data-sequence={snapshot?.sequence} data-source-utc={snapshot?.utc} data-fresh={!stale} className={`state-strip ${state.toLowerCase()} ${stale?'stale':''}`}><div className="state-icon">{state==='NORMAL'?'✓':state==='UNKNOWN'?'?':'!'}</div><div><span className="card-kicker">TRẠNG THÁI TÀI XẾ</span><h2 data-testid="state-label">{stateLabels[state]}</h2><p>{snapshot?.reasons.length?snapshot.reasons.map(label).join(' · '):snapshot?.lifecycle==='finished'?'Phiên đã kết thúc':snapshot?.lifecycle==='initializing'?'Đang khởi động camera và model':stale?'Đang chờ dữ liệu mới từ máy xử lý':'Quan sát chưa có bằng chứng cảnh báo'}</p></div><div className="state-code"><strong>{state}</strong><small>{snapshot?sourceLabel(snapshot.source_kind):'Chưa có phiên'}</small>{snapshot && <span>{timeText(snapshot.utc)}</span>}</div></section>
    {!api && <div className="notice">Kết nối máy chủ để bắt đầu theo dõi. <button className="text-button" onClick={onConnect}>Mở kết nối →</button></div>}
    <div className={`monitor-grid ${stale?'stale-data':''}`}>
      <section className="card camera-card"><div className="card-head"><h2>Camera tài xế</h2><span className="tag">{snapshot?.source_kind==='video'?'PHÁT LẠI':'CAMERA'}</span></div><Preview api={api} connected={!stale}/><div className="camera-meta"><span><i className={!stale?'dot online':'dot'}/>{snapshot?.lifecycle==='running'?'Phiên đang chạy':label(snapshot?.lifecycle || 'unavailable')}</span><span>AI {numberText(snapshot?.performance.fps)} FPS · {numberText(snapshot?.performance.latency_ms,0)} ms</span></div></section>
      <section className="card signal-card"><div className="card-head"><h2>Tín hiệu nhận diện</h2><span className="tag">60 GIÂY</span></div><Chart samples={samples}/><p className="helper">Cùng trục thời gian, thang 0–100%. Khoảng trống biểu thị dữ liệu thiếu; ngáp đã lọc tại runtime.</p></section>
    </div>
    <div className={`metrics-grid ${stale?'stale-data':''}`}><Metric label="CHỚP HAI MẮT" value={String(snapshot?.counts.blink_total ?? '—')} unit="lần trong phiên" detail={`${snapshot?.counts.blink_5s ?? '—'} lần / cửa sổ 5 giây`}/><Metric label="NGÁP ĐÃ XÁC NHẬN" value={String(snapshot?.counts.yawn_60s ?? '—')} unit="lần / 60 giây" detail={`P thô: ${percent(snapshot?.probabilities.yawn_raw)}`}/><Metric label="CHẤT LƯỢNG ẢNH" value={snapshot?label(snapshot.quality.image):'—'} unit="" detail={`Vùng mắt: ${label(snapshot?.quality.eyes || 'unavailable')}`}/><Metric label="ĐỘ TRỄ XỬ LÝ" value={numberText(snapshot?.performance.latency_ms,0)} unit="ms / frame" detail={`${numberText(snapshot?.performance.fps)} FPS`}/></div>
    <Devices snapshot={snapshot}/>
  </>;
}

function Metric({label:caption,value,unit,detail}:{label:string;value:string;unit:string;detail:string}) {return <section className="card metric"><div className="card-kicker">{caption}</div><div className="metric-number">{value}</div><span>{unit}</span><p>{detail}</p></section>;}

function Devices({snapshot}:{snapshot:MonitorSnapshot|null}) {return <section className="card devices"><div className="card-head"><h2>Thiết bị & chất lượng quan sát</h2><span className="helper">{snapshot?.backend?.toUpperCase() || '—'}</span></div><div className="device-grid">{(['camera','models','esp32'] as const).map((key,i)=>{const device=snapshot?.devices[key];return <div className="device" key={key}><span className="device-icon">{['▣','◇','⌁'][i]}</span><div><strong>{['Camera','Model AI','ESP32 → Buzzer'][i]}</strong><p><i className={device && ['connected','ready'].includes(device.state)?'dot online':'dot'}/>{label(device?.state || 'unavailable')}</p>{device?.error && <small className="form-error">{device.error}</small>}</div></div>;})}</div><div className="quality-details">Độ nét mặt: {numberText(metricNumber(snapshot?.quality.metrics.sharpness))} <span>Độ sáng: {numberText(metricNumber(snapshot?.quality.metrics.brightness_median),0)}</span><span>Thời gian nguồn: {numberText(snapshot?.source_timestamp)} s</span></div></section>;}

function Preview({api,connected}:{api:ApiClient|null;connected:boolean}) {
  const [url,setUrl]=useState<string|null>(null); const [fresh,setFresh]=useState(false);
  useEffect(()=>{
    let stopped=false, lastUrl:string|null=null, timer:ReturnType<typeof setTimeout>|undefined;
    let request:AbortController|null=null, lastSequence:string|null=null, receivedAt=-Infinity;
    setUrl(null);setFresh(false);
    if(!api || !connected){setFresh(false);return;}
    const watchdog=setInterval(()=>{if(performance.now()-receivedAt>2000)setFresh(false);},250);
    async function tick(){
      const began=performance.now();
      request=new AbortController();const timeout=setTimeout(()=>request?.abort(),1500);
      try{const response=await fetch(api!.frameUrl(Date.now(),lastSequence??undefined),{headers:api!.headers,signal:request.signal,cache:'no-store'});
        if(response.status===204)return;
        if(!response.ok)throw new Error('no preview');
        const blob=await response.blob();if(stopped)return;
        const sequence=response.headers.get('X-Frame-Sequence');
        if(sequence===null)throw new Error('missing frame sequence');
        if(sequence!==lastSequence){lastSequence=sequence;receivedAt=performance.now();const next=URL.createObjectURL(blob);if(lastUrl)URL.revokeObjectURL(lastUrl);lastUrl=next;setUrl(next);}
        setFresh(performance.now()-receivedAt<=2000);
      }catch{if(!stopped)setFresh(false);}
      finally{clearTimeout(timeout);request=null;if(!stopped)timer=setTimeout(tick,Math.max(0,1000/30-(performance.now()-began)));}
    }
    tick();return()=>{stopped=true;request?.abort();clearInterval(watchdog);if(timer)clearTimeout(timer);if(lastUrl)URL.revokeObjectURL(lastUrl);};
  },[api,connected]);
  return <div className={`preview ${fresh?'':'preview-stale'}`}>{url && <img src={url} alt="Ảnh mới nhất từ camera tài xế"/>}{!fresh && <div className="preview-placeholder"><span>▣</span><strong>{connected?'Đang chờ ảnh camera':'Camera chưa cập nhật'}</strong><small>Driver monitor · tối đa 30 FPS · 640 × 480</small></div>}</div>;
}

function Chart({samples}:{samples:MonitorSnapshot[]}) {
  const end=samples.length?Date.parse(samples.at(-1)!.utc):Date.now(), start=end-60000;
  const current=samples.at(-1);
  return <div className="signal-charts" role="group" aria-label="Ba tín hiệu trong cùng cửa sổ 60 giây">
    {probabilitySignals.map(({key,label:caption,description,color})=><section className="probability-panel" key={key} style={{borderLeftColor:color}}>
      <div className="probability-panel-head"><div><strong>{caption}</strong><span>{description}</span></div><b style={{color}} data-testid={key==='yawn'?'yawn-probability':undefined}>{percent(current?.probabilities[key])}</b></div>
      <svg className="probability-plot" viewBox="0 0 500 86" role="img" aria-label={`${caption} trong 60 giây`}>
        {[0,.5,1].map(v=><g key={v}><line x1="34" x2="490" y1={72-v*60} y2={72-v*60} stroke="#e2e9ee"/><text x="0" y={76-v*60}>{v*100}%</text></g>)}
        {[34,262,490].map(x=><line key={x} x1={x} x2={x} y1="12" y2="72" stroke="#e9eef2" strokeDasharray="3 4"/>)}
        {chartSegments(samples.map(s=>({x:Date.parse(s.utc),y:s.probabilities[key]}))).map((segment,i)=><polyline key={i} fill="none" stroke={color} strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" points={segment.map(p=>`${34+(p.x-start)/60000*456},${72-p.y*60}`).join(' ')}/>)}
      </svg>
    </section>)}
    <div className="signal-timeline"><span>−60 giây</span><span>−30 giây</span><span>Hiện tại</span></div>
  </div>;
}

function History({api,onConnect}:{api:ApiClient|null;onConnect:()=>void}) {
  const [sessions,setSessions]=useState<Session[]>([]);const [selected,setSelected]=useState<Session|null>(null);
  const [samples,setSamples]=useState<MonitorSnapshot[]>([]);const [events,setEvents]=useState<Event[]>([]);
  const [error,setError]=useState('');const [listing,setListing]=useState(false),[detailLoading,setDetailLoading]=useState(false);const busy=listing||detailLoading;
  const listVersion=useRef(0),detailVersion=useRef(0);
  const [start,setStart]=useState(''),[end,setEnd]=useState('');
  const [offset,setOffset]=useState(0),[next,setNext]=useState<number|null>(null);const [filter,setFilter]=useState('');
  async function load(page=0){if(!api)return;const version=++listVersion.current;setListing(true);setError('');try{const q=new URLSearchParams({limit:'20',offset:String(page)});if(start)q.set('start',new Date(start).toISOString());if(end)q.set('end',new Date(end).toISOString());const result=await api.sessions('?'+q);if(version!==listVersion.current)return;setSessions(result.items);setNext(result.next_offset);setOffset(page);}catch(e){if(version===listVersion.current)setError(String(e));}finally{if(version===listVersion.current)setListing(false);}}
  useEffect(()=>{setSessions([]);setSelected(null);setSamples([]);setEvents([]);setDetailLoading(false);setListing(false);load();return()=>{listVersion.current++;detailVersion.current++;};},[api]);
  async function open(session:Session){if(!api)return;const version=++detailVersion.current;setSelected(session);setSamples([]);setEvents([]);setDetailLoading(true);setError('');try{
    const allSamples:MonitorSnapshot[]=[],allEvents:Event[]=[];let cursor:number|null=0;
    do{const result=await api.series(session.id,cursor);if(version!==detailVersion.current)return;allSamples.push(...result.items);cursor=result.next_offset;}while(cursor!==null);
    cursor=0;do{const result=await api.events(session.id,cursor);if(version!==detailVersion.current)return;allEvents.push(...result.items);cursor=result.next_offset;}while(cursor!==null);
    const last=allSamples.at(-1);setSamples(last?allSamples.filter(s=>Date.parse(s.utc)>=Date.parse(last.utc)-60000):[]);setEvents(allEvents.reverse());
  }catch(e){if(version===detailVersion.current)setError(String(e));}finally{if(version===detailVersion.current)setDetailLoading(false);}}
  async function download(){if(!api || !selected)return;try{const text=await api.csv(selected.id);const url=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`${selected.id}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){setError(String(e));}}
  if(!api)return <section className="card empty"><h2>Kết nối để xem lịch sử</h2><p>Nhật ký được lưu tại máy xử lý.</p><button className="primary" onClick={onConnect}>Mở kết nối</button></section>;
  return <><div className="history-toolbar"><div><label htmlFor="from">Từ thời điểm</label><input id="from" type="datetime-local" value={start} onChange={e=>setStart(e.target.value)}/></div><div><label htmlFor="until">Đến thời điểm</label><input id="until" type="datetime-local" value={end} onChange={e=>setEnd(e.target.value)}/></div><div><label htmlFor="session-filter">Tìm phiên trong trang</label><input id="session-filter" value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Mã phiên hoặc nguồn"/></div><button className="secondary" onClick={()=>load(0)} disabled={busy}>Lọc / Làm mới</button></div>
    {error && <div className="notice" role="alert">{error}</div>}{busy && <p className="helper">Đang tải nhật ký…</p>}
    <section className="card history-table"><table><thead><tr><th>THỜI GIAN</th><th>NGUỒN</th><th>PHIÊN</th><th>KẾT QUẢ</th><th/></tr></thead><tbody>{sessions.filter(s=>!filter || `${s.id} ${s.source}`.includes(filter)).map(s=><tr key={s.id}><td>{timeText(s.started_at)}</td><td><span className="tag">{sourceLabel(s.source_kind)}</span><small>{s.source}</small></td><td><code>{s.id}</code><small>{s.backend?.toUpperCase()}</small></td><td>{label(s.lifecycle)}<small>{s.summary.frames ?? '—'} frame</small></td><td><button className="text-button" onClick={()=>open(s)} aria-label="Xem phiên">Chi tiết →</button></td></tr>)}</tbody></table>{!sessions.length && <p className="empty">Chưa có phiên trong khoảng thời gian này.</p>}<div className="pagination"><button className="secondary" disabled={offset===0 || busy} onClick={()=>load(Math.max(0,offset-20))}>Trang trước</button><span>Trang {Math.floor(offset/20)+1}</span><button className="secondary" disabled={next===null || busy} onClick={()=>load(next!)}>Trang sau</button></div></section>
    {selected && <section className="card session-detail"><div className="card-head"><div><h2>Chi tiết phiên</h2><p>{selected.id} · {sourceLabel(selected.source_kind)}</p></div><button className="secondary" onClick={download}>Xuất CSV</button></div><div className="session-stats"><span>{selected.summary.frames ?? '—'} frame</span><span>{numberText(selected.summary.fps)} FPS</span><span>p95 {numberText(selected.summary.latency_p95_ms,0)} ms</span></div>{selected.summary.fault && <p className="form-error">{selected.summary.fault}</p>}<h3>60 giây cuối phiên</h3><Chart samples={samples}/><h3>Sự kiện</h3><div className="event-list">{events.map(e=><div className="event" key={e.id}><time>{timeText(e.utc)}</time><strong>{label(e.kind)}</strong><span>{e.payload.reasons?.map(label).join(' · ') || e.payload.error || e.payload.fault || (e.payload.state && stateLabels[e.payload.state as keyof typeof stateLabels]) || ''}</span></div>)}{!events.length && !busy && <p className="helper">Không có sự kiện.</p>}</div></section>}
  </>;
}
