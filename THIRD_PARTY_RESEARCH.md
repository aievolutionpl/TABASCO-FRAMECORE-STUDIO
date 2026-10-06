# Przegląd projektów źródłowych — 2026-10-04

Publiczne repozytoria pobrano i przejrzano przed zmianą architektury. Odnośniki wskazują sprawdzone rewizje. Do kodu studia włączono bibliotekę HyperFrames Player oraz ikony Phosphor; pozostałe projekty były źródłem wiedzy.

| Projekt i źródło | Zweryfikowana licencja | Sprawdzone dowody | Decyzja |
| --- | --- | --- | --- |
| [HyperFrames](https://github.com/heygen-com/hyperframes/tree/173103dfdec5738f85733e6796d56932ad2a7436) | Apache-2.0, Copyright 2026 HeyGen, Inc. | LICENSE, manifesty przestrzeni roboczej, README odtwarzacza, `composition-probe.ts`, `timeline-adapters.ts`, mechanizmy osi czasu Studio, eksporty core | Bezpośrednio wbudować Player 0.8.124; dostosować kontrakt kompozycji. |
| [OpenCut](https://github.com/OpenCut-app/OpenCut/tree/e668010778568641babef2cc40be4703ae6916d6) | MIT, Copyright 2026 OpenCut | LICENSE, README, manifesty aplikacji, crates/media | Trwa przebudowa API wokół Rust i wtyczek. Wykorzystać wiedzę architektoniczną; bez kopiowania kodu. Classic to osobne repozytorium, niebadane tutaj. |
| [FreeCut](https://github.com/walterlow/freecut/tree/4d62e8082c5eb387a96275bcbd323d28f6e41a62) | MIT, Copyright 2025 FreeCut | LICENSE, README, manifest pakietu, układ workspace-fs, infrastruktura procesów roboczych | Zapis w zwykłych plikach; proxy, OPFS i procesy robocze jako kandydaci dalszej architektury. Bez kopiowania kodu. |
| [CartCut](https://github.com/cartesiancs/cartcut/tree/d6123469067ad20dc53ca3747421fc5f17406b2d) | MIT, Copyright 2025 cartesiancs | LICENSE, README MCP i manifesty mostu, kontekst i kontrolery osi czasu | Agent zmienia bieżącą oś czasu przez komendy i korzysta ze wspólnego cofania. Przyjąć zasadę; bez kopiowania kodu. |
| [Null Motion](https://github.com/blixvip/NullMotion/tree/2795457432a63e7e28879210601cede25915e561) | Nie wybrano licencji całego projektu | README, proces pracy i oświadczenie licencyjne, THIRD_PARTY_NOTICES | Tylko odniesienie; bez kopiowania kodu i materiałów. Repozytorium pokazuje rozpisany film promocyjny; funkcje hostowanego Null Studio są osobne. |

## Pakiety HyperFrames

| Pakiet | Przydatność i decyzja |
| --- | --- |
| `@hyperframes/player` | Niezależny od frameworka komponent przeglądarkowy. Wbudowany bezpośrednio, wersja 0.8.124, lokalny niezmieniony plik i tekst Apache-2.0. |
| `@hyperframes/core` | Przebadany kontrakt kompozycji, gotowość i czas mediów. Pełna integracja odłożona; Player zawiera część kodu core. |
| `@hyperframes/parsers` | Kandydat do importu źródeł HTML/GSAP i ich edycji. Wymaga adaptera JS oraz testów zapisu i ponownego odczytu. |
| `@hyperframes/sdk` | Adaptery edycji bez interfejsu, iframe i plików. Nie jest obecną zależnością API Python. |
| `@hyperframes/producer`, `engine` | Kandydat do nowego renderera. Obecnie zachowano sprawdzony Playwright/FFmpeg. |
| `@hyperframes/studio` | Interfejs React 19/Zustand/Bun. Nie kopiujemy całej aplikacji; integracja wymaga określonych granic modelu. |
| `@hyperframes/studio-server` | Serwer Hono, historia i zmiany źródeł. Przejrzany; nie zastępuje bezpośrednio lokalnego API Python. |
| CLI, instrukcje, rejestr | Kandydaci przyszłej integracji. Materiały i fonty rejestru mają osobne warunki, niezależne od licencji kodu. |

## Granice licencji

Nie kopiujemy źródeł AGPL, GPL ani kodu bez licencji. FFmpeg jest zewnętrznym programem dostępnym na maszynie; repozytorium nie rozpowszechnia jego binariów. Dystrybucja binarna wymaga osobnego audytu użytej kompilacji i kodeków.

GSAP ma własną licencję. Dotychczasowy renderer vstudio pozostaje dostępny, lecz nowe animacje FrameCore nie dołączają GSAP i go nie wymagają. Licencje mediów i fontów są metadanymi materiałów; import nie przyznaje użytkownikowi nowych praw.

Bibliotekę Player pobrano przez npm z kontrolą integralności rejestru. `LICENSES.json` zapisuje wersję, lokalny SHA-256, źródło i sprawdzoną rewizję. Licencja Apache z katalogu głównego upstream dotyczy pakietu mimo braku osobnego pola licencji w niektórych manifestach przestrzeni roboczej.

## Concat — ergonomia montażu

[jub0t/Concat](https://github.com/jub0t/Concat), commit `7b5cc44bc5c58838967e5f9c511e9f0ae3c9929c`, przeanalizowano pod kątem grup klipów, magnetycznego przycinania, monitora źródła i waveform. W MotionDuo powstały własne implementacje tych ogólnych mechanizmów, z użyciem istniejącego Store, API/MCP i historii cofania. Concat ma licencję AGPL-3.0-or-later; jego kod, silnik i materiały nie są dołączone ani kopiowane. [Pełna analiza i granice integracji](docs/CONCAT_REVIEW.md).
