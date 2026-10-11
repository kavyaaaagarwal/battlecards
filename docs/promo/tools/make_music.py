"""Synthesize a subtle score for the film, cued to the same moments the visuals hit.

Act 1 (problem): a low D-minor drone, a soft heartbeat and a sparse tick - tension.
Reveal: a riser into a soft impact; the harmony opens to F - C - Dm - Bb, with a plucked arpeggio.
Research: the arpeggio doubles to 16ths. "Current": a soft kick and off-beat hats arrive.
Re-orders get a quiet whoosh. "Battlecards." lands on an impact and a sustained F major that rings out.
The music is ducked under the voice so it never competes with it."""
import json, sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

OUT = sys.argv[1]
SR = 48000
meta = json.load(open(f"{OUT}/anchors.json"))
A = meta["anchors"]
DUR = meta["duration"]
N = int(DUR * SR)
rng = np.random.default_rng(7)

da = np.array([[0.0, 0.0]] + [[a["design"], a["audio"]] for a in A] + [[57.0, DUR]])
def at(design):  # design time -> audio time
    return float(np.interp(design, da[:, 0], da[:, 1]))

R, RES, CUR, TAIL, PROOF, END = at(12.95), at(16.1), at(22.6), at(32.05), at(43.6), at(52.2)
BEAT = 60 / 96
BAR = BEAT * 4

L = np.zeros(N); Rt = np.zeros(N)
def add(sig, start, gl=1.0, gr=1.0):
    i = int(start * SR)
    if i >= N: return
    sig = sig[: N - i]
    L[i:i + len(sig)] += sig * gl; Rt[i:i + len(sig)] += sig * gr

def lp(x, f, o=2): return sosfilt(butter(o, f, "low", fs=SR, output="sos"), x)
def hp(x, f, o=2): return sosfilt(butter(o, f, "high", fs=SR, output="sos"), x)
def mf(m): return 440 * 2 ** ((m - 69) / 12)
def tt(d): return np.arange(int(d * SR)) / SR
def env_ar(n, a, r):
    e = np.ones(n); na, nr = int(a * SR), int(r * SR)
    if na: e[:na] = np.linspace(0, 1, na)
    if nr: e[-nr:] *= np.linspace(1, 0, nr)
    return e

def saw(f, d, det=0.0):
    ph = (tt(d) * f * 2 ** (det / 1200)) % 1
    return 2 * ph - 1

def pad(notes, start, d, vol=0.05, cut=900, a=1.6, r=1.8):
    for m in notes:
        f = mf(m)
        l = sum(saw(f, d, c) for c in (-8, 3)); rr = sum(saw(f, d, c) for c in (-3, 8))
        e = env_ar(len(l), a, r)
        add(lp(l, cut) * e * vol, start, 1, 0); add(lp(rr, cut) * e * vol, start, 0, 1)

def pluck(m, start, vol=0.10, pan=0.0, tau=0.28):
    t = tt(1.2); f = mf(m)
    s = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.12 * np.sin(6 * np.pi * f * t)
    s *= np.exp(-t / tau) * np.minimum(1, t / 0.004)
    s = lp(s, 3200) * vol
    add(s, start, 1 - max(0, pan), 1 + min(0, pan))

def sub(m, start, d, vol=0.16):
    t = tt(d); s = np.sin(2 * np.pi * mf(m) * t) * env_ar(len(t), 0.01, min(0.25, d / 2))
    add(s * vol, start)

def kick(start, vol=0.28):
    t = tt(0.45); ph = 2 * np.pi * np.cumsum(45 + 85 * np.exp(-t / 0.035)) / SR
    add(np.sin(ph) * np.exp(-t / 0.18) * vol, start)

def hat(start, vol=0.025):
    t = tt(0.08); add(hp(rng.standard_normal(len(t)), 7500) * np.exp(-t / 0.022) * vol, start, 0.8, 1.0)

def tick(start, vol=0.03):
    t = tt(0.05); add(hp(rng.standard_normal(len(t)), 3000) * np.exp(-t / 0.008) * vol, start, 1.0, 0.7)

def heartbeat(start, vol=0.20):
    for off, v in ((0, 1.0), (0.22, 0.6)):
        t = tt(0.35); add(np.sin(2 * np.pi * 52 * t) * np.exp(-t / 0.09) * vol * v, start + off)

def riser(end, d=1.8, vol=0.06):
    t = tt(d); n = rng.standard_normal(len(t))
    s = hp(n, 900) * (t / d) ** 2.2 * vol
    s += np.sin(2 * np.pi * np.cumsum(180 + 520 * (t / d) ** 2) / SR) * (t / d) ** 2 * vol * 0.4
    add(s, end - d)

def impact(start, vol=0.35):
    t = tt(2.5)
    s = np.sin(2 * np.pi * np.cumsum(70 * np.exp(-t / 0.5) + 38) / SR) * np.exp(-t / 0.7)
    s += lp(rng.standard_normal(len(t)), 1800) * np.exp(-t / 0.12) * 0.4
    add(s * vol, start)

def whoosh(center, d=0.9, vol=0.035):
    t = tt(d); w = np.sin(np.pi * t / d) ** 2
    add(lp(hp(rng.standard_normal(len(t)), 600), 4000) * w * vol, center - d / 2, 0.7, 1.0)

# ── Act 1: tension ────────────────────────────────────────────────
pad([38, 45, 50, 53], 0.0, R + 0.4, vol=0.045, cut=700, a=2.0, r=0.6)  # D minor, dark
b = 0.0
while b < R - 1.6:
    heartbeat(b, 0.16 if b < at(3.8) else 0.20)
    b += BEAT * 2
b = BEAT
while b < R - 1.0:
    tick(b, 0.018 if b < at(8.6) else 0.028)
    b += BEAT
riser(R)
impact(R)

# ── Act 2: the product ────────────────────────────────────────────
CH = [  # F, C, Dm, Bb  (pad voicing, bass, arp tones)
    ([53, 57, 60, 65], 41, [65, 69, 72, 77, 72, 69]),
    ([52, 55, 60, 64], 36, [64, 67, 72, 76, 72, 67]),
    ([50, 57, 62, 65], 38, [62, 65, 69, 74, 69, 65]),
    ([50, 53, 58, 62], 34, [62, 65, 70, 74, 70, 65]),
]
bar, t0 = 0, R
while t0 < END - 0.05:
    notes, bass, arp = CH[bar % 4]
    d = min(BAR, END - t0)
    pad(notes, t0, d + 1.2, vol=0.035, cut=1100 if t0 < CUR else 1500, a=0.6, r=1.0)
    for q in range(4):
        bt = t0 + q * BEAT
        if bt >= END: break
        if t0 >= RES - 0.01: sub(bass, bt, BEAT * 0.9, 0.13 if t0 < CUR else 0.16)
        if t0 >= CUR - 0.01 and not (PROOF <= bt < PROOF + BAR):  # drop the kick for one bar at "proof"
            kick(bt, 0.22)
            hat(bt + BEAT / 2)
    step = BEAT / 4 if t0 >= RES - 0.01 else BEAT / 2
    k, st = 0, t0
    while st < t0 + d - 1e-6 and st < END:
        m = arp[k % len(arp)] + (12 if (k // len(arp)) % 2 and step < BEAT / 2 else 0)
        acc = 1.0 if k % 4 == 0 else 0.65
        pluck(m, st, vol=0.055 * acc, pan=(-0.35 if k % 2 else 0.35))
        k += 1; st += step
    t0 += BAR; bar += 1

whoosh(at(32.95) + 0.35); whoosh(at(39.5) + 0.35)
riser(END, d=1.4, vol=0.045)
impact(END, 0.30)
pad([41, 53, 57, 60, 65, 69], END, DUR - END, vol=0.04, cut=1600, a=0.25, r=DUR - END - 0.4)
for i, m in enumerate([65, 69, 72, 77]):
    pluck(m, END + i * 0.09, vol=0.06, tau=0.9)

# ── Space: short delay on everything, then a soft hall ──────────────
dl = int(BEAT * 0.75 * SR)
for _ in range(3):
    L[dl:] += 0.18 * Rt[:-dl].copy(); Rt[dl:] += 0.18 * L[:-dl].copy()
ir_t = tt(2.6)
irL = rng.standard_normal(len(ir_t)) * np.exp(-ir_t / 0.7); irR = rng.standard_normal(len(ir_t)) * np.exp(-ir_t / 0.7)
irL, irR = lp(irL, 5000) / np.abs(irL).sum() * 40, lp(irR, 5000) / np.abs(irR).sum() * 40
L = L + 0.22 * fftconvolve(L, irL)[:N]; Rt = Rt + 0.22 * fftconvolve(Rt, irR)[:N]
mus = np.stack([L, Rt], 1)
mus = hp(mus.T, 30).T
fade = np.ones(N); nf = int(1.2 * SR); fade[-nf:] = np.linspace(1, 0, nf) ** 1.5
mus *= fade[:, None]
mus /= np.abs(mus).max()
wavfile.write(f"{OUT}/music_dry.wav", SR, (mus * 0.9).astype(np.float32))
print("music", f"{DUR:.2f}s", "reveal", round(R, 2), "end", round(END, 2))
