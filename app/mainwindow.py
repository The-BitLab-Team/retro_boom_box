"""Janela principal do Retro Boom Box.

Todas as peças (botões, visor, lista...) ficam soltas na janela e são colocadas nas
posições que a skin manda (`skin.layout`). Trocar de skin é só colocar tudo em outros
lugares, com outras cores e outra imagem de fundo.
"""
import os
import random
import time
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QBrush, QColor, QDesktopServices, QKeySequence, QLinearGradient, QPainter, QPen,
                           QPixmap, QRadialGradient, QShortcut)
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton,
                               QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from .covers import load_cover
from .engine import Engine
from .eq_dialog import EqDialog
from .library import (MEDIA_EXTS, Library, Playlists, ScanThread, Settings, fmt_time, is_media,
                      read_track, walk_media)
from .packs import PackError
from . import __version__, updater
from .settings_dialog import SettingsDialog
from .skins import SkinManager
from .update_dialog import UpdateDialog
from .themes import make_qss
from .visualizers import VisualizerWidget
from .vizpacks import VizPackManager
from .widgets import (InfoWidget, LcdPanel, RetroButton, RetroSlider, TrackDelegate, VideoSurface,
                      rounded_path)

SHADOW = 28
MINI_SHADOW = 18
LIBRARY = "__biblioteca__"


class MainWindow(QWidget):
    scanMessage = Signal(str)
    updateStatus = Signal(str)     # andamento da busca por versões novas (a janela de configurações mostra)

    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.library = Library()
        self.playlists = Playlists()
        self.skins = SkinManager()
        self.skins.scan()
        self.vizpacks = VizPackManager()
        self.vizpacks.scan()
        self.skin = self.skins.get(self.settings["skin"])
        self.theme = self.skin.theme
        self.engine = Engine(self)
        self.queue, self.qi, self.history = [], -1, []
        self.current_path = ""
        self.show_video = False
        self.fail_count = 0
        self.scanner = None
        self.source = self.settings["source"] or LIBRARY
        if self.source != LIBRARY and self.source not in self.playlists.lists:
            self.source = LIBRARY
        self.viz_pack_errors = {}
        self._bg = None
        self._video_btn_in_layout = True
        self.fs_window = None
        self.settings_dialog = None
        self.eq_dialog = None
        self.eq_notice = ""           # último aviso do motor sobre o equalizador (mostrado na janela dele)
        self.update_checker = updater.UpdateChecker(self)
        self.update_checker.done.connect(self._on_update_result)
        self._update_manual = False
        self._update_box = None
        self.mini = bool(self.settings["mini"])

        self.setWindowTitle("Retro Boom Box")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self._set_flags(self.settings["top"])

        self._build_ui()
        self._connect()
        self.reload_viz_packs()
        self.apply_skin(self.skin)
        self.engine.set_volume(self.settings["volume"])
        self.engine.set_fps(self.settings["fps"])
        self.engine.sens = self.settings["sens"] / 100.0
        self.apply_eq()
        self.info.set_show_cover(bool(self.settings["show_cover"]))
        self.viz.set_mode_by_name(self.settings["viz"])
        self._update_viz_label()
        self.refresh_list()

    # ------------------------------------------------------------------ montagem
    def _set_flags(self, on_top: bool):
        flags = Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        if on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def _btn(self, kind, size="md", **kw):
        b = RetroButton(kind, self.theme, size, parent=self, **kw)
        self.btn_by_kind[kind] = b
        return b

    def _build_ui(self):
        t = self.theme
        self.btn_by_kind = {}

        # peças soltas na janela: a skin diz onde cada uma fica
        self.lcd = LcdPanel(t, self)
        self.logo = QLabel("Retro Boom Box", self)
        self.info = InfoWidget(t, self)
        self.stage = QStackedWidget(self)
        self.viz = VisualizerWidget(t)
        self.video = VideoSurface()
        self.stage.addWidget(self.viz)
        self.stage.addWidget(self.video)
        self.lbl_viz = QLabel(self)
        self.lbl_viz.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_theme = self._btn("theme", tip="Trocar de skin")
        self.btn_gear = self._btn("gear", tip="Configurações")
        self.btn_min = self._btn("min", tip="Minimizar")
        self.btn_close = self._btn("close", tip="Fechar")
        self.btn_vprev = self._btn("left", tip="Visualizador anterior")
        self.btn_vnext = self._btn("right", tip="Próximo visualizador")
        self.btn_vid = self._btn("video", tip="Alternar entre vídeo e visualizador")
        self.btn_vid.hide()

        # grupo da lista (fica na janela ou numa janela à parte, conforme a skin)
        self.btn_source = QPushButton("Biblioteca  ▾", self)
        self.btn_source.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_source.setToolTip("Escolher biblioteca ou playlist")
        self.btn_plus = self._btn("plus", tip="Nova playlist")
        self.btn_dots = self._btn("dots", tip="Opções da playlist")
        self.btn_folder = self._btn("folder", tip="Arquivos e pastas")
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Buscar na lista…")
        self.search.setClearButtonEnabled(True)
        self.list = QListWidget(self)
        self.delegate = TrackDelegate(t, self.library, self.list)
        self.list.setItemDelegate(self.delegate)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.list.setMouseTracking(True)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.status = QLabel("", self)
        self.status.setWordWrap(True)
        self.status.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.btn_playlist = self._btn("playlist", tip="Mostrar ou esconder a lista")
        self.btn_eq = self._btn("eq", tip="Equalizador (Ctrl+E)")
        self.btn_mini = self._btn("mini", tip="Modo mini (Ctrl+M)")

        # janela da lista (só usada por skins pequenas, sem espaço para a lista)
        self.pl_window = QWidget(self, Qt.WindowType.Tool)
        self.pl_window.setObjectName("plwin")
        self.pl_window.setWindowTitle("Lista de reprodução")
        self.pl_window.resize(400, 560)
        self.pl_layout = QVBoxLayout(self.pl_window)
        self.pl_layout.setContentsMargins(12, 12, 12, 12)
        self.pl_layout.setSpacing(8)
        self.pl_row = QHBoxLayout()
        self.pl_row.setSpacing(6)

        # barra de progresso e controles
        self.seek = RetroSlider(t, 0, 1000, self)
        self.btn_shuffle = self._btn("shuffle", checkable=True, tip="Ordem aleatória")
        self.btn_prev = self._btn("prev", tip="Faixa anterior")
        self.btn_play = self._btn("play", primary=True, tip="Tocar / Pausar (Espaço)")
        self.btn_stop = self._btn("stop", tip="Parar")
        self.btn_next = self._btn("next", tip="Próxima faixa")
        self.btn_repeat = self._btn("repeat", checkable=True, tip="Repetir: desligado")
        self.btn_mute = self._btn("mute", tip="Silenciar")
        self.vol = RetroSlider(t, 0, 100, self)
        self.vol.setValue(self.settings["volume"])
        self.btn_shuffle.setChecked(bool(self.settings["shuffle"]))
        self._set_repeat(self.settings["repeat"], save=False)

        # nomes usados pelas skins -> botões
        self.skin_buttons = {
            "theme": self.btn_theme, "gear": self.btn_gear, "min": self.btn_min, "close": self.btn_close,
            "left": self.btn_vprev, "right": self.btn_vnext, "video": self.btn_vid,
            "plus": self.btn_plus, "dots": self.btn_dots, "folder": self.btn_folder,
            "shuffle": self.btn_shuffle, "prev": self.btn_prev, "play": self.btn_play, "stop": self.btn_stop,
            "next": self.btn_next, "repeat": self.btn_repeat, "mute": self.btn_mute, "playlist": self.btn_playlist,
            "eq": self.btn_eq, "mini": self.btn_mini,
        }

    def _connect(self):
        e = self.engine
        e.positionChanged.connect(self._on_pos)
        e.durationChanged.connect(lambda ms: self.info.set_info(total=fmt_time(ms / 1000)))
        e.playingChanged.connect(self._on_playing)
        e.finished.connect(lambda: self.next_track(auto=True))
        e.failed.connect(self._on_fail)
        e.hasVideoChanged.connect(self._on_has_video)
        e.loaded.connect(self._on_loaded)
        e.frameReady.connect(self.video.set_frame)
        e.levels.connect(self.viz.feed)
        e.notice.connect(self._on_engine_notice)
        self.viz.packFailed.connect(self._on_pack_failed)

        self.btn_close.clicked.connect(self.close)
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_theme.clicked.connect(self.next_skin)
        self.btn_gear.clicked.connect(self.open_settings)
        self.btn_vprev.clicked.connect(lambda: self.step_viz(-1))
        self.btn_vnext.clicked.connect(lambda: self.step_viz(1))
        self.btn_vid.clicked.connect(self._toggle_video)
        self.video.doubleClicked.connect(self.toggle_fullscreen_video)
        self.btn_playlist.clicked.connect(self._toggle_pl_window)
        self.btn_eq.clicked.connect(self.open_eq)
        self.btn_mini.clicked.connect(self.toggle_mini)

        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_next.clicked.connect(lambda: self.next_track())
        self.btn_prev.clicked.connect(self.prev_track)
        self.btn_shuffle.toggled.connect(self._on_shuffle)
        self.btn_repeat.clicked.connect(self._cycle_repeat)
        self.btn_mute.clicked.connect(self._toggle_mute)
        self.seek.userMoved.connect(self._on_seek_moving)
        self.seek.userReleased.connect(self._on_seek_release)
        self.vol.userMoved.connect(self._on_volume)

        self.btn_source.clicked.connect(self._source_menu)
        self.btn_plus.clicked.connect(lambda: self.new_playlist())
        self.btn_dots.clicked.connect(self._playlist_menu)
        self.btn_folder.clicked.connect(self._files_menu)
        self.search.textChanged.connect(self.apply_filter)
        self.list.itemDoubleClicked.connect(self._on_item_activated)
        self.list.customContextMenuRequested.connect(self._list_menu)
        self.list.model().rowsMoved.connect(self._on_reorder)

        sc = lambda keys, fn: QShortcut(QKeySequence(keys), self, activated=fn)
        sc("Space", self.toggle_play)
        sc("Ctrl+Right", lambda: self.next_track())
        sc("Ctrl+Left", self.prev_track)
        sc("Alt+Right", lambda: self.engine.seek(self.engine.position() + 5000))
        sc("Alt+Left", lambda: self.engine.seek(max(0, self.engine.position() - 5000)))
        sc("Ctrl+Up", lambda: self._nudge_volume(5))
        sc("Ctrl+Down", lambda: self._nudge_volume(-5))
        sc("F11", self.toggle_fullscreen_video)
        sc("Ctrl+O", self.open_files_dialog)
        sc("Ctrl+F", lambda: self.search.setFocus())
        sc("Ctrl+E", self.open_eq)
        sc("Ctrl+M", self.toggle_mini)

    # ------------------------------------------------------------------ skins
    def apply_skin(self, skin):
        """Coloca tudo no lugar, com as cores e imagens da skin."""
        self.skin = skin
        self.theme = t = skin.theme
        self.settings["skin"] = skin.id
        self.settings.save()
        QApplication.instance().setStyleSheet(make_qss(t))
        self.pl_window.setStyleSheet(f"QWidget#plwin {{ background: {t.dialog_bg}; }}")
        lay = skin.view_layout(self.mini)
        self.setFixedSize(*lay["window"])
        self.info.set_compact(self.mini)
        self.viz.panel = self.mini and skin.mini_layout is None

        # botões
        self._video_btn_in_layout = "video" in lay["buttons"]
        for name, btn in self.skin_buttons.items():
            rect = lay["buttons"].get(name)
            btn.apply_theme(t, skin.button_images)
            if rect:
                btn.setParent(self)
                btn.setGeometry(*rect)
                btn.setVisible(name != "video" or (self.engine.has_video() and self._video_btn_in_layout))
            else:
                btn.setVisible(False)

        # peças com posição própria
        def place(widget, key):
            rect = lay.get(key)
            if rect:
                widget.setGeometry(*rect)
                widget.setVisible(True)
            else:
                widget.setVisible(False)
        place(self.lcd, "lcd")
        place(self.logo, "logo")
        place(self.info, "info")
        place(self.stage, "stage")
        place(self.lbl_viz, "viz_label")
        place(self.seek, "seek")
        place(self.vol, "volume")
        self.lcd.lower()

        self._place_list_group(skin)

        self.seek.apply_theme(t, skin.slider_images)
        self.vol.apply_theme(t, skin.slider_images)
        self.lcd.theme = t
        self.lcd.update()
        self.info.set_theme(t)
        self.viz.set_theme(t)
        self.delegate.theme = t
        self.list.viewport().update()
        self.logo.setStyleSheet(f"color:{t.text}; font-family:'{t.font}'; font-size:17px; font-weight:700; background:transparent;")
        self.lbl_viz.setStyleSheet(f"color:{t.lcd_text}; font-family:'{t.font}'; font-weight:700; background:transparent;")
        self.status.setStyleSheet(f"color:{t.text_dim}; font-size:12px; background:transparent;")
        self.btn_source.setStyleSheet("text-align:left; padding:6px 12px;")
        self._bg = None
        self.update()
        if self.settings_dialog:
            self.settings_dialog.sync_skin()
        if self.eq_dialog:
            self.eq_dialog.set_theme(t)

    def _place_list_group(self, skin):
        lay = skin.view_layout(self.mini)
        group = (self.btn_source, self.btn_plus, self.btn_dots, self.btn_folder, self.search, self.list, self.status)
        for i in reversed(range(self.pl_layout.count())):
            self.pl_layout.takeAt(i)
        while self.pl_row.count():
            self.pl_row.takeAt(0)
        if self.mini:
            # no modo mini não há lista: tudo dela fica escondido
            self.pl_window.hide()
            for w in group:
                w.setVisible(False)
            self.btn_playlist.setVisible(False)
        elif skin.has_list:
            self.pl_window.hide()
            for w, key in ((self.btn_source, "source"), (self.search, "search"), (self.list, "list"), (self.status, "status")):
                w.setParent(self)
                rect = lay.get(key)
                if rect:
                    w.setGeometry(*rect)
                w.setVisible(bool(rect))
            for b in (self.btn_plus, self.btn_dots, self.btn_folder):
                b.setParent(self)
                rect = lay["buttons"].get({self.btn_plus: "plus", self.btn_dots: "dots", self.btn_folder: "folder"}[b])
                if rect:
                    b.setGeometry(*rect)
                b.setVisible(bool(rect))
            self.btn_playlist.setVisible(False)
        else:
            for w in group:
                w.setParent(self.pl_window)
            self.btn_source.setMinimumHeight(34)
            self.pl_row.addWidget(self.btn_source, 1)
            for b in (self.btn_plus, self.btn_dots, self.btn_folder):
                b.setFixedSize(32, 32)
                self.pl_row.addWidget(b)
            self.pl_layout.addLayout(self.pl_row)
            self.pl_layout.addWidget(self.search)
            self.pl_layout.addWidget(self.list, 1)
            self.pl_layout.addWidget(self.status)
            for w in group:
                w.show()
            self.btn_playlist.setVisible("playlist" in lay["buttons"])

    def _toggle_pl_window(self):
        if self.pl_window.isVisible():
            self.pl_window.hide()
        else:
            geo = self.geometry()
            self.pl_window.move(geo.right() + 12, geo.top())
            self.pl_window.show()
            self.pl_window.raise_()

    def apply_skin_id(self, skin_id):
        self.apply_skin(self.skins.get(skin_id))

    def next_skin(self):
        ids = self.skins.ids()
        self.apply_skin(self.skins.skins[ids[(ids.index(self.skin.id) + 1) % len(ids)]])

    def reload_skins(self):
        """Chamado depois de instalar ou remover skins."""
        self.skins.scan()
        if self.skin.id not in self.skins.skins:
            self.apply_skin(self.skins.get("aero"))

    # ------------------------------------------------------------------ pintura
    def _render_body(self):
        dpr = self.devicePixelRatioF()
        pm = QPixmap(int(self.width() * dpr), int(self.height() * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        image = self.skin.mini_body if self.mini else self.skin.body
        if image is not None:
            p.drawPixmap(QRectF(0, 0, self.width(), self.height()), image, QRectF(image.rect()))
            p.end()
            return pm
        t = self.theme
        aero = t.button_style == "round"
        sh = MINI_SHADOW if self.mini else SHADOW
        body = QRectF(sh, sh, self.width() - 2 * sh, self.height() - 2 * sh)
        if self.mini:
            top_r, bot_r = (46, 40) if aero else (12, 12)
        else:
            top_r, bot_r = (95, 75) if aero else (18, 18)
        p.setPen(Qt.PenStyle.NoPen)
        shadow = QColor(0, 50, 110, 5) if aero else QColor(0, 0, 0, 6)
        for i in range(12 if self.mini else 22, 0, -1):
            p.setBrush(shadow)
            p.drawPath(rounded_path(body.adjusted(-i, -i + 12, i, i + 12), top_r + i, top_r + i, bot_r + i, bot_r + i))
        path = rounded_path(body, top_r, top_r, bot_r, bot_r)
        if aero:
            g = QLinearGradient(0, body.top(), 0, body.bottom())
            g.setColorAt(0, QColor("#ffffff"))
            g.setColorAt(0.3, QColor("#dff2fd"))
            g.setColorAt(0.7, QColor("#9fd6f4"))
            g.setColorAt(1, QColor("#5fb4e4"))
            p.setBrush(QBrush(g))
            p.setPen(QPen(QColor(255, 255, 255, 240), 1.6))
            p.drawPath(path)
            p.setPen(Qt.PenStyle.NoPen)
            gh = 56 if self.mini else 110
            gloss = QLinearGradient(0, body.top(), 0, body.top() + gh)
            gloss.setColorAt(0, QColor(255, 255, 255, 235))
            gloss.setColorAt(1, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(gloss))
            if self.mini:
                p.drawPath(rounded_path(QRectF(body.left() + 40, body.top() + 5, body.width() - 80, 50), 44, 44, 18, 18))
            else:
                p.drawPath(rounded_path(QRectF(body.left() + 80, body.top() + 8, body.width() - 160, 100), 90, 90, 36, 36))
            ih = 40 if self.mini else 70
            inner = QLinearGradient(0, body.bottom() - ih, 0, body.bottom())
            inner.setColorAt(0, QColor(0, 90, 170, 0))
            inner.setColorAt(1, QColor(0, 90, 170, 80))
            p.setBrush(QBrush(inner))
            p.drawPath(rounded_path(QRectF(body.left() + 2, body.bottom() - ih, body.width() - 4, ih - 2), 0, 0, bot_r, bot_r))
        else:
            g = QLinearGradient(0, body.top(), 0, body.bottom())
            g.setColorAt(0, QColor("#f1f3f5"))
            g.setColorAt(0.45, QColor("#c9ced4"))
            g.setColorAt(0.55, QColor("#aeb4bb"))
            g.setColorAt(1, QColor("#d9dde1"))
            p.setBrush(QBrush(g))
            p.setPen(QPen(QColor("#6f767e"), 1.4))
            p.drawPath(path)
            p.save()
            p.setClipPath(path)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            rnd = random.Random(7)
            x = body.left()
            while x < body.right():
                a = rnd.randint(8, 34)
                p.setPen(QPen(QColor(255, 255, 255, a) if rnd.random() < 0.55 else QColor(0, 0, 0, a // 2), 1))
                p.drawLine(QPointF(x, body.top()), QPointF(x, body.bottom()))
                x += 1.5
            p.restore()
            p.setPen(Qt.PenStyle.NoPen)
            for cx, cy in ((body.left() + 12, body.top() + 12), (body.right() - 12, body.top() + 12),
                           (body.left() + 12, body.bottom() - 12), (body.right() - 12, body.bottom() - 12)):
                rg = QRadialGradient(cx - 1.5, cy - 1.5, 7)
                rg.setColorAt(0, QColor("#ffffff"))
                rg.setColorAt(0.6, QColor("#8a9098"))
                rg.setColorAt(1, QColor("#50565d"))
                p.setBrush(QBrush(rg))
                p.drawEllipse(QPointF(cx, cy), 5.5, 5.5)
        p.end()
        return pm

    def paintEvent(self, _e):
        if self._bg is None:
            self._bg = self._render_body()
        p = QPainter(self)
        p.drawPixmap(0, 0, self._bg)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.windowHandle():
            self.windowHandle().startSystemMove()
        elif e.button() == Qt.MouseButton.RightButton:
            self._window_menu(e.globalPosition().toPoint())

    def _window_menu(self, pos):
        m = QMenu(self)
        m.addAction("Equalizador…\tCtrl+E", self.open_eq)
        m.addAction("Voltar ao modo normal\tCtrl+M" if self.mini else "Modo mini\tCtrl+M", self.toggle_mini)
        m.addAction("Configurações…", self.open_settings)
        sub = m.addMenu("Skin")
        for sid in self.skins.ids():
            act = sub.addAction(self.skins.skins[sid].name)
            act.setCheckable(True)
            act.setChecked(sid == self.skin.id)
            act.triggered.connect(lambda _c=False, i=sid: self.apply_skin_id(i))
        m.addSeparator()
        m.addAction("Fechar", self.close)
        m.exec(pos)

    # ------------------------------------------------------------------ modo mini e equalizador
    def toggle_mini(self):
        self.set_mini(not self.mini)

    def set_mini(self, on):
        on = bool(on)
        if on == self.mini:
            return
        pos = self.pos()
        self.mini = on
        self.settings["mini"] = on
        self.settings.save()
        self.apply_skin(self.skin)
        self.move(pos)
        self.activateWindow()

    def open_eq(self):
        if self.eq_dialog is None:
            self.eq_dialog = EqDialog(self)
        self.eq_dialog.refresh()
        self.eq_dialog.show()
        self.eq_dialog.raise_()
        self.eq_dialog.activateWindow()

    def apply_eq(self):
        self.engine.set_eq(bool(self.settings["eq_on"]), self.settings["eq_gains"], self.settings["eq_preamp"])

    def _on_engine_notice(self, text):
        """O motor desligou o equalizador (dispositivo de som não aceitou): reflete na tela."""
        self.settings["eq_on"] = False
        self.settings.save()
        self.eq_notice = text
        self._update_status(text)
        if self.eq_dialog is not None:
            self.eq_dialog.refresh()

    # ------------------------------------------------------------------ visualizadores
    def _update_viz_label(self):
        self.lbl_viz.setText(f"Visualizador: {self.viz.names[self.viz.mode]}")

    def step_viz(self, d):
        self.viz.set_mode(self.viz.mode + d)
        self.settings["viz"] = self.viz.names[self.viz.mode]
        self.settings.save()
        self._update_viz_label()
        if self.stage.currentIndex() == 1 and self.engine.has_video():
            self._toggle_video()

    def set_viz(self, name):
        self.viz.set_mode_by_name(name)
        self.settings["viz"] = self.viz.names[self.viz.mode]
        self.settings.save()
        self._update_viz_label()

    def reload_viz_packs(self):
        """Carrega (executa) só os pacotes que a pessoa ativou nas configurações."""
        self.vizpacks.scan()
        packs, enabled = [], []
        for pid in self.settings["viz_packs"]:
            pack = self.vizpacks.packs.get(pid)
            if pack is None:
                continue
            try:
                packs.append((pack.name, self.vizpacks.load_draw(pid)))
                enabled.append(pid)
                self.viz_pack_errors.pop(pid, None)
            except Exception as exc:
                self.viz_pack_errors[pid] = f"{type(exc).__name__}: {exc}"
        self.viz.set_packs(packs)
        if hasattr(self, "lbl_viz"):
            self._update_viz_label()

    def _on_pack_failed(self, name, message):
        self._update_status(f"O visualizador “{name}” deu erro e foi desligado: {message}")
        self.set_viz("Barras")

    def _toggle_video(self):
        self.show_video = not self.show_video
        self.stage.setCurrentIndex(1 if self.show_video else 0)

    def _on_has_video(self, has):
        self.btn_vid.setVisible(has and self._video_btn_in_layout)
        self.stage.setCurrentIndex(1 if (has and self.show_video) else 0)
        if not has:
            self.video.clear()

    def toggle_fullscreen_video(self):
        if self.fs_window is not None:
            self.engine.frameReady.disconnect(self.fs_window.set_frame)
            self.fs_window.close()
            self.fs_window = None
            return
        if not self.engine.has_video():
            return
        fs = VideoSurface()
        fs.setWindowFlag(Qt.WindowType.Window)
        fs.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        fs.doubleClicked.connect(self.toggle_fullscreen_video)
        fs.img = self.video.img
        self.engine.frameReady.connect(fs.set_frame)
        self.fs_window = fs
        fs.showFullScreen()
        fs.setFocus()

    # ------------------------------------------------------------------ lista, fontes e playlists
    def source_paths(self):
        if self.source == LIBRARY:
            return self.library.sorted_paths()
        return list(self.playlists.lists.get(self.source, []))

    def refresh_list(self):
        self.list.setUpdatesEnabled(False)
        self.list.clear()
        for path in self.source_paths():
            track = self.library.get(path)
            it = QListWidgetItem()
            it.setData(Qt.ItemDataRole.UserRole, path)
            it.setData(Qt.ItemDataRole.UserRole + 1, (track.label if track else path).lower())
            it.setToolTip(path)
            self.list.addItem(it)
        self.list.setUpdatesEnabled(True)
        is_pl = self.source != LIBRARY
        self.list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove if is_pl else QAbstractItemView.DragDropMode.NoDragDrop)
        self.list.setDefaultDropAction(Qt.DropAction.MoveAction)
        name = "Biblioteca" if self.source == LIBRARY else self.source
        self.btn_source.setText(f"{name}  ▾")
        self.apply_filter()
        self._update_status()

    def _update_status(self, extra=""):
        n = self.list.count()
        shown = sum(1 for i in range(n) if not self.list.item(i).isHidden())
        if self.source == LIBRARY and not self.library.tracks:
            base = "Biblioteca vazia. Use o botão da pasta para adicionar arquivos ou pastas."
        elif self.source != LIBRARY and n == 0:
            base = "Playlist vazia. Clique com o botão direito em músicas da biblioteca para adicioná-las."
        else:
            base = f"{shown} de {n} faixas" if shown != n else f"{n} faixas"
        self.status.setText(f"{extra}\n{base}" if extra else base)

    def apply_filter(self, _text=None):
        text = self.search.text().strip().lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(text) and text not in it.data(Qt.ItemDataRole.UserRole + 1))
        self._update_status()

    def visible_paths(self):
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())
                if not self.list.item(i).isHidden()]

    def set_source(self, source):
        self.source = source
        self.settings["source"] = "" if source == LIBRARY else source
        self.settings.save()
        self.search.clear()
        self.refresh_list()

    def _source_menu(self):
        m = QMenu(self)
        a = m.addAction(f"Biblioteca ({len(self.library.tracks)})")
        a.setCheckable(True)
        a.setChecked(self.source == LIBRARY)
        a.triggered.connect(lambda: self.set_source(LIBRARY))
        names = self.playlists.names()
        if names:
            m.addSeparator()
        for name in names:
            act = m.addAction(f"{name} ({len(self.playlists.lists[name])})")
            act.setCheckable(True)
            act.setChecked(name == self.source)
            act.triggered.connect(lambda _c=False, n=name: self.set_source(n))
        m.addSeparator()
        m.addAction("＋ Nova playlist…", lambda: self.new_playlist())
        m.exec(self.btn_source.mapToGlobal(self.btn_source.rect().bottomLeft()))

    def _playlist_menu(self):
        m = QMenu(self)
        m.addAction("Nova playlist…", lambda: self.new_playlist())
        is_pl = self.source != LIBRARY
        r = m.addAction("Renomear playlist…", self.rename_playlist)
        r.setEnabled(is_pl)
        d = m.addAction("Excluir playlist", self.delete_playlist)
        d.setEnabled(is_pl)
        m.addSeparator()
        m.addAction("Tocar esta lista", lambda: self.play_visible(0, shuffle=False))
        m.addAction("Embaralhar e tocar", lambda: self.play_visible(0, shuffle=True))
        m.addSeparator()
        x = m.addAction("Exportar playlist (M3U)…", self.export_playlist)
        x.setEnabled(is_pl)
        m.addAction("Importar playlist (M3U)…", self.import_playlist)
        m.exec(self.btn_dots.mapToGlobal(self.btn_dots.rect().bottomLeft()))

    def _files_menu(self):
        m = QMenu(self)
        m.addAction("Abrir arquivos…\tCtrl+O", self.open_files_dialog)
        m.addAction("Adicionar pasta à biblioteca…", self.add_folder_dialog)
        m.addSeparator()
        m.addAction("Gerenciar pastas…", lambda: self.open_settings(tab=3))
        m.addAction("Escanear pastas agora", lambda: self.scan(manual=True))
        m.exec(self.btn_folder.mapToGlobal(self.btn_folder.rect().bottomLeft()))

    def _list_menu(self, pos):
        items = self.list.selectedItems()
        if not items:
            return
        paths = [i.data(Qt.ItemDataRole.UserRole) for i in items]
        m = QMenu(self)
        m.addAction("Tocar agora", lambda: self._on_item_activated(items[0]))
        sub = m.addMenu("Adicionar à playlist")
        for name in self.playlists.names():
            if name != self.source:
                sub.addAction(name, lambda n=name: self.add_to_playlist(n, paths))
        if self.playlists.names():
            sub.addSeparator()
        sub.addAction("＋ Nova playlist…", lambda: self.new_playlist(paths))
        if self.source != LIBRARY:
            m.addAction("Remover da playlist", lambda: self.remove_from_playlist(paths))
        m.addSeparator()
        m.addAction("Mostrar na pasta", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(paths[0]).parent))))
        m.exec(self.list.viewport().mapToGlobal(pos))

    def new_playlist(self, paths=None):
        name, ok = QInputDialog.getText(self, "Nova playlist", "Nome da playlist:", text="Minha playlist")
        if ok and name.strip():
            created = self.playlists.create(name, paths or [])
            self.set_source(created)

    def rename_playlist(self):
        if self.source == LIBRARY:
            return
        name, ok = QInputDialog.getText(self, "Renomear playlist", "Novo nome:", text=self.source)
        if ok and name.strip():
            self.set_source(self.playlists.rename(self.source, name))

    def delete_playlist(self):
        if self.source == LIBRARY:
            return
        ask = QMessageBox.question(self, "Excluir playlist",
                                   f"Excluir a playlist “{self.source}”?\nAs músicas continuam no seu computador.")
        if ask == QMessageBox.StandardButton.Yes:
            self.playlists.delete(self.source)
            self.set_source(LIBRARY)

    def add_to_playlist(self, name, paths):
        added = self.playlists.add(name, paths)
        self._update_status(f"{added} faixa(s) adicionada(s) a “{name}”.")

    def remove_from_playlist(self, paths):
        self.playlists.remove_paths(self.source, paths)
        self.refresh_list()

    def export_playlist(self):
        file, _ = QFileDialog.getSaveFileName(self, "Exportar playlist", f"{self.source}.m3u8", "Playlist (*.m3u8 *.m3u)")
        if file:
            self.playlists.export_m3u(self.source, file)
            self._update_status(f"Playlist salva em {file}")

    def import_playlist(self):
        file, _ = QFileDialog.getOpenFileName(self, "Importar playlist", "", "Playlist (*.m3u8 *.m3u)")
        if file:
            paths_before = set(self.library.tracks)
            name = self.playlists.import_m3u(file)
            new = [read_track(p) for p in self.playlists.lists[name] if p not in paths_before and os.path.exists(p)]
            self.library.add(new)
            self.library.save()
            self.set_source(name)

    def _on_reorder(self, *_):
        if self.source != LIBRARY:
            self.playlists.set_order(self.source, [self.list.item(i).data(Qt.ItemDataRole.UserRole)
                                                   for i in range(self.list.count())])

    # ------------------------------------------------------------------ pastas e escaneamento
    def add_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Escolha uma pasta com músicas e vídeos")
        if folder:
            self.add_folder(folder)

    def add_folder(self, folder):
        folder = os.path.normpath(folder)
        if folder not in self.settings["folders"]:
            self.settings["folders"] = self.settings["folders"] + [folder]
            self.settings.save()
        self.scan(manual=True)

    def remove_folder(self, folder):
        self.settings["folders"] = [f for f in self.settings["folders"] if f != folder]
        self.settings.save()

    def scan(self, manual=False):
        if self.scanner is not None and self.scanner.isRunning():
            return
        folders = self.settings["folders"]
        if not folders:
            if manual:
                self._scan_msg("Nenhuma pasta escolhida ainda. Adicione uma pasta primeiro.")
            return
        self.scanner = ScanThread(folders, self.library.tracks.keys(), self)
        self.scanner.progress.connect(lambda n, d: self._scan_msg(f"Escaneando… {n} arquivos encontrados"))
        self.scanner.done.connect(lambda new, total, gone: self._scan_done(new, total, gone, manual))
        self._scan_msg("Escaneando as pastas…")
        self.scanner.start()

    def _scan_done(self, new, total, gone, manual):
        self.library.add(new)
        self.library.remove(gone)
        self.library.save()
        if new or gone:
            self.refresh_list()
        if new:
            msg = f"{len(new)} mídia(s) nova(s) encontrada(s). Total: {total}."
        else:
            msg = f"Nenhuma mídia nova. Total na biblioteca: {len(self.library.tracks)}."
        if gone:
            msg += f" {len(gone)} arquivo(s) não existem mais e foram retirados."
        self._scan_msg(msg)

    def _scan_msg(self, text):
        self._update_status(text)
        self.scanMessage.emit(text)

    # ------------------------------------------------------------------ abrir arquivos / arrastar e soltar
    def open_files_dialog(self):
        exts = " ".join(f"*{e}" for e in sorted(MEDIA_EXTS))
        files, _ = QFileDialog.getOpenFileNames(self, "Abrir músicas e vídeos", "", f"Mídias ({exts});;Todos os arquivos (*)")
        if files:
            self.open_paths(files)

    def open_paths(self, paths):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            files = []
            for p in paths:
                if os.path.isdir(p):
                    files.extend(walk_media(p))
                elif is_media(p):
                    files.append(p)
            files = list(dict.fromkeys(files))
            if not files:
                self._update_status("Nenhum arquivo de mídia reconhecido.")
                return
            new = [read_track(p) for p in files if p not in self.library.tracks]
            if new:
                self.library.add(new)
                self.library.save()
            self.set_source(LIBRARY)
            self.queue = files
            self.qi = 0
            self.history = []
            self.start_current()
        finally:
            QApplication.restoreOverrideCursor()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.open_paths([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    # ------------------------------------------------------------------ reprodução
    def _on_item_activated(self, item):
        paths = self.visible_paths()
        path = item.data(Qt.ItemDataRole.UserRole)
        if path in paths:
            self.play_visible(paths.index(path))

    def play_visible(self, index, shuffle=None):
        paths = self.visible_paths()
        if not paths:
            return
        if shuffle is True:
            self.btn_shuffle.setChecked(True)
            index = random.randrange(len(paths))
        elif shuffle is False:
            self.btn_shuffle.setChecked(False)
        self.queue, self.qi, self.history = paths, index, []
        self.start_current()

    def start_current(self, autoplay=True, start_ms=0):
        if not (0 <= self.qi < len(self.queue)):
            return
        path = self.queue[self.qi]
        track = self.library.get(path)
        if track is None and os.path.exists(path):
            track = read_track(path)
            self.library.add([track])
        self.current_path = path
        self.delegate.playing_path = path
        self.list.viewport().update()
        self.show_video = bool(track and track.kind == "video")
        if self.settings["viz_random"] and not self.show_video:
            current = self.viz.names[self.viz.mode]
            self.set_viz(random.choice([n for n in self.viz.names if n != current]))
        title = track.title if track else Path(path).stem
        artist = track.artist if track else ""
        album = f" · {track.album}" if track and track.album else ""
        quality = f"{track.bitrate} kbps" if track and track.bitrate else ""
        self.info.set_info(title=title, artist=(artist + album).strip(" ·") or Path(path).parent.name,
                           fmt=" · ".join(x for x in (track.tag if track else "", quality) if x),
                           time="00:00", total=fmt_time(track.duration) if track else "00:00")
        self.setWindowTitle(f"{title} - Retro Boom Box")
        is_video = bool(track and track.kind == "video")
        self.info.set_cover(None if is_video else load_cover(path))
        self.seek.setValue(0)
        self.settings["last_path"] = path
        self.settings.save()
        if not os.path.exists(path):
            self._on_fail("Arquivo não encontrado.")
            return
        self.engine.load(path, autoplay=autoplay, start_ms=start_ms, video=is_video)

    def toggle_play(self):
        if not self.current_path:
            paths = self.visible_paths()
            if paths:
                self.play_visible(0)
            return
        if self.engine.player.playbackState() == QMediaPlayer.PlaybackState.StoppedState and self.engine.position() == 0:
            self.engine.play()
        else:
            self.engine.toggle()

    def stop(self):
        self.engine.stop()
        self.seek.setValue(0)
        self.info.set_info(time="00:00")

    def next_track(self, auto=False):
        n = len(self.queue)
        if n == 0:
            return
        repeat = self.settings["repeat"]
        if auto and repeat == "one":
            self.start_current()
            return
        if self.btn_shuffle.isChecked() and n > 1:
            self.history.append(self.qi)
            self.qi = random.choice([i for i in range(n) if i != self.qi])
        else:
            nxt = self.qi + 1
            if nxt >= n:
                if repeat == "all" or not auto:
                    nxt = 0
                else:
                    self.stop()
                    return
            self.history.append(self.qi)
            self.qi = nxt
        self.start_current()

    def prev_track(self):
        if not self.queue:
            return
        if self.engine.position() > 3000 or not self.history:
            self.engine.seek(0)
            return
        self.qi = self.history.pop()
        self.start_current()

    def _on_pos(self, ms):
        if self.seek.dragging:
            return
        dur = self.engine.duration()
        self.info.set_info(time=fmt_time(ms / 1000))
        self.seek.setValue(int(ms * 1000 / dur) if dur > 0 else 0)

    def _on_seek_moving(self, v):
        dur = self.engine.duration()
        self.info.set_info(time=fmt_time(v * dur / 1000 / 1000))

    def _on_seek_release(self, v):
        dur = self.engine.duration()
        if dur > 0:
            self.engine.seek(int(v * dur / 1000))

    def _on_playing(self, playing):
        self.btn_play.set_kind("pause" if playing else "play")
        if playing:
            self.fail_count = 0
            status = "TOCANDO"
        elif self.engine.player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
            status = "PARADO"
        else:
            status = "PAUSADO"
        self.info.set_info(status=status)
        if not playing:
            self.viz.sparks.clear()

    def _on_loaded(self):
        res = self.engine.video_resolution()
        if res and res not in self.info.fmt:
            self.info.set_info(fmt=" · ".join(x for x in (self.info.fmt, res) if x))

    def _on_fail(self, message):
        self.info.set_info(status="ERRO", artist=message)
        self.fail_count += 1
        if len(self.queue) > 1 and self.fail_count < len(self.queue):
            QTimer.singleShot(1500, lambda: self.next_track(auto=True))

    def _on_shuffle(self, on):
        self.settings["shuffle"] = bool(on)
        self.settings.save()

    def _set_repeat(self, mode, save=True):
        self.settings["repeat"] = mode
        self.btn_repeat.setChecked(mode != "off")
        self.btn_repeat.badge = "1" if mode == "one" else ""
        self.btn_repeat.setToolTip({"off": "Repetir: desligado", "all": "Repetir: toda a lista",
                                    "one": "Repetir: só esta faixa"}[mode])
        self.btn_repeat.update()
        if save:
            self.settings.save()

    def _cycle_repeat(self):
        order = ["off", "all", "one"]
        self._set_repeat(order[(order.index(self.settings["repeat"]) + 1) % 3])

    def _on_volume(self, v):
        self.settings["volume"] = v
        self.engine.set_volume(v)
        self.engine.set_muted(False)

    def _nudge_volume(self, d):
        v = max(0, min(100, self.vol.value() + d))
        self.vol.setValue(v)
        self._on_volume(v)

    def _toggle_mute(self):
        self.engine.toggle_mute()

    # ------------------------------------------------------------------ configurações
    def open_settings(self, tab=None):
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self)
        if isinstance(tab, int):
            self.settings_dialog.tabs.setCurrentIndex(tab)
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def set_always_on_top(self, on):
        self.settings["top"] = bool(on)
        self.settings.save()
        self._set_flags(bool(on))
        self.show()

    # ------------------------------------------------------------------ versões novas
    def check_updates(self, manual=False):
        """Procura uma versão nova em segundo plano. Sem `manual`, só procura se a pessoa deixou ligado,
        se já foi configurado onde olhar e se faz mais de um dia desde a última busca."""
        if self.update_checker.running:
            return
        if not manual:
            if not self.settings["update_check"] or updater.configured_url() is None:
                return
            if not updater.due(self.settings["update_last_check"]):
                return
        self._update_manual = manual
        if manual:
            self.updateStatus.emit("Procurando…")
        self.update_checker.start()

    def _on_update_result(self, result):
        self.update_checker.running = False
        manual = self._update_manual
        if result.status in ("newer", "current"):
            self.settings["update_last_check"] = time.time()
            self.settings.save()
        self.updateStatus.emit(result.message)
        if result.status == "newer":
            if manual or result.release.version != self.settings["update_skip"]:
                self._show_update(result.release)

    def _show_update(self, release):
        self._close_update_box()
        box = UpdateDialog(self, release, __version__)
        box.setWindowModality(Qt.WindowModality.NonModal)       # não para a música nem trava a janela
        box.finished.connect(lambda _code, b=box: self._on_update_choice(release, b.choice))
        box.destroyed.connect(lambda *_, b=box: self._forget_update_box(b))
        self._update_box = box
        box.show()
        box.raise_()

    def _forget_update_box(self, box):
        if self._update_box is box:
            self._update_box = None

    def _close_update_box(self):
        box, self._update_box = self._update_box, None
        if box is not None:
            try:
                box.close()
            except RuntimeError:             # já foi apagada
                pass

    def _on_update_choice(self, release, choice):
        if choice == "download" and release.url:
            QDesktopServices.openUrl(QUrl(release.url))
        elif choice == "skip":
            self.settings["update_skip"] = release.version
            self.settings.save()

    # ------------------------------------------------------------------ início e fim
    def restore_session(self):
        if self.settings["scan_on_start"] and self.settings["folders"]:
            QTimer.singleShot(800, lambda: self.scan(manual=False))
        last = self.settings["last_path"]
        if self.settings["resume"] and last and os.path.exists(last):
            paths = self.source_paths()
            self.queue = paths if last in paths else [last]
            self.qi = self.queue.index(last)
            self.start_current(autoplay=False, start_ms=int(self.settings["last_pos"]))

    def closeEvent(self, e):
        self.settings["last_pos"] = self.engine.position()
        self.settings.save()
        if self.scanner is not None and self.scanner.isRunning():
            self.scanner.stop()
            self.scanner.wait(1500)
        self.engine.stop()
        if self.fs_window is not None:
            self.fs_window.close()
        self.pl_window.close()
        if self.settings_dialog is not None:
            self.settings_dialog.close()
        if self.eq_dialog is not None:
            self.eq_dialog.close()
        self._close_update_box()
        super().closeEvent(e)
        QApplication.instance().quit()
