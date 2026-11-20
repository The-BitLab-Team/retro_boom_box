"""Janela do equalizador: 10 faixas, pré-amplificação, curva de resposta e presets.

Tudo vale na hora (sem botão de OK). As escolhas ficam salvas nas configurações.
"""
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from .equalizer import BANDS, GAIN_RANGE, LABELS, PRESETS, curve_db

CUSTOM = "Personalizado"


class EqSlider(QWidget):
    """Barra deslizante vertical de -12 dB a +12 dB (clique duplo volta para 0)."""
    userChanged = Signal(float)

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.value = 0.0
        self.setMinimumSize(40, 150)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_theme(self, theme):
        self.theme = theme
        self.update()

    def set_value(self, v):
        self.value = max(-GAIN_RANGE, min(GAIN_RANGE, round(float(v) * 2) / 2))
        self.update()

    def _track(self):
        return 14.0, self.height() - 14.0

    def _from_y(self, y):
        top, bottom = self._track()
        frac = 1.0 - (y - top) / max(1.0, bottom - top)
        v = round((frac * 2 - 1) * GAIN_RANGE * 2) / 2
        v = max(-GAIN_RANGE, min(GAIN_RANGE, v))
        if v != self.value:
            self.value = v
            self.update()
            self.userChanged.emit(v)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._from_y(e.position().y())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._from_y(e.position().y())

    def mouseDoubleClickEvent(self, e):
        self.value = 0.0
        self.update()
        self.userChanged.emit(0.0)

    def wheelEvent(self, e):
        step = 1.0 if e.angleDelta().y() > 0 else -1.0
        v = max(-GAIN_RANGE, min(GAIN_RANGE, self.value + step))
        if v != self.value:
            self.value = v
            self.update()
            self.userChanged.emit(v)
        e.accept()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self.theme
        top, bottom = self._track()
        cx = self.width() / 2
        mid = (top + bottom) / 2
        frac = (self.value + GAIN_RANGE) / (2 * GAIN_RANGE)
        hy = bottom - (bottom - top) * frac
        groove = QRectF(cx - 4, top - 2, 8, bottom - top + 4)
        g = QLinearGradient(groove.left(), 0, groove.right(), 0)
        g.setColorAt(0, QColor(t.groove_a))
        g.setColorAt(1, QColor(t.groove_b))
        p.setPen(QPen(QColor(t.field_border), 1))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(groove, 4, 4)
        # marcas de 6 em 6 dB
        p.setPen(QPen(QColor(t.dialog_text).lighter(150), 1))
        for db in (-12, -6, 0, 6, 12):
            y = bottom - (bottom - top) * (db + GAIN_RANGE) / (2 * GAIN_RANGE)
            half = 9 if db == 0 else 5
            p.setOpacity(0.55 if db == 0 else 0.3)
            p.drawLine(QPointF(cx - 10 - half + 5, y), QPointF(cx - 10, y))
            p.drawLine(QPointF(cx + 10, y), QPointF(cx + 10 + half - 5, y))
        p.setOpacity(1.0)
        # parte "preenchida" entre o zero e a posição da barra
        fg = QLinearGradient(0, top, 0, bottom)
        fg.setColorAt(0, QColor(t.fill_a))
        fg.setColorAt(1, QColor(t.fill_b))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(fg))
        y0, y1 = sorted((mid, hy))
        p.drawRoundedRect(QRectF(cx - 3, y0, 6, max(1.0, y1 - y0)), 2.5, 2.5)
        # botão
        if t.button_style == "round":
            r = 10
            rg = QRadialGradient(cx - 2, hy - 3, r * 1.4)
            rg.setColorAt(0, QColor(t.knob_a))
            rg.setColorAt(1, QColor(t.knob_b))
            p.setPen(QPen(QColor(t.btn_border), 1.2))
            p.setBrush(QBrush(rg))
            p.drawEllipse(QPointF(cx, hy), r, r)
        else:
            kg = QLinearGradient(0, hy - 8, 0, hy + 8)
            kg.setColorAt(0, QColor(t.knob_a))
            kg.setColorAt(1, QColor(t.knob_b))
            p.setPen(QPen(QColor(t.btn_border), 1.2))
            p.setBrush(QBrush(kg))
            p.drawRoundedRect(QRectF(cx - 12, hy - 7, 24, 14), 3, 3)
            p.setPen(QPen(QColor(t.btn_border), 1))
            p.drawLine(QPointF(cx - 6, hy), QPointF(cx + 6, hy))


class EqCurve(QWidget):
    """Desenho da curva de resposta: mostra como o som fica depois do equalizador."""

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.gains = [0.0] * 10
        self.preamp = 0.0
        self.active = True
        self.setMinimumHeight(86)

    def set_data(self, gains, preamp, active):
        self.gains, self.preamp, self.active = list(gains), preamp, active
        self.update()

    def set_theme(self, theme):
        self.theme = theme
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self.theme
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        bg = QLinearGradient(0, r.top(), 0, r.bottom())
        bg.setColorAt(0, QColor(t.lcd_top))
        bg.setColorAt(1, QColor(t.lcd_bottom))
        p.setPen(QPen(QColor(t.field_border), 1.2))
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(r, 8, 8)
        inner = r.adjusted(8, 8, -8, -8)
        lo, hi = np.log10(20.0), np.log10(20000.0)
        xs = lambda f: inner.left() + (np.log10(f) - lo) / (hi - lo) * inner.width()
        ys = lambda db: inner.center().y() - float(db) / GAIN_RANGE * inner.height() / 2
        # grade
        p.setPen(QPen(QColor(t.lcd_dim), 1))
        for db in (-12, 0, 12):
            p.setOpacity(0.55 if db == 0 else 0.22)
            p.drawLine(QPointF(inner.left(), ys(db)), QPointF(inner.right(), ys(db)))
        for f in BANDS:
            p.setOpacity(0.14)
            p.drawLine(QPointF(xs(f), inner.top()), QPointF(xs(f), inner.bottom()))
        p.setOpacity(1.0 if self.active else 0.4)
        freqs = np.geomspace(20, 20000, 160)
        db = np.clip(curve_db(self.gains, freqs) + self.preamp, -GAIN_RANGE, GAIN_RANGE)
        path = QPainterPath(QPointF(xs(freqs[0]), ys(db[0])))
        for f, d in zip(freqs[1:], db[1:]):
            path.lineTo(QPointF(xs(f), ys(d)))
        fill = QPainterPath(path)
        fill.lineTo(QPointF(xs(freqs[-1]), ys(0)))
        fill.lineTo(QPointF(xs(freqs[0]), ys(0)))
        fill.closeSubpath()
        c = QColor(t.lcd_text)
        c.setAlpha(55)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawPath(fill)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(t.lcd_text), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)


class EqDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.s = main.settings
        self.setWindowTitle("Equalizador")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(640)
        t = main.theme

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        top = QHBoxLayout()
        self.on = QCheckBox("Equalizador ligado")
        self.on.toggled.connect(self._on_toggle)
        top.addWidget(self.on)
        top.addStretch()
        self.combo = QComboBox()
        self.combo.setMinimumWidth(170)
        self.combo.activated.connect(self._on_preset)
        top.addWidget(self.combo)
        self.btn_save = QPushButton("Salvar…")
        self.btn_save.setToolTip("Guardar estas configurações como um preset seu")
        self.btn_save.clicked.connect(self._save_preset)
        top.addWidget(self.btn_save)
        self.btn_del = QPushButton("Excluir")
        self.btn_del.clicked.connect(self._delete_preset)
        top.addWidget(self.btn_del)
        self.btn_reset = QPushButton("Zerar")
        self.btn_reset.clicked.connect(lambda: self._apply_preset("Plano"))
        top.addWidget(self.btn_reset)
        root.addLayout(top)

        self.curve = EqCurve(t)
        root.addWidget(self.curve)

        grid = QHBoxLayout()
        grid.setSpacing(2)
        self.sliders = []
        self.value_labels = []
        grid.addLayout(self._column("Pré", self._make_pre(t)))
        grid.addSpacing(10)
        for i, label in enumerate(LABELS):
            sl = EqSlider(t)
            sl.userChanged.connect(lambda v, k=i: self._on_band(k, v))
            self.sliders.append(sl)
            grid.addLayout(self._column(label, sl))
        root.addLayout(grid, 1)

        self.default_note = ("Frequências em Hz (1k = 1.000 Hz). O equalizador vale para músicas; vídeos tocam sem ele. "
                             "Clique duas vezes numa barra para voltar a 0 dB.")
        self.note = QLabel(self.default_note)
        self.note.setWordWrap(True)
        self.note.setStyleSheet("font-size: 12px;")
        root.addWidget(self.note)
        row = QHBoxLayout()
        row.addStretch()
        close = QPushButton("Fechar")
        close.clicked.connect(self.close)
        row.addWidget(close)
        root.addLayout(row)

        self.refresh()

    # ------------------------------------------------------------ montagem
    def _make_pre(self, theme):
        self.pre = EqSlider(theme)
        self.pre.userChanged.connect(self._on_pre)
        return self.pre

    def _column(self, name, slider):
        col = QVBoxLayout()
        col.setSpacing(2)
        val = QLabel("0")
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont(val.font())
        f.setPixelSize(11)
        f.setBold(True)
        val.setFont(f)
        self.value_labels.append(val)
        col.addWidget(val)
        col.addWidget(slider, 1)
        lab = QLabel(name)
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setFont(f)
        col.addWidget(lab)
        return col

    # ------------------------------------------------------------ estado
    def gains(self):
        return list(self.s["eq_gains"])

    def _all_presets(self):
        presets = {k: [float(v) for v in g] for k, g in PRESETS.items()}
        presets.update({k: list(g) for k, g in self.s["eq_user"].items()})
        return presets

    def _match_preset(self):
        g = self.gains()
        if abs(self.s["eq_preamp"]) > 0.01:
            return CUSTOM
        for name, vals in self._all_presets().items():
            if all(abs(a - b) < 0.01 for a, b in zip(g, vals)):
                return name
        return CUSTOM

    def refresh(self):
        """Puxa tudo das configurações para a tela (sem mexer no que toca)."""
        self.on.blockSignals(True)
        self.on.setChecked(bool(self.s["eq_on"]))
        self.on.blockSignals(False)
        g = self.gains()
        for sl, v in zip(self.sliders, g):
            sl.set_value(v)
        self.pre.set_value(self.s["eq_preamp"])
        name = self._match_preset()
        self.s["eq_preset"] = name
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(list(PRESETS) + list(self.s["eq_user"]) + ([CUSTOM] if name == CUSTOM else []))
        self.combo.setCurrentText(name)
        self.combo.blockSignals(False)
        self.btn_del.setEnabled(name in self.s["eq_user"])
        for lab, v in zip(self.value_labels, [self.s["eq_preamp"]] + g):
            lab.setText(f"{v:+g}" if abs(v) >= 0.05 else "0")
        self.curve.set_data(g, self.s["eq_preamp"], bool(self.s["eq_on"]))
        self.note.setText(self.main.eq_notice or self.default_note)
        self.set_theme(self.main.theme)

    def set_theme(self, theme):
        for w in (self.curve, self.pre, *self.sliders):
            w.set_theme(theme)

    def _commit(self, save=True):
        self.main.apply_eq()
        if save:
            self.s.save()
        self.refresh()

    # ------------------------------------------------------------ ações
    def _on_toggle(self, on):
        self.s["eq_on"] = bool(on)
        if on:
            self.main.eq_notice = ""
        self._commit()

    def _on_band(self, k, v):
        g = self.gains()
        g[k] = v
        self.s["eq_gains"] = g
        self._commit()

    def _on_pre(self, v):
        self.s["eq_preamp"] = v
        self._commit()

    def _apply_preset(self, name):
        vals = self._all_presets().get(name)
        if vals is None:
            return
        self.s["eq_gains"] = list(vals)
        self.s["eq_preamp"] = 0.0
        self._commit()

    def _on_preset(self, index):
        name = self.combo.itemText(index)
        if name != CUSTOM:
            self._apply_preset(name)
            if not self.s["eq_on"]:       # escolher um preset é sinal de que a pessoa quer usá-lo
                self.s["eq_on"] = True
                self._commit()

    def _save_preset(self):
        name, ok = QInputDialog.getText(self, "Salvar preset", "Nome do preset:")
        name = name.strip()[:40]
        if not ok or not name:
            return
        if name in PRESETS or name == CUSTOM:
            QMessageBox.information(self, "Salvar preset", "Esse nome já é de um preset do programa. Escolha outro.")
            return
        user = dict(self.s["eq_user"])
        user[name] = self.gains()
        self.s["eq_user"] = user
        self._commit()

    def _delete_preset(self):
        name = self.combo.currentText()
        if name in self.s["eq_user"]:
            user = dict(self.s["eq_user"])
            del user[name]
            self.s["eq_user"] = user
            self._commit()

