"""Generic camera staging. Never changes narration, evidence or scientific labels."""
from copy import deepcopy


def stage_story(story):
    obj=deepcopy(story)
    lines=obj.get('lines',[])
    before=[line.get('beat') for line in lines]
    raw=sum(beat=='explain' for beat in before)
    for line in lines:
        if line.get('speaker')=='PIP':line['beat']='dialogue'
    current=[i for i,line in enumerate(lines) if line.get('speaker')=='RAY' and line.get('beat')=='explain']
    if not 3<=len(current)<=5:
        eligible=[i for i,line in enumerate(lines) if line.get('speaker')=='RAY' and 2<=len(line.get('diagram',[]))<=4]
        if len(eligible)>=3:
            count=min(4,len(eligible))
            selected={eligible[round(i*(len(eligible)-1)/(count-1))] for i in range(count)}
            for i,line in enumerate(lines):
                if line.get('speaker')=='RAY':line['beat']='explain' if i in selected else 'dialogue'
    return obj,{'raw_explanation_beats':raw,'staged_explanation_beats':sum(line.get('beat')=='explain' for line in lines),
                'changed_line_indices':[i for i,line in enumerate(lines) if line.get('beat')!=before[i]],
                'narration_and_evidence_unchanged':True}
