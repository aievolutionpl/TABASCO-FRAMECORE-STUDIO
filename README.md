<div align="center">

<img src="assets/tabasco-framecore-collaboration.jpg" alt="TABASCO CREATIVES + FRAMECORE — STUDIO: człowiek i agent AI tworzą razem" width="100%">

# TABASCO CREATIVES + FRAMECORE — STUDIO

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/framecore-logo-reversed.svg">
  <img alt="FrameCore — Wspólna rama" src="assets/framecore-logo.svg" width="640">
</picture>

**Projekt współpracy: człowiek, agent AI i jeden wspólny montaż.**

Lokalne studio do tworzenia filmów, animacji i rolek. Ty układasz historię i poprawiasz sceny; agent korzysta z tych samych materiałów, zaznaczenia, osi czasu i historii cofania.

![Edytor FrameCore: podgląd filmu, materiały, oś czasu i panel właściwości](assets/framecore-editor.png)

Python 3.11+ · FFmpeg · Chromium · [Kod MIT](LICENSE) · [Licencje bibliotek](THIRD_PARTY_NOTICES.md)

</div>

## Jak działa projekt

**Pomysł → materiały → plan scen → wspólny montaż → podgląd → MP4.**

Projekt ma jeden zapis JSON. Interfejs, API i serwer MCP czytają ten sam stan. Zmiana agenta pojawia się w edytorze, a przycisk cofania działa również dla jego operacji. Numer rewizji chroni przed nadpisaniem nowszego montażu. Większe zmiany można przygotować jako propozycję, obejrzeć i zastosować jednym krokiem.

Podgląd korzysta z lokalnej biblioteki HyperFrames Player. Render zapisuje klatki przez Chromium i składa film oraz dźwięk za pomocą FFmpeg. Do uruchomienia podstawowego studia nie potrzebujesz serwera Node ani CDN.

## Uruchom na swoim komputerze

Zainstaluj Python 3.11 lub nowszy, Git oraz FFmpeg z FFprobe dostępnymi w PATH.

```bash
git clone https://github.com/aievolutionpl/TABASCO-FRAMECORE-STUDIO.git vstudio
cd vstudio
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt pytest
python -m playwright install chromium
python framecore.py editor
```

Na Windows aktywuj środowisko poleceniem `.venv\Scripts\Activate.ps1`. Instrukcja i skrypty instalacji: [Uruchomienie lokalne](docs/URUCHOMIENIE_LOKALNE.md).

`python framecore.py editor` uruchamia studio na porcie 8877. `python vstudio.py dashboard` otwiera tę samą aplikację na porcie 8765. Starszy dashboard jest dostępny przez `python vstudio.py dashboard --legacy`.

## Pierwszy film

1. Otwórz projekt przykładowy lub utwórz własny.
2. Dodaj zdjęcie produktu, logo, nagranie i dźwięk.
3. W panelu **Szablony** wybierz strukturę filmu i przejrzyj plan scen.
4. Zbuduj montaż, popraw teksty i dobierz animacje.
5. Przesuwaj, przycinaj i dziel klipy na osi czasu. Sprawdź podgląd i dźwięk.
6. Wyeksportuj film do MP4.

Przykład FORM zawiera własną ilustrację produktu i proceduralnie przygotowany podkład. Materiały przykładowe nie są przedstawiane jako wyniki generatora AI.

## Przykład współpracy

[![Klatka polskiego filmu przykładowego FrameCore](assets/framecore-collaboration-poster.jpg)](assets/framecore-collaboration.mp4)

[Obejrzyj film 15 sekund](assets/framecore-collaboration.mp4) · [Klatki kontrolne](assets/framecore-collaboration-frames.jpg) · [Edytowalny zapis projektu](examples/framecore-collaboration/project.json)

Film 1920 × 1080 pokazuje sześć scen z polskimi tekstami, ikonami MIT i własnym podkładem. Utwórz jego lokalną wersję poleceniem `python framecore.py sample`, następnie wybierz projekt w menu studia.

## Wbudowane materiały

**Biblioteka** pozwala wyszukiwać ikony Phosphor, Tabler i Lucide oraz ilustracje Microsoft Fluent Emoji. **Tekst** i **Marka** udostępniają lokalne fonty: Manrope, Space Grotesk, Playfair Display, Fraunces, Bebas Neue, DM Sans, DM Serif Display i JetBrains Mono. W panelu **Tła** wybierzesz gradienty, wzory i animowane kompozycje.

[![Przykład wbudowanych materiałów](assets/framecore-creator-pack-poster.jpg)](assets/framecore-creator-pack.mp4)

[Obejrzyj pokaz 12 sekund](assets/framecore-creator-pack.mp4) · [Przegląd 12 szablonów](assets/framecore-templates.jpg) · [Instrukcja Creator Pack](docs/CREATOR_PACK.md)

Utwórz edytowalną kopię pokazu: `python framecore.py sample --creator-pack`. Po instalacji fonty, ilustracje i eksport działają bez CDN. Oryginalne licencje i źródła są dołączone do repozytorium.

## Edycja i narzędzia agenta

Studio obsługuje tekst, obrazy, wideo, kształty, napisy i dźwięk na osobnych ścieżkach. Możesz zmieniać geometrię, typografię, czas, markę i format: 9:16, 4:5, 1:1 lub 16:9. Materiały pozostają lokalnie w katalogu projektu. Biblioteka zawiera **28 animacji, 12 szablonów, 60 ikon, 24 ilustracje 3D, 8 rodzin fontów z polskimi znakami oraz 24 tła**. Wszystkie materiały są lokalne; sześć teł ma deterministyczną animację. Szablony dobierają własną typografię, paletę, układ i ruch. Nowe narzędzia obejmują duplikowanie klipów, liniowe klatki kluczowe, głośność oraz narastanie i wyciszenie dźwięku. Agent może przeprowadzić kontrolę struktury i obejrzeć rzeczywistą klatkę filmu.

Uruchom `.venv/bin/python framecore.py mcp` z katalogiem repozytorium ustawionym jako katalog pracy klienta MCP. Na Windows użyj `.venv\Scripts\python.exe`. [Konfiguracja MCP](MCP_SPEC.md) i [instrukcja pracy agenta](skills/framecore/SKILL.md) opisują odczyt kontekstu, zmiany, propozycje i kontrolę jakości.

Przykładowe polecenie:

> Przeczytaj instrukcję FrameCore. Sprawdź zaznaczenie i bieżącą rewizję. Przesuń zaznaczony nagłówek o 0,4 sekundy wcześniej, dodaj mocniejsze wejście i pokaż propozycję. Następnie sprawdź klatkę i oś czasu.

Lokalny asystent rozpoznaje konkretne polecenia czasu i animacji. Swobodne polecenia twórcze wymagają podłączonego agenta. Generowanie obrazów, wideo, głosu i automatyczna transkrypcja mają interfejsy dostawców; bez skonfigurowanej integracji nie działają. Napisy można edytować ręcznie.

## Dokumentacja i licencje

| Temat | Dokument |
| --- | --- |
| Architektura i wspólny zapis projektu | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Format projektu | [FRAMECORE_PROJECT_SPEC.md](FRAMECORE_PROJECT_SPEC.md) |
| Integracja agenta | [MCP_SPEC.md](MCP_SPEC.md) |
| Przegląd projektów źródłowych | [THIRD_PARTY_RESEARCH.md](THIRD_PARTY_RESEARCH.md) |
| Wbudowane materiały, fonty, tła i szablony | [Creator Pack](docs/CREATOR_PACK.md) |
| Biblioteki, ikony i licencje | [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [LICENSES.json](LICENSES.json) |
| Wyniki sprawdzeń | [Walidacja](docs/FRAMECORE_VALIDATION.md) |
| Dotychczasowe narzędzia vstudio | [REFERENCE.md](REFERENCE.md), [mapa możliwości](docs/CAPABILITIES.md) |

Kod projektu jest dostępny na licencji MIT. HyperFrames Player ma licencję Apache-2.0, ikony Phosphor i Tabler oraz ilustracje Fluent — MIT, Lucide — ISC/MIT, a fonty — SIL OFL 1.1. Teksty licencji zachowujemy w oryginale. Własne zdjęcia, nagrania, fonty i ilustracje podlegają prawom ich autorów. Przesłana ilustracja poniżej jest materiałem identyfikacji projektu; licencja kodu nie przenosi praw do niej.

## Testy

```bash
python -m pytest tests/test_framecore.py tests/test_framecore_creator_pack.py tests/test_framecore_browser.py -q
```

Test przeglądarkowy importuje materiały, uruchamia osobny proces agenta MCP, sprawdza wspólną historię i eksportuje rzeczywisty film 15 sekund w rozdzielczości 1080 × 1920 z dźwiękiem. Wyniki dotyczą wykonanego przebiegu i są opisane w dokumencie walidacji.

## Logo — Wspólna rama

Wybrany znak łączy dwa otwarte narożniki w jedną ramę: dwie strony współpracy tworzą wspólny film. [Logo SVG](assets/framecore-logo.svg) · [wariant odwrócony](assets/framecore-logo-reversed.svg) · [plansza identyfikacji](assets/framecore-logo-board.png) · [zasady użycia](docs/IDENTYFIKACJA.md).

## Współpraca

**TABASCO CREATIVES + FRAMECORE — STUDIO** to projekt współpracy nad narzędziami twórczymi. Łączymy decyzje człowieka z narzędziami agenta, aby film dało się obejrzeć, poprawić i dalej edytować.

Poniższa ilustracja została dostarczona do projektu. Przedstawia jego ideę i identyfikację; aktualny interfejs pokazuje zrzut ekranu na początku README.

![TABASCO CREATIVES + FRAMECORE — STUDIO: człowiek i agent AI wspólnie tworzą film](assets/tabasco-framecore-collaboration.jpg)
