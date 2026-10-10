"""Small synthesis / mixing toolkit used by audio/build_audio.py.

Everything is plain numpy + scipy and fully deterministic: every random
source is seeded from a stable string (zlib.crc32), never from Python's
salted hash() or the clock.
"""
