"""Built-in edit presets and safe, track-local timeline operations."""
from .model import EditorError, number

TRANSITION_NAMES = {
    'none': 'Cięcie', 'dip': 'Przez czerń', 'flash': 'Błysk',
    'wipe': 'Kurtyna marki', 'light-leak': 'Smuga światła', 'blur': 'Rozmycie',
    'iris': 'Przysłona', 'diagonal': 'Kurtyna ukośna', 'zoom-blur': 'Zoom z rozmyciem',
    'slide-up': 'Kurtyna pionowa', 'pixel-dissolve': 'Mozaika',
}
CLIP_LOOKS = {
    'none': ('Naturalny', {}),
    'warm': ('Złota godzina', {'sepia': .3, 'saturate': 1.2, 'brightness': 1.04}),
    'cool': ('Chłodny błękit', {'hue-rotate': 18, 'saturate': .9, 'contrast': 1.08}),
    'noir': ('Noir', {'grayscale': 1, 'contrast': 1.45, 'brightness': .92}),
    'vintage': ('Vintage', {'sepia': .45, 'saturate': .7, 'contrast': .88, 'brightness': 1.08}),
    'punch': ('Żywy kontrast', {'saturate': 1.5, 'contrast': 1.15}),
    'dream': ('Miękki sen', {'brightness': 1.1, 'contrast': .9, 'blur': 2}),
}


def catalog():
    return {'transitions': [{'id': k, 'name': v} for k, v in TRANSITION_NAMES.items()],
            'clipLooks': [{'id': k, 'name': v[0], 'filters': v[1]} for k, v in CLIP_LOOKS.items()]}


def validate_clip_fx(fx):
    if not isinstance(fx, dict) or set(fx) - {'look', 'strength'} or not isinstance(fx.get('look'), str) or fx['look'] not in CLIP_LOOKS:
        raise EditorError('Wybierz wbudowany efekt klipu')
    number(fx.get('strength', 1), 'Siła efektu', 0, 1)


def validate_transition(value):
    if not isinstance(value, dict) or set(value) != {'id', 'duration'} or not isinstance(value.get('id'), str) or value['id'] not in TRANSITION_NAMES:
        raise EditorError('Wybierz wbudowane przejście i jego czas')
    number(value['duration'], 'Czas przejścia', .1, 2)


def track_clips(p, track_id):
    track = next((t for t in p['tracks'] if t['id'] == track_id), None)
    if not track or track['locked']:
        raise EditorError('Wybierz odblokowaną ścieżkę')
    clips = sorted((e for e in p['elements'] if e['trackId'] == track_id), key=lambda e: (e['start'], e['id']))
    if any(a['start']+a['duration'] > b['start']+1e-6 for a, b in zip(clips, clips[1:])):
        raise EditorError('Klipy na ścieżce nachodzą na siebie; rozsuń je przed usuwaniem luk')
    return clips


def ripple_delete(p, e):
    clips = track_clips(p, e['trackId'])
    end = e['start']+e['duration']
    for clip in clips:
        if clip['start'] >= end-1e-6 and clip is not e:
            clip['start'] -= e['duration']
    p['elements'].remove(e)


def close_gaps(p, track_id):
    cursor = 0
    for e in track_clips(p, track_id):
        e['start'] = cursor
        cursor += e['duration']


def slip(p, e, source_start):
    if e['type'] not in {'video', 'audio'}:
        raise EditorError('Przesunięcie źródła działa dla nagrania wideo lub dźwięku')
    a = next(a for a in p['assets'] if a['id'] == e['assetId'])
    start = number(source_start, 'Początek źródła', 0, 36000)
    if not a.get('duration') or start+e['duration'] > a['duration']+1e-6:
        raise EditorError('Wybrany zakres przekracza długość nagrania')
    e['sourceStart'] = start
