# Cave Story Best Ending TAS in 49:58.66

A tool-assisted speedrun of Cave Story's Best Ending (Japanese freeware `Doukutsu.exe` 1.0.0.6) that finishes in
**149,933 frames = 49:58.660**. That's **582 frames (11.64 s) faster** than nitsuja's TASVideos publication
[1917M](https://tasvideos.org/1917M) (50:10.300). As far as we know, it's the first Best Ending TAS under 50 minutes.

The write-up, with interactive charts, ghost races and videos: **[zoan.space/cave-story](https://zoan.space/cave-story/)** (coming soon).
The long version is in [WRITEUP.md](WRITEUP.md).

**Snapshot:** this is record-522. The search is still running and newer records exist (record-538, 49:58.340, 598
frames under 1917M, as of October 19, 2026). This repo is updated at milestones.

**Status: unofficial.** Every record was checked frame for frame against the original exe running under Wine. It
hasn't been played back in Hourglass itself, and it hasn't been submitted to TASVideos.

## What's here

| path | what |
|---|---|
| [`movies/record-522frames.txt`](movies/) | the run, one input per logic frame (format below) |
| [`WRITEUP.md`](WRITEUP.md) | how it was found: the bit-exact twin, GPU ports, luck engineering, bosses, failed ideas, how close to optimal |
| [`data/records.csv`](data/records.csv) | all 81 records the project banked, in order, with their commit messages |
| [`data/rooms.csv`](data/rooms.csv) | all 148 room visits, nitsuja vs this run, in frames |
| [`tools/`](tools/) | the movie-format library and the Hourglass `.wtf` converter |

This repo is the public window into a private working repo. The working repo also holds the engine patch, the GPU
ports of the game and close to 200 tools. Those are built on code decompiled from the game, so they aren't
published here. More of the original tooling and notes may follow once it has been checked for that.

## Movie format

Plain text, whitespace-separated tokens. `KEYS` is one frame; `KEYS:N` repeats it for N frames. `.` means no keys.
Lines starting with `#` are comments.

    token  key        token  key        token  key
    L R U D  arrows   J      Z (jump)   S      X (shoot)
    A      S          B      A          I      Q (inventory)
    M      W (map)    E      Esc

Keys within a token are written in the order `LRUDJSABIME`. (`A` and `B` are the two weapon-switch keys.) Each entry is one *logic frame*, a frame where the game
reads input. The original sleeps 100 ms on every music change, so the run also has 1,210 lag frames where no input is
read. Hourglass `.wtf` files store those lag frames as entries, and
`tools/hourglass.py` converts between the two formats:

    Hourglass entries = logic frames − 5 (Hourglass clock offset at the title) + 1,210 lag frames
    149,933           = 148,728      − 5                                         + 1,210

## Credits

- **nitsuja**: the 2011 Best Ending TAS (1917M) this run is built on, and Hourglass. About two-thirds of these inputs
  are his, replayed unchanged once the luck lines up at a door.
- **periwinkle**: the 2022 TASVideos WIP whose Graveyard damage boost is the run's single biggest gain (261 frames).
  The first 10,470 frames are his inputs, unchanged.
- **CSE2**, the community decompilation of Cave Story that made a bit-exact, searchable copy of the game possible.
- **zoan** ([@zoan37](https://x.com/zoan37)): the project, its direction and its hardware.
- **Claude** (Anthropic's Claude Opus 5.5 in Claude Code) wrote the tools, ran the searches through dozens of
  parallel agents, verified every record and wrote these docs. **OpenAI Codex** finished the full-world GPU port.

Cave Story is by Daisuke "Pixel" Amaya / Studio Pixel. This repo has no game code or game data.

## License

The code in `tools/` and the documentation written for this repo are MIT licensed (see [LICENSE](LICENSE)). The
movie is a derivative of nitsuja's and periwinkle's published movies. Please credit them.
