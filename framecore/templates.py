"""Własne, edytowalne szablony narracyjne, MIT."""
from .commands import storyboard
from .model import EditorError

TEMPLATES = {
    "product": ("Premiera produktu", ["Odkryj nową jakość.", "Codzienność zasługuje na więcej.", "{title}", "Zobacz detale.", "Poczuj różnicę.", "Poznaj produkt."]),
    "social": ("Reklama społecznościowa", ["Zatrzymaj się na chwilę.", "Znasz ten problem?", "{title}", "Tak to działa.", "Mniej wysiłku. Więcej efektu.", "Sprawdź teraz."]),
    "explainer": ("Film wyjaśniający", ["Jak to działa?", "Zacznijmy od pytania.", "{title}", "Krok pierwszy: przygotuj materiały.", "Krok drugi: nadaj im znaczenie.", "Spróbuj samodzielnie."]),
    "collaboration": ("Współpraca człowieka z AI", ["Pomysł zaczyna się od Ciebie.", "Materiały potrzebują historii.", "{title}", "Człowiek nadaje kierunek.", "Agent pomaga w montażu.", "Stwórzmy film razem."]),
}


def template_scenes(template_id, duration, title):
    if template_id not in TEMPLATES:
        raise EditorError("Nieznany szablon")
    name, messages = TEMPLATES[template_id]
    scenes = storyboard(duration, title, name)
    for scene, message in zip(scenes, messages):
        scene["message"] = message.replace("{title}", title)
    return scenes

TEMPLATES.update({
    'cinematic': ('Filmowy zwiastun',['Każda historia ma początek.','Wszystko może się zmienić.','{title}','Spójrz z innej perspektywy.','Przeżyj ten moment.','Oglądaj dalej.']),
    'editorial': ('Magazyn i opowieść',['Nowe spojrzenie.','Za każdym detalem stoi historia.','{title}','Przyjrzyj się bliżej.','Forma spotyka znaczenie.','Odkryj więcej.']),
    'neon': ('Technologia w ruchu',['Przyszłość jest tutaj.','Zmień sposób działania.','{title}','Połącz pomysł z narzędziem.','Twórz szybciej.','Zacznij eksperyment.']),
    'minimal': ('Minimalny manifest',['Mniej. Lepiej.','Zostaw to, co najważniejsze.','{title}','Jeden dobry pomysł.','Przestrzeń na Twój głos.','Daj mu formę.']),
    'podcast': ('Podcast i rozmowa',['Porozmawiajmy.','Dobre pytanie zmienia wszystko.','{title}','Posłuchaj innej perspektywy.','Myśl, która zostaje.','Włącz nowy odcinek.']),
    'event': ('Zaproszenie na wydarzenie',['Zapisz ten moment.','Coś dobrego nadchodzi.','{title}','Poznaj ludzi i nowe pomysły.','Bądź częścią historii.','Dołącz do nas.']),
    'education': ('Krótka lekcja',['Zrozum w minutę.','Od czego zacząć?','{title}','Krok pierwszy: zauważ różnicę.','Krok drugi: zastosuj w praktyce.','Sprawdź, co potrafisz.']),
    'launch': ('Kreatywna premiera',['Gotowi na coś nowego?','Pomysł potrzebuje energii.','{title}','Wybierz własny kierunek.','Zrób następny krok.','Premiera właśnie teraz.']),
})
# Własne kierunki: font, tło, tekst, akcent, układ, animacja wejścia, ilustracja.
_LOOKS = {
 'product': ('Manrope','aurora-breath','#f7f5ed','#c8ecb3','left','premium-blur-reveal','fluent-rocket'),
 'social': ('Bebas Neue','ember','#fff4e7','#ffd797','center','impact-rise','fluent-fire'),
 'explainer': ('DM Sans','grid','#f4f1e9','#8de0d0','left','wipe-left','fluent-light-bulb'),
 'collaboration': ('Space Grotesk','orbit-blue','#faf5ec','#ffb593','center','float','fluent-robot'),
 'cinematic': ('Playfair Display','graphite','#f5e9d5','#dcb381','center','cinema-rise','fluent-movie-camera'),
 'editorial': ('Fraunces','cream','#302b2d','#985941','left','wipe-up','fluent-books'),
 'neon': ('JetBrains Mono','prism','#f4f1ff','#b8f5e5','left','focus-in','fluent-laptop'),
 'minimal': ('DM Serif Display','pearl','#2e2b39','#71547d','center','soft-fade','fluent-seedling'),
 'podcast': ('Manrope','drift-pink','#fff4ed','#ffc494','left','slide-right','fluent-microphone'),
 'event': ('Space Grotesk','morph-sunset','#fff2df','#ffd383','center','elastic-pop','fluent-party-popper'),
 'education': ('DM Sans','dots','#26363d','#376d69','left','drop-in','fluent-light-bulb'),
 'launch': ('Bebas Neue','royal','#fff3e1','#e9b2df','center','bounce-in','fluent-sparkles'),
}

# Ruch 2.0: tekst kinetyczny sceny tytułowej, wyjście nagłówków i look całego filmu.
_DIRECTION = {
 'product': ('word-cascade','blur-out',{'grade':'warm','vignette':.3,'grain':.1,'transition':'dip'}),
 'social': ('char-rise','zoom-through',{'grade':'vivid','vignette':.2,'transition':'flash','transitionDuration':.35}),
 'explainer': ('type-on','slide-out-left',{'transition':'wipe','transitionDuration':.6}),
 'collaboration': ('word-blur','fade-out',{'grade':'cool','vignette':.3,'transition':'light-leak','transitionDuration':.8}),
 'cinematic': ('word-blur','blur-out',{'grade':'cinematic','vignette':.5,'grain':.3,'letterbox':.12,'transition':'dip','transitionDuration':.7}),
 'editorial': ('word-cascade','wipe-out',{'grade':'faded','grain':.25,'transition':'dip'}),
 'neon': ('scramble-in','zoom-through',{'grade':'vivid','vignette':.4,'grain':.15,'transition':'blur'}),
 'minimal': ('word-blur','fade-out',{'transition':'dip','transitionDuration':.8}),
 'podcast': ('word-highlight','fade-out',{'grade':'warm','vignette':.3,'transition':'light-leak'}),
 'event': ('char-wave','scale-out',{'grade':'vivid','transition':'flash'}),
 'education': ('type-on','slide-out-left',{'transition':'wipe','transitionDuration':.6}),
 'launch': ('char-rise','zoom-through',{'grade':'vivid','vignette':.3,'transition':'flash','transitionDuration':.4}),
}


def look(template_id):
    if template_id not in _LOOKS: raise EditorError('Nieznany szablon')
    font,bg,text,accent,layout,motion,illustration=_LOOKS[template_id]
    from .backgrounds import resolve
    return {'font':font,'background_id':bg,'background':resolve(bg)['preview'],'text':text,
            'accent':accent,'layout':layout,'motion':motion,'illustration_id':illustration,
            'kinetic':_DIRECTION[template_id][0],'exit':_DIRECTION[template_id][1],'fx':dict(_DIRECTION[template_id][2])}


def catalog():
    return [{'id':key,'name':value[0],'scenes':6,'license':'MIT','formats':['9:16','4:5','1:1','16:9'],
             'look':look(key)} for key,value in TEMPLATES.items()]


def apply_look(p, template_id):
    from .library import library_asset, manifest
    from .model import element
    from .backgrounds import resolve
    style=look(template_id);w,h=p['canvas']['width'],p['canvas']['height']
    p['canvas'].update(background=resolve(style['background_id'])['colors'][0],backgroundPreset=style['background_id'],backgroundAnimated=True)
    p['brand'].update(font=style['font'], colors={'background':p['canvas']['background'],'text':style['text'],'accent':style['accent']})
    p['metadata']['templateId']=template_id
    from .model import FX_DEFAULTS
    from .motion import resolve as resolve_motion
    p['canvas']['fx']={**FX_DEFAULTS,**style['fx']}
    hero=p['scenes'][2]['id'] if len(p['scenes'])>2 else None
    face=next(f for f in manifest()['fonts'] if f['family']==style['font'])
    has_visual=any(e['type'] in {'image','video'} for e in p['elements'])
    for e in p['elements']:
        if e['type'] in {'text','caption'}:
            is_title=e['type']=='text'
            e['style'].update(fontFamily=style['font'],fontWeight=min(700 if is_title else 400,face['weight'][1]),
                              color=style['text'] if is_title else style['accent'],align=style['layout'])
            e.update(x=w*.08,width=w*.84)
            if is_title:
                e.update(y=h*.12 if has_visual else h*.13,height=h*.26)
                e['style']['fontSize']=w*(.058 if w>h else .075)
                e['motion']={'id':style['motion'],'duration':round(min(.8,e['duration']*.6),2)}
                if hero and e.get('sceneId')==hero:
                    kinetic=resolve_motion(style['kinetic'])['defaults']
                    e['motion']={'id':style['kinetic'],'duration':round(max(.3,min(kinetic['duration'],e['duration']*.6)),2),'easing':kinetic['easing']}
                e['exit']={'id':style['exit'],'duration':round(max(.1,min(.4,e['duration']*.25)),2),'easing':'cubic-out'}
            else:
                e.update(y=h*.88,height=max(h*.055,w*.019*1.7))
                e['style']['fontSize']=w*.019 if w>h else w*.027
        elif e['type']=='image' and e.get('assetId') != p['brand'].get('logoAssetId'):
            e.update(x=w*.19,y=h*.43,width=w*.62,height=h*.38)
    if not has_visual:
        asset=library_asset(style['illustration_id']);p['assets'].append(asset)
        for scene in p['scenes']:
            p['elements'].append(element(p,'image',assetId=asset['id'],sceneId=scene['id'],start=scene['start'],duration=scene['duration'],
                                         x=w*.32,y=h*.43,width=w*.36,height=h*.37,motion={'id':'float','duration':.8}))
