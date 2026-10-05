# Wspólna rama — identyfikacja FrameCore

**TABASCO CREATIVES + FRAMECORE — STUDIO** to projekt współpracy człowieka i agenta nad jednym filmem. Dwa otwarte narożniki tworzą wspólną ramę. Dopracowany znak zachowuje wybrany kierunek 01, ma zaokrąglone końce i pomarańczowy akcent Tabasco.

## Gotowe pliki

| Zastosowanie | Plik |
| --- | --- |
| Logo podstawowe, przezroczyste | [SVG](../assets/framecore-logo.svg), [PNG](../assets/framecore-logo-primary.png) |
| Jasna nazwa na ciemnym tle | [SVG odwrócony](../assets/framecore-logo-reversed.svg) |
| Układ pionowy | [SVG](../assets/framecore-logo-stacked.svg) |
| Symbol / avatar | [PNG 256 px](../assets/framecore-logo-mark.png), [SVG pomarańczowy](../framecore/static/brand/mark-orange.svg) |
| Monochrom | [Grafitowy](../framecore/static/brand/mark.svg), [jasny](../framecore/static/brand/mark-light.svg) |
| Nagłówek edytora | [Wariant kompaktowy](../framecore/static/brand/wordmark-light.svg) |
| Paleta i przykłady użycia | [Plansza identyfikacji](../assets/framecore-brand-kit.png) |
| Wygenerowane odniesienie wizualne | [PNG](../assets/framecore-logo-refined.png) |

Pliki SVG są przygotowanymi osobno wektorami: geometryczny symbol i litery Manrope zamienione na krzywe. Można skalować je bez utraty ostrości; wyświetlenie logo nie wymaga instalowania fontu. PNG wygenerowany przez AI jest odniesieniem, a nie automatycznie zwektoryzowanym plikiem. Starsze plansze `framecore-logo-concepts.png` i `framecore-logo-board.png` dokumentują wcześniejsze koncepcje.

## Kolory i typografia

| Rola | HEX |
| --- | --- |
| Tabasco — znak i ważne akcje | `#EF421B` |
| Grafit — tekst i ciemne powierzchnie | `#151719` |
| Krem — jasne tło / jasny tekst | `#F5F3EC` |
| Ciepły akcent — zaznaczenie i kontrolki | `#F48D6E` |
| Mięta — współpraca i status | `#A5D8C8` |

**Manrope** jest krojem interfejsu i logo. **Space Grotesk** służy jako druga rodzina do nagłówków i plansz filmowych. Oba są już lokalnie w aplikacji, mają polskie znaki i licencję SIL OFL 1.1. [Manrope — licencja](../licenses/fonts/manrope-OFL.txt) · [Space Grotesk — licencja](../licenses/fonts/spacegrotesk-OFL.txt).

## Zasady użycia

Zachowaj proporcje i wolne miejsce wokół symbolu co najmniej równe grubości jego kreski: 32 jednostki w siatce 256 × 256. Dla logo z podpisem zalecana minimalna szerokość wynosi 320 px. Kompaktowy nagłówek bez podpisu można używać od 180 px. Symbol w interfejsie powinien mieć co najmniej 24 px; favicon 16 px jest uproszczonym zastosowaniem samego symbolu.

Używaj wersji z ciemną nazwą na jasnym tle, jasnej nazwy na graficie oraz monochromu tam, gdzie dostępny jest jeden kolor. Nie rozciągaj znaku, nie zmieniaj odstępów między literami i symbolem, nie dodawaj cieni, obrysów ani gradientów. Nie umieszczaj logo na obrazie, na którym traci czytelność.

## W aplikacji i filmie

Logo jest w nagłówku, faviconie i dokumentacji repozytorium. W panelu **Marka** przycisk **Dodaj logo FrameCore** importuje przezroczysty PNG, ustawia go jako logo marki i dodaje edytowalny klip w prawym górnym rogu filmu. Pozycję, rozmiar i animację zmienisz w inspektorze. Cofnięcie usuwa montaż znaku i przywraca wcześniejsze logo marki; sam zaimportowany materiał pozostaje w projekcie.
