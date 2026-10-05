---
name: framecore
description: Edycja wspólnego projektu filmowego człowieka i agenta przez MCP FrameCore.
---

# Agent w TABASCO CREATIVES + FRAMECORE — STUDIO

Pracujesz nad istniejącym projektem współpracy. Zachowuj intencję użytkownika, materiały i jego ostatnie poprawki.

1. Odczytaj `get_editing_guide`, `get_project` i `get_selection`. Ustal zaznaczenie, czas, markę, ścieżki i bieżącą rewizję.
2. Poznaj dostępne zasoby przez `list_assets`, `list_motion`, `list_templates`, `list_icons`, `list_library`, `list_fonts` i `list_backgrounds`. Nie wymyślaj identyfikatorów ani wyników dostawców.
3. Przy konkretnej zmianie użyj odpowiedniej komendy. Większe powiązane operacje przygotuj przez `propose_changes`. Jedna zastosowana propozycja to jeden krok cofania.
4. Wszystkie zmiany treści wysyłaj z `expected_revision`. Po konflikcie odczytaj projekt ponownie i dostosuj plan do nowych zmian.
5. Zaznaczenie i wskaźnik czasu są współdzielone z człowiekiem. Nie przenoś ich bez potrzeby. Blokada ścieżki chroni jej klipy.
6. Klatki kluczowe ustawiaj przez `set_keyframes`; czas jest lokalny względem początku klipu, a interpolacja liniowa. Obsługiwane właściwości: `x`, `y`, `rotation`, `scale`, `opacity`. Narzędzie zastępuje całą listę klatek elementu — zachowaj inne właściwości.
7. `set_audio` ustawia `gain` 0–1, `fadeIn` i `fadeOut` w sekundach. Nagranie wideo musi mieć osobny klip audio, aby jego dźwięk wszedł do miksu.
8. Użyj `inspect_project` do kontroli struktury i `capture_frame` do obejrzenia rzeczywistych klatek. Obejrzyj początek, środek i koniec ruchu. Sprawdź teksty, kadr, rytm i dźwięk w wyeksportowanym filmie.
9. `export` zamraża bieżącą rewizję. `get_job` zwraca stan i adres wyniku. Nie opisuj filmu jako wyrenderowanego przed zakończeniem zadania.

## Kontrakt produkcyjny i przegląd

Przeczytaj [PRODUCTION_PIPELINE.md](../../docs/PRODUCTION_PIPELINE.md). Odczytaj `get_production_status` i brief `production`. Fakty odróżnij od decyzji kreatywnych. `requiredAssets` wskazuje rzeczywiste materiały; przy brakującym wymaganym pliku zatrzymaj przegląd i render, nie generuj zamiennika.

`annotate_story_beats` przygotowuje propozycję opisów. Doprecyzuj `set_scene_beat`: cel, stan wejściowy i wyjściowy oraz główny element w czasie beatu. `apply_motion_rules` różnicuje masę ruchu czasem i krzywą; nie narusza blokad ścieżek. `apply_motion` może dostać `easing`: linear, quad-out, cubic-out, quint-out.

Przed eksportem użyj `create_review`; MCP zwraca również planszę JPEG. Obejrzyj pełne klatki w potrzebnych czasach przez `capture_frame`, a roboczy film odsłuchaj, jeśli masz możliwość. `review_verdict` wymaga jawnej checklisty. Nie deklaruj oglądania lub odsłuchu, których nie wykonano. Nowa rewizja albo zmieniony plik unieważnia ocenę. Bramka `requireReview` blokuje finalny eksport bez aktualnej oceny; wersja draft służy do kontroli filmu.

Wprowadzaj tylko poprawki związane z nazwanym problemem z przeglądu, poprzez `propose_changes`. Ogranicz autonomiczną naprawę do dwóch rund. Jeśli problem pozostaje, podaj dowód i potrzebną decyzję. Limit jest instrukcją pracy, nie automatycznym kontrolerem po stronie serwera.

`create_format_variant` tworzy niezależny projekt z układem startowym dla formatu; złożone sceny mogą wymagać ręcznej korekty. Wykonaj osobny przegląd wariantu. `package_delivery` wymaga ukończonego eksportu i pakuje jego zamrożone artefakty. Kontrakt nie pozwala wykonywać dowolnego kodu HTML/JS modelu.

## Przykłady

„Przesuń zaznaczony nagłówek o 0,4 sekundy wcześniej i nadaj mocniejsze wejście”: odczytaj zaznaczenie, zaproponuj `move_clip` i `apply_motion` (`impact-rise`, 0.5 s), przejrzyj propozycję, zastosuj zgodnie z poleceniem użytkownika, obejrzyj klatkę.

„Utwórz film o współpracy”: sprawdź materiały, użyj `plan_storyboard` z `template_id: collaboration`, popraw teksty, zbuduj montaż przez `assemble_storyboard`, przekazując także `template_id`, aby zachować wygląd. Zastąpienie istniejącego montażu wymaga jawnego `replace: true`; pokaż propozycję i zachowaj możliwość cofnięcia.

„Ożyw ikonę”: wybierz ikonę z `list_icons`, dodaj ją przez `add_icon`, ustaw `float` albo własne dwie klatki pozycji. Ikony mają licencję podaną w katalogu (MIT lub ISC/MIT); zapis zachowuje ich pochodzenie.

„Dodaj ilustrację i tło”: odczytaj `list_library` i `list_backgrounds`, wybierz materiały, zaproponuj `add_library_asset` oraz `set_background`. Przykład identyfikatorów: `fluent-rocket`, `aurora-breath`. Odczytaj aktualny katalog przed użyciem. Współdzielone propozycje i undo obejmują pliki biblioteki.

„Zmień typografię”: odczytaj `list_fonts`, użyj `set_property` z `property: style.fontFamily` dla tekstu lub `set_brand` dla całej marki. Osadzone fonty zawierają polskie znaki i nie potrzebują CDN. Sprawdź łamanie wierszy przez `capture_frame`.

## Granice

Nie ma skonfigurowanego dostawcy AI ani transkrypcji. Asystent w interfejsie jest parserem konkretnych poleceń czasu i animacji. Kontrola struktury nie mierzy automatycznie jakości montażu, kontrastu ani łamania wierszy. Import dowolnych dokumentów HTML HyperFrames, marketplace, ripple/slip i edytor krzywych animacji pozostają kolejnymi etapami.
