import {test,expect} from '@playwright/test';
import type {MonitorSnapshot} from '@driver-monitor/shared';

const sample: MonitorSnapshot = {schema_version:1,session_id:'test-session',sequence:1,utc:new Date().toISOString(),source_timestamp:1,source_kind:'camera',source:'0',backend:'onnx',lifecycle:'running',state:'UNKNOWN',alert:false,alert_episode_id:null,reasons:['blurry'],connected:true,age_ms:0,probabilities:{eye_1_closed:null,eye_2_closed:null,yawn:null,yawn_raw:null},counts:{blink_total:0,blink_5s:0,yawn_60s:0,eye_cycles:0},quality:{image:'blurry',eyes:'blurry',metrics:{}},performance:{fps:15,latency_ms:30,processing_ms:20},devices:{camera:{state:'connected',error:null},models:{state:'ready',error:null},esp32:{state:'not_configured',configured:false,error:null,ack_age_seconds:null}}};
test('Vietnamese monitor shows nulls, all states, stale connection and read-only history',async({page})=>{
  let send:(value:MonitorSnapshot)=>void = ()=>{};
  await page.route('**/api/v1/**',route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('status'))return route.fulfill({json:sample});
    if(path.endsWith('sessions'))return route.fulfill({json:{items:[{id:'test-session',started_at:sample.utc,ended_at:sample.utc,source_kind:'video',source:'test.avi',backend:'onnx',lifecycle:'finished',summary:{frames:30}}],next_offset:null}});
    if(path.endsWith('series'))return route.fulfill({json:{items:[sample],next_offset:null}});
    if(path.endsWith('events'))return route.fulfill({json:{items:[],next_offset:null}});
    return route.fulfill({status:503,body:'waiting'});
  });
  await page.routeWebSocket('**/api/v1/ws',ws=>{
    send=value=>ws.send(JSON.stringify({type:'snapshot',snapshot:value}));
    ws.onMessage(()=>send(sample));
  });
  await page.goto('/');
  await page.getByLabel('Địa chỉ máy chủ').fill('http://127.0.0.1:8765');
  await page.getByLabel('Mã kết nối').fill('test-code');
  await page.getByRole('button',{name:'Kết nối máy chủ'}).click();
  await expect(page.getByTestId('state-label')).toHaveText('Chưa xác định');
  await expect(page.getByTestId('yawn-probability')).toContainText('—');
  await expect(page.getByText('Chưa cấu hình',{exact:true})).toBeVisible();
  for(const [state,text] of [['NORMAL','Bình thường'],['WARNING','Cần chú ý'],['ALERT','Cảnh báo']] as const){
    send({...sample,state,sequence:sample.sequence++,reasons:[],alert:state==='ALERT',alert_episode_id:state==='ALERT'?'test-session:1':null});
    await expect(page.getByTestId('state-label')).toHaveText(text);
  }
  send({...sample,connected:false,age_ms:3000});
  await expect(page.getByText('Mất kết nối',{exact:true}).first()).toBeVisible();
  await page.getByRole('button',{name:'Lịch sử phiên',exact:true}).click();
  await expect(page.getByText('Phát lại video',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Xem phiên'}).click();
  await expect(page.getByText('60 giây cuối phiên')).toBeVisible();
  await expect(page.getByRole('button',{name:/Dừng hệ thống|Chỉnh ngưỡng/})).toHaveCount(0);
  await page.screenshot({path:'.cache/dashboard_implementation/web-history.png',fullPage:true});
  await page.getByRole('button',{name:'Giám sát',exact:true}).click();
  await page.getByRole('button',{name:'Ẩn thông báo'}).click();
  for(let i=0;i<61;i++)send({...sample,state:'NORMAL',reasons:[],alert:false,connected:true,sequence:10+i,utc:new Date(Date.now()-(60-i)*1000).toISOString(),age_ms:0,probabilities:{eye_1_closed:i===30?null:.02+.02*Math.sin(i/6),eye_2_closed:.04+.03*Math.sin(i/7),yawn:i===30?null:.1+.08*Math.sin(i/10),yawn_raw:.12},quality:{image:'usable',eyes:'usable',metrics:{}}});
  await expect(page.getByTestId('state-label')).toHaveText('Bình thường');
  await page.screenshot({path:'.cache/dashboard_implementation/web-monitor.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'.cache/dashboard_implementation/web-phone-layout.png',fullPage:true});
});

test('frozen or stalled camera becomes stale while telemetry stays connected, then recovers',async({page})=>{
  let sequence=1, stalled=false, release=()=>{}, heartbeat:ReturnType<typeof setInterval>|undefined;
  const image=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXZkAAAAASUVORK5CYII=','base64');
  await page.route('**/api/v1/status',route=>route.fulfill({json:sample}));
  await page.route('**/api/v1/frame.jpg?*',async route=>{
    if(stalled)await new Promise<void>(resolve=>{release=resolve;});
    await route.fulfill({body:image,contentType:'image/png',headers:{'X-Frame-Sequence':String(sequence),'Access-Control-Expose-Headers':'X-Frame-Sequence'}}).catch(()=>{});
  });
  await page.routeWebSocket('**/api/v1/ws',ws=>{
    const send=()=>ws.send(JSON.stringify({type:'snapshot',snapshot:{...sample,state:'NORMAL',reasons:[],connected:true,age_ms:0,sequence:Date.now(),utc:new Date().toISOString()}}));
    ws.onMessage(()=>{send();heartbeat=setInterval(send,200);});
  });
  try{
    await page.goto('/');
    await page.getByLabel('Địa chỉ máy chủ').fill('http://127.0.0.1:8765');
    await page.getByLabel('Mã kết nối').fill('test-code');
    await page.getByRole('button',{name:'Kết nối máy chủ'}).click();
    await expect(page.locator('.preview img')).toBeVisible();
    await expect(page.locator('.preview')).not.toHaveClass(/preview-stale/);
    await expect(page.locator('.preview')).toHaveClass(/preview-stale/,{timeout:4500});
    await expect(page.locator('.state-strip')).not.toHaveClass(/stale/);
    sequence=2;
    await expect(page.locator('.preview')).not.toHaveClass(/preview-stale/);
    stalled=true;
    await expect(page.locator('.preview')).toHaveClass(/preview-stale/,{timeout:4500});
    await expect(page.locator('.state-strip')).not.toHaveClass(/stale/);
    stalled=false;sequence=3;release();
    await expect(page.locator('.preview')).not.toHaveClass(/preview-stale/);
  }finally{if(heartbeat)clearInterval(heartbeat);release();}
});

test('switching sessions does not show a late response from the previous session',async({page})=>{
  let release=()=>{};
  const session=(id:string)=>({id,started_at:sample.utc,ended_at:sample.utc,source_kind:'video',source:`${id}.avi`,backend:'onnx',lifecycle:'finished',summary:{frames:30}});
  await page.route('**/api/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('status'))return route.fulfill({json:sample});
    if(path.endsWith('sessions'))return route.fulfill({json:{items:[session('slow'),session('fast')],next_offset:null}});
    if(path.endsWith('series')){
      if(path.includes('/slow/'))await new Promise<void>(resolve=>{release=resolve;});
      return route.fulfill({json:{items:[sample],next_offset:null}});
    }
    if(path.endsWith('events')){
      const slow=path.includes('/slow/');
      return route.fulfill({json:{items:[{id:slow?'slow-event':'fast-event',utc:sample.utc,kind:'runtime_fault',payload:{error:slow?'SLOW SESSION EVENT':'FAST SESSION EVENT'}}],next_offset:null}});
    }
    return route.fulfill({status:503,body:'waiting'});
  });
  await page.routeWebSocket('**/api/v1/ws',ws=>ws.onMessage(()=>ws.send(JSON.stringify({type:'snapshot',snapshot:sample}))));
  try{
    await page.goto('/');
    await page.getByLabel('Địa chỉ máy chủ').fill('http://127.0.0.1:8765');
    await page.getByLabel('Mã kết nối').fill('test-code');
    await page.getByRole('button',{name:'Kết nối máy chủ'}).click();
    await page.getByRole('button',{name:'Lịch sử phiên',exact:true}).click();
    await page.getByRole('button',{name:'Xem phiên'}).first().click();
    await expect(page.locator('.session-detail')).toContainText('slow');
    await page.getByRole('button',{name:'Xem phiên'}).last().click();
    await expect(page.getByText('FAST SESSION EVENT')).toBeVisible();
    const oldResponse=page.waitForResponse(response=>response.url().includes('/slow/series'));
    release();
    // The old request may be cancelled before fetching events, or finish without overwriting the current view.
    await oldResponse;
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.session-detail')).not.toContainText('SLOW SESSION EVENT');
    await expect(page.locator('.session-detail')).toContainText('FAST SESSION EVENT');
  }finally{release();}
});
