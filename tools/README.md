# tools

- `cstas.py`: the movie format (`load_movie`, `write_movie`, `expand`, `compress`) plus the client for the TAS
  engine's server mode (`Game`: run inputs, fork savestates, read state). The server is the patched engine from the
  private working repo, so only the movie-format functions work on their own.
- `wtf2movie.py`: read an Hourglass `.wtf` (Cave Story's default keys) into the movie format, one entry per
  Hourglass frame, lag frames included.
- `hourglass.py`: exact conversion between `.wtf` and the logic-frame format, including the lag-frame and
  title-clock model. It documents the full `.wtf` r77 header layout. `to-movie`, `to-wtf` and `verify` replay the
  movie in the engine to find the lag frames, so they need the engine too.

Example, counting frames:

    python3 -c "import sys; sys.path.insert(0, 'tools'); import cstas; print(len(cstas.load_movie('movies/record-522frames.txt')))"
    # 148728
