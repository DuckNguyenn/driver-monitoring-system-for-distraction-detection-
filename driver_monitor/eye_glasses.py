"""Read MRL's published annotation order without guessing class-folder labels."""
from pathlib import PurePosixPath
from collections import defaultdict
import hashlib
import re


def mrl_annotation(member):
    match = re.fullmatch(r'(s\d{4})_(\d+)_([01])_([01])_([01])_([012])_([01])_(0[123])\.png',
                         PurePosixPath(member).name)
    if match is None:
        return None
    subject, frame, gender, glasses, eye, reflection, lighting, sensor = match.groups()
    split = next((part for part in PurePosixPath(member).parts if part in ('train','val','valid','test')), 'unspecified')
    return {'member':member,'subject':subject,'image_id':int(frame),'gender':int(gender),
            'glasses':bool(int(glasses)),'label':'Closed' if eye=='0' else 'Open',
            'reflection':int(reflection),'lighting':int(lighting),'sensor':sensor,'source_split':split}


def sample_mrl(rows, per_glasses_class=256):
    """Round-robin subjects/conditions, within each glasses/class group.

    This creates a balanced audit, not a population-weighted accuracy estimate.
    Selection depends solely on published metadata, never model predictions.
    """
    if per_glasses_class <= 0:
        raise ValueError('sample size must be positive')
    result=[]
    for glasses in (False,True):
        for label in ('Closed','Open'):
            groups=defaultdict(list)
            for row in rows:
                if row['glasses']==glasses and row['label']==label:
                    groups[row['subject'],row['reflection'],row['lighting'],row['sensor']].append(row)
            pools=[sorted(group,key=lambda r:hashlib.sha256(r['member'].encode()).hexdigest())
                   for _,group in sorted(groups.items())]
            count=0;offset=0
            while count < per_glasses_class and any(offset < len(pool) for pool in pools):
                for pool in pools:
                    if offset < len(pool) and count < per_glasses_class:
                        result.append(pool[offset]);count+=1
                offset+=1
    return result
