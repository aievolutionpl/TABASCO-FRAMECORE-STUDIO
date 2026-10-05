"""Story-led visual lessons adapted from the user's supplied prompt image."""
from copy import deepcopy
from .model import EditorError, element, number, uid

PHASES = [('hook','Pytanie'),('familiar','Znany przykład'),('disruption','Problem'),
          ('mechanism','Mechanizm'),('discovery','Odkrycie'),('consequence','Konsekwencja'),('recap','Odpowiedź')]
BRIEF_FIELDS = {'topic','audience','coreIdea','misconception','openingQuestion'}
SCENE_FIELDS = {'phase','purpose','narration','visual','transition','audio'}
PLAYBOOK = {
 'source':'Grafika promptu dostarczona przez użytkownika; adaptacja do FrameCore, bez przypisywania autorstwa modelowi.',
 'arc':[{'id':key,'name':name} for key,name in PHASES],
 'rules':[
  'Jedna relacja i jeden cel nauki na scenę. Najpierw znany przykład, potem nazwa pojęcia.',
  'Pytanie otwierające musi dostać odpowiedź w finale. Wskaż typowe błędne przekonanie.',
  'Przejście wyjaśnia związek; przenoś istniejący obiekt, kierunek lub kolor zamiast dekorować zmianę.',
  'Narracja i tekst ilustracji są oddzielne. Napisy mogą odtwarzać mowę, ale nagłówek ma ją uzupełniać.',
  'Cel narracji: 125–145 słów na minutę; zmierz rzeczywisty plik audio przed synchronizacją.',
  'Projekt papierowy: krem, węgiel, koral, musztarda, teal; proste sylwetki, bez losowych gradientów.',
  'Czytelność na telefonie, bezpieczne marginesy, znaczenie przekazane także kształtem i podpisem.',
  'Sprawdź bez dźwięku i osobno sam dźwięk. Spójność postaci i domknięcie historii ocenia człowiek.',
  'Tekst narracji nie jest nagraniem. Brakujący lektor wymaga wgrania audio lub zewnętrznego dostawcy.',
  'Wszystkie sceny, klipy, źródła i animacje pozostają edytowalne. Nie spłaszczaj filmu przed oddaniem człowiekowi.',
 ],
 'review':['Odpowiedź na pytanie otwierające','Unikalny cel każdej sceny','Czytelność bez dźwięku',
           'Narracja zrozumiała bez obrazu','Ciągłość obiektów i postaci','Napisy i marginesy','Rzeczywiste audio zsynchronizowane'],
}


def fields(value, allowed):
    if not isinstance(value,dict) or set(value)-allowed:
        raise EditorError('Nieznane pola planu lekcji')
    if any(not isinstance(v,str) or len(v)>4000 for v in value.values()):
        raise EditorError('Pola lekcji muszą być tekstem do 4000 znaków')
    return deepcopy(value)


def validate(p):
    if 'lesson' in p: fields(p['lesson'],BRIEF_FIELDS)
    for scene in p['scenes']:
        if 'lesson' not in scene: continue
        data=fields(scene['lesson'],SCENE_FIELDS)
        if data.get('phase') not in {key for key,_ in PHASES}:
            raise EditorError('Nieznana faza lekcji')


def plan(brief, duration):
    brief=fields(brief,BRIEF_FIELDS)
    if not brief.get('topic','').strip() or not brief.get('coreIdea','').strip():
        raise EditorError('Podaj temat i główną myśl lekcji')
    number(duration,'Długość lekcji',7,600)
    messages=[brief.get('openingQuestion') or f"Jak działa {brief['topic']}?",'Spójrz na znany przykład.',
              brief.get('misconception') or 'Co może nas tutaj zmylić?','Zobacz, co dzieje się w środku.',
              brief['coreIdea'],'Co to zmienia w praktyce?',brief['coreIdea']]
    scenes=[]
    for index,((phase,name),message) in enumerate(zip(PHASES,messages)):
        start=index*duration/7
        scenes.append({'id':uid('scene'),'name':name,'start':start,'duration':duration/7,
            'message':message,'visualPurpose':message,'motionIntent':'title_reveal','audioIntent':'',
            'lesson':{'phase':phase,'purpose':message,'narration':'','visual':'',
                      'transition':'Zachowaj wspólny obiekt lub kierunek; dopracuj przejście.','audio':''}})
    return {'brief':brief,'scenes':scenes,'duration':duration,'status':'editable_starter',
            'note':'Plan startowy. Uzupełnij przykład, wyjaśnienie mechanizmu, obrazy i narrację; to nie jest gotowa lekcja.'}


def assemble(p,args,session):
    from .commands import mutate, target
    duration=args.get('duration',p['duration'])
    proposed=plan(args['brief'],duration)
    scenes=deepcopy(args.get('scenes',proposed['scenes']))
    if not isinstance(scenes,list) or len(scenes)!=7:
        raise EditorError('Plan lekcji musi zawierać siedem scen')
    if [s.get('lesson',{}).get('phase') for s in scenes]!=[key for key,_ in PHASES]:
        raise EditorError('Zachowaj kolejność siedmiu faz historii')
    if any(abs(s['start']-(scenes[i-1]['start']+scenes[i-1]['duration'] if i else 0))>1e-6 for i,s in enumerate(scenes)) or abs(scenes[-1]['start']+scenes[-1]['duration']-duration)>1e-6:
        raise EditorError('Sceny muszą pokrywać całą lekcję bez przerw i nakładania')
    if p['elements'] and not args.get('replace',False):
        raise EditorError('Przejrzyj plan i wybierz zastąpienie montażu; zmianę można cofnąć')
    for e in p['elements']:target(p,{'element_id':e['id']},session)
    if any(t['locked'] and t['kind'] in {'text','shape'} for t in p['tracks']):
        raise EditorError('Odblokuj ścieżki tekstu i kształtów przed zbudowaniem lekcji')
    p['duration']=duration;p['lesson']=proposed['brief'];p['scenes']=scenes;p['elements']=[]
    paper=args.get('paper_style',not bool(p.get('brandProfile')))
    if not isinstance(paper,bool):raise EditorError('paper_style musi być wartością logiczną')
    p['canvas']['fps']=24
    if paper:
        p['canvas']['background']='#f5eee3';p['canvas'].pop('backgroundPreset',None)
        p['brand'].update(font='Manrope',colors={'background':'#f5eee3','text':'#252927','accent':'#d24b32'})
    font=p['brand']['font'];ink=p['brand']['colors']['text'];accent='#a13828' if paper else p['brand']['colors']['accent']
    w,h=p['canvas']['width'],p['canvas']['height']
    for index,scene in enumerate(scenes):
        start,span=scene['start'],scene['duration']
        base={'sceneId':scene['id'],'start':start,'duration':span}
        card=element(p,'shape',**base,x=w*.08,y=h*.43,width=w*.84,height=h*.32,
                     motion=None)
        card['style'].update(background='#e7dcc8' if paper else p['brand']['colors']['accent'],radius=20)
        if not paper:card['opacity']=.12
        title=element(p,'text',**base,text=scene['message'],x=w*.08,y=h*.13,width=w*.84,height=h*.23,
                      style={'fontSize':min(w*.065,h*.09),'fontFamily':font,'fontWeight':700,'color':ink,'align':'left','background':'transparent','radius':0},
                      motion=None if index==0 else {'id':'wipe-up','duration':.65})
        label=element(p,'caption',**base,text=f'{index+1:02} / {scene["name"]}',x=w*.08,y=h*.83,width=w*.84,height=h*.06,
                      style={'fontSize':min(w*.027,h*.036),'fontFamily':font,'fontWeight':500,'color':accent,'align':'left','background':'transparent','radius':0},
                      motion={'id':'soft-fade','duration':.3})
        p['elements'].extend([card,title,label])
        scene['beat']={'purpose':scene.get('lesson',{}).get('purpose',scene['message']),
                       'entryState':scenes[index-1]['message'] if index else (p['lesson'].get('openingQuestion') or 'Początek historii'),
                       'exitState':scene['message'],'focusElementId':title['id']}
    p.setdefault('production',{}).update(product=p['lesson']['topic'][:2000],message=p['lesson']['coreIdea'][:2000],requireReview=True)
    p['metadata'].pop('templateId',None)
    p['metadata']['workflow']='Lekcja przez historię'


def status(p):
    issues=[]
    for scene in p['scenes']:
        lesson=scene.get('lesson')
        if not lesson:continue
        for key in ('purpose','narration','visual','transition'):
            if not lesson.get(key,'').strip():issues.append({'scene_id':scene['id'],'field':key,'message':f'{scene["name"]}: uzupełnij {key}'})
        words=len(lesson.get('narration','').split());pace=words*60/scene['duration']
        if words and not 125<=pace<=145:
            issues.append({'scene_id':scene['id'],'field':'narration','message':f'{scene["name"]}: tekst ma około {pace:.0f} słów/min; dopasuj po nagraniu lektora'})
    return {'issues':issues,'reviewChecklist':PLAYBOOK['review'],
            'note':'Kontrola opisów i szacowanego tempa tekstu; nie mierzy nagrania, nie ocenia sensu historii ani synchronizacji.'}
