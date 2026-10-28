"""Glasses adaptation contract: subject splits, native augmentation, validation guards."""
from collections import Counter
import cv2
import numpy as np
from .multiview_learning import augment_native

VAL_SUBJECTS=frozenset({'s0002','s0014'})
TEST_SUBJECTS=frozenset({'s0019','s0036'})


def subject_split(subject):
    if subject in VAL_SUBJECTS:return 'val'
    if subject in TEST_SUBJECTS:return 'test'
    return 'train'


def validate_subjects(rows):
    validate_rgb_subjects(rows)
    owners={}
    for row in rows:
        if row['domain']!='mrl':continue
        person=row['subject'];split=row['split']
        if person in owners and owners[person]!=split:raise ValueError('MRL subject leakage: '+person)
        if split!=subject_split(person):raise ValueError('Locked subject assignment changed: '+person)
        owners[person]=split
    for split in ('train','val','test'):
        for glasses in (False,True):
            for label in ('Closed','Open'):
                if not any(r['domain']=='mrl' and r['split']==split and r['glasses']==glasses and r['label']==label for r in rows):
                    raise ValueError('Missing MRL group support')


def validate_rgb_subjects(rows,require_complete=False,minimum_per_class=20):
    """Only new reviewed RGB captures require new subject/group split ownership."""
    people={};groups={};counts=Counter()
    for row in rows:
        if not row.get('new_glasses_camera'):continue
        if (row['domain']!='rgb_rehearsal' or row.get('glasses') is not True or row.get('reviewed') is not True
                or row.get('split') not in ('train','val','test') or row.get('label') not in ('Closed','Open')):
            raise ValueError('Expected manually reviewed RGB glasses labels')
        person=row.get('subject');group=row.get('capture_group');split=row['split']
        if not isinstance(person,str) or not person.strip() or not isinstance(group,str) or not group.strip():
            raise ValueError('Reviewed RGB requires subject and capture group')
        if people.get(person,split)!=split or groups.get(group,split)!=split:
            raise ValueError('Reviewed RGB subject/group crosses splits')
        people[person]=split;groups[group]=split;counts[split,row['label']]+=1
    if require_complete:
        for split in ('train','val','test'):
            for label in ('Closed','Open'):
                if counts[split,label]<minimum_per_class:
                    raise ValueError(f'Missing reviewed RGB support: {split}/{label} requires {minimum_per_class} crops')
    return counts


def sampling_mass(rows):
    if any(r.get('new_glasses_camera') for r in rows):
        return {'rgb_glasses':.45,'rgb_rehearsal':.25,'mrl_glasses':.20,'mrl_no_glasses':.10}
    return {'rgb_rehearsal':.55,'mrl_glasses':.30,'mrl_no_glasses':.15}


def group_name(row):
    if row['domain']=='rgb_rehearsal':return 'rgb_glasses' if row.get('new_glasses_camera') else 'rgb_rehearsal'
    if row['domain']=='mrl':return 'mrl_glasses' if row['glasses'] else 'mrl_no_glasses'
    raise ValueError('Unsupported glasses training domain')


def sampler_weights(rows):
    mass=sampling_mass(rows)
    groups=Counter((group_name(r),r['label']) for r in rows)
    if any(groups[group,label]==0 for group in mass for label in ('Closed','Open')):
        raise ValueError('Sampling requires both eye classes in every active group')
    weights=[]
    for row in rows:
        key=(group_name(row),row['label'])
        domain_mass=mass[key[0]]
        weights.append(domain_mass/(2*groups[key]))
    return np.array(weights,dtype=np.float64)


def augment_glasses(crop,rng,enabled=True):
    image=augment_native(crop,rng,enabled)
    if enabled and rng.random()<.3:
        factor=float(rng.uniform(.85,1.15))
        center=np.mean(image,axis=(0,1),keepdims=True)
        image=np.clip((image.astype(np.float32)-center)*factor+center,0,255).astype(np.uint8)
    return image


def glasses_selection(metrics,baseline):
    """Fixed validation contract; no test rows, epochs, or thresholds enter it."""
    reasons=[]
    for group in ('rgb_rehearsal','mrl_no_glasses'):
        if metrics[group]['macro_f1']<baseline[group]['macro_f1']-.015:
            reasons.append('F1_regression:'+group)
    for label in ('Closed','Open'):
        before=baseline['rgb_rehearsal']['confidence_and_quality_gate']['per_class'][label]
        after=metrics['rgb_rehearsal']['confidence_and_quality_gate']['per_class'][label]
        if before['support'] and after['recall']<before['recall']-.03:
            reasons.append('RGB_confident_recall_regression:'+label)
    if 'rgb_glasses' in baseline:
        before=baseline['rgb_glasses'];after=metrics['rgb_glasses']
        if any(before['per_class'][label]['support']<20 for label in ('Closed','Open')):
            reasons.append('insufficient_RGB_glasses_validation')
        if after['macro_f1']<before['macro_f1']+.02:
            reasons.append('RGB_glasses_F1_gain_below_2pp')
        a=after['confidence_and_quality_gate'];b=before['confidence_and_quality_gate']
        if a['confusion_matrix_with_unknown'][1][0]>b['confusion_matrix_with_unknown'][1][0]:
            reasons.append('RGB_glasses_confident_false_closed_increased')
        if a['per_class']['Closed']['recall']<b['per_class']['Closed']['recall']:
            reasons.append('RGB_glasses_confident_closed_recall_regressed')
        if metrics['mrl_glasses']['macro_f1']<baseline['mrl_glasses']['macro_f1']-.02:
            reasons.append('MRL_glasses_F1_regression')
        score=(.55*after['macro_f1']+.30*metrics['rgb_rehearsal']['macro_f1']+.15*metrics['mrl_glasses']['macro_f1']
               -.05*after.get('brier_score',0.))
    else:
        if metrics['mrl_glasses']['macro_f1']<baseline['mrl_glasses']['macro_f1']+.03:
            reasons.append('glasses_F1_gain_below_3pp')
        score=(.65*metrics['rgb_rehearsal']['macro_f1']+.35*metrics['mrl_glasses']['macro_f1']
               -.05*metrics['rgb_rehearsal'].get('brier_score',0.))
    return float(score),reasons
