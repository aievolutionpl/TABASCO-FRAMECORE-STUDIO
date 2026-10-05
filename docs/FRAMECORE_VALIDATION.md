# Sprawdzenie FrameCore — 2026-10-05

Środowisko chmurowe: Python 3.12.14, Playwright 1.63.0, systemowy Chromium 151.0.7922.173 i dostępne FFmpeg/FFprobe. Nie skonfigurowano dostawcy generowania materiałów.

## Wyniki wykonanych testów

Nowy zestaw FrameCore: **42 testy przeszły, bez pominięć**. Polecenie:

```bash
python -m pytest tests/test_framecore.py tests/test_framecore_creator_pack.py tests/test_framecore_browser.py tests/test_framecore_interface.py tests/test_framecore_production.py tests/test_framecore_quality.py tests/test_framecore_motion_evidence.py tests/test_framecore_agent_control.py -o addopts='' -q
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

Dysk `F:\CREATOR PACK` nie jest udostępniony w chmurze. Żaden materiał z tego folderu nie został przejrzany ani dodany. Wcześniejszy zestaw interfejsu obejmował 23 testy (19 kontraktu/integracji i 4 przeglądarkowe) i zakończył się w 132,66 s. Zestaw produkcyjny przed kolejnymi adaptacjami obejmował 30 testów: 23 kontraktu/integracji i 7 przeglądarkowych.

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

Kontrola struktury nie zastępuje oceny wizualnej i odsłuchu. Pełny historyczny zestaw repozytorium wykonano przed dołączeniem Creator Pack: **233 testy przeszły, 24 nie przeszły** (257 łącznie). Wszystkie 24 błędy dotyczą testów animacji otwierających `file://`, blokowanych przez politykę zarządzanego Chromium. Dwie nieaktualne asercje dokumentacji i nazwy profilu zostały poprawione. Wynik 42/42 dotyczy aktualnego zestawu FrameCore; cały historyczny zestaw pozostaje zablokowany w opisanej części.

## Adaptacja Motion Video Kit

Pełny aktualny zestaw: **34/34 testy**. Nowe przypadki sprawdzają rzeczywisty statyczny i ruchomy MP4, ciszę i głośność, SHA-256 zamrożonego filmu niezależnie od edycji projektu, raport w ZIP oraz przycisk pomiaru i pobranie JSON na komputerze i telefonie. Test z celowo wprowadzoną zależnością od historii seek wykrywa inne piksele i blokuje zatwierdzenie przeglądu.

Pokaz 6 s: **4,2 s** prawie nieruchomego obrazu przy 10 FPS, najdłuższy przedział **1,4 s**, **−36,3 LUFS**, **−21,2 dBFS true peak**. To demonstracja wykrywania problemów, a nie film spełniający wszystkie nowe kryteria. Trzy badane powroty do czasu (0 / 3 / 5,95 s) dały identyczne piksele. Świeży krytyk niezależnie wyciągnął 24 próbki i 12 dokładnych klatek, potwierdził potrzebę poprawy identyfikacji, CTA i rytmu. [Pełna recenzja](MOTION_VIDEO_KIT_REVIEW.md). Audio nie było odsłuchane.

## fframes i sterowanie agentem w dashboardzie

Końcowy pełny przebieg: **42/42 w 175,46 s**, bez pominięć. Obejmuje 30 testów kontraktu/integracji i 12 przeglądarkowych. Dodatkowy przebieg ośmiu nowych przypadków: **8/8 w 11,92 s**. Po rozszerzeniu obsługi launcherów npm ponownie wykonano cztery testy adapterów i kontraktu: **4/4 w 0,82 s** (test przeglądarkowy wyłączono jawnie w tym uzupełniającym przebiegu).

- `create_motion_strip`: rzeczywiste PNG i ważona nakładka z różnymi pozycjami obiektu; `get_review` przez MCP zwrócił JPEG i PNG.
- Adresy klatek: nazwa/id sceny, procent, ostatnia klatka, sekundy, milisekundy i zegar; nieprawidłowe zakresy są odrzucane.
- Porównanie tych samych klatek daje 0% zmian; zmieniony tekst daje różnice i diff PNG. Różne harmonogramy są odrzucane.
- Dashboard: połączenie OpenRouter z fikcyjnym kluczem, zadanie stosujące zmianę do projektu, historia agenta, cofanie oraz widok telefonu. Test czeka na zamknięcie dialogu przed wpisaniem polecenia. Szkic polecenia i tryb sterowania są zachowywane w pamięci przeglądarki przy odświeżaniu panelu.
- Ochrona rewizji podczas pracy modelu, zamrożone zaznaczenie, anulowanie i brak zastosowania niepoprawnych komend. Wygenerowane odpowiedzi błędów nie ujawniają fikcyjnego klucza i nie zapisują go w JSON projektu.
- Transport OpenRouter zweryfikowano z podstawioną odpowiedzią HTTP, z kontrolą endpointu, nagłówka i payloadu. Adaptery Codex/Claude uruchomiły rzeczywiste lokalne podprocesy z deterministycznymi atrapami odpowiedzi, bez płatnych sesji. Launcher `.cmd` rozwiązywano do oficjalnego układu pakietu i wykonywano przez rzeczywisty Node, bez powłoki.

Nie wykonano uwierzytelnionych wywołań OpenRouter, OpenAI ani Claude, nie zweryfikowano abonamentów ani działania na Windows. Nie uruchomiono natywnego Rust/Skia z fframes; zaadaptowano narzędzia przeglądu do obecnego silnika. Konfiguracja połączenia nie jest dowodem logowania — pierwsze zadanie sprawdza odpowiedź dostawcy.

Przykład laboratorium: dwie wersje sceny 960×540, po 10 klatek; oba przeglądy bez błędów tekstu/kadru, zmiana nagłówka wykryta. Zrzuty panelu połączenia, telefonu i nakładki wykonano z działającego serwera, bez błędów JavaScript. [Połączenie agenta](AGENT_DASHBOARD.md) · [fframes](FFRAMES.md) · [przykład różnic](../assets/framecore-motion-comparison.json).

## Profile marek · Company brain

Nowe testy sprawdzają trwały zapis profilu, konflikt wersji, obrazy i ich SHA-256, kopie w projektach oraz Cofnij/Ponów. Aktualizacja i usunięcie biblioteki nie zmieniają wybranego profilu ani bajtów materiałów wcześniejszego filmu. Niepoprawny obraz, font, adres i ścieżka spoza katalogu importów są odrzucane; konflikt przypisania nie zostawia skopiowanych plików.

Test przeglądarkowy tworzy firmę usługową, wpisuje produkt/usługę i źródło zwykłymi polami, wgrywa logo, wybiera profil i przenosi szkic agenta do formularza. Sprawdza oddzielny zapis oraz zachowanie wcześniejszej kopii projektu, brak zapisu bez tokena i dostęp do Ustawień na telefonie. Test dotychczasowego interfejsu sprawdza szerokości 320, 390, 900 i 1512 px. Odrzucony upload zamyka połączenie POST, aby pozostałe bajty nie stały się kolejnym żądaniem HTTP.

Adapter researchu był sprawdzany z deterministycznymi odpowiedziami: szkic nie zapisuje profilu samodzielnie, a anulowana odpowiedź nie pojawia się jako gotowy szkic. Osobny test potwierdza, że agent montażu otrzymuje company brain z ofertą, źródłami i metadanymi obrazów. Nie wykonywano płatnych sesji AI ani pobierania stron przez adapter szkicu. Zewnętrzny research zależy od narzędzi klienta MCP.

Trzy zrzuty panelu wykonano z rzeczywistego serwera; obejrzano widok komputera i telefonu. Przeglądarka nie zgłosiła błędów JavaScript. Profil na zrzutach jest fikcyjnym przykładem. Po restarcie studia potwierdzono dostępność biblioteki, siedmiu narzędzi i nowego menu na działającym serwerze.

Końcowy pełny przebieg FrameCore: **47/47 przeszło w 183,27 s**, bez pominięć. Uzupełniający przebieg interfejsu i marek po korekcie paska na telefonie: **6/6 w 11,42 s**. To weryfikacja modułów FrameCore, nie całego historycznego zestawu testów starszego silnika CLI.
