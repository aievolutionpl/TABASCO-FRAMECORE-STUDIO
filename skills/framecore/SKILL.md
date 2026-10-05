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

## Przykłady

„Przesuń zaznaczony nagłówek o 0,4 sekundy wcześniej i nadaj mocniejsze wejście”: odczytaj zaznaczenie, zaproponuj `move_clip` i `apply_motion` (`impact-rise`, 0.5 s), przejrzyj propozycję, zastosuj zgodnie z poleceniem użytkownika, obejrzyj klatkę.

„Utwórz film o współpracy”: sprawdź materiały, użyj `plan_storyboard` z `template_id: collaboration`, popraw teksty, zbuduj montaż przez `assemble_storyboard`, przekazując także `template_id`, aby zachować wygląd. Zastąpienie istniejącego montażu wymaga jawnego `replace: true`; pokaż propozycję i zachowaj możliwość cofnięcia.

„Ożyw ikonę”: wybierz ikonę z `list_icons`, dodaj ją przez `add_icon`, ustaw `float` albo własne dwie klatki pozycji. Ikony mają licencję podaną w katalogu (MIT lub ISC/MIT); zapis zachowuje ich pochodzenie.

„Dodaj ilustrację i tło”: odczytaj `list_library` i `list_backgrounds`, wybierz materiały, zaproponuj `add_library_asset` oraz `set_background`. Przykład identyfikatorów: `fluent-rocket`, `aurora-breath`. Odczytaj aktualny katalog przed użyciem. Współdzielone propozycje i undo obejmują pliki biblioteki.

„Zmień typografię”: odczytaj `list_fonts`, użyj `set_property` z `property: style.fontFamily` dla tekstu lub `set_brand` dla całej marki. Osadzone fonty zawierają polskie znaki i nie potrzebują CDN. Sprawdź łamanie wierszy przez `capture_frame`.

## Szybki onboarding

Przeczytaj `docs/AGENT_QUICKSTART.md`. W interfejsie dostępne są **Jak zacząć**, **Integracje** i **Twój agent**. OpenRouter/OpenAI obsługują rozmowę i wywołania narzędzi montażowych. Wbudowany agent tekstowy korzysta z tego samego API i historii, ale nie ogląda klatek i nie ma dostępu do terminala. Klucze pozostają w lokalnej konfiguracji serwera; nie zapisuj ich w projekcie ani dokumentacji.

Dla reklamy stosuj jeden komunikat na scenę, 3–6 sekund na scenę, kontrastową typografię i różne animacje bez nadmiaru efektów. Biblioteka FrameCore Cinema zawiera trzy tła AI (`kind: scene`) z odrębną informacją o pochodzeniu. Nie opisuj ich jako ikon MIT.

## Granice

Klucz dostawcy rozmowy konfiguruje użytkownik. Generowanie mediów i transkrypcja nadal wymagają osobnych adapterów. Starsze lokalne skróty poleceń działają bez modelu. Kontrola struktury nie mierzy automatycznie jakości montażu, kontrastu ani łamania wierszy. Import dowolnych dokumentów HTML HyperFrames, marketplace, ripple/slip i edytor krzywych animacji pozostają kolejnymi etapami.
