"""Exercise the built web against the real process/API and an existing private video."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parent))
from benchmark_dashboard import ROOT, stop_process


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--port',type=int,default=8879);args=p.parse_args()
    root=ROOT/'.cache/dashboard_implementation/web-live';root.mkdir(parents=True,exist_ok=True)
    code=secrets.token_urlsafe(32);env=dict(os.environ,DRIVER_MONITOR_TOKEN=code,PYTHONIOENCODING='utf-8')
    base=f'http://127.0.0.1:{args.port}'
    with (root/'server.console.txt').open('w',encoding='utf-8') as console:
        process=subprocess.Popen([sys.executable,'-m','driver_monitor','serve','--source',args.source,'--realtime','--max-frames','600',
            '--host','127.0.0.1','--port',str(args.port),'--log-dir',str(root/'logs')],cwd=ROOT,stdout=console,stderr=console,env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0)
        try:
            for _ in range(100):
                try:
                    if httpx.get(base+'/api/v1/status',headers={'Authorization':f'Bearer {code}'},timeout=.3).status_code==200:break
                except httpx.RequestError:pass
                time.sleep(.1)
            else:raise RuntimeError('API startup timeout')
            checked=subprocess.run(['node','tools/check_dashboard_browser.mjs',base],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
            if checked.returncode:raise RuntimeError(checked.stderr.replace(code,'[redacted]'))
            result=json.loads(checked.stdout.strip().splitlines()[-1])
            (ROOT/'reports/dashboard_verification/web-browser.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps(result))
        finally:stop_process(process)
    path=root/'server.console.txt';path.write_text(path.read_text(encoding='utf-8').replace(code,'[redacted]'),encoding='utf-8')


if __name__=='__main__':main()
