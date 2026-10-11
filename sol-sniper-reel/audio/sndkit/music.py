"""The score: 125 BPM, F minor, arranged to picture from timing.json's music markers.

Beat b sits at t = b * 0.48 s = b * 23040 samples (exact), so every musical
event lands on the beat grid sample-accurately.

Form (beats):
  0-3     intro     impact (SFX) + dark Fm9 pad swell, reverse swell into the cut at b3
  3-8     groove_a  low-passed kick on quarters, sub pulses, filtered 16th pluck arp, offbeat hats (Fm9)
  8-11    groove_b  + 8th hats, arp filter opens (Dbmaj7); its clap on 2 gives way to the UI blip there
  11-12.5 build     snare roll 8ths -> 16ths, arp/pad filter sweep up, bus crescendo (Eb)
  12.5-13 gap       pre-drop gap (only tails; the SFX riser / reverse swell fill it, ~4 LU under the build)
  13-20   drop      kick 4/4, clap 2 & 4, open hats, sidechained rolling bass, chord stabs; the bus
                    peaks (+1.5 dB) on the downbeat. Fm9 (3 beats) -> Db (2) -> Eb (2)
  20-25   montage   drop + 16th hats + shaker; claps next to the cut hits are lighter (the hits carry
                    the body). Fm9 (2) -> Db (1) -> Eb (1) -> Cm7 (1) (harmonic rhythm follows the cuts)
  25-26   break     everything cuts on a stab throw (delay + reverb tail)
  26-     outro     Dbmaj9 -> Abmaj9 (at the CTA reveal) in open voicings: warm keys + wide pad + sub,
                    the Ab pad's filter opens and a soft top line blooms (resolve bright). The Ab chord
                    (pad, sub, keys, top line) is held THROUGH the end of the reel: it stays present
                    to ~14.85 s and the master's 150 ms end fade takes it to digital silence at 15.000

Sidechain depth follows kick velocity. Arrangement rules that keep the frame-snapped SFX cues
(up to 13 ms off the grid) clear of flams are in build_music().
"""
import numpy as np

from . import instruments as I
from .dsp import (SR, add_at, convolve_ir, duck_env, eq, fades, lp, midi_hz, ns, pan, pingpong, rng,
                  taxis)

BEAT = 0.48
BEAT_N = 23040  # samples per beat at 48 kHz (exact)


def bs(b):
    """Beat -> sample index (exact for 1/32-beat multiples)."""
    return int(round(b * BEAT_N))


CHORDS = {
    #          bass root   pad voicing               arp tones                 stab voicing (no shared Eb4)
    'Fm9':    dict(root=41, pad=[53, 56, 60, 63, 67], arp=[65, 68, 72, 75, 79], stab=[60, 67, 68, 72]),
    'Db':     dict(root=37, pad=[49, 53, 56, 60, 65], arp=[65, 68, 72, 75, 77], stab=[60, 65, 68, 72]),
    'Eb':     dict(root=39, pad=[51, 55, 58, 63, 65], arp=[65, 67, 70, 75, 79], stab=[58, 63, 67, 70]),
    'Cm7':    dict(root=36, pad=[48, 55, 58, 63, 67], arp=[67, 70, 72, 75, 79], stab=[58, 63, 67, 70]),
    # outro: open voicings spread over three octaves (no stack of four tones in 200-400 Hz)
    'Dbmaj9': dict(root=37, pad=[49, 56, 65, 72, 75, 80], keys=[49, 56, 65, 72, 75, 80]),
    'Abmaj9': dict(root=32, pad=[51, 56, 67, 70, 72, 75], keys=[44, 51, 56, 67, 70, 72, 75]),
}

HARMONY = [(0, 'Fm9'), (8, 'Db'), (11, 'Eb'), (13, 'Fm9'), (16, 'Db'), (18, 'Eb'),
           (20, 'Fm9'), (22, 'Db'), (23, 'Eb'), (24, 'Cm7'), (26, 'Dbmaj9'), (28, 'Abmaj9')]


def chord_at(b):
    name = HARMONY[0][1]
    for s, c in HARMONY:
        if b + 1e-9 >= s:
            name = c
    return name


def chord_at_time(t):
    return chord_at(t / BEAT)


ARP_PATTERN = [0, 2, 1, 3, 2, 4, 3, 1]
ARP_VEL = [1.0, 0.62, 0.78, 0.6, 0.92, 0.6, 0.76, 0.62]


def hum(*key, lo=0.88, hi=1.0):
    """Deterministic velocity humanisation."""
    return float(rng('hum', *key).uniform(lo, hi))


UI_CUES = ('click', 'click_final', 'tap_soft', 'tick', 'ui_blip', 'success', 'toast')
POINTER_CUES = ('click', 'click_final', 'tap_soft', 'ui_blip')  # sharp pointer/UI transients a clap would flam with
HIT_CUES = ('hit_cut', 'punch', 'impact_big', 'impact_drop', 'impact_outro')


def build_music(n_total, ir_hall, ir_room, cues=()):
    """Render every track. `cues` lets the arrangement leave room for the sound design, the way
    a composer scoring to picture would. Cues are frame-snapped (up to 13 ms off the beat grid),
    so: no hats/stabs right on top of a UI sound or 1-20 ms away from a cut hit; no clap 20 ms
    around a pointer sound; a clap next to a cut hit is kept lighter (the hit's snap is thinned in
    sfx.hit_cut, so the on-grid clap carries the timing and the hit carries the body).

    Returns (tracks, kick_trig, events); events = {'kick': [(sample, vel)], 'clap': [sample]}."""
    ui_t = np.array([c['t'] for c in cues if c['type'] in UI_CUES])
    ptr_t = np.array([c['t'] for c in cues if c['type'] in POINTER_CUES])
    hit_t = np.array([c['t'] for c in cues if c['type'] in HIT_CUES])

    def clear(b, times, before, after):
        if len(times) == 0:
            return True
        t = b * BEAT
        return not np.any((t >= times - before) & (t <= times + after))

    def flam(b, times, lo=0.001, hi=0.02):
        """A cue 1-20 ms off this grid position (coincident cues reinforce, they don't flam)."""
        if len(times) == 0:
            return False
        dt = np.abs(b * BEAT - times)
        return bool(np.any((dt >= lo) & (dt <= hi)))

    T = {k: np.zeros((2, n_total)) for k in
         ('kick', 'bass', 'clap', 'snare', 'hats', 'perc', 'arp', 'pad', 'stab', 'keys', 'air', 'fx', 'crash')}
    sends = {k: np.zeros((2, n_total)) for k in ('hall', 'room', 'arp_dly', 'stab_dly', 'throw')}
    kick_trig = []
    clap_trig = []

    # ------------------------------------------------------------------ drums
    def put_kick(b, vel, soft):
        s = bs(b)
        add_at(T['kick'], I.kick(vel, soft, seed=int(b * 4)), s)
        kick_trig.append((s, vel))

    for b in range(3, 8):
        put_kick(b, 0.56, True)
    for b in range(8, 11):
        put_kick(b, 0.72, False)
    for b in (11, 12):
        put_kick(b, 0.8, False)
    for b in range(13, 25):
        put_kick(b, 0.88, False)

    def put_hat(b, vel, open_=False, p=0.18):
        if not clear(b, ui_t, 0.04, 0.03) or flam(b, hit_t):
            return
        add_at(T['hats'], pan(I.hat(vel * hum('h', b), open_, seed=int(b * 16)), p), bs(b))

    for b in range(3, 8):
        put_hat(b + 0.5, 0.36)
    for b in range(8, 11):
        put_hat(b, 0.22)
        put_hat(b + 0.5, 0.42)
    for i, b in enumerate(np.arange(11, 12.5, 0.25)):
        put_hat(b, 0.18 + 0.05 * i)
    for b in range(13, 20):
        put_hat(b + 0.25, 0.20, p=0.25)
        put_hat(b + 0.5, 0.46, open_=True, p=0.1)
        put_hat(b + 0.75, 0.16, p=0.25)
    for b in range(20, 25):
        for k, v in enumerate((0.26, 0.18, 0.0, 0.2)):
            if v:
                put_hat(b + k * 0.25, v, p=0.25)
        put_hat(b + 0.5, 0.46, open_=True, p=0.1)
    # open hats are choked by the next closed hat (natural hi-hat behaviour): handled by their own
    # 120-200 ms envelope, short enough at this tempo.

    def put_clap(b, vel):
        if not clear(b, ptr_t, 0.02, 0.02):
            return
        if flam(b, hit_t):
            vel = min(vel, 0.55)
        x = I.clap(vel, seed=int(b * 8))
        add_at(T['clap'], x, bs(b))
        clap_trig.append(bs(b))

    put_clap(9, 0.50)
    for b in (14, 16, 18, 21, 23):
        put_clap(b, 0.92)

    for b, v, br in ((11, 0.32, 0.6), (11.5, 0.42, 0.7), (11.75, 0.48, 0.8), (12, 0.6, 0.9), (12.25, 0.74, 1.0)):
        add_at(T['snare'], I.snare(v, seed=int(b * 8), bright=br), bs(b))

    for b in np.arange(20, 25, 0.25):
        v = (0.22, 0.38, 0.26, 0.42)[int(round((b % 1) * 4))]
        add_at(T['perc'], pan(I.shaker(v * hum('sh', b), seed=int(b * 16)), 0.4), bs(b))

    add_at(T['crash'], I.crash(0.30, seed=13), bs(13))
    add_at(T['crash'], I.crash(0.22, seed=20), bs(20))

    # ------------------------------------------------------------------ bass
    def put_bass(b, midi, dur_beats, vel, mid=0.42, release=0.012, cutoff=380.0, drive=1.2):
        x = I.bass_note(midi, dur_beats * BEAT, vel, mid=mid, release=release, cutoff=cutoff, drive=drive)
        add_at(T['bass'], x, bs(b))

    for b in range(3, 8):  # groove_a: sub pulses on the offbeats (F1, an octave under the drop bass)
        put_bass(b + 0.5, 29, 0.36, 0.62, mid=0.34)
    for b in range(8, 11):
        put_bass(b + 0.5, 37, 0.36, 0.85, mid=0.36)
        put_bass(b + 0.75, 37, 0.2, 0.5, mid=0.36)
    put_bass(11.5, 39, 0.4, 0.85)
    put_bass(12.0 + 0.25, 39, 0.2, 0.8)
    for b in range(13, 25):
        root = CHORDS[chord_at(b)]['root']
        for k, (o, v) in enumerate(((0, 0.82), (12, 0.95), (0, 0.78))):
            put_bass(b + 0.25 * (k + 1), root + o, 0.23, v * hum('bs', b, k, lo=0.94), mid=0.6,
                     cutoff=650.0, drive=1.8)  # rolling bass: brighter + driven so it reads on phones
    # outro: sustained sub, Db -> Ab
    # (the outro impact's sub drop lands on Db1, so the Db2 bass swells in under it instead of beating against it)
    add_at(T['bass'], I.bass_note(37, 0.96 + 0.4, 0.62, mid=0.18, attack=0.35, release=0.25, decay=3.0), bs(26))
    # the Ab sub holds to the end of the reel (note-off 14.94 s; the master end fade closes it)
    add_at(T['bass'], I.bass_note(32, 1.5, 0.62, mid=0.16, attack=0.05, release=0.3, decay=2.6), bs(28))

    # ------------------------------------------------------------------ arp
    def arp_section(b0, b1, cut0, cut1, vel0, vel1, decay=0.15):
        steps = int(round((b1 - b0) * 4))
        for i in range(steps):
            b = b0 + i * 0.25
            u = i / max(steps - 1, 1)
            ch = CHORDS[chord_at(b)]['arp']
            m = ch[ARP_PATTERN[i % 8]]
            v = (vel0 + (vel1 - vel0) * u) * ARP_VEL[i % 8]
            if not clear(b, ui_t, 0.03, 0.03):
                v *= 0.45
            cut = cut0 * (cut1 / cut0) ** u
            x = I.pluck(m, v, cut_peak=cut, cut_base=min(320.0, cut * 0.4), decay=decay, seed=int(b * 4))
            add_at(T['arp'], pan(x, 0.22 if i % 2 else -0.22), bs(b))

    arp_section(3, 8, 900.0, 1600.0, 0.78, 0.82)
    arp_section(8, 11, 1800.0, 3200.0, 0.66, 0.7)
    arp_section(11, 12.5, 3400.0, 7500.0, 0.7, 0.92, decay=0.13)
    arp_section(13, 20, 2800.0, 3200.0, 0.5, 0.5, decay=0.12)
    arp_section(20, 25, 3200.0, 4000.0, 0.5, 0.54, decay=0.12)

    # ------------------------------------------------------------------ pads
    def put_pad(b0, b1, notes, level, attack, release, cutoff, seed, hp_f=170.0, post=None, stages=2):
        dur = (b1 - b0) * BEAT
        n = ns(dur + release)
        if callable(cutoff):
            cutoff = cutoff(taxis(n))
        x = I.pad(notes, dur, attack, release, cutoff, seed=seed, hp_f=hp_f, stages=stages)
        if post is not None:
            x = post(x)
        add_at(T['pad'], x * level, bs(b0))

    put_pad(0, 3, [41, 48, 53, 56, 60, 63], 0.78, 0.55, 0.35,
            lambda t: 380.0 * (1500.0 / 380.0) ** np.clip(t / 1.44, 0, 1), seed=1, hp_f=70.0)
    put_pad(3, 8, CHORDS['Fm9']['pad'], 0.40, 0.12, 0.25, 1500.0, seed=2)
    put_pad(8, 11, CHORDS['Db']['pad'], 0.44, 0.1, 0.25, 2000.0, seed=3)
    put_pad(11, 12.5, CHORDS['Eb']['pad'], 0.5, 0.08, 0.04,
            lambda t: 1800.0 * (7500.0 / 1800.0) ** np.clip(t / 0.72, 0, 1), seed=4)
    for b0, b1 in ((13, 16), (16, 18), (18, 20), (20, 22), (22, 23), (23, 24), (24, 25)):
        rel = 0.2 if b1 < 25 else 0.05
        put_pad(b0, b1, CHORDS[chord_at(b0)]['pad'], 0.46, 0.03, rel, 3800.0, seed=int(b0))
    # outro: wide warm sustained chords in open voicings; the Ab chord's filter OPENS on the CTA
    # reveal (resolve bright), low mids trimmed so the chord doesn't box up under the end card
    outro_eq = lambda x: eq(x, 'peak', 300.0, 1.0, -3.0)
    put_pad(26, 28.1, CHORDS['Dbmaj9']['pad'], 0.55, 0.06, 0.45, 3000.0, seed=26, hp_f=110.0, post=outro_eq)
    # the last chord is held past the end of the reel (no release inside the picture): it stays
    # present to the final frame and the master's 150 ms end fade closes it at 15.000 s
    put_pad(28, 31.6, CHORDS['Abmaj9']['pad'], 0.58, 0.2, 0.3,
            lambda t: 2600.0 * (5200.0 / 2600.0) ** np.clip(t / 1.2, 0, 1), seed=28, hp_f=110.0, post=outro_eq,
            stages=1)
    # soft top line: upper chord tones two octaves up + a breath of air, blooming on the CTA reveal
    add_at(T['air'], I.shimmer([84, 87, 92], 0.96, attack=0.5, release=0.4, seed=26, air=0.25), bs(26))
    add_at(T['air'], I.shimmer([87, 91, 94, 96], 1.4, attack=0.35, release=0.6, seed=28, air=0.8), bs(28))

    # ------------------------------------------------------------------ stabs
    for b in range(13, 25):
        for o in (0.5,):
            if not clear(b + o, ui_t, 0.06, 0.04) or flam(b + o, hit_t):
                continue
            v = 0.62 * hum('st', b, lo=0.92)
            add_at(T['stab'], I.stab(CHORDS[chord_at(b + o)]['stab'], v, seed=int(b * 4)), bs(b + o))
        if b in (15, 17, 19, 21, 22, 23, 24) and clear(b + 0.75, ui_t, 0.06, 0.04) and not flam(b + 0.75, hit_t):
            nxt = CHORDS[chord_at(b + 1)]['stab']
            add_at(T['stab'], I.stab(nxt, 0.42, seed=int(b * 4) + 1, decay=0.07), bs(b + 0.75))
    # break: stab throw on the stop (delay + reverb carry the break)
    throw = I.stab(CHORDS['Cm7']['stab'], 0.5, seed=250, decay=0.12, cut_peak=4200.0)
    add_at(T['stab'], throw, bs(25))
    add_at(sends['throw'], throw, bs(25))

    # ------------------------------------------------------------------ keys (outro)
    def keys_post(x):
        return eq(eq(x, 'peak', 300.0, 1.0, -3.0), 'highshelf', 6000.0, 0.7, 2.0)

    add_at(T['keys'], keys_post(I.keys(CHORDS['Dbmaj9']['keys'], 1.2, 0.55, seed=26, lp_f=6500.0, hp_f=90.0)), bs(26))
    add_at(T['keys'], keys_post(I.keys(CHORDS['Abmaj9']['keys'], 1.9, 0.55, seed=28, lp_f=7500.0, hp_f=90.0)), bs(28))

    # ------------------------------------------------------------------ reverse swell into groove_a
    src_n = ns(0.3)
    t = taxis(src_n)
    src = np.zeros(src_n)
    for m in CHORDS['Fm9']['arp']:
        src += I.saw(float(midi_hz(m)), src_n, 0.5) * np.exp(-t / 0.07)
    src = lp(src, 2400.0, 2)
    buf = np.zeros(ir_hall.shape[1] + src_n)
    buf[:src_n] = src
    rev = convolve_ir(buf, ir_hall)[:, ::-1]
    seg_n = ns(1.0)
    seg = rev[:, -seg_n:]
    seg /= np.max(np.abs(seg)) + 1e-12
    seg *= (np.linspace(0, 1, seg_n) ** 1.5)[None, :]
    seg = fades(seg, 0.05, 0.004)
    # it is an FX tail, not a beat onset: it ends ON the frame-snapped cut at the start of groove_a
    # (6.7 ms before the downbeat) so its loudest part doesn't trail the hit
    end = bs(3)
    near = [ns(c['t']) for c in cues if c['type'] in ('hit_cut', 'whoosh_rise') and abs(ns(c['t']) - end) <= ns(0.02)]
    if near:
        end = min(near)
    add_at(T['fx'], seg * 0.75, end - seg_n)

    # ------------------------------------------------------------------ mix the music bus
    n = n_total
    kicks = sorted(kick_trig)
    kick_trig = [s for s, _ in kicks]
    kv = np.array([v / 0.88 for _, v in kicks])  # sidechain depth follows kick velocity (soft groove_a kicks pump less)
    sc_bass = duck_env(n, kick_trig, np.minimum(0.88 * kv, 0.88), release=0.11)
    sc_pad = duck_env(n, kick_trig, 0.55 * kv, release=0.17)
    sc_stab = duck_env(n, kick_trig, 0.35 * kv, release=0.10)
    sc_arp = duck_env(n, kick_trig, 0.28 * kv, release=0.12)
    sc_fx = duck_env(n, kick_trig, 0.35 * kv, release=0.16)

    L = dict(kick=1.0, bass=0.65, clap=1.55, snare=0.9, hats=1.0, perc=0.7, arp=0.85, pad=0.62,
             stab=1.6, keys=0.6, air=0.12, fx=1.0, crash=0.5)
    T['bass'] *= sc_bass
    T['pad'] *= sc_pad
    T['stab'] *= sc_stab
    T['arp'] *= sc_arp

    sends['hall'] += T['pad'] * 0.22 * L['pad'] + T['arp'] * 0.32 * L['arp'] + T['stab'] * 0.30 * L['stab'] \
        + T['keys'] * 0.40 * L['keys'] + T['air'] * 0.5 * L['air'] + T['clap'] * 0.16 * L['clap'] \
        + T['snare'] * 0.18 * L['snare'] \
        + T['crash'] * 0.12 * L['crash']
    sends['room'] += T['clap'] * 0.32 * L['clap'] + T['snare'] * 0.28 * L['snare'] \
        + T['hats'] * 0.08 * L['hats'] + T['perc'] * 0.12 * L['perc']

    arp_mono = 0.5 * (T['arp'][0] + T['arp'][1]) * L['arp']
    stab_mono = 0.5 * (T['stab'][0] + T['stab'][1]) * L['stab']
    dly = pingpong(arp_mono, 0.36, fb=0.42, reps=5, lp_f=3800.0) * 0.55
    dly += pingpong(stab_mono, 0.36, fb=0.32, reps=3, lp_f=3200.0, first='R') * 0.30
    dly *= sc_fx
    throw_mono = 0.5 * (sends['throw'][0] + sends['throw'][1]) * L['stab']
    dly += pingpong(throw_mono, 0.24, fb=0.45, reps=3, lp_f=3200.0, first='L', cross=0.3) * 0.6

    hall = convolve_ir(0.5 * (sends['hall'][0] + sends['hall'][1]) + 0.0, ir_hall)
    hall += convolve_ir(throw_mono * 0.3, ir_hall)
    hall *= sc_fx
    room = convolve_ir(0.5 * (sends['room'][0] + sends['room'][1]), ir_room)

    # fader ride (smooth bus automation): build crescendo, the drop downbeat is the peak (+1.5 dB,
    # settling over its first two bars), the montage sits just above unity
    tt = np.arange(n) / SR
    ride_db = np.interp(tt, [0, 3.84, 5.28, 5.99, 6.24, 7.2, 9.5, 9.62, 12.0, 12.1],
                        [0, -0.3, -1.0, 0.6, 1.5, 0.8, 0.0, 0.3, 0.3, 0.0])
    ride = 10.0 ** (ride_db / 20.0)

    tracks = {k: T[k] * L[k] * ride for k in T}
    # music bus presence EQ (synths/claps/hats get a little 3-5 kHz air for small speakers)
    for k in ('pad', 'stab', 'arp', 'clap', 'keys'):
        tracks[k] = eq(tracks[k], 'peak', 3800.0, 0.8, 2.5)
    # tame the recurring common tones (Eb4 in most pad voicings, Eb5 in every arp chord)
    tracks['pad'] = eq(tracks['pad'], 'peak', 311.0, 4.0, -3.0)
    tracks['arp'] = eq(tracks['arp'], 'peak', 622.0, 4.0, -3.0)
    tracks['delay'] = dly * ride
    tracks['hall'] = hall * 0.85 * ride
    tracks['room'] = room * 0.6 * ride
    return tracks, kick_trig, dict(kick=kicks, clap=sorted(clap_trig))
