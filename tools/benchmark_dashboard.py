"""Compare identical replay decisions and two LAN-client loads; no ground-truth claims."""
import argparse
import asyncio
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[1]


def summaries(directory):
    return list(directory.glob('*.summary.json'))


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        process.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=12)
    except subprocess.TimeoutExpired:
        process.terminate(); process.wait(timeout=4)


async def clients(port, token, logs, process, source_kind):
    base = f'http://127.0.0.1:{port}'
    ages, frame_sizes, status_counts, resources, preview_counts = [], [], [], [], []
    done = asyncio.Event()
    headers = {'Authorization': f'Bearer {token}'}
    async def status_client(index):
        seen = set()
        try:
            async with websockets.connect(base.replace('http', 'ws') + '/api/v1/ws', max_queue=1) as ws:
                await ws.send(json.dumps({'type':'auth','token':token}))
                while not done.is_set():
                    try: message = json.loads(await asyncio.wait_for(ws.recv(), 2))
                    except asyncio.TimeoutError: continue
                    value = message['snapshot']
                    if value:
                        if value['source_kind'] != source_kind and value['lifecycle']=='running':
                            raise RuntimeError('Wrong replay/camera source label')
                        key = (value['session_id'], value['sequence'])
                        if value['connected'] and key not in seen:
                            seen.add(key)
                            ages.append(max(0., (datetime.now(timezone.utc)-datetime.fromisoformat(value['utc'])).total_seconds()*1000))
                        if value['lifecycle'] in ('finished','error'): done.set()
                status_counts.append({'client':index,'snapshots':len(seen)})
        except Exception:
            done.set(); raise
    async def preview_client(index):
        arrivals, frame_ages = [], []
        last_sequence = None
        async with httpx.AsyncClient(timeout=2) as client:
            while not done.is_set():
                began = time.monotonic()
                try:
                    response = await client.get(base+'/api/v1/frame.jpg', headers=headers,
                                                params={} if last_sequence is None else {'after':last_sequence})
                    if response.status_code==200:
                        frame_sizes.append(len(response.content))
                        sequence = response.headers.get('X-Frame-Sequence')
                        if sequence is not None and sequence != last_sequence:
                            arrivals.append(time.monotonic())
                            last_sequence = sequence
                            age = response.headers.get('X-Frame-Age-Ms')
                            if age is not None: frame_ages.append(float(age) + (time.monotonic()-began)*1000)
                    elif response.status_code not in (204,503): response.raise_for_status()
                except httpx.TimeoutException: pass
                await asyncio.sleep(max(0.,1/30-(time.monotonic()-began)))
        intervals = [(b-a)*1000 for a,b in zip(arrivals,arrivals[1:])]
        preview_counts.append({'client':index,'unique_frames':len(arrivals),
                               'received_fps':(len(arrivals)-1)/(arrivals[-1]-arrivals[0]) if len(arrivals)>1 else None,
                               'interarrival_p95_ms':percentile(intervals),
                               'frame_age_with_request_p95_ms':percentile(frame_ages)})
    async def watch():
        import psutil
        try: parent=psutil.Process(process.pid); parent.cpu_percent()
        except psutil.Error: parent=None
        started=time.monotonic()
        while not done.is_set():
            if process.poll() is not None: done.set(); raise RuntimeError('API process exited unexpectedly')
            if summaries(logs): done.set(); break
            if time.monotonic()-started > 120: done.set(); raise RuntimeError('Replay did not finish in 120 seconds')
            if parent:
                try:
                    children=parent.children(recursive=True)
                    resources.append({'rss_bytes':parent.memory_info().rss+sum(c.memory_info().rss for c in children),
                                      'parent_cpu_percent':parent.cpu_percent(),
                                      'worker_cpu_seconds':sum(sum(c.cpu_times()[:2]) for c in children)})
                except psutil.Error: pass
            await asyncio.sleep(.5)
    await asyncio.gather(status_client(1), status_client(2), preview_client(1), preview_client(2), watch())
    return {'snapshot_latency_p95_ms': percentile(ages), 'snapshot_count':len(ages), 'client_counts':status_counts,
            'jpeg_responses':len(frame_sizes), 'jpeg_mean_bytes':sum(frame_sizes)/max(1,len(frame_sizes)),
            'preview_clients':sorted(preview_counts,key=lambda item:item['client']),
            'rss_peak_bytes':max((r['rss_bytes'] for r in resources),default=None),
            'parent_cpu_percent_peak':max((r['parent_cpu_percent'] for r in resources),default=None)}


def percentile(values):
    if not values: return None
    return sorted(values)[max(0, __import__('math').ceil(.95*len(values))-1)]


def compare_decisions(first, second):
    fields = ['timestamp','state','alert','reasons','quality','eye_quality','eye_closed','left_closed','right_closed',
              'yawn_probability','yawn_raw_probability','yawn_state','yawn_count','blink_count','blink_total',
              'blink_detected','left_eye_events','right_eye_events']
    def rows(directory):
        with next(directory.glob('*.csv')).open(newline='',encoding='utf-8') as source:
            return [{key:row[key] for key in fields} for row in csv.DictReader(source)]
    left,right=rows(first),rows(second)
    different = [i for i,(a,b) in enumerate(zip(left,right)) if a!=b]
    return {'identical':len(left)==len(right) and not different, 'frames_baseline':len(left), 'frames_dashboard':len(right), 'different_indices':different[:10]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True)
    parser.add_argument('--config',default='configs/camera_pc.yaml')
    parser.add_argument('--frames',type=int,default=600)
    parser.add_argument('--preview-fps',type=int,choices=(2,5,10,15,30),default=15)
    parser.add_argument('--display',action='store_true',help='Show the same local OpenCV view in both comparison runs')
    parser.add_argument('--port',type=int,default=8876)
    parser.add_argument('--output',default='reports/dashboard_verification')
    parser.add_argument('--camera-seconds',type=float,default=0)
    args=parser.parse_args()
    output=Path(args.output).resolve(); output.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root=output/stamp; root.mkdir()
    token=__import__('secrets').token_urlsafe(32)
    env=dict(os.environ,DRIVER_MONITOR_TOKEN=token,PYTHONIOENCODING='utf-8')
    common=['--config',args.config,'--source',args.source,'--display' if args.display else '--headless','--backend','onnx']
    if args.camera_seconds: common += ['--duration',str(args.camera_seconds)]
    else: common += ['--max-frames',str(args.frames)]
    baseline,loaded=root/'baseline',root/'dashboard'
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0
    report={'utc':datetime.now(timezone.utc).isoformat(),'source_kind':'camera' if args.camera_seconds else 'video',
            'config':args.config,'preview_fps':args.preview_fps,'local_display':args.display,
            'physical_iphone_tested':False,'radxa_tested':False}
    if not args.camera_seconds:
        with (root/'baseline.console.txt').open('w',encoding='utf-8') as console:
            subprocess.run([sys.executable,'-m','driver_monitor','run',*common,'--log-dir',str(baseline)],cwd=ROOT,stdout=console,stderr=console,check=True,timeout=120)
    with (root/'server.console.txt').open('w',encoding='utf-8') as console:
        process=subprocess.Popen([sys.executable,'-m','driver_monitor','serve',*common,'--host','127.0.0.1','--port',str(args.port),'--preview-fps',str(args.preview_fps),'--log-dir',str(loaded)],cwd=ROOT,env=env,stdout=console,stderr=console,creationflags=creationflags)
        try:
            for _ in range(150):
                if process.poll() is not None: raise RuntimeError('serve exited during startup')
                try:
                    response=httpx.get(f'http://127.0.0.1:{args.port}/api/v1/status',headers={'Authorization':f'Bearer {token}'},timeout=.3)
                    if response.status_code==200: break
                except httpx.RequestError: pass
                time.sleep(.1)
            else: raise RuntimeError('API startup timeout')
            report['two_clients']=asyncio.run(clients(args.port,token,loaded,process,report['source_kind']))
            latest=json.loads(next(loaded.glob('*.summary.json')).read_text())
            report['dashboard']=latest
            if not args.camera_seconds:
                original=json.loads(next(baseline.glob('*.summary.json')).read_text())
                report['baseline']=original
                report['decisions']=compare_decisions(baseline,loaded)
                report['fps_decrease_percent']=(1-latest['fps']/original['fps'])*100
                report['fps_target_passed']=report['fps_decrease_percent']<=10
            report['latency_target_passed']=report['two_clients']['snapshot_latency_p95_ms'] is not None and report['two_clients']['snapshot_latency_p95_ms']<=1000
        finally:
            stop_process(process)
            report['api_exit_code']=process.returncode
    # Private console files may contain the pairing token; do not publish them.
    for path in root.glob('*.console.txt'):
        path.write_text(path.read_text(encoding='utf-8').replace(token,'[redacted]'),encoding='utf-8')
    result=root/'result.json';result.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'result':str(result),'fps_decrease_percent':report.get('fps_decrease_percent'),'decision_parity':report.get('decisions',{}).get('identical'),'ui_p95_ms':report.get('two_clients',{}).get('snapshot_latency_p95_ms'),
                      'preview_clients':report.get('two_clients',{}).get('preview_clients'),'api_exit_code':report['api_exit_code']}))

if __name__=='__main__':main()
