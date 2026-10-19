"""Driver for the CSE2 TAS server (engine/src/Tas.cpp).

    g = Game()                 # headless, from power-on
    g.run("J:1 .:40")          # tokens: KEYS or KEYS:N; keys L R U D J S A B I M E, '.' = none
    s = g.save()               # fork savestate; remembers the input log
    g.run("R:30"); print(g.state())
    g.load(s)                  # back, input log restored
    g.write_movie("movies/x.txt")
"""
import os
import subprocess
import struct
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM = os.path.join(ROOT, "out", "sim", "CSE2")


def expand(tokens):
    """'J:2 .' -> ['J', 'J', '.']"""
    out = []
    for tok in tokens.split():
        if ":" in tok:
            k, n = tok.split(":")
            out += [k] * int(n)
        else:
            out.append(tok)
    return out


def compress(frames):
    """['J', 'J', '.'] -> 'J:2 .'"""
    out = []
    i = 0
    while i < len(frames):
        j = i
        while j < len(frames) and frames[j] == frames[i]:
            j += 1
        n = j - i
        out.append(frames[i] if n == 1 else f"{frames[i]}:{n}")
        i = j
    return " ".join(out)


def norm(k):
    order = "LRUDJSABIME"
    s = "".join(c for c in order if c in k)
    return s or "."


def parse_entities(r):
    """'npcs 3:c18,x1,..' -> [{'i': 3, 'c': 18, 'x': 1, ...}] (f, b are hex)"""
    import re
    out = []
    for e in r.split()[1:]:
        idx, rest = e.split(":", 1)
        d = {"i": int(idx)}
        for f in rest.split(","):
            m = re.match(r"([a-z]+)(-?[0-9a-fA-F]*)$", f)
            if not m or not m.group(2) or m.group(2) == "-":
                continue
            try:
                d[m.group(1)] = int(m.group(2), 16 if m.group(1) in ("f", "b") else 10)
            except ValueError:
                pass
        out.append(d)
    return out


def parse_state(r):
    d = {}
    for kv in r.split():
        k, v = kv.split("=", 1)
        if k in ("life", "boost"):
            d[k] = v
        else:
            d[k] = int(v, 0)
    return d


class State:
    def __init__(self, pid, log):
        self.pid = pid
        self.log = list(log)

    @property
    def frame(self):
        return len(self.log)


class Game:
    def __init__(self, movie=None, headless=True, binary=SIM):
        env = dict(os.environ, TAS_SERVER="1", TAS_END="server")
        if headless:
            env["TAS_HEADLESS"] = "1"
        self.log = []
        if movie:
            env["TAS_MOVIE"] = movie
            self.log = load_movie(movie)
        self.p = subprocess.Popen([binary], cwd=os.path.dirname(binary), env=env,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.states = []

    def cmd(self, line):
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()
        r = self.p.stdout.readline().rstrip("\n")
        if r.startswith("error"):
            raise RuntimeError(f"{line!r}: {r}")
        return r

    def run(self, tokens):
        frames = [norm(k) for k in expand(tokens)]
        if not frames:
            return self.frame
        self.log += frames
        r = self.cmd("i " + compress(frames))
        return int(r.split()[1])

    @property
    def frame(self):
        return len(self.log)

    def state(self):
        return parse_state(self.cmd("s"))

    def npcs(self):
        return parse_entities(self.cmd("n"))

    def boss(self):
        return parse_entities(self.cmd("b"))

    def flag(self, n):
        return self.cmd(f"flag {n}").split()[2] == "1"

    def save(self):
        r = self.cmd("save")
        st = State(int(r.split()[1]), self.log)
        self.states.append(st)
        return st

    def load(self, st):
        r = self.cmd(f"load {st.pid}")
        assert r.startswith("loaded"), r
        self.log = list(st.log)
        if int(r.split()[1]) != len(self.log) and not os.environ.get("TAS_MOVIE_HAS_LAG"):
            raise AssertionError((r, len(self.log)))

    def drop(self, st):
        self.cmd(f"drop {st.pid}")
        if st in self.states:
            self.states.remove(st)

    # Memory snapshots: ~100x faster than fork savestates, but only valid in the
    # same game loop they were taken in (the server refuses otherwise).
    def snap(self):
        sid = int(self.cmd("ss").split()[1])
        return State(sid, self.log)

    def restore(self, st):
        self.cmd(f"sl {st.pid}")
        self.log = list(st.log)

    def free(self, st):
        self.cmd(f"sd {st.pid}")

    def batch(self, base, candidates, keep=False):
        """Run each token string from snapshot `base`; return [(state dict, State or None)].
        Leaves the game at the last candidate's end; call restore() afterwards."""
        out = []
        CH = 64
        for i in range(0, len(candidates), CH):
            chunk = candidates[i:i + CH]
            lines = []
            for tokens in chunk:
                frames = [norm(k) for k in expand(tokens)]
                lines.append(f"sl {base.pid}")
                if frames:
                    lines.append("i " + compress(frames))
                lines.append("s")
                if keep:
                    lines.append("ss")
            self.p.stdin.write("\n".join(lines) + "\n")
            self.p.stdin.flush()
            for tokens in chunk:
                frames = [norm(k) for k in expand(tokens)]
                r = self.p.stdout.readline()
                assert r.startswith("loaded"), r
                if frames:
                    r = self.p.stdout.readline()
                    assert r.startswith("ok"), r
                st = parse_state(self.p.stdout.readline())
                sn = None
                if keep:
                    r = self.p.stdout.readline()
                    sn = State(int(r.split()[1]), base.log + frames)
                out.append((st, sn))
        self.log = list(base.log)
        return out

    def shot(self, path):
        """PNG of the current frame (needs headless=False)."""
        ppm = path + ".ppm"
        self.cmd(f"shot {ppm}")
        ppm_to_png(ppm, path)
        os.remove(ppm)

    def write_movie(self, path, header=""):
        write_movie(path, self.log, header)

    def close(self):
        for st in list(self.states):
            try:
                self.cmd(f"drop {st.pid}")
            except Exception:
                pass
        try:
            self.p.stdin.write("q\n")
            self.p.stdin.flush()
        except Exception:
            pass
        self.p.wait()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def load_movie(path):
    frames = []
    for line in open(path):
        line = line.split("#", 1)[0]
        frames += [norm(k) for k in expand(line)]
    return frames


def write_movie(path, frames, header=""):
    with open(path, "w") as f:
        for h in header.splitlines():
            f.write(f"# {h}\n")
        line = []
        for tok in compress(frames).split():
            line.append(tok)
            if len(line) == 16:
                f.write(" ".join(line) + "\n")
                line = []
        if line:
            f.write(" ".join(line) + "\n")


def ppm_to_png(ppm, png, scale=2):
    data = open(ppm, "rb").read()
    parts = data.split(b"\n", 3)
    w, h = map(int, parts[1].split())
    px = parts[3]
    rows = []
    for y in range(h):
        row = px[y * w * 3:(y + 1) * w * 3]
        if scale > 1:
            row = b"".join(row[x * 3:x * 3 + 3] * scale for x in range(w))
        rows += [b"\0" + row] * scale
    raw = b"".join(rows)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)

    with open(png, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w * scale, h * scale, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 6)))
        f.write(chunk(b"IEND", b""))
