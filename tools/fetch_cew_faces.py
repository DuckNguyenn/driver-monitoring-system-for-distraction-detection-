"""Download the official CEW research archive; do not redistribute raw images.

F. Song, X. Tan, X. Liu and S. Chen, Eyes Closeness Detection from Still Images
with Multi-scale Histograms of Principal Oriented Gradients, PR 47 (2014).
"""
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / '.cache/cew'
PAGE = 'https://parnec.nuaa.edu.cn/_upload/tpl/02/db/731/template731/pages/xtan/ClosedEyeDatabases.html'
# Public file linked by the authors' official dataset page (06 October 2026).
URL = 'https://drive.usercontent.google.com/download?id=12DB4kwdeikxyQcK4gA7hL0QbzF6iOAZ2&export=download&confirm=t'
EXPECTED_SHA256 = '25c1eb8572a8755b87106a4bfea7f2dd89c1abaab95196eee51d43de9f8c6b48'


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    archive = DESTINATION / 'cew_faces.rar'
    if not archive.exists():
        temporary = archive.with_suffix('.part')
        request = urllib.request.Request(URL, headers={'User-Agent':'driver-monitor-research/1.0'})
        total = 0
        with urllib.request.urlopen(request, timeout=45) as response, temporary.open('wb') as out:
            for block in iter(lambda: response.read(1024*1024), b''):
                total += len(block)
                if total > 64 * 1024 * 1024:
                    raise ValueError('Unexpected archive size')
                out.write(block)
        if not temporary.read_bytes().startswith(b'Rar!'):
            raise ValueError('Expected a public RAR archive, not a login/confirmation page')
        temporary.replace(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError('Official CEW archive checksum mismatch')
    metadata = DESTINATION / 'source.json'
    if metadata.exists() and json.loads(metadata.read_text())['archive_sha256'] != digest:
        raise ValueError('CEW archive changed')
    metadata.write_text(json.dumps({'official_page':PAGE, 'archive_sha256':digest,
        'bytes':archive.stat().st_size, 'terms':'Research only; raw images not redistributed in release bundles',
        'citation':'Song et al., Pattern Recognition 47 (2014), 2825-2838'},indent=2),encoding='utf-8')
    # Windows libarchive supports RAR. Accept only the flat JPEG image directory
    # and validate every resolved target before extracting any member.
    listing = subprocess.run(['tar.exe','-tf',str(archive)],capture_output=True,text=True,check=True).stdout.splitlines()
    members = [n for n in listing if n.lower().endswith('.jpg')]
    folder = (DESTINATION / 'faces').resolve()
    for name in members:
        parts = name.replace('\\','/').split('/')
        if (len(parts) != 2 or parts[0] != 'dataset_B_FacialImages_highResolution'
                or any(part in ('','.','..') or ':' in part for part in parts)
                or not (folder / name).resolve().is_relative_to(folder)):
            raise ValueError('Unsafe archive member')
    if len(members) != 1192:
        raise ValueError('Unexpected CEW face count')
    folder.mkdir(parents=True,exist_ok=True)
    member_list = DESTINATION / 'extract_members.txt'
    member_list.write_text('\n'.join(members)+'\n',encoding='utf-8')
    subprocess.run(['tar.exe','-xf',str(archive),'-C',str(folder),'-T',str(member_list)],check=True)
    print(json.dumps({'archive':str(archive),'sha256':digest,'bytes':archive.stat().st_size}))


if __name__ == '__main__':
    main()
