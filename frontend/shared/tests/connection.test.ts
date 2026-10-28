import assert from 'node:assert/strict';
import {test} from 'node:test';
import {AlertMemory, normalizeServer, chartSegments, effectiveConnection, ApiClient, LiveConnection} from '../src/index.ts';
import * as shared from '../src/index.ts';

test('server addresses never carry secrets in a URL', () => {
  assert.equal(normalizeServer('192.168.1.10:8765'), 'http://192.168.1.10:8765');
  assert.throws(() => normalizeServer('http://user:secret@192.168.1.10:8765'));
  assert.throws(() => normalizeServer('http://192.168.1.10:8765?token=secret'));
});
test('mobile connection rejects its own loopback address and accepts the PC LAN address', () => {
  for(const address of ['http://127.0.0.1:8765','localhost:8765','http://127.2.3.4:8765','http://[::1]:8765','0.0.0.0:8765'])
    assert.throws(()=>shared.normalizeMobileServer(address), /IPv4.*PC/);
  assert.equal(shared.normalizeMobileServer('192.168.2.19:8765'),'http://192.168.2.19:8765');
  assert.equal(normalizeServer('http://127.0.0.1:8765'),'http://127.0.0.1:8765','PC web still supports localhost');
});
test('connection errors explain the PC address and LAN check instead of native Swift internals', async(t) => {
  const client=new ApiClient({server:'http://192.168.2.19:8765',token:'private-test-code'});
  t.mock.method(globalThis,'fetch',async()=>{throw new TypeError('fetch failed: UnexpectedException at ExpoModulesCore/Promise.swift:56');});
  await assert.rejects(client.status(),error=>{
    assert.match((error as Error).message,/Không kết nối được.*192\.168\.2\.19/);
    assert.match((error as Error).message,/Wi-Fi/);
    assert.doesNotMatch((error as Error).message,/Swift|swift|private-test-code/);
    return true;
  });
});
test('an alert episode vibrates once even after reconnect', () => {
  const memory = new AlertMemory();
  const snapshot = {connected: true, alert: true, alert_episode_id: 'session:1', source_kind: 'camera'};
  assert.equal(memory.accept(snapshot), true);
  assert.equal(memory.accept(snapshot), false);
  memory.accept({...snapshot, alert: false});
  assert.equal(memory.accept(snapshot), false);
  assert.equal(memory.accept({...snapshot, alert_episode_id: 'session:2'}), true);
  assert.equal(memory.accept({...snapshot, source_kind: 'video', alert_episode_id: 'replay:1'}), false);
});
test('missing probabilities create real chart gaps and stale samples disconnect', () => {
  const segments = chartSegments([{x: 1, y: .9}, {x: 2, y: null}, {x: 3, y: .1}]);
  assert.deepEqual(segments, [[{x:1,y:.9}], [{x:3,y:.1}]]);
  assert.equal(effectiveConnection(true, 100, 200, 2201), false);
});
test('socket startup failure reports offline and remains recoverable', () => {
  let error = '';
  const live = new LiveConnection(new ApiClient({server:'http://192.168.1.1:8765',token:'test-code'}),()=>{},message=>{error=message;},()=>{throw new Error('Network unavailable');});
  try {assert.doesNotThrow(()=>live.start());assert.match(error,/kết nối/);} finally {live.stop();}
});
test('probability charts do not interpolate across a telemetry outage',()=>{
  assert.deepEqual(chartSegments([{x:1000,y:.2},{x:1200,y:.3},{x:11200,y:.8},{x:11400,y:.9}]),[
    [{x:1000,y:.2},{x:1200,y:.3}],[{x:11200,y:.8},{x:11400,y:.9}]
  ]);
});

test('superseded history requests and unmounted pagination cannot overwrite evidence',async()=>{
  let release:()=>void=()=>{},calls:string[]=[];
  const client={
    sessions:async()=>({items:[],next_offset:null}),
    series:async(id:string)=>{calls.push(id);if(id==='slow')await new Promise<void>(resolve=>{release=resolve;});return {items:[],next_offset:id==='slow'?1000:null};},
    events:async(id:string)=>({items:[{id,kind:'alert',utc:'2026-10-08T01:00:00Z',payload:{}}],next_offset:null})
  };
  const reader=new shared.HistoryReader(client as any);
  const slow=reader.load('slow');
  const fast=await reader.load('fast');
  assert.equal(fast?.events[0].id,'fast');
  release();assert.equal(await slow,null);assert.equal(calls.filter(id=>id==='slow').length,1);
  const abandoned=reader.load('slow');reader.invalidate();release();assert.equal(await abandoned,null);
  assert.equal(calls.filter(id=>id==='slow').length,2);
});

test('native preview expires repeated frames, recovers stalled requests, and stops on unmount',async(t)=>{
  t.mock.timers.enable({apis:['setTimeout','setInterval','Date'],now:1000});
  let sequence='1',stall=false,metadataCalls=0,source:{uri:string;sequence:string}|null=null,fresh=false;
  const client={frameMetadata:async(nonce:number,signal:AbortSignal)=>{
    metadataCalls++;
    if(stall)await new Promise<void>((_,reject)=>signal.addEventListener('abort',()=>reject(new Error('aborted')),{once:true}));
    return {uri:`http://server/frame.jpg?t=${nonce}`,sequence};
  }};
  const stream=new shared.PreviewStream(client,value=>{source=value;},value=>{fresh=value;});
  async function advance(ms:number){t.mock.timers.tick(ms);await Promise.resolve();await Promise.resolve();}
  try{
    stream.start();await advance(0);
    stream.loaded(source!.uri);assert.equal(fresh,true);
    await advance(2100);assert.equal(fresh,false,'repeated sequence cannot keep old image fresh');
    stall=true;await advance(200);await advance(1600);
    assert.equal(fresh,false);
    stall=false;sequence='2';await advance(200);await advance(200);
    stream.loaded(source!.uri);assert.equal(fresh,true);
    sequence='3';await advance(200);const abandonedImage=source!.uri;
    // HEAD remains responsive, but the native image never calls onLoad/onError.
    await advance(1600);await advance(300);
    assert.notEqual(source!.uri,abandonedImage,'stalled native decode/request is replaced');
    await advance(300);assert.equal(fresh,false);
    stream.loaded(abandonedImage);assert.equal(fresh,false,'an obsolete native callback cannot revive the image');
    stream.loaded(source!.uri);assert.equal(fresh,true);
    const callsBeforeStop=metadataCalls;stream.stop();await advance(3000);
    assert.equal(metadataCalls,callsBeforeStop);assert.equal(fresh,false);
  }finally{stream.stop();t.mock.timers.reset();}
});

test('native preview lets a slow image load finish before asking for another frame',async(t)=>{
  t.mock.timers.enable({apis:['setTimeout','setInterval','Date'],now:1000});
  let sequence='1',source:shared.FrameSource|null=null;
  const client={frameMetadata:async(nonce:number)=>({uri:`http://server/frame.jpg?t=${nonce}`,sequence})};
  const stream=new shared.PreviewStream(client,value=>{source=value;},()=>{});
  async function advance(ms:number){t.mock.timers.tick(ms);await Promise.resolve();await Promise.resolve();}
  try{
    stream.start();await advance(0);
    const first=source!.uri;
    sequence='2';await advance(200);
    assert.equal(source!.uri,first,'Do not cancel an image while native decoding is still making progress');
    stream.loaded(first);await advance(200);
    assert.equal(source!.sequence,'2');
  }finally{stream.stop();t.mock.timers.reset();}
});
