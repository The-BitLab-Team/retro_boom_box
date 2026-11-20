"""Equalizador gráfico de 10 faixas.

Como funciona (resumo): o som chega em pedacinhos, é cortado em janelas de 4096
amostras que se sobrepõem pela metade, cada janela passa para o mundo das
frequências (FFT), cada faixa é multiplicada pelo ganho que a pessoa escolheu e
tudo volta para o som normal, emendado sem estalos. Só usa o numpy.
"""
import math

import numpy as np

BANDS = (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)       # centros, em Hz
LABELS = ("31", "62", "125", "250", "500", "1k", "2k", "4k", "8k", "16k")
GAIN_RANGE = 12.0         # cada faixa vai de -12 dB a +12 dB

PRESETS = {
    "Plano": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "Rock": [4, 3, 2, -1, -2, -1, 1, 3, 4, 5],
    "Pop": [-1, 1, 3, 4, 3, 0, -1, -1, 1, 2],
    "Jazz": [3, 2, 1, 2, -2, -2, 0, 1, 2, 3],
    "Clássica": [3, 2, 1, 0, 0, 0, -1, 1, 2, 3],
    "Eletrônica": [6, 5, 2, 0, -2, 1, 0, 2, 5, 6],
    "Vocal": [-3, -2, -1, 1, 4, 4, 3, 1, 0, -1],
    "Graves+": [6, 5, 4, 2, 0, 0, 0, 0, 0, 0],
    "Agudos+": [0, 0, 0, 0, 0, 1, 2, 4, 5, 6],
    "Menos graves": [-6, -5, -4, -2, 0, 0, 0, 0, 0, 0],
    "Volume baixo": [6, 4, 1, 0, -1, 0, -1, 0, 3, 5],
}

_LOG_BANDS = np.log2(np.array(BANDS, dtype=np.float64))


def curve_db(gains, freqs):
    """Ganho em dB para cada frequência (suave entre as faixas, reto nas pontas)."""
    freqs = np.maximum(np.asarray(freqs, dtype=np.float64), 1.0)
    pos = np.log2(freqs)
    g = np.asarray(gains, dtype=np.float64)
    out = np.empty_like(pos)
    for i, x in enumerate(pos):
        if x <= _LOG_BANDS[0]:
            out[i] = g[0]
        elif x >= _LOG_BANDS[-1]:
            out[i] = g[-1]
        else:
            k = int(np.searchsorted(_LOG_BANDS, x) - 1)
            u = (x - _LOG_BANDS[k]) / (_LOG_BANDS[k + 1] - _LOG_BANDS[k])
            u = (1.0 - math.cos(math.pi * u)) / 2.0           # transição suave, sem "degraus"
            out[i] = g[k] * (1.0 - u) + g[k + 1] * u
    return out


def soft_limit(y, knee=0.82):
    """Evita estourar o som quando o equalizador aumenta o volume: acima do joelho, curva suave."""
    a = np.abs(y)
    over = a > knee
    if not over.any():
        return y
    out = y.copy()
    room = 1.0 - knee
    out[over] = np.sign(y[over]) * (knee + room * np.tanh((a[over] - knee) / room))
    return out


class EqProcessor:
    """Processa o som em fluxo: process() recebe pedaços e devolve o que já está pronto."""
    N = 4096
    HOP = N // 2

    def __init__(self, rate=44100):
        self.rate = rate
        self.window = np.sqrt(np.hanning(self.N + 1)[:-1]).astype(np.float32)   # janela que emenda sem estalo
        self.gains = [0.0] * len(BANDS)
        self.preamp = 0.0
        self._gain = None
        self.reset()
        self._rebuild()

    # --------------------------------------------------------------- configuração
    def set_rate(self, rate):
        if rate != self.rate:
            self.rate = rate
            self._rebuild()
            self.reset()

    def set_gains(self, gains, preamp=0.0):
        g = [max(-GAIN_RANGE, min(GAIN_RANGE, float(v))) for v in list(gains)[:len(BANDS)]]
        g += [0.0] * (len(BANDS) - len(g))
        self.gains = g
        self.preamp = max(-GAIN_RANGE, min(GAIN_RANGE, float(preamp)))
        self._rebuild()

    @property
    def is_flat(self):
        return abs(self.preamp) < 0.05 and all(abs(v) < 0.05 for v in self.gains)

    def _rebuild(self):
        freqs = np.fft.rfftfreq(self.N, 1.0 / self.rate)
        db = curve_db(self.gains, freqs) + self.preamp
        self._gain = (10.0 ** (db / 20.0)).astype(np.float32)[:, None]

    def reset(self):
        """Esquece o que estava no meio do caminho (usado ao pular para outro ponto da música)."""
        self._inbuf = np.zeros((self.HOP, 2), dtype=np.float32)    # começa com meia janela de silêncio
        self._tail = np.zeros((self.HOP, 2), dtype=np.float32)
        self._skip = self.HOP         # a primeira meia janela é só o silêncio do começo
        self.n_in = 0
        self.n_out = 0

    # --------------------------------------------------------------- processamento
    def process(self, x):
        """x: matriz (amostras, 2) em float32. Devolve (amostras prontas, 2) — pode ser vazia."""
        x = np.asarray(x, dtype=np.float32)
        if x.ndim == 1:
            x = np.column_stack([x, x])
        self.n_in += len(x)
        self._inbuf = np.concatenate([self._inbuf, x]) if len(x) else self._inbuf
        outs = []
        N, H = self.N, self.HOP
        while len(self._inbuf) >= N:
            frame = self._inbuf[:N] * self.window[:, None]
            spec = np.fft.rfft(frame, axis=0) * self._gain
            y = np.fft.irfft(spec, n=N, axis=0).astype(np.float32) * self.window[:, None]
            outs.append(y[:H] + self._tail)
            self._tail = y[H:].copy()
            self._inbuf = self._inbuf[H:]
        if not outs:
            return np.zeros((0, 2), dtype=np.float32)
        out = np.concatenate(outs)
        if self._skip:
            cut = min(self._skip, len(out))
            out = out[cut:]
            self._skip -= cut
        self.n_out += len(out)
        return out

    def flush(self):
        """Fim da música: empurra silêncio para sair o que ficou preso e corta o excesso."""
        real_in, before = self.n_in, self.n_out
        out = self.process(np.zeros((self.N, 2), dtype=np.float32))
        out = out[:max(0, real_in - before)]
        self.n_in, self.n_out = real_in, before + len(out)
        return out
