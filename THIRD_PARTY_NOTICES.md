# Biblioteki i materiały zewnętrzne

TABASCO CREATIVES + FRAMECORE — STUDIO zachowuje licencję MIT kodu repozytorium (AI Evolution Polska).

## HyperFrames Player 0.8.124

Copyright 2026 HeyGen, Inc. Licencja Apache License, Version 2.0.

Lokalny, niezmieniony plik `framecore/static/vendor/hyperframes-player-0.8.124.js` pochodzi z opublikowanego pakietu `@hyperframes/player` 0.8.124 i zawiera kod bibliotek HyperFrames. [Pełny tekst licencji](licenses/HyperFrames-Apache-2.0.txt). Źródło: https://github.com/heygen-com/hyperframes. Grafiki marki HyperFrames i materiały ich rejestru nie zostały skopiowane.

Ruch 2.0 (przejścia scen ✦ i reguły kontroli projektu) opiera się na pomysłach z pakietów `@hyperframes/shader-transitions` i `@hyperframes/lint` oraz instrukcji `hyperframes-animation` (Apache-2.0, Copyright HeyGen, Inc.). Implementacja w `framecore/static/composition.js` i `framecore/inspection.py` jest własna; nie kopiowano kodu shaderów ani reguł.

## Phosphor Icons 2.1.1

Copyright (c) 2023 Phosphor Icons. Licencja MIT. W `framecore/static/icons/` znajduje się 39 niezmienionych ikon SVG z pakietu `@phosphor-icons/core`. Plik licencji i manifest sprawdzono przed skopiowaniem. [Pełny tekst licencji](licenses/Phosphor-MIT.txt).

12 ikon jest dostępnych również jako materiały do filmu. Zapis projektu zachowuje identyfikator, wersję i licencję. Kolorowanie w kompozycji korzysta z maski CSS; plik źródłowy SVG pozostaje niezmieniony.

## Pozostałe materiały

Nie rozpowszechniamy kodu OpenCut, FreeCut, CartCut ani Null Motion. [Przegląd źródeł](THIRD_PARTY_RESEARCH.md) opisuje zakres audytu. Zależności Pythona są instalowane przez `requirements.txt`. FFmpeg i Chromium są zewnętrznymi programami; nie dołączamy ich plików binarnych.

Ilustracja `assets/tabasco-framecore-collaboration.jpg` została dostarczona przez użytkownika jako materiał identyfikacji projektu. Licencja MIT kodu nie obejmuje automatycznie praw do tej ilustracji. `assets/framecore-logo-concepts.png` przedstawia trzy wstępne koncepcje. Użytkownik wybrał Wspólną ramę; plansza `assets/framecore-logo-board.png` pokazuje ten kierunek, a symbol i pliki SVG są jego geometryczną wersją. Dopracowane logo ma własną konstrukcję geometryczną i liternictwo Manrope zamienione na krzywe. Plik fontu Manrope, informacja copyright i licencja SIL OFL 1.1 są zachowane w bibliotece projektu (odnośniki poniżej). `assets/framecore-logo-refined.png` jest wygenerowanym przez AI odniesieniem, a `assets/framecore-brand-kit.png` przedstawia produkcyjne wektory, paletę i przykłady użycia.

## Tabler Icons

24 niezmienione SVG outline. Copyright (c) 2020–2026 Paweł Kuna. Licencja MIT. [Źródło](https://github.com/tabler/tabler-icons), commit `a49ebdf8e13cc30794a5629c5b637e13ed5699d0`. [Pełna licencja](licenses/Tabler-LICENSE.txt).

## Lucide

24 niezmienione SVG. Copyright (c) 2026 Lucide Icons and Contributors, licencja ISC. Część ikon pochodzi z Feather, Copyright (c) 2013–present Cole Bemis, licencja MIT. Zachowano cały plik licencji z wykazem ikon Feather. [Źródło](https://github.com/lucide-icons/lucide), commit `500620a2e8123f8d1db191538886dc0c223f69a9`. [Pełna licencja](licenses/Lucide-LICENSE.txt).

## Microsoft Fluent Emoji

24 niezmienione PNG 3D, Copyright (c) Microsoft Corporation, licencja MIT. [Źródło](https://github.com/microsoft/fluentui-emoji), commit `1ffb34c752ecf5d402f04cfb4b392c77f57c54bc`. [Pełna licencja](licenses/Fluent-Emoji-MIT.txt).

## Google Fonts — osiem rodzin

Niezmienione pliki TTF na licencji SIL Open Font License 1.1. [Źródło](https://github.com/google/fonts), commit `9710da1eacb3be272583c3224dcb70f9da6eadbb`. Zachowano pełną licencję każdej rodziny wraz z jej informacją copyright i Reserved Font Names:

- [Manrope](licenses/fonts/manrope-OFL.txt)
- [Space Grotesk](licenses/fonts/spacegrotesk-OFL.txt)
- [Playfair Display](licenses/fonts/playfairdisplay-OFL.txt)
- [Fraunces](licenses/fonts/fraunces-OFL.txt)
- [Bebas Neue](licenses/fonts/bebasneue-OFL.txt)
- [DM Sans](licenses/fonts/dmsans-OFL.txt)
- [DM Serif Display](licenses/fonts/dmserifdisplay-OFL.txt)
- [JetBrains Mono](licenses/fonts/jetbrainsmono-OFL.txt)

[Katalog plików i sum SHA-256](framecore/static/library/catalog.json) pozwala zweryfikować każdy pobrany plik. Fonty nie zostały przetworzone ani przemianowane. Własne receptury teł, animacje i szablony mają licencję MIT projektu. Powielone pliki w przykładzie `examples/creator-pack/assets/` zachowują pochodzenie opisane w jego `project.json`; stosują się te same licencje.

Przewodnik `docs/references/AI_Evolution_Opus_55_Video_Studio_Guide_PL.pdf` został dostarczony przez użytkownika jako materiał źródłowy. Zachowano go w oryginale; licencja kodu nie przenosi automatycznie praw do tego dokumentu. Przykład `examples/production-pipeline/` zachowuje pochodzenie i licencje materiałów w manifestach; ilustracje i fonty mają te same licencje opisane powyżej.

## Motion Video Kit

Zasady filmu biznesowego i filtry pomiarowe zaadaptowano z [echris6/motion-video-kit](https://github.com/echris6/motion-video-kit/tree/255562b04b1e5ecaa4ba98e5c9aa191d5ba7f6fa), commit `255562b04b1e5ecaa4ba98e5c9aa191d5ba7f6fa`, Copyright (c) 2026 echris6, MIT. [Pełna oryginalna licencja](licenses/Motion-Video-Kit-MIT.txt). Adaptacja obejmuje `framecore/quality.py`, `framecore/playbook.py`, instrukcje i polski skill; nie zawiera cudzych filmów referencyjnych. [Zakres i ograniczenia](docs/MOTION_VIDEO_KIT.md).

## fframes

Adresowanie klatek, liniowe wagi onion skin i porównanie pikseli zaadaptowano z [dmtrKovalenko/fframes](https://github.com/dmtrKovalenko/fframes/tree/b7fc055f7028f4380ed6102d33040fd1bf491036), commit `b7fc055f7028f4380ed6102d33040fd1bf491036`. Copyright (c) 2025–2026 Dmitriy Kovalenko, MIT. [Pełna licencja](licenses/fframes-MIT.txt). Implementacja w `framecore/motion_evidence.py`; [zakres](docs/FFRAMES.md). Nie redystrybuujemy filmu demonstracyjnego ani fontów i muzyki tego repozytorium.
