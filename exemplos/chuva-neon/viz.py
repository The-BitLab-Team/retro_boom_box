"""Chuva Neon: exemplo de visualizador. Copie esta pasta e mude o que quiser!

O player chama draw(p, w, h, v) a cada quadro:
  p  é o pintor (QPainter) já pronto para desenhar
  w, h  largura e altura da área do visualizador
  v  traz o som: v.bands, v.wave, v.energy, v.bass, v.beat, v.dt, v.time, v.lcd,
     v.color(t) (cor do degradê da skin) e v.state (um dicionário para guardar coisas)
"""
import random

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPen


def draw(p, w, h, v):
    drops = v.state.setdefault("drops", [])

    # nascem mais gotas quanto mais forte está o som (e uma rajada em cada batida)
    n_new = int(v.energy * 7) + (14 if v.beat > 0 else 0)
    for _ in range(n_new):
        if len(drops) < 260:
            band = random.randrange(48)
            drops.append({"x": (band + random.random()) / 48.0, "y": -10.0,
                          "speed": random.uniform(0.7, 1.6) * h, "len": random.uniform(10, 34),
                          "band": band})

    # um clarão leve no fundo quando bate o grave
    if v.bass > 0.55:
        c = v.color(0.0)
        c.setAlpha(int(70 * v.bass))
        p.fillRect(0, 0, w, h, c)

    alive = []
    for d in drops:
        d["y"] += d["speed"] * v.dt
        if d["y"] - d["len"] > h:
            continue
        c = v.color(d["band"] / 47.0)
        pen_w = 3.0 if not v.lcd else 2.0
        # cauda: vários riscos cada vez mais fracos
        for i in range(4):
            c.setAlpha(255 - i * 60)
            p.setPen(QPen(c, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            y0 = d["y"] - i * d["len"] / 4
            p.drawLine(QPointF(d["x"] * w, y0), QPointF(d["x"] * w, y0 - d["len"] / 4))
        alive.append(d)
    v.state["drops"] = alive
