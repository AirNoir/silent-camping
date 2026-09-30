"""純程式合成的環境音（不用任何素材）。輸出 44.1 kHz 立體聲 WAV，每一段都是無縫循環。
用法：<python with numpy> tools/gen_audio.py <輸出資料夾>
      （系統 python 沒有 numpy 的話用 Blender 內建的：
       /Applications/Blender.app/Contents/Resources/*/python/bin/python3* tools/gen_audio.py audio）
之後用 ffmpeg 轉 OGG（見 README）。

做法：所有濾波都在頻域做（rfft × 頻率響應 → irfft），等於循環卷積，所以整段本來就是週期的；
慢速起伏（陣風、火勢）用「整數個週期」的正弦疊加；點狀事件（鳥叫、爆裂）超出尾端就繞回開頭。
- wind     風：粉紅噪音 60–800 Hz + 陣風包絡；陣風強時多一層樹葉沙沙（2–6 kHz）
- birds    白天鳥叫：四種叫聲（連啾、顫音、下滑哨、顫抖音）隨機落點、隨機左右
- crickets 夜晚：三隻不同音高／節奏的蟋蟀 + 遠處的紡織娘嗡嗡 + 兩聲貓頭鷹
- fire     營火：低頻轟鳴 + 火焰呼呼 + 隨機爆裂聲（3D 音源，放在營火位置）
- water    池塘：很輕的水波拍岸（3D 音源，放在池塘）
"""
import sys, os, struct, math
import numpy as np

SR = 44100
rng = np.random.default_rng(7)


# ---------------------------------------------------------------- 基礎工具

def white(n, seed=None):
    r = rng if seed is None else np.random.default_rng(seed)
    return r.standard_normal(n).astype(np.float64)


def shape(x, fn):
    """頻域濾波：fn(f) 回傳每個頻率的增益。循環卷積 → 結果仍是無縫循環。"""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    g = fn(np.maximum(f, 1e-3))
    return np.fft.irfft(X * g, n=len(x))


def band(lo, hi, order=2, tilt=0.0):
    """帶通增益（巴特沃斯型），tilt<0 讓高頻遞減（粉紅／棕色噪音）。"""
    def fn(f):
        g = 1.0 / np.sqrt(1.0 + (lo / f) ** (2 * order)) / np.sqrt(1.0 + (f / hi) ** (2 * order))
        if tilt:
            g = g * (f / lo) ** tilt
        return g
    return fn


def lfo(n, cycles, phase=0.0):
    """整數週期的正弦（cycles 必須是整數才能無縫循環）。"""
    t = np.arange(n) / n
    return np.sin(2 * math.pi * cycles * t + phase)


def slow_env(n, spec, floor=0.0):
    """多個整數週期正弦疊起來、正規化到 [floor, 1]。spec=[(cycles, weight, phase), ...]"""
    e = sum(w * lfo(n, c, p) for c, w, p in spec)
    e = (e - e.min()) / (e.max() - e.min() + 1e-9)
    return floor + (1.0 - floor) * e


def place(buf, start, ev):
    """把事件 ev 疊到 buf 的 start 位置，超出尾端就繞回開頭（循環）。buf 形狀 (n,) 或 (n,2)。"""
    n = len(buf)
    idx = (np.arange(len(ev)) + int(start)) % n
    np.add.at(buf, idx, ev)


def pan(mono, p):
    """等功率左右擺位，p∈[-1,1]。"""
    a = (p + 1.0) * 0.25 * math.pi
    return np.stack([mono * math.cos(a), mono * math.sin(a)], axis=1)


def hann(n):
    return 0.5 - 0.5 * np.cos(2 * math.pi * np.arange(n) / max(n - 1, 1))


def adsr(n, a, d, sustain=1.0):
    """簡單包絡：a 秒起音、d 秒釋音（指數），中間 sustain。"""
    env = np.ones(n)
    na = int(a * SR)
    if na > 0:
        env[:na] = np.linspace(0, 1, na)
    nd = int(d * SR)
    if 0 < nd < n:
        env[n - nd:] *= np.exp(-4.0 * np.linspace(0, 1, nd))
    return env * sustain


def reverb(x, secs=0.35, mix=0.18, seed=3):
    """很短的合成殘響：指數衰減的噪音當脈衝響應，FFT 卷積。x 形狀 (n,2)。"""
    n = len(x)
    ir_n = int(secs * SR)
    ir = white(ir_n, seed) * np.exp(-6.0 * np.arange(ir_n) / ir_n)
    ir = shape(ir, band(300, 5000))
    ir /= np.abs(ir).sum() * 0.08
    out = np.empty_like(x)
    for ch in range(x.shape[1]):
        X = np.fft.rfft(x[:, ch], n)
        H = np.fft.rfft(ir, n)
        out[:, ch] = np.fft.irfft(X * H, n=n)
    return x + mix * out


def normalize(x, peak=0.7):
    m = np.abs(x).max() + 1e-9
    return x * (peak / m)


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype("<i2")
    if pcm.ndim == 1:
        pcm = np.stack([pcm, pcm], axis=1)
    data = pcm.tobytes()
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE")
        f.write(b"fmt " + struct.pack("<IHHIIHH", 16, 1, 2, SR, SR * 4, 4, 16))
        f.write(b"data" + struct.pack("<I", len(data)) + data)
    print("AUDIO %-12s %5.1f s  peak=%.2f  rms=%.3f" % (os.path.basename(path), len(x) / SR, np.abs(x).max(), np.sqrt((x ** 2).mean())))


# ---------------------------------------------------------------- 風

def wind(secs=24):
    n = secs * SR
    gust = slow_env(n, [(2, 1.0, 0.0), (3, 0.6, 1.1), (5, 0.35, 2.3), (7, 0.2, 0.4)], floor=0.25)
    out = np.zeros((n, 2))
    for ch, seed in enumerate((11, 12)):
        base = shape(white(n, seed), band(60, 800, order=2, tilt=-0.5))   # 粉紅感的低鳴
        body = shape(white(n, seed + 20), band(250, 1500, order=2, tilt=-0.3))
        leaves = shape(white(n, seed + 40), band(2000, 6000, order=2))
        out[:, ch] = base * gust + 0.55 * body * gust ** 2 + 0.16 * leaves * gust ** 3
    # 左右稍微不同步的陣風，聽得出方向
    out[:, 1] *= 0.85 + 0.15 * slow_env(n, [(3, 1.0, 2.0)])
    return normalize(out, 0.6)


# ---------------------------------------------------------------- 鳥

def tone(secs, freq_fn, vib_hz=0.0, vib_depth=0.0):
    n = int(secs * SR)
    t = np.arange(n) / SR
    f = freq_fn(t / secs) + vib_depth * np.sin(2 * math.pi * vib_hz * t)
    phase = np.cumsum(f) / SR
    return np.sin(2 * math.pi * phase), n


def bird_chirp():
    """連啾：3–5 個短促上滑音。"""
    k = rng.integers(3, 6)
    gap = int(rng.uniform(0.11, 0.16) * SR)
    f0 = rng.uniform(2600, 3400)
    parts = []
    for i in range(k):
        s, m = tone(rng.uniform(0.06, 0.09), lambda u, f0=f0: f0 + 700 * u)
        s *= hann(m) ** 0.7
        parts.append(s)
        if i < k - 1:
            parts.append(np.zeros(gap))
    return np.concatenate(parts) * rng.uniform(0.5, 0.9)


def bird_warble():
    f0 = rng.uniform(1800, 2400)
    s, m = tone(rng.uniform(0.35, 0.55), lambda u, f0=f0: f0 + 150 * np.sin(6.28 * u), vib_hz=28, vib_depth=260)
    return s * adsr(m, 0.02, 0.12) * 0.6


def bird_whistle():
    f0 = rng.uniform(4000, 4800)
    s, m = tone(rng.uniform(0.10, 0.16), lambda u, f0=f0: f0 - 1400 * u * u)
    return s * hann(m) ** 0.5 * 0.55


def bird_trill():
    f0 = rng.uniform(2900, 3500)
    s, m = tone(rng.uniform(0.4, 0.6), lambda u, f0=f0: f0 + 80 * u)
    am = 0.55 + 0.45 * np.sin(2 * math.pi * 16 * np.arange(m) / SR)
    return s * am * adsr(m, 0.03, 0.15) * 0.5


def birds(secs=32):
    n = secs * SR
    out = np.zeros((n, 2))
    makers = [bird_chirp, bird_chirp, bird_warble, bird_whistle, bird_trill]
    for _ in range(26):
        ev = makers[rng.integers(len(makers))]()
        dist = rng.uniform(0.25, 1.0)                    # 遠的比較小、比較悶
        if dist < 0.55:
            ev = shape(ev, band(200, 3500 + 3000 * dist, order=1))
        ev = ev * dist
        st = pan(ev, rng.uniform(-0.9, 0.9))
        place(out, rng.uniform(0, n), st)
    out = reverb(out, 0.4, 0.22)
    return normalize(out, 0.55)


# ---------------------------------------------------------------- 蟋蟀、貓頭鷹

def cricket_track(n, freq, rate, pulses, pan_pos, amp, seed):
    """一隻蟋蟀：每秒 rate 聲，每聲 pulses 個 20 ms 的短脈衝（4–5 kHz 純音）。"""
    r = np.random.default_rng(seed)
    out = np.zeros((n, 2))
    period = SR / rate
    pulse_n = int(0.021 * SR)
    gap_n = int(0.012 * SR)
    t = np.arange(pulse_n) / SR
    pulse = np.sin(2 * math.pi * freq * t) * hann(pulse_n) ** 0.8
    k = int(n / period)
    for i in range(k):
        start = i * period + r.uniform(-0.03, 0.03) * period
        if r.uniform() < 0.08:       # 偶爾漏一聲，才不像節拍器
            continue
        ev = np.concatenate([np.concatenate([pulse, np.zeros(gap_n)]) for _ in range(pulses)])
        place(out, start, pan(ev * amp * r.uniform(0.8, 1.0), pan_pos))
    return out


def owl_hoot():
    """兩聲「呼—呼」，低頻、帶一點抖音。"""
    parts = []
    for i, (f, d) in enumerate(((390, 0.42), (355, 0.55))):
        s, m = tone(d, lambda u, f=f: f - 12 * u, vib_hz=5.5, vib_depth=6)
        s = s + 0.35 * np.sin(2 * math.pi * 2 * f * np.arange(m) / SR)   # 一點第二諧波
        parts.append(s * adsr(m, 0.05, 0.25))
        if i == 0:
            parts.append(np.zeros(int(0.18 * SR)))
    ev = np.concatenate(parts)
    return shape(ev, band(80, 900, order=1)) * 0.5


def crickets(secs=30):
    n = secs * SR
    out = np.zeros((n, 2))
    out += cricket_track(n, 4300, 2.2, 3, -0.6, 0.55, 1)
    out += cricket_track(n, 4650, 2.7, 4, 0.55, 0.45, 2)
    out += cricket_track(n, 5000, 3.1, 3, 0.05, 0.30, 3)
    # 遠處紡織娘：6–8 kHz 噪音，15 Hz 顫動，很小聲
    katy = shape(white(n, 31), band(6000, 8500, order=3))
    katy *= 0.5 + 0.5 * np.sin(2 * math.pi * 15 * np.arange(n) / SR)
    katy *= slow_env(n, [(1, 1.0, 0.0), (4, 0.4, 1.0)], floor=0.3)
    out += pan(katy * 0.06, -0.2)
    for st, p in ((0.31 * n, -0.7), (0.74 * n, 0.5)):
        place(out, st, pan(owl_hoot(), p))
    out = reverb(out, 0.5, 0.15, seed=5)
    return normalize(out, 0.5)


# ---------------------------------------------------------------- 營火

def fire(secs=16):
    n = secs * SR
    flutter = slow_env(n, [(3, 1.0, 0.0), (7, 0.6, 1.0), (11, 0.4, 2.0), (19, 0.25, 0.5)], floor=0.35)
    rumble = shape(white(n, 41), band(30, 160, order=2, tilt=-0.4)) * flutter
    roar = shape(white(n, 42), band(200, 1400, order=2, tilt=-0.4)) * flutter ** 2
    mono = 1.0 * rumble + 0.35 * roar
    # 爆裂：短促的高頻噪音爆，振幅長尾分布（多數小、偶爾很大）
    for _ in range(90):
        dur = rng.uniform(0.003, 0.014)
        m = int(dur * SR)
        ev = white(m) * np.exp(-np.linspace(0, 7, m))
        ev = shape(ev, band(1500, 7000, order=1)) if m > 32 else ev
        a = min(1.0, rng.pareto(2.2) * 0.35 + 0.15)
        place(mono, rng.uniform(0, n), ev * a * 0.9)
    # 悶悶的「啵」：木頭裡的水氣
    for _ in range(14):
        m = int(0.02 * SR)
        t = np.arange(m) / SR
        ev = np.sin(2 * math.pi * rng.uniform(220, 420) * t) * np.exp(-t * 180)
        place(mono, rng.uniform(0, n), ev * rng.uniform(0.3, 0.7))
    st = np.stack([mono, mono], axis=1)
    return normalize(st, 0.7)


# ---------------------------------------------------------------- 池塘

def water(secs=24):
    n = secs * SR
    swell = slow_env(n, [(5, 1.0, 0.0), (8, 0.5, 1.3), (13, 0.3, 0.7)], floor=0.15)
    lap = shape(white(n, 51), band(120, 700, order=2, tilt=-0.5)) * swell ** 2
    sparkle = shape(white(n, 52), band(2500, 6000, order=2)) * swell ** 3
    mono = lap + 0.12 * sparkle
    # 幾滴「叮」：小水珠
    for _ in range(10):
        m = int(0.06 * SR)
        t = np.arange(m) / SR
        f = rng.uniform(1800, 3200)
        ev = np.sin(2 * math.pi * (f + 900 * t / 0.06) * t) * np.exp(-t * 60)
        place(mono, rng.uniform(0, n), ev * rng.uniform(0.1, 0.25))
    st = np.stack([mono, mono], axis=1)
    return normalize(st, 0.45)


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "audio"
    os.makedirs(out_dir, exist_ok=True)
    for name, fn in (("wind", wind), ("birds", birds), ("crickets", crickets), ("fire", fire), ("water", water)):
        write_wav(os.path.join(out_dir, name + ".wav"), fn())
