# Od briefu do sprawdzonego filmu

Wdrożenie na podstawie dostarczonego [przewodnika AI Evolution Polska](references/AI_Evolution_Opus_55_Video_Studio_Guide_PL.pdf), który adaptuje wątek @0xwhrrari. Źródłem implementacji jest ten PDF; oryginalny wpis X nie był dostępny z sieci środowiska.

FrameCore zachowuje swój lokalny renderer HyperFrames/Chromium/FFmpeg. Agent opisuje projekt przez sprawdzany model JSON. Dowolny HTML lub JavaScript od agenta nie jest wykonywany. Nie dodano integracji Claude ani fikcyjnego dostawcy generowania materiałów.

## Przepływ w edytorze

1. Otwórz **Produkcja**. Zapisz produkt lub temat, główny komunikat, potwierdzone fakty, referencje oraz kryteria odrzucenia. Linki są zapisanymi referencjami, nie automatycznie pobranymi źródłami.
2. W **Obowiązkowych materiałach** nazwij wymagany plik i wskaż rzeczywisty materiał projektu. Możesz zapisać pozycję bez pliku, ale dopóki jej nie uzupełnisz, przegląd i render będą zatrzymane. Biblioteka nie generuje zastępczego logo, produktu ani ekranu.
3. Wybierz **Uzupełnij beaty z montażu**. Istniejące sceny zachowują czasy i opis; przy braku scen powstaną beaty na podstawie początków klipów. Opis jest propozycją. Otwórz każdy beat, popraw jego cel, stan wejściowy, wyjściowy i główny element. Usunięcie głównego klipu zachowuje opis i wymaga ponownego wyboru elementu.
4. **Zastosuj reguły ruchu** ustawia czas i krzywą istniejących animacji: napisy szybciej, obrazy i wideo wolniej. To operacja wspólnej historii z cofnięciem; nie zmienia typu animacji i respektuje blokady ścieżek. Krzywą pojedynczego elementu wybierzesz również w inspektorze: liniowa, lekka, płynna lub osiadanie.
5. **Generuj planszę klatek** zapisuje rzeczywiste obrazy renderera: środki beatów, próbki wokół cięć i końców wejść. Kliknij czas pod planszą, aby obejrzeć pełną klatkę. W tym przebiegu można przeglądać do 64 wskazanych czasów; domyślny przegląd zwykle mieści się w 24 klatkach. To próbkowanie, nie analiza każdej klatki filmu.
6. Automatyczna kontrola mierzy wyjście elementu poza kadr i tekstu poza jego pole, po zakończeniu wejścia. Dodatkowo pokazuje ostrzeżenia kontroli struktury. Samodzielnie oceń czytelność, hierarchię, branding, ciągłość i audio. Nikt nie zaznacza checklisty automatycznie. Można zapisać **Wymaga poprawek** wraz z uwagami.
7. Włączone **Wymagaj oceny przed finalnym eksportem** wymaga kompletnego briefu, beatów i zatwierdzenia aktualnego przeglądu bez wykrytych błędów. Każda zmiana rewizji albo pliku materiału unieważnia ocenę. Robocze MP4 można wyrenderować do oglądania i odsłuchu bez zatwierdzenia, ale wymagane materiały muszą istnieć.
8. Po eksporcie wybierz **Pobierz pakiet produkcyjny ZIP**. Paczka pochodzi z zamrożonej wersji filmu i zawiera MP4, edytowalny projekt, materiały, lokalny HTML, brief, manifest z SHA-256, shot list, reguły ruchu, informacje i pełne teksty licencji materiałów oraz osadzonych fontów, ich manifest i przegląd, jeśli był wykonany.

Bramka oceny jest opcją kontraktu. Dotychczasowe projekty nadal mogą eksportować bez niej. Przegląd i decyzja nie dodają kroków montażu do undo; są osobnymi artefaktami. Brief, beaty i reguły ruchu są normalnymi zmianami projektu i mają historię cofania.

## Osobne układy formatów

Przyciski **16:9 / 9:16 / 4:5 / 1:1** tworzą niezależny projekt z kopiami materiałów. Źródłowy montaż pozostaje nienaruszony. Układ poziomy dzieli przestrzeń na tekst i ilustrację; pionowy ustawia tekst nad ilustracją. Etykiety otrzymują dolną strefę, logo górny narożnik. Proporcje ilustracji i wielkości tekstu są ustalane dla nowego kadru. Pozycje klatek kluczowych przechodzą ten sam ruch co element.

Jest to układ startowy do dalszej edycji. Wideo i kształty zachowują skalowane pozycje; złożone sceny z kilkoma równoczesnymi tekstami wymagają ręcznego dopracowania hierarchii. Nie jest to automatyczna adaptacja dowolnego projektu. Każdy wariant ma własną rewizję, historię i obowiązkowy przegląd. Po zatwierdzeniu eksportuj każdy wariant osobno.

## Kontrakt dla agenta MCP

| Narzędzie | Zastosowanie |
| --- | --- |
| `set_production_contract` | Zapis briefu, kryteriów, wymaganych plików i bramki oceny |
| `annotate_story_beats` | Propozycja stanów i beatów na podstawie istniejącej osi czasu |
| `set_scene_beat` | Poprawka celu, stanów i głównego elementu danej sceny |
| `apply_motion_rules` | Czasy i krzywe ruchu według rodzaju elementu |
| `get_production_status` | Wymagane materiały, blokery i ważność oceny |
| `create_review` | Rzeczywiste klatki i plansza, również jako obraz w odpowiedzi MCP |
| `get_review` | Odczyt zapisanego przeglądu i planszy |
| `review_verdict` | Jawna ocena, checklista i uwagi; sprawdza wersję i materiały |
| `create_format_variant` | Niezależna kopia z układem startowym dla formatu |
| `package_delivery` | ZIP ukończonego, zamrożonego eksportu |

Przykład briefu:

```json
{
  "name": "set_production_contract",
  "arguments": {
    "project_id": "ID_PROJEKTU",
    "expected_revision": 4,
    "contract": {
      "product": "FrameCore Studio",
      "message": "Człowiek i agent tworzą jeden wspólny film.",
      "facts": ["Materiały pozostają lokalnie"],
      "references": ["Zatwierdzony widok interfejsu"],
      "rejectionCriteria": ["Ucięty nagłówek", "Nieprawdziwe logo"],
      "requiredAssets": [{"label": "Prawdziwe logo", "assetId": "ID_MATERIAŁU"}],
      "requireReview": true
    }
  }
}
```

Podstaw rzeczywiste identyfikatory i aktualną rewizję. `set_scene_beat` przyjmuje `scene_id` oraz `beat` z polami `purpose`, `entryState`, `exitState`, `focusElementId`. `create_review` opcjonalnie przyjmuje listę `times` w sekundach. Agent dostaje dane i planszę JPEG; do sprawdzenia szczegółu może użyć `capture_frame`.

`review_verdict` wymaga `review_id`, `verdict: approved/rejected`, `notes` i pięciu boolowskich pól `checklist`: `readability`, `hierarchy`, `brand`, `continuity`, `audio`. Zatwierdzenie nie przechodzi, gdy istnieją błędy pomiaru lub choć jeden punkt jest niezaznaczony. Zapis oceny i eksport wymagają bieżącego `expected_revision`. Zmiany proponuj przez wspólne `propose_changes`; nie regeneruj poprawnych scen.

## Pętla poprawek

Odczytaj brief → sprawdź blokery → obejrzyj planszę → nazwij problem i klatkę → zaproponuj tylko odpowiednią poprawkę → zastosuj zgodnie z zadaniem → wygeneruj nowy przegląd. Przyjmij najwyżej dwie rundy automatycznej naprawy w instrukcji agenta; jeśli problem pozostaje albo trzeba zmienić zatwierdzony materiał, zatrzymaj się z konkretnym raportem. Jest to instrukcja pracy agenta, nie nowy autonomiczny kontroler ani automatyczna ocena obrazu.

## Przykład i dowody

[Panel produkcji](../assets/framecore-production.png) · [Przegląd w edytorze](../assets/framecore-review.png) · [Film 6 s](../assets/framecore-production-demo.mp4) · [Układ 16:9](../assets/framecore-production-16x9.jpg) · [Układ 9:16](../assets/framecore-production-9x16.jpg) · [Układ 4:5](../assets/framecore-production-4x5.jpg).

Projekt przykładu i artefakty są w `examples/production-pipeline/`. Utwórz lokalną, niezależną kopię:

```bash
python framecore.py sample --production
python framecore.py editor
```

 Oceny przykładu odnoszą się do jego wyrenderowanych materiałów; import tworzy nowy projekt, który wymaga nowego przeglądu. Własny podkład proceduralny i biblioteka ilustracji nie są przedstawiane jako wyniki generatora AI.
