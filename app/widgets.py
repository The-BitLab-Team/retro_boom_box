"""Peças visuais do player: botões, barras deslizantes, visor LCD e vídeo."""
import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath,
                           QPen, QPixmap, QPolygonF, QRadialGradient)
from PySide6.QtWidgets import QAbstractButton, QSlider, QStyle, QStyledItemDelegate, QWidget


def rounded_path(rect: QRectF, tl, tr, br, bl) -> QPainterPath:
    """Retângulo com um raio de arredondamento diferente em cada canto."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    path = QPainterPath()
    path.moveTo(x + tl, y)
    path.lineTo(x + w - tr, y)
    path.arcTo(x + w - 2 * tr, y, 2 * tr, 2 * tr, 90, -90)
    path.lineTo(x + w, y + h - br)
    path.arcTo(x + w - 2 * br, y + h - 2 * br, 2 * br, 2 * br, 0, -90)
    path.lineTo(x + bl, y + h)
    path.arcTo(x, y + h - 2 * bl, 2 * bl, 2 * bl, 270, -90)
    path.lineTo(x, y + tl)
    path.arcTo(x, y, 2 * tl, 2 * tl, 180, -90)
    path.closeSubpath()
    return path


# ------------------------------------------------------------------ botões
SIZES = {  # tamanho por tema: (vidro, metal)
    "xs": ((26, 26), (28, 22)),
    "sm": ((30, 30), (34, 26)),
    "md": ((44, 44), (56, 42)),
    "lg": ((64, 64), (76, 50)),
}


class RetroButton(QAbstractButton):
    def __init__(self, kind, theme, size="md", primary=False, checkable=False, tip="", parent=None):
        super().__init__(parent)
        self.kind = kind
        self.theme = theme
        self.size_class = size
        self.primary = primary
        self.badge = ""
        self.images = {}          # imagens da skin: tipo -> {estado: QPixmap}
        self.setCheckable(checkable)
        self.setToolTip(tip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.apply_theme(theme)

    def apply_theme(self, theme, images=None):
        self.theme = theme
        if images is not None:
            self.images = images
        self.update()

    def set_kind(self, kind):
        if kind != self.kind:
            self.kind = kind
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self.theme
        down = self.isDown()
        imgs = self.images.get(self.kind)
        if imgs:   # botão desenhado por imagens da skin
            state = ""
            if self.isCheckable() and self.isChecked() and "on" in imgs:
                state = "on"
            elif down and "down" in imgs:
                state = "down"
            elif self.underMouse() and "hover" in imgs:
                state = "hover"
            pm = imgs.get(state) or imgs.get("")
            if pm is not None:
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                p.drawPixmap(self.rect(), pm)
                return
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        if down:
            r.translate(0, 1)
        glyph = QColor(t.glyph)
        if t.button_style == "round":
            radius = min(r.width(), r.height()) / 2
            if self.primary:
                g = QRadialGradient(r.center().x(), r.top() + r.height() * 0.3, r.height() * 0.75)
                g.setColorAt(0, QColor(t.play_light))
                g.setColorAt(0.45, QColor(t.play_mid))
                g.setColorAt(1, QColor(t.play_dark))
                p.setPen(QPen(QColor("#ffffff"), 2))
                glyph = QColor("#ffffff")
            else:
                g = QLinearGradient(0, r.top(), 0, r.bottom())
                g.setColorAt(0, QColor(t.btn_top))
                g.setColorAt(0.5, QColor(t.btn_mid))
                g.setColorAt(0.51, QColor(t.btn_low))
                g.setColorAt(1, QColor(t.btn_end))
                p.setPen(QPen(QColor(t.btn_border), 1.2))
            p.setBrush(QBrush(g))
            p.drawRoundedRect(r, radius, radius)
            if self.underMouse() and not down:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, 70))
                p.drawRoundedRect(r, radius, radius)
        else:
            g = QLinearGradient(0, r.top(), 0, r.bottom())
            g.setColorAt(0, QColor(t.btn_top))
            g.setColorAt(0.48, QColor(t.btn_mid))
            g.setColorAt(0.52, QColor(t.btn_low))
            g.setColorAt(1, QColor(t.btn_end))
            p.setPen(QPen(QColor(t.btn_border), 1.2))
            p.setBrush(QBrush(g))
            p.drawRoundedRect(r, 6, 6)
            p.setPen(QPen(QColor(255, 255, 255, 200), 1))
            p.drawLine(QPointF(r.left() + 5, r.top() + 1.5), QPointF(r.right() - 5, r.top() + 1.5))
            if self.underMouse() and not down:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, 60))
                p.drawRoundedRect(r, 6, 6)
            if self.primary:  # luzinha de "ligado"
                led = QColor("#5cff4a") if self.kind == "pause" else QColor("#3a4a3a")
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(led)
                p.drawEllipse(QPointF(r.left() + 11, r.center().y()), 3.5, 3.5)
        if self.isCheckable() and self.isChecked():
            glyph = QColor(t.accent).darker(115)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(t.accent))
            p.drawEllipse(QPointF(r.center().x(), r.bottom() - 4), 2.4, 2.4)
        cx = r.center().x() + (6 if (self.primary and t.button_style == "rect") else 0)
        self._glyph(p, QPointF(cx, r.center().y()), min(r.width(), r.height()) * 0.40 / 12.0, glyph)

    def _glyph(self, p, c, s, color):
        p.save()
        p.translate(c)
        p.scale(s, s)
        pen = QPen(color, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        k = self.kind
        poly = lambda *pts: p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
        if k == "play":
            poly((-6, -9), (9, 0), (-6, 9))
        elif k == "pause":
            p.drawRoundedRect(QRectF(-8, -9, 5.5, 18), 1.2, 1.2)
            p.drawRoundedRect(QRectF(2.5, -9, 5.5, 18), 1.2, 1.2)
        elif k == "stop":
            p.drawRoundedRect(QRectF(-8, -8, 16, 16), 2, 2)
        elif k == "prev":
            p.drawRect(QRectF(-10, -9, 3, 18))
            poly((10, -9), (10, 9), (-6, 0))
        elif k == "next":
            p.drawRect(QRectF(7, -9, 3, 18))
            poly((-10, -9), (-10, 9), (6, 0))
        elif k in ("shuffle", "repeat"):
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(pen)
            if k == "shuffle":
                for sign in (1, -1):
                    path = QPainterPath(QPointF(-10, 6 * sign))
                    path.lineTo(-4, 6 * sign)
                    path.cubicTo(QPointF(0, 6 * sign), QPointF(0, -6 * sign), QPointF(4, -6 * sign))
                    path.lineTo(8, -6 * sign)
                    p.drawPath(path)
                    p.setBrush(color)
                    p.setPen(Qt.PenStyle.NoPen)
                    poly((6, -6 * sign - 3.5), (11, -6 * sign), (6, -6 * sign + 3.5))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(pen)
            else:
                path = QPainterPath(QPointF(-9, 1))
                path.lineTo(-9, -3)
                path.quadTo(-9, -7, -5, -7)
                path.lineTo(7, -7)
                p.drawPath(path)
                path = QPainterPath(QPointF(9, -1))
                path.lineTo(9, 3)
                path.quadTo(9, 7, 5, 7)
                path.lineTo(-7, 7)
                p.drawPath(path)
                p.setBrush(color)
                p.setPen(Qt.PenStyle.NoPen)
                poly((4, -11), (10, -7), (4, -3))
                poly((-4, 3), (-10, 7), (-4, 11))
                if self.badge:
                    f = QFont(self.theme.font)
                    f.setPixelSize(10)
                    f.setBold(True)
                    p.setFont(f)
                    p.drawText(QRectF(-6, -5, 12, 10), Qt.AlignmentFlag.AlignCenter, self.badge)
        elif k == "folder":
            path = QPainterPath(QPointF(-11, -6))
            path.lineTo(-4, -6)
            path.lineTo(-2, -3)
            path.lineTo(10, -3)
            path.lineTo(10, 8)
            path.lineTo(-11, 8)
            path.closeSubpath()
            p.drawPath(path)
        elif k == "gear":
            for i in range(8):
                p.save()
                p.rotate(i * 45)
                p.drawRoundedRect(QRectF(-2.4, -11, 4.8, 6), 1, 1)
                p.restore()
            p.drawEllipse(QPointF(0, 0), 7.6, 7.6)
            p.setBrush(QColor(255, 255, 255, 235))
            p.drawEllipse(QPointF(0, 0), 3, 3)
        elif k == "plus":
            p.setPen(pen)
            p.drawLine(QPointF(-8, 0), QPointF(8, 0))
            p.drawLine(QPointF(0, -8), QPointF(0, 8))
        elif k == "dots":
            for x in (-8, 0, 8):
                p.drawEllipse(QPointF(x, 0), 2.4, 2.4)
        elif k == "theme":
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(pen)
            p.drawEllipse(QPointF(0, 0), 9, 9)
            p.setBrush(color)
            path = QPainterPath()
            path.moveTo(0, -9)
            path.arcTo(QRectF(-9, -9, 18, 18), 90, 180)
            path.closeSubpath()
            p.drawPath(path)
        elif k == "min":
            p.setPen(pen)
            p.drawLine(QPointF(-7, 6), QPointF(7, 6))
        elif k == "close":
            p.setPen(pen)
            p.drawLine(QPointF(-7, -7), QPointF(7, 7))
            p.drawLine(QPointF(-7, 7), QPointF(7, -7))
        elif k in ("left", "right"):
            p.setPen(pen)
            sgn = -1 if k == "left" else 1
            p.drawPolyline(QPolygonF([QPointF(-4 * sgn, -8), QPointF(4 * sgn, 0), QPointF(-4 * sgn, 8)]))
        elif k == "video":
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(pen)
            p.drawRoundedRect(QRectF(-11, -7, 14, 14), 2.5, 2.5)
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            poly((6, -2), (11, -6), (11, 6), (6, 2))
        elif k == "playlist":
            p.setPen(pen)
            for y in (-7, 0, 7):
                p.drawLine(QPointF(-4, y), QPointF(10, y))
            p.setPen(Qt.PenStyle.NoPen)
            for y in (-7, 0, 7):
                p.drawEllipse(QPointF(-9, y), 1.6, 1.6)
        elif k == "eq":       # três barrinhas com botões, como uma mesa de som
            p.setPen(pen)
            for x, ky in ((-8, 3), (0, -4), (8, 1)):
                p.drawLine(QPointF(x, -9), QPointF(x, 9))
            p.setPen(Qt.PenStyle.NoPen)
            for x, ky in ((-8, 3), (0, -4), (8, 1)):
                p.drawRoundedRect(QRectF(x - 4, ky - 2.5, 8, 5), 1.5, 1.5)
        elif k == "mini":     # janelinha dentro de uma janela
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(pen)
            p.drawRoundedRect(QRectF(-11, -9, 22, 18), 2.5, 2.5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(0, 0, 9, 6.5), 1.2, 1.2)
        elif k in ("speaker", "mute"):
            poly((-10, -3.5), (-5, -3.5), (1, -9), (1, 9), (-5, 3.5), (-10, 3.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(pen)
            p.drawArc(QRectF(-1, -5, 10, 10), -50 * 16, 100 * 16)
            p.drawArc(QRectF(-3, -9, 18, 18), -50 * 16, 100 * 16)
        p.restore()


# ------------------------------------------------------------------ barras deslizantes
class RetroSlider(QSlider):
    userMoved = Signal(int)      # quando a pessoa arrasta ou clica
    userReleased = Signal(int)   # quando solta

    def __init__(self, theme, minimum=0, maximum=1000, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.theme = theme
        self.setRange(minimum, maximum)
        self.dragging = False
        self.images = {}          # groove, fill, handle (QPixmap) vindos da skin
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def apply_theme(self, theme, images=None):
        self.theme = theme
        if images is not None:
            self.images = images
        self.update()

    def _from_x(self, x):
        m = 12
        v = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), int(x - m), max(1, self.width() - 2 * m))
        self.setValue(v)
        self.userMoved.emit(v)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self._from_x(e.position().x())
            e.accept()

    def mouseMoveEvent(self, e):
        if self.dragging:
            self._from_x(e.position().x())
            e.accept()

    def mouseReleaseEvent(self, e):
        if self.dragging:
            self.dragging = False
            self.userReleased.emit(self.value())
            e.accept()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self.theme
        m = 12
        span = max(1, self.maximum() - self.minimum())
        frac = (self.value() - self.minimum()) / span
        cy = self.height() / 2
        x0, x1 = m, self.width() - m
        hx = x0 + (x1 - x0) * frac
        if "groove" in self.images:
            im = self.images
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            gh = min(im["groove"].height(), self.height())
            groove = QRectF(x0 - 4, cy - gh / 2, x1 - x0 + 8, gh)
            p.drawPixmap(groove, im["groove"], QRectF(im["groove"].rect()))
            if "fill" in im:
                p.save()
                p.setClipRect(QRectF(groove.left(), groove.top(), max(0.0, hx - groove.left()), gh))
                p.drawPixmap(groove, im["fill"], QRectF(im["fill"].rect()))
                p.restore()
            if "handle" in im:
                hh = min(im["handle"].height(), self.height())
                hw = im["handle"].width() * hh / max(1, im["handle"].height())
                p.drawPixmap(QRectF(hx - hw / 2, cy - hh / 2, hw, hh), im["handle"], QRectF(im["handle"].rect()))
            return
        if t.button_style == "round":
            gh = 10
            groove = QRectF(x0 - 4, cy - gh / 2, x1 - x0 + 8, gh)
            g = QLinearGradient(0, groove.top(), 0, groove.bottom())
            g.setColorAt(0, QColor(t.groove_a))
            g.setColorAt(1, QColor(t.groove_b))
            p.setPen(QPen(QColor(60, 120, 170, 120), 1))
            p.setBrush(QBrush(g))
            p.drawRoundedRect(groove, 5, 5)
            fill = QRectF(groove.left(), groove.top(), hx - groove.left() + 2, gh)
            g2 = QLinearGradient(0, fill.top(), 0, fill.bottom())
            g2.setColorAt(0, QColor(t.fill_a))
            g2.setColorAt(1, QColor(t.fill_b))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g2))
            p.drawRoundedRect(fill, 5, 5)
            hr = 10 if not self.dragging else 11
            rg = QRadialGradient(hx - 3, cy - 4, hr * 1.5)
            rg.setColorAt(0, QColor(t.knob_a))
            rg.setColorAt(0.6, QColor(t.btn_mid))
            rg.setColorAt(1, QColor(t.knob_b))
            p.setPen(QPen(QColor(40, 100, 160, 160), 1))
            p.setBrush(QBrush(rg))
            p.drawEllipse(QPointF(hx, cy), hr, hr)
        else:
            gh = 12
            groove = QRectF(x0 - 4, cy - gh / 2, x1 - x0 + 8, gh)
            p.setPen(QPen(QColor(t.groove_b), 1))
            p.setBrush(QColor(t.groove_a))
            p.drawRoundedRect(groove, 3, 3)
            g2 = QLinearGradient(0, groove.top(), 0, groove.bottom())
            g2.setColorAt(0, QColor(t.fill_a))
            g2.setColorAt(1, QColor(t.fill_b))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g2))
            p.drawRect(QRectF(groove.left() + 2, groove.top() + 2, max(0, hx - groove.left() - 2), gh - 4))
            hand = QRectF(hx - 8, cy - 12, 16, 24)
            g = QLinearGradient(hand.left(), 0, hand.right(), 0)
            g.setColorAt(0, QColor(t.knob_b))
            g.setColorAt(0.5, QColor(t.knob_a))
            g.setColorAt(1, QColor(t.knob_b))
            p.setPen(QPen(QColor("#5b6168"), 1))
            p.setBrush(QBrush(g))
            p.drawRoundedRect(hand, 3, 3)


# ------------------------------------------------------------------ visor LCD
class LcdPanel(QWidget):
    """Fundo do visor (vidro azul ou LCD verde)."""

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self.theme
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        radius = 24 if t.button_style == "round" else 8
        g = QLinearGradient(0, r.top(), 0, r.bottom())
        g.setColorAt(0, QColor(t.lcd_top))
        g.setColorAt(1, QColor(t.lcd_bottom))
        p.setPen(QPen(QColor(t.lcd_border), 2))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(r, radius, radius)
        sh = QLinearGradient(0, r.top(), 0, r.top() + 22)
        sh.setColorAt(0, QColor(0, 40, 90, 70 if t.button_style == "round" else 150))
        sh.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(sh))
        p.drawRoundedRect(QRectF(r.left() + 2, r.top() + 2, r.width() - 4, 24), radius, radius)


class InfoWidget(QWidget):
    """Tempo, formato, título e artista da música atual (o título rola se for longo)."""

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.fmt = ""
        self.status = "PARADO"
        self.time = "00:00"
        self.total = "00:00"
        self.title = "Nenhuma música"
        self.artist = "Abra um arquivo ou adicione uma pasta"
        self.offset = 0.0
        self.cover = None             # QPixmap da capa do álbum (ou None)
        self.show_cover = True
        self.compact = False          # visual do modo mini
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._scroll)

    def set_theme(self, theme):
        self.theme = theme
        self.update()

    def set_info(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
            if k == "title":
                self.offset = 0.0
        self._check_marquee()
        self.update()

    COVER = 92          # lado da capa no visor de 124 px de altura
    COVER_MIN_W = 380   # abaixo dessa largura não sobra espaço para a capa

    def set_cover(self, image):
        """Recebe um QImage (ou None) com a capa do álbum."""
        self.cover = QPixmap.fromImage(image) if image is not None and not image.isNull() else None
        self._check_marquee()
        self.update()

    def set_show_cover(self, on):
        self.show_cover = bool(on)
        self._check_marquee()
        self.update()

    def set_compact(self, on):
        self.compact = bool(on)
        self.offset = 0.0
        self._check_marquee()
        self.update()

    def _cover_visible(self):
        if self.compact:
            return self.show_cover and self.cover is not None and self.width() >= 260
        return (self.show_cover and self.cover is not None
                and self.width() / self._scale() >= self.COVER_MIN_W)

    def _text_width(self):
        """Largura (nas medidas de 124 px de altura) que sobra para título e artista."""
        w = self.width() / self._scale()
        if self.compact:
            return w - 104 - (self.height() + 8 if self._cover_visible() else 0)
        return w - (self.COVER + 14) if self._cover_visible() else w

    def _title_font(self):
        f = QFont(self.theme.font)
        f.setPixelSize(16 if self.compact else 18)
        f.setBold(True)
        return f

    def _scale(self):
        """O visor foi desenhado para 124 px de altura; em outras alturas, tudo encolhe ou cresce junto."""
        if self.compact:
            return 1.0
        return max(0.5, min(1.4, self.height() / 124.0))

    def _check_marquee(self):
        need = QFontMetrics(self._title_font()).horizontalAdvance(self.title) > self._text_width() - 8
        if need and not self._timer.isActive():
            self._timer.start()
        elif not need and self._timer.isActive():
            self._timer.stop()
            self.offset = 0.0

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._check_marquee()

    def _scroll(self):
        tw = QFontMetrics(self._title_font()).horizontalAdvance(self.title) + 70
        self.offset = (self.offset + 0.9) % tw
        self.update()

    def _paint_compact(self, p):
        """Visor do modo mini: capa à esquerda, título e artista no meio, tempo à direita."""
        t = self.theme
        w, h = self.width(), self.height()
        x0 = 0
        if self._cover_visible():
            side = h
            box = QRectF(0, 0, side, side)
            src = self.cover
            scale = max(side / src.width(), side / src.height())
            sw = side / scale
            crop = QRectF((src.width() - sw) / 2, (src.height() - sw) / 2, sw, sw)
            clip = QPainterPath()
            clip.addRoundedRect(box, 6, 6)
            p.save()
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.setClipPath(clip)
            p.drawPixmap(box, src, crop)
            p.restore()
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 170) if t.button_style == "round" else QColor(t.lcd_border), 1.2))
            p.drawRoundedRect(box, 6, 6)
            x0 = side + 8
        tw = w - x0 - 104
        small = QFont(t.font)
        small.setPixelSize(10)
        small.setBold(True)
        p.setFont(small)
        p.setPen(QColor(t.lcd_dim))
        top = " · ".join(x for x in (self.status, self.fmt) if x)
        p.drawText(QRectF(x0, 0, tw, 13), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   QFontMetrics(small).elidedText(top, Qt.TextElideMode.ElideRight, int(tw)))
        p.save()
        p.setClipRect(QRectF(x0, 14, tw, 22))
        f = self._title_font()
        p.setFont(f)
        p.setPen(QColor(t.lcd_text))
        fm = QFontMetrics(f)
        y = 14 + fm.ascent() + 1
        if self._timer.isActive():
            p.drawText(QPointF(x0 - self.offset, y), self.title)
            p.drawText(QPointF(x0 - self.offset + fm.horizontalAdvance(self.title) + 70, y), self.title)
        else:
            p.drawText(int(x0), int(y), self.title)
        p.restore()
        a = QFont(t.font)
        a.setPixelSize(12)
        p.setFont(a)
        p.setPen(QColor(t.lcd_dim))
        p.drawText(QRectF(x0, 36, tw, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   QFontMetrics(a).elidedText(self.artist, Qt.TextElideMode.ElideRight, int(tw)))
        big = QFont(t.mono)
        big.setPixelSize(27)
        big.setStyleHint(QFont.StyleHint.Monospace)
        p.setFont(big)
        p.setPen(QColor(t.lcd_text))
        p.drawText(QRectF(w - 104, 0, 104, 32), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self.time)
        mid = QFont(t.mono)
        mid.setPixelSize(13)
        p.setFont(mid)
        p.setPen(QColor(t.lcd_dim))
        p.drawText(QRectF(w - 104, 32, 104, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"/ {self.total}")

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        if self.compact:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._paint_compact(p)
            return
        t = self.theme
        k = self._scale()
        p.scale(k, k)
        w = self.width() / k
        small = QFont(t.font)
        small.setPixelSize(12)
        small.setBold(True)
        p.setFont(small)
        p.setPen(QColor(t.lcd_dim))
        p.drawText(QRectF(0, 0, w * 0.7, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.fmt)
        p.drawText(QRectF(0, 0, w, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self.status)

        big = QFont(t.mono)
        big.setPixelSize(54)
        big.setStyleHint(QFont.StyleHint.Monospace)
        p.setFont(big)
        p.setPen(QColor(t.lcd_text))
        fm = QFontMetrics(big)
        p.drawText(0, 18 + fm.ascent() - 6, self.time)
        tw = fm.horizontalAdvance(self.time)
        mid = QFont(t.mono)
        mid.setPixelSize(24)
        p.setFont(mid)
        p.setPen(QColor(t.lcd_dim))
        p.drawText(tw + 10, 18 + fm.ascent() - 6, f"/ {self.total}")

        text_w = self._text_width()
        if self._cover_visible():
            side = self.COVER
            box = QRectF(w - side, 22, side, side)
            src = self.cover
            scale = max(side / src.width(), side / src.height())
            sw, sh = side / scale, side / scale
            crop = QRectF((src.width() - sw) / 2, (src.height() - sh) / 2, sw, sh)
            clip = QPainterPath()
            clip.addRoundedRect(box, 9, 9)
            p.save()
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.setClipPath(clip)
            p.drawPixmap(box, src, crop)
            p.restore()
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 190) if t.button_style == "round" else QColor(t.lcd_border), 1.6))
            p.drawRoundedRect(box, 9, 9)
            gl = QLinearGradient(0, box.top(), 0, box.top() + side * 0.5)
            gl.setColorAt(0, QColor(255, 255, 255, 70 if t.button_style == "round" else 28))
            gl.setColorAt(1, QColor(255, 255, 255, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(gl))
            gloss = QPainterPath()
            gloss.addRoundedRect(box, 9, 9)
            p.save()
            p.setClipPath(gloss)
            p.drawRect(QRectF(box.left(), box.top(), side, side * 0.5))
            p.restore()

        p.save()
        p.setClipRect(QRectF(0, 76, text_w, 28))
        p.setFont(self._title_font())
        p.setPen(QColor(t.lcd_text))
        fm2 = QFontMetrics(self._title_font())
        y = 76 + fm2.ascent() + 2
        if self._timer.isActive():
            p.drawText(QPointF(-self.offset, y), self.title)
            p.drawText(QPointF(-self.offset + fm2.horizontalAdvance(self.title) + 70, y), self.title)
        else:
            p.drawText(0, int(y), self.title)
        p.restore()

        a = QFont(t.font)
        a.setPixelSize(13)
        p.setFont(a)
        p.setPen(QColor(t.lcd_dim))
        p.drawText(QRectF(0, 102, text_w, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   QFontMetrics(a).elidedText(self.artist, Qt.TextElideMode.ElideRight, int(text_w)))


# ------------------------------------------------------------------ vídeo
class VideoSurface(QWidget):
    """Mostra os quadros do vídeo. Clique duplo alterna tela cheia."""
    doubleClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.img = None
        self.setMinimumHeight(24)
        self.setStyleSheet("background: #000;")

    def set_frame(self, img):
        self.img = img
        if self.isVisible():
            self.update()

    def clear(self):
        self.img = None
        self.update()

    def mouseDoubleClickEvent(self, _e):
        self.doubleClicked.emit()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Escape, Qt.Key.Key_F):
            self.doubleClicked.emit()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0))
        if self.img is not None and not self.img.isNull():
            size = self.img.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            x = (self.width() - size.width()) // 2
            y = (self.height() - size.height()) // 2
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.drawImage(QRectF(x, y, size.width(), size.height()), self.img)


# ------------------------------------------------------------------ lista de faixas
class TrackDelegate(QStyledItemDelegate):
    def __init__(self, theme, library, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.library = library
        self.playing_path = ""

    def sizeHint(self, option, index):
        return QSize(0, 32)

    def paint(self, p, option, index):
        t = self.theme
        path = index.data(Qt.ItemDataRole.UserRole)
        track = self.library.get(path)
        r = QRectF(option.rect).adjusted(2, 1, -2, -1)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if selected:
            g = QLinearGradient(0, r.top(), 0, r.bottom())
            g.setColorAt(0, QColor(t.list_sel_top))
            g.setColorAt(1, QColor(t.list_sel_bottom))
            p.setPen(QPen(QColor(t.list_border), 1))
            p.setBrush(QBrush(g))
            p.drawRoundedRect(r, 6, 6)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            hover = QColor(t.list_sel_bottom)
            hover.setAlpha(110)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(hover)
            p.drawRoundedRect(r, 6, 6)
        main = QColor(t.list_sel_text if selected else t.list_text)
        dim = QColor(t.list_dim if not selected else t.list_sel_text)
        playing = path == self.playing_path
        f = QFont(t.font)
        f.setPixelSize(11)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(t.accent) if playing else dim)
        tag = "▶" if playing else (track.tag if track else "")
        p.drawText(QRectF(r.left() + 6, r.top(), 40, r.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, tag)
        dur = ""
        if track and track.duration:
            m, s = divmod(int(track.duration), 60)
            dur = f"{m}:{s:02d}"
        f.setBold(False)
        p.setFont(f)
        p.setPen(dim)
        p.drawText(QRectF(r.right() - 52, r.top(), 46, r.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, dur)
        f2 = QFont(t.font)
        f2.setPixelSize(13)
        f2.setBold(playing)
        p.setFont(f2)
        p.setPen(main)
        label = track.label if track else str(path).replace("\\", "/").split("/")[-1]
        width = int(r.width() - 46 - 58)
        p.drawText(QRectF(r.left() + 46, r.top(), width, r.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   QFontMetrics(f2).elidedText(label, Qt.TextElideMode.ElideRight, width))
        p.restore()
