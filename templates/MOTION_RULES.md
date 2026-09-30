# Motion rules for every shot

Numeric rules that separate studio motion from cheap motion. Measured, not guessed (source: a reverse-engineering study of
motion that works; see `Skills/video-reference-remake/`). When the critic says "feels cheap", correct it with one of these.

1. **Arrive fast, land soft.** Each frame covers roughly **12 to 19% of the remaining distance** (an exponential ease-out).
   Never constant speed, never a dead stop. `vstudio analyze` reports this as `arrival_k` per move.
2. **Nothing ever freezes.** Holds keep a slow push-in of about **0.25% per frame**, or a tiny drift.
3. **Every move lasts at least 0.3 s**; big moves 0.5 to 0.75 s.
4. **Stagger grouped elements 2 to 4 frames apart.** Three things entering never fire on the same frame.
5. **Blur follows the movement.** Horizontal motion gets horizontal blur, vertical gets vertical; it fades as the object settles.
   Fast moves get real in-between frames blended (`--subframes 6`), never blended across a cut.
6. **Text stays still at least 8 frames before it moves**, and stays fully readable for `characters / 15 + 1.5 s`
   (`vstudio readcheck`).
7. **One focal point per frame.** It is obvious where to look first.
8. **Cuts land on the beat or 2 frames before it; morphs start about 4 frames early.**
9. **Sound lands on the strongest visual moment.** A click on the press frame, a whoosh peaking with the move, an impact
   under the big reveal. Master to about **-14 LUFS**.
10. **Frames are a pure function of time.** No timers, no random values without a seed: any frame can be re-rendered alone.

Checks that enforce these: `vstudio analyze` (dead stops, frozen runs, arrival_k), `vstudio readcheck`, `vstudio compare`
(against a reference), `scripts/video_qa.py` (dead time, black frames, loop, loudness).
