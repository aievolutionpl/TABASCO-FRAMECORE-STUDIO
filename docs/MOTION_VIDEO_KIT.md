# Motion Video Kit w FrameCore

Przejrzeliśmy [echris6/motion-video-kit](https://github.com/echris6/motion-video-kit/tree/255562b04b1e5ecaa4ba98e5c9aa191d5ba7f6fa): skill, reguły ruchu, niezależną ocenę Gauntlet, kryteria jakości, audio i skrypty pomiarowe. Zaadaptowano elementy pasujące do deterministycznego edytora FrameCore. Źródło jest przypięte do commitu `255562b04b1e5ecaa4ba98e5c9aa191d5ba7f6fa`; zachowano [oryginalną licencję MIT](../licenses/Motion-Video-Kit-MIT.txt).

## Co działa w narzędziu

- **Reguły reżyserskie:** panel Produkcja zawiera wskazówki ciągłości, hierarchii i przyczyny → skutku. Agent otrzymuje pełny polski playbook przez `get_motion_playbook`, w tym sześć receptur możliwych do wykonania istniejącymi klipami i klatkami kluczowymi.
- **Powtarzalność klatek:** `create_review` porównuje piksele maksymalnie trzech rzeczywistych klatek po powrotach z innych czasów. Niezgodność tworzy błąd `seek_inconsistent` i uniemożliwia zatwierdzenie przeglądu. To kontrola próbek, nie dowód powtarzalności każdego czasu filmu.
- **Pomiary gotowego MP4:** po zakończeniu eksportu kliknij **Zmierz rytm i dźwięk**. Wybierz profil spokojny, dynamiczny albo świadomą ciszę. Otrzymasz czasy zastojów, zintegrowaną głośność LUFS, zakres głośności LU i szczyt rzeczywisty dBFS.
- **Przenośny dowód:** raport JSON wiąże pomiar z `job_id`, zamrożoną rewizją i SHA-256 filmu. Trafia również do ZIP po wykonaniu pomiaru. Zmiana pliku MP4 unieważnia raport; dalsza edycja projektu nie zmienia wyniku starego eksportu.
- **Instrukcja niezależnej oceny:** [skill filmu biznesowego](../skills/business-motion-film/SKILL.md) i [dotychczasowy skill edycji](../skills/framecore/SKILL.md) opisują przekazanie artefaktu świeżemu krytykowi albo człowiekowi i weryfikację problemów runda po rundzie. Serwer nie powołuje automatycznie agentów i nie sprawdza ich tożsamości.

## MCP i HTTP

Wywołania przez MCP `tools/call` albo POST `/api/command`:

```json
{"name":"get_motion_playbook","args":{}}
```

Po ukończeniu eksportu:

```json
{"name":"analyze_export","args":{"project_id":"fc_…","job_id":"render_…","profile":"calm"}}
```

```json
{"name":"get_quality_report","args":{"project_id":"fc_…","job_id":"render_…"}}
```

Profile: `calm` — orientacyjnie −16 LUFS; `punchy` — −14 LUFS; `mute` — świadoma cisza. Odchylenie większe niż 2 LU oraz szczyt powyżej −1 dBFS tworzą uwagę. Zakres głośności analizujemy jako kryterium dramaturgii dopiero dla filmów ≥10 s; minimum 1,5 LU dla spokojnych i 3 LU dla dynamicznych to wskazówki, nie uniwersalna norma. Cisza w istniejącej ścieżce audio pozostaje mierzalnym przypadkiem, a nie pozytywnym wynikiem głośności.

Pomiar zastojów adaptuje upstreamowy filtr FFmpeg: 10 klatek/s, obraz o szerokości 320 px, luminancja 8-bit, średnia bezwzględna różnica <0,35. Raport pokazuje wszystkie wykryte przedziały. Ostrzega przy sumie większej niż około 1 s na 30 s filmu i zastojach >0,6 s przed ostatnimi 1,5 s, pozostawionymi na CTA. Nie rozpoznaje automatycznie, czy w końcówce rzeczywiście jest CTA. Zamierzoną pauzę i mały ruch trzeba ocenić wzrokowo.

Pomiar używa FFmpeg i FFprobe już wymaganych przez eksport, bez nowych zależności ani CDN. Nie modyfikuje filmu, gain ani historii montażu. Jest wykonywany na żądanie i może potrwać; procesy pomiarowe mają limit 180 s każdy. Pomiary nie stanowią nowej blokady eksportu.

## Skill i zapis rund

Podaj krytykowi faktyczny MP4, brief, referencje, planszę klatek i pomiary. W rundzie weryfikacyjnej dodaj poprzednie problemy, bez argumentów autora, że zostały naprawione. Krytyk wybiera czasy do własnego sprawdzenia. Zapisz [dziennik rund](../skills/business-motion-film/references/REVIEW_LEDGER.md) przy projekcie. Poprawiaj najważniejszy problem i wykrywaj regresje, zamiast dopisywać ogólne „jest lepiej”. W FrameCore nadal obowiązują najwyżej dwie autonomiczne rundy napraw przed przekazaniem nierozwiązanego problemu użytkownikowi.

## Zakres adaptacji

Pomiary nie zastępują obejrzenia pełnego filmu i odsłuchu. Nie mierzą kontrastu tekstu, kolorów marki ani stosunku efektów do muzyki. Nie oceniają prawdziwości obietnic ani sensu historii. Te punkty należą do niezależnej oceny i checklisty.

Przeniesiono zasady i pomiary zgodne z istniejącym silnikiem. Nie importowano zewnętrznych szablonów wykonujących dowolny HTML/JS, fizyki 3D, muzyki ani materiałów cudzych filmów referencyjnych. Mechanizmy 3D z upstreamu wymagają osobnej integracji; receptury playbooka nie przedstawiają ich jako dostępnych efektów.

[Przykładowy pomiar filmu FrameCore](../assets/framecore-motion-quality.json) · [film](../assets/framecore-production-demo.mp4) · [klatki i powroty w czasie](../assets/framecore-motion-review.jpg).
