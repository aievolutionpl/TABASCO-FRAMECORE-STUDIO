"""Własne receptury tła, MIT. Ruch zależy wyłącznie od czasu filmu."""
from copy import deepcopy
from .model import EditorError

# id, nazwa, rodzaj, kolory. Żadnych adresów ani dowolnego CSS z projektu.
_RECIPES = [
    ('midnight','Noc','solid',['#11141d']),('cream','Papier','solid',['#f5eee3']),
    ('ember','Żar','gradient',['#32112d','#9c273a','#ef7846']),
    ('aurora','Zorza','gradient',['#081f28','#165c61','#64a590']),
    ('violet','Fiolet','gradient',['#171330','#483577','#9274c8']),
    ('candy','Cukier','gradient',['#ffd5e5','#d0bcff','#b3e5ec']),
    ('ocean','Ocean','gradient',['#071e40','#17556f','#488c9e']),
    ('dusk','Zmierzch','gradient',['#251a42','#76486b','#cd8c77']),
    ('mint','Mięta','gradient',['#d6efe0','#abe0cf','#80bcb1']),
    ('graphite','Grafit','gradient',['#10121b','#29323b','#505967']),
    ('pearl','Perła','gradient',['#f5eee7','#e2d5e8','#d2dded']),
    ('solar','Słońce','gradient',['#f8da8d','#efab66','#dc7047']),
    ('peach','Brzoskwinia','gradient',['#ffede0','#ecc0ac','#d3a2b0']),
    ('royal','Kobalt','gradient',['#090e37','#253875','#536fda']),
    ('grid','Siatka','grid',['#101b27','#263b51']),
    ('dots','Kropki','dots',['#f3efe6','#b6b0a5']),
    ('lines','Linie','lines',['#1c2130','#343e55']),
    ('grain','Prążki papieru','grain',['#eae1d3','#d5c8b8']),
    ('aurora-breath','Oddech zorzy','animated',['#081b29','#18675c','#365380']),
    ('orbit-blue','Błękitna orbita','animated',['#090f28','#234d88','#5c4892']),
    ('drift-pink','Różowy dryf','animated',['#291832','#90466b','#545181']),
    ('starfield','Konstelacja','animated',['#111629','#405372','#7d94b6']),
    ('morph-sunset','Płynny zachód','animated',['#341b2b','#a04c3d','#70558a']),
    ('prism','Pryzmat','animated',['#15182f','#3f4a83','#725680']),
]
PRESETS = {i: {'id':i,'name':n,'kind':k,'colors':c,'animated':k=='animated','license':'MIT',
               'preview': c[0] if k=='solid' else f'linear-gradient(135deg, {", ".join(c)})'} for i,n,k,c in _RECIPES}


for preset in PRESETS.values():
    base, *accents = preset['colors']
    ink = accents[0] if accents else base
    kind = preset['kind']
    if kind == 'grid':
        preset['preview'] = f'linear-gradient({ink} 1px, transparent 1px),linear-gradient(90deg,{ink} 1px,transparent 1px),{base}'
    elif kind == 'dots':
        preset['preview'] = f'radial-gradient({ink} 1.5px,transparent 1.5px),{base}'
    elif kind == 'lines':
        preset['preview'] = f'repeating-linear-gradient(135deg,{base} 0px,{base} 28px,{ink} 29px,{base} 30px)'
    elif kind == 'grain':
        preset['preview'] = f'repeating-linear-gradient(15deg,{base} 0px,{base} 3px,{ink} 4px,{base} 5px)'
    preset['previewSize'] = '24px 24px' if kind in {'grid','dots'} else 'auto'


def resolve(key):
    if key not in PRESETS:
        raise EditorError('Nieznane tło biblioteki')
    return deepcopy(PRESETS[key])


def catalog():
    return deepcopy(list(PRESETS.values()))
