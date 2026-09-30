# Motion graphics (GSAP) — 6 pętli z promptów

Sześć samodzielnych plików HTML, po jednym na technikę z dokumentu *„6 motion graphics you can steal: the prompts”*
(autor promptów: **@andremass.ai**). Każdy plik to jedna pętla **1080×1350**, **7 s**, jedna oś czasu
GSAP 3.12.5 z `repeat: -1`, gotowa do podglądu w przeglądarce **i** do renderu przez `vstudio`.

| # | Plik | Technika | Do czego | Co się dzieje |
| --- | --- | --- | --- | --- |
| 1 | [`01-hide-the-cut.html`](01-hide-the-cut.html) | Ukryj cięcie | demo produktu od pomysłu do aplikacji | biała kropka → ikona → ląduje w telefonie → rośnie w ekran „Placed” → wraca do kropki |
| 2 | [`02-one-frame-for-everything.html`](02-one-frame-for-everything.html) | Jedna ramka na wszystko | przegląd narzędzi | telefon stoi; 6 ekranów wjeżdża z prawej i wypycha poprzedni w lewo (0.4 s) |
| 3 | [`03-three-colours-only.html`](03-three-colours-only.html) | Tylko trzy kolory | wykresy, dashboardy, slajdy | „Before: 9 colours” → granatowy pasek przemalowuje wszystko na 3 kolory → „After: 3 colours” |
| 4 | [`04-quiet-start-then-a-hit.html`](04-quiet-start-then-a-hit.html) | Cisza, potem uderzenie | premiery, duże liczby | kropka pulsuje i odlicza 3 s → błysk, wstrząs, „LIVE”, 8 kart powiadomień |
| 5 | [`05-pieces-first-whole-last.html`](05-pieces-first-whole-last.html) | Części najpierw, całość na końcu | odsłony logo, listy funkcji | burger z 6 warstw spada z odbiciem; gotowy dopiero po ostatniej warstwie |
| 6 | [`06-one-hero-one-world.html`](06-one-hero-one-world.html) | Jeden bohater, jeden prosty świat | ujęcie produktu | flakon NOIR obraca się w studiu (CSS 3D), odblask, cień, wolny najazd |

## Uruchomienie

```bash
# podgląd: otwórz plik w przeglądarce (pętla startuje sama, scena skaluje się do okna)
start examples/motion-graphics/03-three-colours-only.html

# render przez vstudio (kadr 4:5, 7 s)
py -3 -I vstudio.py new motion-3 --brand "Demo" --engine html --size 1080x1350 --fps 30 --duration 7
cp examples/motion-graphics/03-three-colours-only.html output/Demo/motion-3/src/index.html
py -3 -I vstudio.py render --final -p motion-3
```

> **GSAP z CDN.** Pliki ładują `https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js` — dokładnie ten adres,
> którego wymagają prompty. Render wymaga więc dostępu do `cdnjs.cloudflare.com` (to jedyne wyjście do sieci; reszta
> jest w pliku). Do pracy offline podmień `src` na lokalną kopię GSAP 3.12.5.

## Kontrakt strony vstudio

Każdy plik wystawia `window.DURATION` (7), `window.seek(t)` (zatrzymuje oś i ustawia ją na `t`, z zawijaniem co 7 s),
`window.EV` (zdarzenia dla cue sheetu), `window.TEXTS(t)` (widoczne teksty z boksami pikselowymi dla `readcheck`),
`window.__ready` i reaguje na `window.__CAPTURE__` (w renderze oś jest wstrzymana i sterowana tylko przez `seek`).

## Zasady z promptów, które wszystkie pliki spełniają

- wyśrodkowanie flexboxem lub jawnymi `left/top`, **nigdy** `transform: translate(-50%)` (GSAP nadpisuje `transform`),
- stan początkowy każdego elementu ustawiany `tl.set(..., 0)` w czasie 0 osi, więc pętla resetuje się czysto,
- rozmiar i promień rogów animowane w **px**, nigdy w `%` (plik 1),
- zero `Math.random`, zero timerów: ruch (także wstrząs w pliku 4) to stałe sekwencje.

## Odstępstwa od promptów (i dlaczego)

| Gdzie | Odstępstwo | Powód |
| --- | --- | --- |
| 1 | Treść ekranu zamówienia zaczyna się pojawiać od **3.2 s** (pełna ~3.5 s), ptaszek nadal o 3.4 s | Przy „w pełni widoczna o 3.2 s” rosnący jeszcze element (~60 % rozmiaru) ucina napis „Placed”. |
| 1 | Kropka gaśnie do zera w 6.5–7.0 s | Pętla ma być szczelna: klatka 0 s (kropka „wyskakuje” od zera) = ostatnia klatka. |
| 3 | Pasek przemalowuje **też** tło (krem), karty (granat) i pigułkę (granat → koral) | Reguła „po wycieraczce żaden inny kolor niż trzy” obejmuje wszystko, także białe tło i szare karty. Przejście jest liczone z pozycji paska (ta sama krzywa `power3.inOut`), bez callbacków. |
| 3 | Reset do 9 kolorów jest twardy (o 7 s) | Tak mówi prompt; to przełącznik przed/po, nie płynna pętla. |
| 5 | Etykieta nazywa warstwę przy pierwszym dotknięciu stosu (pierwsze odbicie), nie po całkowitym osadzeniu | Inaczej „Top bun” nigdy by się nie pokazał: „The whole thing” wchodzi dokładnie w chwili osadzenia ostatniej warstwy (3.9 s). |
| 1, 3, 4, 5 | Delikatny ruch w czasie przytrzymań (oddech ptaszka, powolny najazd sceny) | `MOTION_RULES.md` #2 („nic nie zamarza”); bez tego `qa` ostrzega o martwym czasie > 1 s. |
| 4 | Zegar i etykiety po 0.77 s | Z promptu: „jeden odczyt na puls” w 2.3 s. |
| 6 | Flakon 1.3×, stos cienkich paneli za szkłem i nakrętką | Sam płaski panel przy obrocie wygląda jak kartka; panele dają grubość bryły. Scena wraca do skali 1 w 6.3–7.0 s dla szczelnej pętli. |

## `readcheck` i krótkie teksty

Prompty narzucają krótkie czasy pokazu (np. etykiety warstw burgera ~0.5 s, ekrany po ~1 s, odliczanie 0.77 s).
`vstudio readcheck` wymaga `znaki / 15 + 1.5 s`, więc **zgłosi** te teksty jako zbyt krótkie. To zamierzone:
to są animacje pętlowe do oglądania „na szybko”, a `TEXTS` mówi prawdę o tym, co jest na ekranie, zamiast
ukrywać napisy przed kontrolą.

Wynik na czas pisania (`size 1080x1350`): plik 6 przechodzi czysto; plik 1 zgłasza 2 teksty (1.8 s zamiast 1.9–2.1 s),
plik 2 — wszystkie ekrany (~1.2 s zamiast 1.7–2.8 s), plik 4 — trzy odczyty zegara (0.77 s), plik 5 — sześć etykiet
warstw (~0.5 s). W plikach 3 i 4 pojawia się też zgłoszenie „na t=7.00 / 6.80 s”: to zawijanie pętli na granicy
`DURATION` (`seek(7)` = `seek(0)`), a nie osobny napis.

## Determinizm

Kadr jest funkcją czasu: `seek(t)` daje ten sam obraz niezależnie od kolejności wywołań. Dlatego w plikach
nie ma `yoyo`/`repeat` w tweenach, callbacków ani zachodzących na siebie tweenów tej samej właściwości,
a GSAP działa z `gsap.config({ force3D: false })` (bez promocji warstw kompozytora). Testy:
`pytest tests/test_motion_graphics.py` (część przeglądarkowa ma marker `browser`; potrzebuje GSAP 3.12.5 z sieci
albo z pliku wskazanego w `GSAP_JS`).

---

Pomysł i treść promptów: **@andremass.ai**. Implementacja: vstudio.
