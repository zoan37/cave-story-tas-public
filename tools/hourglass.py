"""Hourglass r77 .wtf <-> our movie format (one input per logic frame), for TASVideos submissions.

nitsuja's 1917M was made in Hourglass r77 and published as nitsuja-cavestory.wtf (in 1917M.zip,
kept at ref/dl/nitsuja/). This tool converts in both directions and checks the conversion.

.wtf layout (Hourglass r77, little endian; every byte of nitsuja's 1024-byte header is accounted for):
    0   4   magic "fTw" + format version 0x02
    4   u32 number of input frames
    8   u32 rerecord count
    12  8   keyboard layout name ("00000411" = Japanese)
    20  u32 fps setting (nitsuja: 51)
    24  u32 initial system time (ms)
    28  u32 executable hash
    32  u32 executable size
    36  48  executable name ("Doukutsu.exe")
    84  16 x u32 desync-detection timer values: the game's clock at input frames 2^0..2^15
    148 u32 Hourglass version (77)
    152 0   zero padding up to 1024
    1024+8n entry n: up to 8 held virtual-key codes, ascending, zero padded

Timing model (verified on the original exe, see WRITEUP.md):
  * Hourglass stores an entry for every frame, including the 4 lag frames that follow each music
    change (the original sleeps 100 ms). The game never reads input on those entries.
  * Our engine numbers frames like a real 50 Hz machine (engine frame = logic frames + lag frames).
    Hourglass's clock ran 100 ms ahead after the first music change, so the opening's 500 ms wait
    ended 5 frames earlier: in real-hardware time the title press needs 5 more frames.
    Hourglass entries + 5 blank entries before the title press == engine frames (real hardware).

Directions:
  to-movie IN.wtf OUT.txt         Hourglass -> ours: insert the 5 title frames, replay with
                                  TAS_MOVIE_HAS_LAG=1, keep the input of every logic frame.
  to-wtf MOVIE.txt OUT.wtf        ours -> Hourglass: replay, put each logic input at its engine
                                  frame, fill the lag entries, drop the 5 title frames.
      --fill next|prev|blank|template   lag-entry contents (the game never reads them). Default
                                  'next' (the input the game reads after the stall, so an emulator
                                  that applied a lag entry's input instead would still see the same
                                  keys). 'template' copies them from --template (exact round trip).
      --template WTF              header fields to keep (default: nitsuja's movie)
      --rerecords N               rerecord count (default: the template's)
  verify WTF [--movie MOVIE.txt]  Hourglass-mode replay of WTF (its entries as stored, lag entries
                                  skipped by the engine): final state, and with --movie a per-frame
                                  trace comparison against the replay of our movie.
  roundtrip                       nitsuja's .wtf -> ours (== movies/baseline-nitsuja-best.txt)
                                  -> .wtf (== his file: header + every input the game reads; and
                                  byte for byte with --fill template).
"""
import argparse
import os
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cstas

ROOT = cstas.ROOT
SIM = os.path.join(ROOT, "out", "sim", "CSE2")
NITSUJA_WTF = os.path.join(ROOT, "ref", "dl", "nitsuja", "nitsuja-cavestory.wtf")
NITSUJA_MOVIE = os.path.join(ROOT, "movies", "baseline-nitsuja-best.txt")

# Cave Story default keys: arrows, Z jump, X shoot, A/S weapon prev/next, Q inventory, W map, Esc
VK = {0x25: "L", 0x27: "R", 0x26: "U", 0x28: "D", 0x5A: "J", 0x58: "S", 0x41: "B", 0x53: "A",
      0x51: "I", 0x57: "M", 0x1B: "E"}
KEY_VK = {k: v for v, k in VK.items()}
TITLE_FRAMES = 5     # real-hardware frames to insert before the title press
HEADER = 1024


# ---------------------------------------------------------------- .wtf file

def read_wtf(path):
    d = open(path, "rb").read()
    h = {
        "magic": d[0:4],
        "frames": struct.unpack_from("<I", d, 4)[0],
        "rerecords": struct.unpack_from("<I", d, 8)[0],
        "keyboard": d[12:20],
        "fps": struct.unpack_from("<I", d, 20)[0],
        "initial_time": struct.unpack_from("<I", d, 24)[0],
        "exe_hash": struct.unpack_from("<I", d, 28)[0],
        "exe_size": struct.unpack_from("<I", d, 32)[0],
        "exe_name": d[36:84],
        "desync": list(struct.unpack_from("<16I", d, 84)),
        "version": struct.unpack_from("<I", d, 148)[0],
    }
    assert h["magic"][:3] == b"fTw", "not a Hourglass movie"
    assert d[152:HEADER] == bytes(HEADER - 152), "unknown header bytes after offset 152"
    entries = [d[i:i + 8] for i in range(HEADER, len(d), 8)]
    assert len(entries) == h["frames"], (len(entries), h["frames"])
    return h, entries


def write_wtf(path, h, entries):
    hdr = bytearray(HEADER)
    hdr[0:4] = h["magic"]
    struct.pack_into("<II", hdr, 4, len(entries), h["rerecords"])
    hdr[12:20] = h["keyboard"]
    struct.pack_into("<IIII", hdr, 20, h["fps"], h["initial_time"], h["exe_hash"], h["exe_size"])
    hdr[36:84] = h["exe_name"]
    struct.pack_into("<16I", hdr, 84, *h["desync"])
    struct.pack_into("<I", hdr, 148, h["version"])
    with open(path, "wb") as f:
        f.write(bytes(hdr))
        f.write(b"".join(entries))


def entry_keys(e):
    keys = "".join(VK[b] for b in e if b)
    return cstas.norm(keys)


def keys_entry(k):
    codes = sorted(KEY_VK[c] for c in k if c != ".")
    assert len(codes) <= 8
    return bytes(codes) + bytes(8 - len(codes))


def title_press(keys):
    """Index of the title-screen press: the first jump/OK input after the very first entry
    (entry 0 holds OK to skip the opening; the title ignores input until its press)."""
    return next(i for i in range(1, len(keys)) if "J" in keys[i])


# ---------------------------------------------------------------- engine

def replay(frames, has_lag=False, extra_env=None):
    """Replay a list of inputs headless. -> (engine frame per trace row, trace rows (str), final state).
    The last trace row is written when the movie runs out (its frame = the engine's end frame)."""
    with tempfile.TemporaryDirectory(prefix="hourglass-") as tmp:
        mv, tr = os.path.join(tmp, "m.txt"), os.path.join(tmp, "t.trace")
        cstas.write_movie(mv, frames)
        env = dict(os.environ, TAS_MOVIE=mv, TAS_TRACE=tr, TAS_HEADLESS="1", TAS_END="quit")
        for k in ("TAS_MOVIE_HAS_LAG", "TAS_HOURGLASS", "TAS_LAG_SEQ", "TAS_SLEEP_LAG", "TAS_TICK_HZ",
                  "TAS_TITLE_EXTRA_MS"):
            env.pop(k, None)
        if has_lag:
            env["TAS_MOVIE_HAS_LAG"] = "1"
        env.update(extra_env or {})
        p = subprocess.run([SIM], cwd=os.path.dirname(SIM), env=env, capture_output=True, text=True)
        rows = open(tr).read().splitlines()
    final = p.stderr.strip().splitlines()[-1] if p.stderr.strip() else ""
    return [int(r.split(" ", 1)[0]) for r in rows], rows, final


def final_fields(final):
    return dict(kv.split("=", 1) for kv in final.split() if "=" in kv)


# ---------------------------------------------------------------- conversions

def wtf_to_movie(entries):
    """Hourglass entries -> (our movie, engine frame of each logic frame, final state)."""
    raw = [entry_keys(e) for e in entries]
    t = title_press(raw)
    r5 = raw[:t] + ["."] * TITLE_FRAMES + raw[t:]
    fr, _, final = replay(r5, has_lag=True)
    logic = [r5[f] for f in fr[:-1]]
    return logic, final


def movie_to_entries(movie, fill="next", template=None):
    """Our movie -> (Hourglass entries, info)."""
    fr, rows, final = replay(movie)
    n = len(movie)
    assert len(fr) == n + 1, (len(fr), n)
    end = fr[-1]                       # engine frames in total (real hardware)
    r5 = [None] * end
    for i in range(n):
        r5[fr[i]] = movie[i]
    # title: the TITLE_FRAMES logic frames before the press exist only on real hardware
    t = title_press(movie)
    T = fr[t]
    assert fr[t - TITLE_FRAMES] == T - TITLE_FRAMES, "title frames must be consecutive logic frames"
    assert all(movie[i] == "." for i in range(t - TITLE_FRAMES, t)), "title frames must be blank"
    lag = [f for f in range(end) if r5[f] is None]
    if fill in ("next", "prev"):
        nxt = None
        for f in range(end - 1, -1, -1):
            if r5[f] is not None:
                nxt = r5[f]
            elif fill == "next":
                r5[f] = nxt if nxt is not None else "."
        prv = "."
        for f in range(end):
            if r5[f] is None:
                r5[f] = prv
            prv = r5[f]
    keys = r5[:T - TITLE_FRAMES] + r5[T:]
    ent = [None if k is None else keys_entry(k) for k in keys]
    if fill == "template":
        assert template is not None
        ent = [e if e is not None else (template[i] if i < len(template) else bytes(8)) for i, e in enumerate(ent)]
    elif fill == "blank":
        ent = [e if e is not None else bytes(8) for e in ent]
    # Hourglass entry index of each lag frame
    lag_h = [f if f < T else f - TITLE_FRAMES for f in lag]
    info = {"logic": n, "engine_end": end, "lag": len(lag), "hourglass": len(ent), "title_press": t,
            "final": final, "lag_entries": lag_h, "engine_frames": fr}
    return ent, info


def desync_values(entries, info, tmpl_h, tmpl_entries):
    """Timer values at input frames 2^k. Up to the first entry the game reads differently from the
    template (lag-entry contents don't count) the value is the template's: same inputs, same clock.
    Past it we use a model of Hourglass's clock in nitsuja's run: initial_time + 20*h + 99 ms, and
    inside a music stall's lag entries ahead by the part of the 100 ms not yet played out. It
    reproduces all 10 of his values from frame 64 on (1..32 are the opening, always copied).
    As far as we know Hourglass only uses them to flag a possible desync on playback (unverified);
    they don't affect the inputs."""
    lagset = set(info["lag_entries"])
    first_diff = next((i for i, (a, b) in enumerate(zip(entries, tmpl_entries)) if a != b and i not in lagset),
                      min(len(entries), len(tmpl_entries)))
    out = []
    for k in range(16):
        h = 1 << k
        if h < first_diff or h <= 32:          # frame 32: real Hourglass r77 gives his 6740 (2026-10-21 playback)
            out.append(tmpl_h["desync"][k])
            continue
        v = tmpl_h["initial_time"] + 20 * h + 99
        # entry h is the j-th (1..4) lag entry after its stall: the clock already holds the whole
        # 100 ms. Fitted to his one in-stall sample (h=512, j=3: +60 ms).
        j = 0
        while h - j >= 0 and (h - j) in lagset:
            j += 1
        if j:
            v += 20 * (6 - j)
        out.append(v)
    return out, first_diff


def build_wtf(movie, out, fill="next", template_path=NITSUJA_WTF, rerecords=None):
    th, tent = read_wtf(template_path)
    ent, info = movie_to_entries(movie, fill, tent)
    h = dict(th)
    h["frames"] = len(ent)
    if rerecords is not None:
        h["rerecords"] = rerecords
    h["desync"], info["first_diff_vs_template"] = desync_values(ent, info, th, tent)
    write_wtf(out, h, ent)
    return info


def verify_wtf(path, movie=None):
    """Hourglass-mode replay of a .wtf. Returns a dict with the final state and, given our movie,
    whether every trace row (frame, flags, stage, x, y, xm, ym, hp, script, key, rng, ...) matches."""
    h, entries = read_wtf(path)
    raw = [entry_keys(e) for e in entries]
    t = title_press(raw)
    r5 = raw[:t] + ["."] * TITLE_FRAMES + raw[t:]
    fr, rows, final = replay(r5, has_lag=True)
    res = {"entries": len(entries), "logic": len(fr) - 1, "engine_end": fr[-1], "final": final}
    ff = final_fields(final)
    res["ending"] = ff.get("stage") == "71" and ff.get("tsevent") == "3608"
    if movie is not None:
        fr2, rows2, final2 = replay(movie)
        res["trace_identical"] = rows == rows2 and final == final2
        if not res["trace_identical"]:
            res["first_trace_diff"] = next((i for i, (a, b) in enumerate(zip(rows, rows2)) if a != b),
                                           min(len(rows), len(rows2)))
    return res


def roundtrip():
    """nitsuja's .wtf -> ours -> .wtf, checked against his file and our baseline."""
    th, tent = read_wtf(NITSUJA_WTF)
    ok = True
    logic, final = wtf_to_movie(tent)
    base = cstas.load_movie(NITSUJA_MOVIE)
    same = logic == base
    ok &= same
    print(f"wtf -> movie: {len(logic)} logic frames, {'==' if same else '!='} {os.path.relpath(NITSUJA_MOVIE, ROOT)}")
    with tempfile.TemporaryDirectory(prefix="hourglass-rt-") as tmp:
        for fill in ("template", "next"):
            out = os.path.join(tmp, f"rt-{fill}.wtf")
            info = build_wtf(logic, out, fill=fill)
            a, b = open(out, "rb").read(), open(NITSUJA_WTF, "rb").read()
            h2, e2 = read_wtf(out)
            hdr_same = a[:HEADER] == b[:HEADER]
            lag = set(info["lag_entries"])
            read_same = len(e2) == len(tent) and all(e2[i] == tent[i] for i in range(len(tent)) if i not in lag)
            lag_diff = sum(1 for i in lag if i < len(tent) and e2[i] != tent[i])
            print(f"movie -> wtf (--fill {fill}): {len(e2)} entries; header {'identical' if hdr_same else 'DIFFERS'}; "
                  f"{len(tent) - len(lag)} input-read entries {'identical' if read_same else 'DIFFER'}; "
                  f"{len(lag)} lag entries, {lag_diff} with other contents; file "
                  f"{'BYTE-IDENTICAL' if a == b else f'differs in {sum(x != y for x, y in zip(a, b))} bytes'}")
            ok &= hdr_same and read_same and (fill != "template" or a == b)
            if fill == "next":
                model, _ = desync_values(tent, info, th, [])
                hit = sum(m == v for m, v in zip(model, th["desync"]))
                print(f"desync-timer model (used only past our first difference from his entries): "
                      f"{hit}/16 of his values reproduced; misses at frames "
                      f"{[1 << k for k in range(16) if model[k] != th['desync'][k]]}")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("to-movie"); p.add_argument("wtf"); p.add_argument("out")
    p = sub.add_parser("to-wtf"); p.add_argument("movie"); p.add_argument("out")
    p.add_argument("--fill", default="next", choices=["next", "prev", "blank", "template"])
    p.add_argument("--template", default=NITSUJA_WTF)
    p.add_argument("--rerecords", type=int)
    p = sub.add_parser("verify"); p.add_argument("wtf"); p.add_argument("--movie")
    sub.add_parser("roundtrip")
    a = ap.parse_args()
    if a.cmd == "to-movie":
        h, ent = read_wtf(a.wtf)
        logic, final = wtf_to_movie(ent)
        cstas.write_movie(a.out, logic, f"converted from {os.path.basename(a.wtf)} by tools/hourglass.py "
                                        f"({len(ent)} Hourglass frames)")
        print(len(logic), "logic frames;", final)
    elif a.cmd == "to-wtf":
        info = build_wtf(cstas.load_movie(a.movie), a.out, a.fill, a.template, a.rerecords)
        print(f"{info['hourglass']} Hourglass frames = {info['logic']} logic - {TITLE_FRAMES} title + "
              f"{info['lag']} lag; real hardware {info['engine_end']}")
    elif a.cmd == "verify":
        res = verify_wtf(a.wtf, cstas.load_movie(a.movie) if a.movie else None)
        for k, v in res.items():
            print(f"{k}: {v}")
        sys.exit(0 if res["ending"] and res.get("trace_identical", True) else 1)
    elif a.cmd == "roundtrip":
        sys.exit(0 if roundtrip() else 1)


if __name__ == "__main__":
    main()
