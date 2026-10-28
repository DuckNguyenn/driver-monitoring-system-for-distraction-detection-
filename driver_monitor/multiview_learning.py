"""Native crop augmentation and transparent binary evaluation for GPU refinement."""
import cv2
import numpy as np


CLASSES = {'eye':['Closed','Open'], 'yawn':['no_yawn','yawn']}


def augment_native(image, rng, enabled=True):
    if not enabled:
        return image.copy()
    image = image.copy()
    h,w = image.shape[:2]
    if rng.random() < .6:
        dx,dy = rng.integers(-2,3,2)
        image = cv2.warpAffine(image, np.float32([[1,0,dx],[0,1,dy]]), (w,h),
                               flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    if rng.random() < .4 and min(h,w) >= 36:
        factor = float(rng.choice([.5,.75]))
        size = (max(24,round(w*factor)),max(24,round(h*factor)))
        small = cv2.resize(image,size,interpolation=cv2.INTER_AREA)
        image = cv2.resize(small,(w,h),interpolation=cv2.INTER_LINEAR)
    if rng.random() < .2:
        image = cv2.GaussianBlur(image,(3,3),float(rng.uniform(.35,.65)),borderType=cv2.BORDER_REPLICATE)
    if rng.random() < .1:
        kernel = np.zeros((3,3),np.float32);kernel[1,:]=1/3
        image = cv2.filter2D(image,-1,kernel,borderType=cv2.BORDER_REPLICATE)
    if rng.random() < .6:
        gamma = float(rng.uniform(.8,1.2))
        table = np.clip((np.arange(256)/255.)**gamma*255,0,255).astype(np.uint8)
        image = cv2.LUT(image,table)
    if rng.random() < .5:
        image = cv2.flip(image,1)
    if rng.random() < .15:
        image = cv2.cvtColor(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),cv2.COLOR_GRAY2BGR)
    return image


def matrix_metrics(truth, predictions, classes):
    matrix = np.zeros((2,2),int)
    extended = np.zeros((2,3),int)
    for label,guess in zip(truth,predictions):
        i=classes.index(label)
        if guess in classes:
            j=classes.index(guess);matrix[i,j]+=1;extended[i,j]+=1
        else:
            extended[i,2]+=1
    scores = {}
    for i,label in enumerate(classes):
        tp=int(matrix[i,i]);fp=int(matrix[:,i].sum()-tp);support=int(extended[i].sum());fn=support-tp
        scores[label]={'precision':tp/(tp+fp) if tp+fp else 0.,
                       'recall':tp/support if support else None,
                       'f1':2*tp/(2*tp+fp+fn) if support and 2*tp+fp+fn else (0. if support else None),
                       'support':support}
    f1=[x['f1'] for x in scores.values() if x['f1'] is not None]
    n=len(truth)
    return {'classes':classes,'confusion_matrix':matrix.tolist(),
            'confusion_matrix_with_unknown':extended.tolist(),'prediction_columns':classes+['UNKNOWN'],
            'per_class':scores,'macro_f1':float(np.mean(f1)) if f1 else None,
            'accuracy':float(np.trace(matrix))/n if n else None,'samples':n,
            'unknown_samples':int(extended[:,2].sum()),
            'coverage':1-float(extended[:,2].sum())/n if n else None}


def evaluate(rows, probabilities, name):
    classes=CLASSES[name];truth=[r['label'] for r in rows]
    raw=[classes[int(np.argmax(p))] for p in probabilities]
    result=matrix_metrics(truth,raw,classes)
    positive=classes.index('Closed' if name=='eye' else 'yawn')
    result['brier_score']=float(np.mean((probabilities[:,positive]-np.array([r['label']==classes[positive] for r in rows]))**2)) if rows else None
    guesses=[]
    for row,p in zip(rows,probabilities):
        if row.get('quality','usable')!='usable':guesses.append('UNKNOWN')
        elif name=='eye':guesses.append(classes[int(np.argmax(p))] if float(p.max())>=.8 else 'UNKNOWN')
        else:guesses.append('yawn' if p[1]>=.7 else 'no_yawn' if p[1]<=.35 else 'UNKNOWN')
    result['confidence_and_quality_gate']=matrix_metrics(truth,guesses,classes)
    result['gate_note']='Eye confidence 0.8; yawn frame proxy 0.70/0.35. Static gates are not temporal event accuracy.'
    groups={}
    for key in sorted({(r['domain'],r['source'],r.get('resolution','original')) for r in rows}):
        indices=[i for i,r in enumerate(rows) if (r['domain'],r['source'],r.get('resolution','original'))==key]
        selected=[rows[i] for i in indices];p=probabilities[indices]
        metric=matrix_metrics([r['label'] for r in selected],[classes[int(np.argmax(x))] for x in p],classes)
        metric['confidence_and_quality_gate']=matrix_metrics([r['label'] for r in selected],[guesses[i] for i in indices],classes)
        groups['/'.join(key)]=metric
    result['groups']=groups
    return result


def validation_score(metrics, baseline):
    reasons=[]
    for group,current in metrics['groups'].items():
        before=baseline['groups'][group]
        if current['macro_f1'] < before['macro_f1']-.025:
            reasons.append('F1_regression:'+group)
        for label,before_class in before['confidence_and_quality_gate']['per_class'].items():
            after_class=current['confidence_and_quality_gate']['per_class'][label]
            if before_class['support'] and after_class['recall'] < before_class['recall']-.05:
                reasons.append('confident_recall_regression:'+group+':'+label)
    score=metrics['macro_f1']-.1*metrics['brier_score']
    return float(score),reasons
