# Sprawdzenie FrameCore — 2026-10-05

Środowisko chmurowe: Python 3.12.14, Playwright 1.63.0, systemowy Chromium 151.0.7922.173 i dostępne FFmpeg/FFprobe. Nie skonfigurowano dostawcy generowania materiałów.

## Wyniki wykonanych testów

Nowy zestaw FrameCore: **30 testów przeszło, bez pominięć**. Polecenie:

```bash
python -m pytest tests/test_framecore.py tests/test_framecore_creator_pack.py tests/test_framecore_browser.py tests/test_framecore_interface.py tests/test_framecore_production.py -o addopts='' -q
```

Sprawdzono wspólną edycję przez HTTP i osobny proces MCP, zaznaczenie, propozycje, cofanie, ponowną edycję człowieka, trwałość historii, konflikty rewizji i atomowość błędnych operacji. Import przez interfejs obejmował obraz produktu, logo oraz MP4 z dźwiękiem.

Test przeglądarkowy wyeksportował i pobrał film **15 s, 1080 × 1920, H.264 z audio**. FFprobe niezależnie sprawdził czas, rozdzielczość i kodeki. Oddzielnie wyrenderowano polski przykład współpracy **15 s, 1920 × 1080, H.264 + AAC**, dostępny w `assets/framecore-collaboration.mp4`. Klatki kontrolne obejrzano po renderze.

Dodatkowe sprawdzenia nowych funkcji:

- Ciągłość klatek kluczowych po podziale, skalowanie punktów przy zmianie formatu i odrzucanie błędnych wartości bez zmiany historii.
- Duplikowanie klipu oraz blokada zmiany na zablokowanej ścieżce.
- Ikony MIT jako materiały projektu, również dodawane przez propozycję z zachowaniem identyfikatorów.
- Dwanaście szablonów i 28 animacji. Każdą animację sprawdzono po przewinięciu w różnej kolejności; stan tego samego czasu był zgodny.
- Głośność, narastanie i wyciszenie, walidacja czasów oraz ich zachowanie po podziale audio.
- Polski interfejs, edycja klatek przez panel, kontrola struktury i rzeczywisty obraz klatki przekazywany agentowi. Bez błędów JavaScript w testowanych ścieżkach.
- Ochrona tokenem, odpowiedź HTTP 409, odrzucanie błędnych ścieżek/SVG oraz bezpieczne traktowanie tekstu zawierającego znaczniki skryptów.
- Stan eksportu dostępny z osobnego procesu; brak dostawcy nie tworzy fikcyjnych materiałów.

Ponownie uruchomiono serwer studia. Otwiera polski interfejs i lokalny Player osiąga gotowość. Układy 1512, 900 i 390 px sprawdzono pod kątem poziomego przepełnienia. Zrzut: `assets/framecore-editor.png`.

Skrypt `scripts/install-local.sh` wykonano w obecnym środowisku i potwierdzono sprawdzenie instalacji. Skrypt PowerShell przygotowano, ale nie uruchomiono na Windows. Brak narzędzia dostępu do systemu użytkownika oznacza, że nie wykonano instalacji na jego komputerze.

## Creator Pack — dodatkowa walidacja

- **60 ikon, 24 ilustracje 3D, 8 fontów, 24 tła i 12 szablonów**. Sumy SHA-256 i obecność oryginalnych licencji sprawdzono dla każdego pobranego pliku.
- W chmurze wykonano dodatkowy checkout z `core.autocrlf=true`. Wszystkie 80 sum plików fontów i nowych materiałów pozostało zgodnych dzięki `.gitattributes`; jest to sprawdzenie zachowania Git, nie uruchomienie aplikacji na Windows.
- Tablice znaków ośmiu fontów sprawdzono przez FontTools. Wszystkie zawierają `ĄąĆćĘęŁłŃńÓóŚśŹźŻż`. FontTools służył do audytu; aplikacja go nie wymaga.
- Test Chromium blokował wszystkie żądania poza własnym lokalnym serwerem. Biblioteka, wybór fontu, ilustracji i tła, propozycja nowego montażu i cofanie działały bez błędów JavaScript. Każdy z ośmiu fontów osiągnął stan załadowany w kompozycji przy zablokowanym internecie.
- Zrzuty animowanego tła w dwóch czasach były różne; powrót do tego samego czasu dał identyczny PNG.
- Przygotowano **48 rzeczywistych podglądów**: wszystkie 12 szablonów w formatach 16:9, 9:16, 1:1 i 4:5. Po poprawieniu wysokości etykiet i zawijania spacji sprawdzono 288 klatek tekstowych bez wykrytego przekroczenia pól. Nie jest to gwarancja dopasowania dowolnego tekstu użytkownika; po zmianach trzeba obejrzeć kadr.
- Wyrenderowano i obejrzano pokaz **12 s, 1920 × 1080, H.264 + AAC**. FFprobe potwierdził parametry; [film](../assets/framecore-creator-pack.mp4), [klatki](../assets/framecore-creator-pack-frames.jpg) i [przegląd szablonów](../assets/framecore-templates.jpg) są w repozytorium.
- `python framecore.py sample --creator-pack` tworzy niezależną kopię przykładu. Test potwierdza zachowanie wcześniejszej kopii i oryginalnego projektu.
- Ponownie sprawdzono żywy interfejs w szerokościach 1512, 900 i 390 px: brak poziomego przepełnienia dokumentu. Zrzut README pokazuje nową bibliotekę ilustracji.

Dysk `F:\CREATOR PACK` nie jest udostępniony w chmurze. Żaden materiał z tego folderu nie został przejrzany ani dodany. Wcześniejszy zestaw interfejsu obejmował 23 testy (19 kontraktu/integracji i 4 przeglądarkowe) i zakończył się w 132,66 s. Obecny zestaw obejmuje 30 testów: 23 kontraktu/integracji i 7 przeglądarkowych.

## Dopracowany interfejs i logo

- Nowy nagłówek, favicon, większa typografia Manrope, grafitowe powierzchnie i akcenty Tabasco. Obejrzano rzeczywiste zrzuty kompozycji na komputerze i paneli na telefonie.
- Wyrównanie elementu w osi X/Y zapisuje zmianę projektu i działa z cofnięciem. Ulubione przetrwały przeładowanie strony bez zmiany rewizji. Filtr kolekcji Tabler zwrócił 24 materiały.
- Dodanie logo przez panel Marka importuje lokalny PNG, ustawia logo marki i dodaje klip przez wspólną propozycję. Test sprawdził czas klipu oraz cofnięcie montażu i logo marki.
- Wybór animacji uruchamia rzeczywisty krótki podgląd. Preferencja ograniczonego ruchu wyłącza dekoracyjne animacje kart.
- Sprawdzono szybką sekwencję zaznaczenie → duplikowanie przy celowo opóźnionym zapisie zaznaczenia: duplikowany jest właściwy klip. Poprawka usuwa wyścig ujawniony przez pierwsze uruchomienie pełnego zestawu (22 przeszły, 1 nie przeszedł); końcowy przebieg 23/23 podano powyżej.
- Telefon: biblioteka i właściwości wykorzystują wysokość ekranu, mają tło nieaktywne przez `inert`, zamykanie Escape, pułapkę Tab i powrót fokusu do przycisku. Test sprawdził również dostęp do tworzenia i wyboru projektu.
- Po końcowej poprawce wysokości i układu paneli dodatkowo wykonano rozszerzony test interfejsu: **1/1 przeszedł w 7,46 s**. Dokument nie miał poziomego przepełnienia w szerokościach 320, 390, 900 i 1512 px. Brak błędów JavaScript w testowanych ścieżkach.
- Pliki logo SVG mają wektorowy symbol oraz liternictwo Manrope zamienione na krzywe; PNG wygenerowany przez AI zachowano osobno jako odniesienie wizualne. Paleta, warianty i zasady użycia są w [identyfikacji](IDENTYFIKACJA.md).

## Pipeline produkcyjny z dostarczonego przewodnika

Źródło: oryginalny PDF użytkownika zachowany w `docs/references/`. Nowy panel zapisuje brief, obowiązkowe materiały i beaty w modelu JSON. Testy sprawdziły walidację kontraktu bez zmiany historii po błędzie, cofnięcie, blokowanie draft/final przy braku wymaganego materiału i finalnego eksportu przy brakujących beatach lub ocenie.

- Generowanie przeglądu otwiera rzeczywistą kompozycję w Chromium, zapisuje PNG i planszę JPEG. Celowo zbyt małe pole tekstu zostało wykryte. Nie można zatwierdzić raportu z błędem ani przeglądu wcześniejszej rewizji.
- Zmiana bajtów PNG bez zmiany rewizji unieważniła ocenę dzięki SHA-256; przywrócenie pliku przywróciło zgodność z dowodem. MCP zwrócił planszę jako obraz JPEG obok JSON.
- Osobne kopie formatów zachowały oryginał i bajty jego materiałów. Poziom rozdziela tekst i obraz, pion ustawia je jeden pod drugim. Nieprawidłowy format nie utworzył projektu. Reguły ruchu nadają ilustracji dłuższe osiadanie niż tekstowi i nie naruszają zablokowanej ścieżki.
- Usunięcie głównego elementu nie blokuje dalszej edycji: cel beatu pozostaje, fokus wymaga uzupełnienia. Cofnięcie przywróciło powiązanie.
- Podkład źródłowy podmieniono na ciszę po wyrenderowaniu obrazu. Wynik nadal zawierał oryginalny dźwięk, bo miks czyta zamrożoną kopię. Dodatkowy test tej sytuacji przeszedł w 3,22 s. Eksport sprawdza również zgodność bajtów skopiowanych materiałów z preflightem.
- Test interfejsu zapisał brief, poprawił cel beatu, wygenerował i ocenił przegląd, wyeksportował MP4 oraz pobrał ZIP. Paczka zawierała film, zamrożony projekt, brief, shot list, manifest, reguły ruchu, informacje o licencjach i zatwierdzony przegląd tej samej rewizji. Paczka zawiera pełny oryginalny tekst licencji Manrope i materiałów wbudowanych oraz manifest osadzonych fontów. Bajty OFL w paczce przykładu porównano z plikiem źródłowym.
- Przygotowano pokaz **6 s, 960 × 540, H.264 + AAC** i **68 rzeczywistych klatek kontrolnych**: po 17 dla mastera oraz wariantów 16:9, 9:16 i 4:5. Pomiar nie wykrył przekroczenia pól; plansze obejrzano. Nie jest to kontrola dowolnego filmu ani każdej klatki.
- Roboczy miks MP4 sprawdzono przez FFprobe i dekodowanie do PCM: audio obecne, szczyt około 0,087 i RMS około 0,017, bez clippingu. To weryfikacja techniczna proceduralnego podkładu, nie deklaracja odsłuchu przez użytkownika.
- Zapisano film, ZIP i edytowalny przykład `examples/production-pipeline/`. `python framecore.py sample --production` wykonano; test dwóch importów potwierdza niezależne projekty i obowiązek nowego przeglądu.
- Dodatkowy przebieg rozszerzonych testów produkcji: **6/6 przeszło w 11,25 s**. Końcowy pełny zestaw: **30/30, 158,99 s**. Obejrzano panel oraz modal przeglądu, a szerokości 390/900/1512 nie powodowały poziomego przepełnienia ani błędów JavaScript.

[Instrukcja pipeline’u](PRODUCTION_PIPELINE.md) · [Film](../assets/framecore-production-demo.mp4) · [Paczka](../assets/framecore-production-delivery.zip).

## Granice potwierdzenia

To działający etap rozbudowy, a nie wszystkie fazy z briefu. Test osobnego procesu MCP potwierdza protokół; nie oznacza skonfigurowania klienta Codex/Claude na komputerze użytkownika.

Dostawcy AI i automatyczna transkrypcja wymagają integracji. Plan scen jest szablonem lokalnym. Nie obsługujemy jeszcze dowolnego importu źródeł HyperFrames, marketplace, ripple/slip, własnych krzywych Béziera ani automatycznego dopasowania transkrypcji.

Kontrola struktury nie zastępuje oceny wizualnej i odsłuchu. Pełny historyczny zestaw repozytorium wykonano przed dołączeniem Creator Pack: **233 testy przeszły, 24 nie przeszły** (257 łącznie). Wszystkie 24 błędy dotyczą testów animacji otwierających `file://`, blokowanych przez politykę zarządzanego Chromium. Dwie nieaktualne asercje dokumentacji i nazwy profilu zostały poprawione. Wynik 30/30 dotyczy aktualnego zestawu FrameCore; cały historyczny zestaw pozostaje zablokowany w opisanej części.
