"""Visualizadores: desenhos animados que reagem ao som real da música.

Os visualizadores que já vêm com o programa são métodos `_viz_nome(self, p, w, h)`
listados em `builtin_list` (nome mostrado, método). Eles recebem o pintor `p`,
a largura `w` e a altura `h` e usam:
    self.bands  -> 48 níveis de frequência (graves à esquerda), de 0 a 1
    self.wave   -> 256 pontos da forma de onda, de -1 a 1
    self.energy -> volume geral de 0 a 1
    self.bass   -> força dos graves de 0 a 1

Visualizadores de terceiros chegam como pacotes (.rbbviz): uma pasta com viz.json e
viz.py, onde viz.py tem `draw(p, w, h, v)`. O `v` é um VizContext (veja abaixo).
O guia completo está em GUIA-DE-SKINS.txt.
"""
import math
import random
import time

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget


def resample(values, n):
    values = np.asarray(values, dtype=np.float32)
    return np.interp(np.linspace(0, len(values) - 1, n), np.arange(len(values)), values)


def mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


class VizContext:
    """O que um visualizador de pacote recebe como `v` em draw(p, w, h, v)."""

    def __init__(self, widget):
        self._w = widget
        self.state = {}          # guarde aqui o que precisa lembrar de um quadro para o outro
        self.dt = 0.03           # segundos desde o quadro anterior
        self.time = 0.0          # segundos desde que o programa abriu
        self.beat = 0.0          # 0 normalmente; de 0 a 1 no quadro em que bate um grave forte

    bands = property(lambda self: self._w.bands)        # 48 níveis de frequência (graves primeiro), 0 a 1
    wave = property(lambda self: self._w.wave)          # 256 pontos da onda, -1 a 1
    energy = property(lambda self: self._w.energy)      # volume geral, 0 a 1
    bass = property(lambda self: self._w.bass)          # força dos graves, 0 a 1
    lcd = property(lambda self: self._w.lcd)            # True quando a skin pede visual de "display LCD"
    colors = property(lambda self: [QColor(c) for c in self._w.theme.viz_colors])

    def color(self, t):
        """Cor do degradê da skin: 0 = graves, 1 = agudos."""
        return self._w._grad_color(t)

    @staticmethod
    def resample(values, n):
        return resample(values, n)


_START = time.perf_counter()


class VisualizerWidget(QWidget):
    packFailed = Signal(str, str)     # nome do visualizador, mensagem de erro

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.ctx = VizContext(self)
        self.dt = 0.03
        self.mode = 0
        self.bands = np.zeros(48, dtype=np.float32)
        self.wave = np.zeros(256, dtype=np.float32)
        self.energy = 0.0
        self.bass = 0.0
        self.peaks = np.zeros(64, dtype=np.float32)
        self.slow = np.zeros(64, dtype=np.float32)
        self.rings = []
        self.sparks = []
        self.angle = 0.0
        self._last = time.perf_counter()
        self.setMinimumHeight(24)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.panel = False     # desenha um fundo de "visor" atrás (usado no modo mini padrão)
        self.packs = []        # [(nome, função draw)] de pacotes ativados
        self.builtin_list = [
            ("Barras", self._viz_bars),
            ("Espelho", self._viz_mirror),
            ("Onda", self._viz_wave),
            ("Montanhas", self._viz_mountains),
            ("Pontos", self._viz_dots),
            ("Círculos", self._viz_radial),
            ("Anéis", self._viz_rings),
            ("Faíscas", self._viz_sparks),
        ]
        self._rebuild()

    # ---------------------------------------------------------------- dados
    def _rebuild(self):
        self.VIZ_LIST = list(self.builtin_list) + [(n, self._wrap_pack(n, fn)) for n, fn in self.packs]

    def _wrap_pack(self, name, draw):
        def run(p, w, h):
            self.ctx.dt = self.dt
            self.ctx.time = time.perf_counter() - _START
            try:
                draw(p, w, h, self.ctx)
            except Exception as exc:   # um pacote com defeito não pode derrubar o player
                self.fail_pack(name, f"{type(exc).__name__}: {exc}")
        return run

    def fail_pack(self, name, message):
        self.packs = [(n, f) for n, f in self.packs if n != name]
        self._rebuild()
        self.mode = 0
        self.packFailed.emit(name, message)

    def set_packs(self, packs):
        current = self.names[self.mode] if self.mode < len(self.names) else "Barras"
        self.packs = list(packs)
        self._rebuild()
        self.mode = self.names.index(current) if current in self.names else 0
        self.update()

    def set_mode_by_name(self, name):
        names = self.names
        self.set_mode(names.index(name) if name in names else 0)

    @property
    def names(self):
        return [n for n, _ in self.VIZ_LIST]

    def set_theme(self, theme):
        self.theme = theme
        self.update()

    def set_mode(self, mode: int):
        self.mode = mode % len(self.VIZ_LIST)
        self.rings.clear()
        self.sparks.clear()
        self.update()

    def feed(self, bands, wave, beat):
        self.bands = bands
        self.wave = wave
        self.energy = float(np.mean(bands))
        self.bass = float(np.mean(bands[:6]))
        self.ctx.beat = beat
        if beat > 0:
            self.rings.append([time.perf_counter(), beat])
            if len(self.rings) > 8:
                self.rings.pop(0)
            self._beat_sparks(beat)
        self.update()

    def _beat_sparks(self, beat):
        for _ in range(int(8 + 14 * beat)):
            if len(self.sparks) > 320:
                break
            self.sparks.append({
                "x": random.random(), "y": 1.0, "vx": random.uniform(-0.12, 0.12),
                "vy": -random.uniform(0.35, 0.9) * (0.6 + beat), "life": random.uniform(0.9, 1.8),
                "age": 0.0, "size": random.uniform(2.0, 5.0), "c": random.random()})

    # ---------------------------------------------------------------- cores
    def _c(self, i):
        return QColor(self.theme.viz_colors[i])

    def _grad_color(self, t):
        """0 = graves, 1 = agudos."""
        low, mid, high = self._c(0), self._c(1), self._c(2)
        return mix(low, mid, t * 2) if t < 0.5 else mix(mid, high, (t - 0.5) * 2)

    @property
    def lcd(self):
        return self.theme.viz_style == "lcd"

    # ---------------------------------------------------------------- pintura
    def paintEvent(self, _event):
        now = time.perf_counter()
        dt = min(0.1, now - self._last)
        self._last = now
        self.dt = dt
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, not self.lcd)
        w, h = self.width(), self.height()
        # os picos caem devagar
        b = resample(self.bands, 64)
        self.peaks = np.maximum(b, self.peaks - dt * 0.5)
        self.slow = self.slow + (b - self.slow) * min(1.0, dt * 6)
        if self.panel:
            t = self.theme
            g = QLinearGradient(0, 0, 0, h)
            g.setColorAt(0, QColor(t.lcd_top))
            g.setColorAt(1, QColor(t.lcd_bottom))
            p.setPen(QPen(QColor(t.lcd_border), 1.2))
            p.setBrush(QBrush(g))
            p.drawRoundedRect(QRectF(0.6, 0.6, w - 1.2, h - 1.2), 7, 7)
            p.translate(5, 5)
            w, h = w - 10, h - 10
            p.setClipRect(QRectF(0, 0, w, h))
        self.VIZ_LIST[min(self.mode, len(self.VIZ_LIST) - 1)][1](p, w, h)
        self.ctx.beat = 0.0
        p.end()

    # 1) Barras com "tampinhas" que caem devagar
    def _viz_bars(self, p, w, h):
        n = max(8, min(40, int(w // 7)))      # em palcos estreitos (modo mini) usa menos barras
        vals, peaks = resample(self.bands, n), resample(self.peaks, n)
        gap = min(3 if not self.lcd else 4, max(1.0, w / n * 0.3))
        bw = (w - gap * (n - 1)) / n
        for i in range(n):
            x = i * (bw + gap)
            bh = max(2.0, vals[i] * (h - 4))
            color = self._grad_color(i / (n - 1))
            if self.lcd:
                seg, sgap = 6, 2
                count = int(bh // (seg + sgap))
                for s in range(count):
                    y = h - (s + 1) * (seg + sgap)
                    p.fillRect(QRectF(x, y, bw, seg), color)
                py = h - (int(peaks[i] * (h - 4)) // (seg + sgap) + 1) * (seg + sgap)
                p.fillRect(QRectF(x, max(0, py), bw, seg), color.lighter(140))
            else:
                g = QLinearGradient(0, h - bh, 0, h)
                g.setColorAt(0, color.lighter(130))
                g.setColorAt(1, color.darker(130))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(g))
                p.drawRoundedRect(QRectF(x, h - bh, bw, bh), 3, 3)
                p.setBrush(QColor(255, 255, 255, 200))
                p.drawRoundedRect(QRectF(x, h - peaks[i] * (h - 4) - 5, bw, 3), 1.5, 1.5)

    # 2) Espelho: barras que crescem do centro para cima e para baixo
    def _viz_mirror(self, p, w, h):
        n = max(8, min(44, int(w // 7)))
        vals = resample(self.bands, n)
        gap = min(3, max(1.0, w / n * 0.3))
        bw = (w - gap * (n - 1)) / n
        mid = h / 2
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(n):
            x = i * (bw + gap)
            half = max(1.5, vals[i] * (h / 2 - 3))
            color = self._grad_color(i / (n - 1))
            if self.lcd:
                seg = 4
                for s in range(int(half // (seg + 2))):
                    off = s * (seg + 2)
                    p.fillRect(QRectF(x, mid - off - seg, bw, seg), color)
                    p.fillRect(QRectF(x, mid + off, bw, seg), color)
            else:
                g = QLinearGradient(0, mid - half, 0, mid + half)
                g.setColorAt(0, color.lighter(125))
                g.setColorAt(0.5, color)
                g.setColorAt(1, color.lighter(125))
                p.setBrush(QBrush(g))
                p.drawRoundedRect(QRectF(x, mid - half, bw, half * 2), bw / 2.2, bw / 2.2)

    # 3) Onda: osciloscópio com a forma real do som
    def _viz_wave(self, p, w, h):
        mid = h / 2
        if self.lcd:
            p.setPen(QPen(QColor(63, 154, 51, 70), 1))
            for gx in range(0, w, 40):
                p.drawLine(gx, 0, gx, h)
            for gy in range(0, h, 20):
                p.drawLine(0, gy, w, gy)
        wave = resample(self.wave, 160)
        path = QPainterPath()
        for i, v in enumerate(wave):
            x = i * w / (len(wave) - 1)
            y = mid - float(v) * (h / 2 - 4)
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        base = self._c(1)
        glow = QColor(base)
        glow.setAlpha(60)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(glow, 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)
        p.setPen(QPen(self._c(0) if self.lcd else base, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)
        # segunda linha: contorno do volume (graves e médios)
        env = resample(self.slow, 160)
        path2 = QPainterPath()
        for i, v in enumerate(env):
            x = i * w / (len(env) - 1)
            y = mid - float(v) * (h / 2 - 6) * math.sin(i * 0.35 + self.angle)
            path2.moveTo(x, y) if i == 0 else path2.lineTo(x, y)
        self.angle += self.dt * 3
        p.setPen(QPen(self._c(2), 1.6))
        p.drawPath(path2)

    # 4) Montanhas: espectro suave, com uma camada mais lenta atrás
    def _viz_mountains(self, p, w, h):
        def make_path(vals, scale):
            n = len(vals)
            pts = [QPointF(i * w / (n - 1), h - 2 - float(v) * (h - 8) * scale) for i, v in enumerate(vals)]
            path = QPainterPath(QPointF(0, h))
            path.lineTo(pts[0])
            for a, b in zip(pts, pts[1:]):
                mx = (a.x() + b.x()) / 2
                path.cubicTo(QPointF(mx, a.y()), QPointF(mx, b.y()), b)
            path.lineTo(QPointF(w, h))
            path.closeSubpath()
            return path
        slow = make_path(resample(self.slow, 36), 0.85)
        fast = make_path(resample(self.bands, 36), 1.0)
        for path, alpha, top, bot in ((slow, 120, self._c(2), self._c(1)), (fast, 210, self._c(1), self._c(0))):
            g = QLinearGradient(0, 0, 0, h)
            t, b = QColor(top), QColor(bot)
            t.setAlpha(alpha)
            b.setAlpha(max(40, alpha - 120))
            g.setColorAt(0, t)
            g.setColorAt(1, b)
            p.setBrush(QBrush(g))
            p.setPen(QPen(QColor(255, 255, 255, 170) if not self.lcd else self._c(0).lighter(130), 1.4))
            p.drawPath(path)

    # 5) Pontos: matriz de pontos, como os equalizadores de aparelho de som
    def _viz_dots(self, p, w, h):
        cols, rows = 32, 9
        vals = resample(self.bands, cols)
        cw, rh = w / cols, h / rows
        d = min(cw, rh) * 0.62
        p.setPen(Qt.PenStyle.NoPen)
        for c in range(cols):
            lit = int(round(vals[c] * rows))
            for r in range(rows):
                cx, cy = c * cw + cw / 2, h - (r * rh + rh / 2)
                on = r < lit
                color = self._grad_color(r / (rows - 1))
                if not on:
                    color = QColor(color)
                    color.setAlpha(36)
                if self.lcd:
                    p.fillRect(QRectF(cx - d / 2, cy - d / 2, d, d), color)
                else:
                    g = QRadialGradient(cx - d * 0.15, cy - d * 0.2, d * 0.7)
                    g.setColorAt(0, QColor(255, 255, 255, 230 if on else 60))
                    g.setColorAt(1, color)
                    p.setBrush(QBrush(g))
                    p.drawEllipse(QPointF(cx, cy), d / 2, d / 2)

    # 6) Círculos: espectro em volta de um centro que pulsa com os graves
    def _viz_radial(self, p, w, h):
        cx, cy = w / 2, h / 2
        r0 = min(w, h) * (0.18 + 0.05 * self.bass)
        rmax = min(w, h) * 0.5 - 3
        spokes = 72
        vals = resample(self.bands, spokes // 2)
        self.angle += self.dt * 0.5
        for i in range(spokes):
            v = float(vals[i if i < spokes // 2 else spokes - 1 - i])
            a = self.angle + i * 2 * math.pi / spokes
            r1, r2 = r0 + 3, r0 + 3 + max(2.0, v * (rmax - r0 - 3))
            color = self._grad_color(v)
            p.setPen(QPen(color, 3.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap if self.lcd else Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(cx + math.cos(a) * r1, cy + math.sin(a) * r1),
                       QPointF(cx + math.cos(a) * r2, cy + math.sin(a) * r2))
        orb = QRadialGradient(cx - r0 * 0.3, cy - r0 * 0.35, r0 * 1.2)
        orb.setColorAt(0, QColor(255, 255, 255, 235 if not self.lcd else 90))
        orb.setColorAt(1, self._c(1))
        p.setPen(QPen(self._c(0), 2))
        p.setBrush(QBrush(orb))
        p.drawEllipse(QPointF(cx, cy), r0, r0)

    # 7) Anéis: uma onda nasce a cada batida e se espalha
    def _viz_rings(self, p, w, h):
        cx, cy = w / 2, h / 2
        now = time.perf_counter()
        rmax = math.hypot(w, h) * 0.42
        r0 = min(w, h) * (0.10 + 0.07 * self.bass)
        self.rings = [r for r in self.rings if now - r[0] < 1.8]
        for t0, strength in self.rings:
            k = (now - t0) / 1.8
            r = r0 + k * (rmax - r0)
            color = self._grad_color(k)
            color.setAlpha(int(255 * (1 - k) * (0.5 + 0.5 * strength)))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(color, 4 * (1 - k) + 1))
            p.drawEllipse(QPointF(cx, cy), r, r)
        orb = QRadialGradient(cx - r0 * 0.3, cy - r0 * 0.35, r0 * 1.3)
        orb.setColorAt(0, QColor(255, 255, 255, 235 if not self.lcd else 110))
        orb.setColorAt(1, self._c(0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(orb))
        p.drawEllipse(QPointF(cx, cy), r0, r0)

    # 8) Faíscas: partículas que sobem a cada batida
    def _viz_sparks(self, p, w, h):
        dt = self.dt
        if self.energy > 0.05 and random.random() < self.energy * 1.5:
            self.sparks.append({"x": random.random(), "y": 1.0, "vx": random.uniform(-0.05, 0.05),
                                "vy": -random.uniform(0.15, 0.4), "life": random.uniform(0.8, 1.4),
                                "age": 0.0, "size": random.uniform(1.5, 3.0), "c": random.random()})
        alive = []
        p.setPen(Qt.PenStyle.NoPen)
        for s in self.sparks:
            s["age"] += dt
            if s["age"] >= s["life"]:
                continue
            s["x"] += s["vx"] * dt
            s["y"] += s["vy"] * dt
            k = s["age"] / s["life"]
            color = self._grad_color(s["c"])
            color.setAlpha(int(255 * (1 - k)))
            size = s["size"] * (1.2 - 0.6 * k)
            p.setBrush(color)
            if self.lcd:
                p.drawRect(QRectF(s["x"] * w, s["y"] * h, size, size))
            else:
                p.drawEllipse(QPointF(s["x"] * w, s["y"] * h), size, size)
            alive.append(s)
        self.sparks = alive
        # linha do espectro na base para dar "chão" aos pontos
        vals = resample(self.bands, 60)
        path = QPainterPath(QPointF(0, h - 1))
        for i, v in enumerate(vals):
            path.lineTo(i * w / (len(vals) - 1), h - 1 - float(v) * h * 0.22)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(self._c(1), 2))
        p.drawPath(path)
