# How it works
The run, the twin of the game it was searched in, the searches, and the ideas that didn't work. Frame numbers are 50 fps "logic frames" unless noted.

## The rules of the game
- **Version:** `Doukutsu.exe`, the Japanese freeware release 1.0.0.6, no translation patch. This is the version nitsuja's 1917M uses.
- **Goal:** the Best Ending, as fast as possible. The time is the Hourglass frame count at 50 fps: 149,858 frames = 49:57.160, against 1917M's 150,515 = 50:10.300.
- **Lag you can't avoid:** every music change in the original calls `Sleep(100)`. That's 100 ms with no game frame, 4 lag frames at 50 fps (9 when two changes land in the same frame). The run has 302 of them, 1,210 lag frames in all. The same stalls appear in both runs, and an audit showed every one is required.

## A bit-exact twin of the game
Searching means replaying the game millions of times, so it can't be the original exe. The work engine is **CSE2**, a community decompilation of Cave Story, built as the Japanese version with a TAS patch: headless replay, savestates, per-frame traces and a server mode the search tools drive.

The **ground truth** is the original `Doukutsu.exe` running under Wine. A proxy `dinput.dll` feeds it the movie's inputs and logs a per-frame trace: game flags, stage, position, speed, HP, script state and the RNG seed. A diff tool compares the two traces frame by frame. nitsuja's full movie matches on all 149,311 frames, and every record since has been banked only after it matched on the exe too ("real exe IDENTICAL over 148,654 frames" for the current one).

Getting there meant finding the original's quirks. One: the exe's sound initialisation consumes a `rand()` call, so the harness needs an audio device, even a null one, or the RNG starts one draw off. Another: Hourglass's clock ran 100 ms ahead after the first music change. That's why nitsuja's title-screen press sits 5 entries earlier in his file than on real hardware, which the converter has to reproduce.

## The game on a GPU
- **Quote only.** A CUDA port of the player's movement, map collision, spikes and Machine Gun. It shows 0 mismatches over 1.69 million frames in 15 rooms and runs about **10 billion player-frames per second** on an RTX 4090. Good for pure-movement shortcuts.
- **The whole world.** Enemies, scripts, weapons, drops, room transfers and the RNG, ported for the GPU. Finished by OpenAI's Codex, it replays the entire game with zero frame-hash differences against the CPU engine. It runs about **1.8 million world-frames per second** on a 4090, plus a Metal build for Apple GPUs.

## Shortcuts that keep the world identical
The first 60 frames came from the cautious version of the idea. Cut nitsuja's run into short windows (≤ 240 frames) where no script is running and Quote is in control. Search on the GPU for inputs that reach his exact state at the end of the window sooner. Then keep only variants that leave *everything* the same at the next door. Two hidden counters survive doors and had to be put back:

- **The walk animation counter.** Pressing Left and Right together on a frame where Quote is standing still cancels the movement but still ticks the counter, which is legal on a keyboard.
- **The Machine Gun recharge timer** only runs while the Machine Gun is selected. Switching weapon and back during idle frames pauses it for exactly as long as needed.

The enemy-aware version ("esc") runs an evolution strategy over edited input prefixes in the full GPU world. It scores each candidate at its room exit on frames saved, RNG offset and every word of carried state. Most of the run's small gains came from esc and from re-sweeps of rooms a new record had changed.

## Luck engineering
Cave Story uses one RNG, the C library's `rand()`. Rooms draw from it constantly, so almost any frame saved shifts every later random event. The insight that unlocked most of the run: at a door, the game reloads the room's enemies, so the world is just **Quote + carried state + the RNG seed**. Land on the same seed with good-enough state, and the reference run's inputs replay from there unchanged.

- **Burns** add draws at no time cost. A head bonk spawns two particles: +4. A Machine Gun shot: +1. A splash: +32 to +500. Two frames saved in a room that draws 2 per frame, plus one bonk, comes out exactly even.
- **Negative burns** draw fewer numbers: kill an enemy sooner, don't trigger it, stay out of its activation box, fire one fewer missile. A per-call RNG logger (every `Random()` call with its source) made these findable. One record came from dropping a single Machine Gun shot.
- **Good sets.** For each door, the luck planner tabulates which RNG offsets still replay the rest of the game correctly, not only offset 0. Some doors have a dozen.
- **Convergence.** Some differences, like a few points of weapon EXP, wash out a few rooms later, for example when a pickup would have capped anyway. A checker replays the candidate to the ending and accepts it if the end state is identical.
- **Transplants.** A near miss from one search can be moved onto a newer record's line and closed there with burns.
- **Spending the luck in the next room.** A faster exit that lands on the wrong seed usually ruins the next room, unless the next room is re-solved for the new seed. Records 592 and 597 took Balfrog's room exit 4 and then 2 frames faster this way, each with a Grasstown re-solve that absorbed the whole RNG difference. The lesson: try the biggest gains and offsets, not only the nearest misses.
- **Keeping near misses.** esc used to drop any exit that wasn't byte-identical in carried state. Some differ only in booster fuel, a hidden animation counter or a few points of weapon EXP that heal on their own. Keeping those (`--keep-other`, `--keep-arms`) and replaying each to the ending gave four records in the last two days.

## The periwinkle splice
periwinkle's 2022 WIP takes a Pignon hit in the Graveyard and rides the knockback up the shaft, 261 frames faster than nitsuja. Attaching it to the rest of the game was the hardest problem in the project. Under the new line's luck (532 draws ahead after the Graveyard), the Grasstown kills leave the Missile Launcher at level 2, and a level-2 Balfrog fight costs about 700 frames. A level-3 launcher from extra EXP orbs costs about 845.

The fix wasn't to fight the luck but to re-synchronise it. A GPU luck search re-solved Grasstown up to Santa's house. A health-refill detour there was tuned so that the RNG at the next Weed room door equalled the reference's exactly, and from there the reference's inputs ran to the end: record-217, a 217-frame jump in one commit. Later, a search found a line that picks up one more heart on the way and skips the refill: record-357, +53.

## Bosses
Boss fights are about 8,000 of the run's frames. Hitboxes, invulnerability windows, damage caps and phase timers make them search problems of their own:

- **Kill windows.** Many bosses take damage only in windows that close after a damage cap or a timer. Closing a window one tick sooner can save the rest of the fight. Balfrog's first window now closes at tick 2, and the fight ends 25 frames sooner than it did in record-497, a few hours earlier.
- **Ballos**, the final boss, had phases 3–4 solved from scratch and its final window re-solved several times: about 28 frames in total.
- **pes**, a positional evolution strategy that searches Quote's position, movement and weapon choice per frame and grades each line on the boss's death script, found gains in the Undead Core, Toroko+, Ballos and Balfrog that older window tools missed.
- **Lower bounds.** Each fight got a damage-per-frame bound, read from the source, so the searches knew where slack could exist and where it provably couldn't.

## The Core air timer
After the Core boss, Quote drowns as part of the story, exactly 1,000 frames after his last dive plus 972 frames of frozen script. Diving earlier ends the room earlier, if the boss is dead in time. The water level is an oscillator that never looks at Quote: it accelerates 4/512 px per frame² toward its rest line, giving a ±16 px swing with a 256-frame period. Modelled exactly, it decides where Quote has to stand to stay underwater on each frame. Two constraints shaped the solution. The fight's missile drops must leave at least 8 missiles, or the late game, as far ahead as the Undead Core, plays out differently. And the boss's damage windows each close after 200 damage. The two tide lines banked 24 frames (the sub-50 record) and 16 more.

## Keeping the machine running
- **The gap map.** Every one of the 148 room visits gets its length, its best lower bound, the gap between them, what blocks the gap, and what has been tried. A **tool selector** picks which search to run where, and a **gap loop** re-sweeps every room the newest record changed. Each new line is a fresh starting point, so records beget records: one Outer Wall room improved four times in a row.
- **Shadow prices.** What is one HP, one missile or one point of EXP worth over the whole run? Mining 9,249 archived window searches showed the run isn't resource-bound at window scale. Only about 35 frames were blocked purely by a resource, and each of those had no cheap supply.
- **Banking protocol.** Every record is a new file, never an overwrite. It's stacked on the newest master, replayed to the ending in the twin, checked for every story flag and item, matched frame by frame on the original exe, and diffed room by room against the previous record. The last check was added after a record built on a stale base quietly reverted 2 frames in Grasstown.
- **Hardware.** A desktop RTX 4090, an NVIDIA DGX Spark, an Apple M5 Max, a mini PC running the original exe under Wine for verification, and rented cloud GPUs (about 1,045 GPU-hours on 185 machines across Runpod and Vast.ai, mostly RTX 5090s and 4090s, up to about 25 at once). Dozens of AI agents coordinated through shared docs and a lock file on the verification machine.
- **Faster search.** On the last two days, moving the mutation step onto the GPU, refilling idle GPU lanes and running six windows at once made each GPU about 8 times faster. Fresh random seeds turned out to beat bigger search budgets per window.

## What didn't work
Most of the project was ideas that didn't pan out. Each one is written up in the repo with its numbers:

- **Route-level skips.** Sequence breaks, trigger skips, wall clips, a developer warp in Hell, story-graph analysis. The warp would save about 2,000 frames, but it needs a one-frame horizontal displacement of 8+ px into a sealed stem, and nothing in the game provides one. Skip flags are the only progress that survives death, Continue and reset, and presetting all 14 would save 2,114 frames. But each is set only by the event it shortens (the one exception costs more to get than it saves), which gives a short proof that dying or resetting can never save time on this route.
- **Misery's uncapped phase.** If Quote is far from Misery when she lands from a teleport, she enters a 73-frame phase with no damage cap. Forcing it saves 161 frames in the room, but it spends Super Missiles the run needs for two later bosses, and there's nowhere to re-buy them.
- **Nitsuja's "through the wall" Super Missile bug in Hell.** It works on the real exe and moves a timer 207 frames earlier, but it needs Super Missile EXP that costs more frames to earn than it saves.
- **Monster X** paired explosions: geometrically impossible.
- **Learned and tree search.** A value network trained on 9.2 million game states predicts frames-to-go within 2.2 frames on rooms it never saw. Monte Carlo tree search matched the GPU evolution strategy on movement. Neither beat the simpler searches overall. The deciding factor is almost always the RNG at the door, which neither optimises directly.

## How close to optimal?
- **Proofs.** An exact GPU breadth-first search, with a sound pruning bound, proves that 153 short segments of nitsuja's run (1,576 frames) can't be beaten at all. With one extra assumption about pushing into corners, the proof covers 280 segments (3,021 frames). A follow-up proves push bounds per room with the SMT solver Bitwuzla, so bounds like this need no assumption.
- **Bounds.** Splitting the run's time: about 69,700 frames of scripts, cutscenes and music lag (fixed by the story), about 16,200 frames of boss rooms, death scripts included (maybe 0 to 30 more, almost all behind the missile budget) and about 64,000 frames of everything else (maybe 20 to 80 more, a frame or two at a time). That puts this route's floor around **49:55 to 49:57**. A 45-minute Best Ending would need about 15,000 frames, and no mechanism found comes close.
- **Big boss leads, re-measured at the end, all blocked:** an Omega kill 11 frames faster leaves Quote about 100 px further from the exit (costing ~51 frames on the walk out), a Muscle Doctor kill 9 to 22 faster puts the RNG 27,272 draws behind at the next door, and a faster Ironhead costs a Super Missile the Undead Core needs.

## Lessons, briefly
- A frame isn't saved until the door matches.
- Verify on the original. The twin has been right every time, but only because every record was checked against the exe.
- Every new record changes the starting point for searches, so re-sweep the rooms it changed.
- The biggest gain came from a human idea (periwinkle's damage boost). The machines' job was making it fit.

## Paused, not finished
The search was paused on October 21, 2026 at record-597, while records were still arriving about once an hour. The best open leads at the pause: a sweep of near-miss exits across the whole run (about two-thirds done), each to be followed by a re-solve of the next room; a +1 exit into Santa's House at RNG −17 that was never run; and the Sand Zone doors, whose set of accepted RNG offsets grew with almost every Sand Zone record and whose newest members were never searched. If you want to carry it further, nitsuja's inputs still cover 60% of the run.
