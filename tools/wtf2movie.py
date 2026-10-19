"""Convert an Hourglass .wtf (Cave Story, default keys) to our movie format.
usage: wtf2movie.py in.wtf out.txt [drop_frames_after_title_press]"""
import sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
import cstas

VK = {0x25: "L", 0x27: "R", 0x26: "U", 0x28: "D", 0x5A: "J", 0x58: "S", 0x41: "B", 0x53: "A", 0x51: "I", 0x57: "M", 0x1B: "E"}

def read_wtf(path):
    d = open(path, "rb").read()
    frames = []
    for i in range(1024, len(d), 8):
        keys = "".join(VK.get(b, "?") for b in d[i:i + 8] if b)
        assert "?" not in keys, d[i:i + 8]
        frames.append(cstas.norm(keys))
    return frames

if __name__ == "__main__":
    frames = read_wtf(sys.argv[1])
    cstas.write_movie(sys.argv[2], frames, f"converted from {sys.argv[1]}")
    print(len(frames), "frames")
