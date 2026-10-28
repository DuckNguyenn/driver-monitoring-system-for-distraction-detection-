"""Conservative, eye-only routing. Original eye and yawn artifacts remain immutable."""
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
import json

from .models import Classifier, artifact_path, prepare_rgb, prepare_tensor


def read_eyewear_manifest(path):
    value=json.loads(Path(path).read_text(encoding='utf-8'))
    if value.get('kind')!='driver_monitor_eyewear_selector' or value.get('schema_version')!=1:
        raise ValueError('invalid eyewear selector manifest')
    spec=value['classifier'];p=spec['preprocessing'];gate=value['gate']
    if spec['classes']!=['no_glasses','glasses'] or spec['output']!='probabilities':
        raise ValueError('invalid eyewear labels/output')
    if p['color']!='RGB' or p['resize']!='shorter_center_crop' or p['interpolation']!='bilinear':
        raise ValueError('invalid eyewear preprocessing')
    if not isinstance(spec['input_size'],int) or spec['input_size']<=0 or p['resize_shorter']<spec['input_size']:
        raise ValueError('invalid eyewear input size')
    if len(p['mean'])!=3 or len(p['std'])!=3 or not all(isfinite(v) for v in p['mean']+p['std']) or min(p['std'])<=0:
        raise ValueError('invalid eyewear normalization')
    EyewearGate(**gate)  # validate the temporal policy before opening models/camera
    return value


@dataclass(frozen=True)
class Route:
    branch: str
    changed: bool
    probability: float | None
    classification: str
    confirming_seconds: float = 0.


class EyewearGate:
    def __init__(self,enter_probability=.99,confirm_seconds=1.5,poll_seconds=.5,
                 max_score_age_seconds=.8,max_frame_gap_seconds=.25):
        if not isfinite(enter_probability) or not .5<enter_probability<=1:
            raise ValueError('invalid eyewear threshold')
        if any(not isfinite(v) or v<=0 for v in (confirm_seconds,poll_seconds,max_score_age_seconds,max_frame_gap_seconds)):
            raise ValueError('invalid eyewear time limits')
        if poll_seconds>=max_score_age_seconds or confirm_seconds<poll_seconds:
            raise ValueError('eyewear policy cannot confirm fresh repeated scores')
        self.threshold=enter_probability;self.confirm=confirm_seconds;self.poll=poll_seconds
        self.max_age=max_score_age_seconds;self.max_gap=max_frame_gap_seconds
        self.reset()

    def reset(self):
        self.last=self.scored_at=self.score=self.since=None
        self.branch='original'

    def needs_score(self,t):
        return self.scored_at is None or t-self.scored_at>=self.poll-1e-9

    def update(self,t,score=None,*,valid=True,track_changed=False):
        before=self.branch
        bad_time=not isfinite(t) or (self.last is not None and (t<=self.last or t-self.last>self.max_gap+1e-9))
        if bad_time or not valid or track_changed:
            self.reset()
        if not isfinite(t):
            return Route('original',before!='original',None,'unknown')
        self.last=t
        if not valid:
            return Route('original',before!='original',None,'unknown')
        if score is not None:
            if not isfinite(score) or not 0<=score<=1:
                raise ValueError('invalid eyewear probability')
            self.score=float(score);self.scored_at=t
        if self.scored_at is None or t-self.scored_at>self.max_age+1e-9:
            self.score=self.scored_at=self.since=None;self.branch='original'
            return Route('original',before!='original',None,'unknown')
        high=self.score>=self.threshold
        if high:
            if self.since is None:self.since=t
            if t-self.since>=self.confirm-1e-9:self.branch='glasses'
        else:
            self.since=None;self.branch='original'
        classification='glasses' if high else 'no_glasses' if self.score<=1-self.threshold else 'uncertain'
        return Route(self.branch,before!=self.branch,self.score,classification,0. if self.since is None else t-self.since)


class EyewearModel:
    """Small CPU ONNX classifier, independent of the eye/yawn backend."""
    def __init__(self,manifest_path,threads=2):
        import onnxruntime as ort
        self.manifest=read_eyewear_manifest(manifest_path);self.spec=self.manifest['classifier']
        path=artifact_path(manifest_path,self.spec['artifact'])
        options=ort.SessionOptions();options.intra_op_num_threads=threads;options.inter_op_num_threads=1
        self.model=ort.InferenceSession(str(path),options,providers=['CPUExecutionProvider'])
        entry=self.model.get_inputs()[0];self.input_name=entry.name
        if entry.shape!=[1,3,self.spec['input_size'],self.spec['input_size']]:
            raise ValueError('eyewear ONNX shape differs from manifest')

    def predict(self,crop):
        import numpy as np
        x=prepare_tensor(prepare_rgb(crop,self.spec),self.spec)
        p=np.asarray(self.model.run(None,{self.input_name:x})[0],dtype=float).reshape(-1)
        if len(p)!=2 or not np.isfinite(p).all() or np.min(p)<0 or np.max(p)>1 or abs(p.sum()-1)>.001:
            raise ValueError('invalid eyewear distribution')
        return float(p[1])

    def close(self):
        self.model=None


class EyeRouter:
    """Select only the eye classifier. Does not own or call the yawn model."""
    def __init__(self,original,config):
        self.original=original;self.specialist=self.selector=None;self.error=None
        try:
            self.selector=EyewearModel(config.eyewear_manifest,config.cpu_threads)
            self.specialist=Classifier(config.glasses_eye_manifest,'eye',config.backend,config.cpu_threads)
            policy=dict(self.selector.manifest['gate']);policy['max_frame_gap_seconds']=config.monitor.max_frame_gap_seconds
            self.gate=EyewearGate(**policy)
        except Exception:
            self.close();raise

    def warmup(self,sample):
        self.specialist.predict(sample);self.selector.predict(sample)

    def select(self,result,t):
        valid=result.quality=='usable' and result.crops is not None and self.error is None
        # Reset before polling: a new driver/gap must never inherit a cached score.
        before=self.gate.branch
        if result.track_changed or not valid or (self.gate.last is not None and (t<=self.gate.last or t-self.gate.last>self.gate.max_gap+1e-9)):
            self.gate.reset()
        score=None
        if valid and self.gate.needs_score(t):
            try:score=self.selector.predict(result.crops[2])
            except Exception as exc:
                self.error=f'{type(exc).__name__}: {exc}';valid=False
        route=self.gate.update(t,score,valid=valid)
        if route.changed!=(before!=route.branch):
            route=Route(route.branch,before!=route.branch,route.probability,route.classification,route.confirming_seconds)
        result.metrics.update(eye_model_branch=route.branch,eyewear_probability=route.probability,
                              eyewear_state=route.classification,eyewear_confirming_seconds=route.confirming_seconds,
                              eyewear_error=self.error)
        if route.changed and result.eye_quality=='usable':
            # Interrupt only the eye timers; mouth EMA/events continue normally.
            result.eye_quality='eye_model_changed'
        return self.specialist if route.branch=='glasses' else self.original,route

    def close(self):
        if self.specialist is not None:self.specialist.close()
        if self.selector is not None:self.selector.close()
