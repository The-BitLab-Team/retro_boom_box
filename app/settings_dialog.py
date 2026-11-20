"""Janela de configurações. As mudanças valem na hora, sem botão de "OK"."""
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QSlider, QTabWidget, QVBoxLayout, QWidget)

from . import LICENSE_NAME, REPO_URL, __version__
from .library import AUDIO_EXTS, VIDEO_EXTS
from .license_dialog import LicenseDialog
from .packs import PackError

TAB_LIBRARY = 3


class SettingsDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.s = main.settings
        self.setWindowTitle("Configurações")
        self.setMinimumSize(580, 600)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._tab_appearance(), "Aparência")
        self.tabs.addTab(self._tab_packages(), "Skins e pacotes")
        self.tabs.addTab(self._tab_playback(), "Reprodução")
        self.tabs.addTab(self._tab_library(), "Biblioteca")
        self.tabs.addTab(self._tab_about(), "Sobre")
        close = QPushButton("Fechar")
        close.clicked.connect(self.close)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        root.addLayout(row)
        main.scanMessage.connect(self._on_scan_message)

    # ------------------------------------------------------------ abas
    def _page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        return w, lay

    def _tab_appearance(self):
        w, lay = self._page()
        lay.addWidget(self._bold("Visualizador"))
        self.viz_combo = QComboBox()
        self.viz_combo.currentTextChanged.connect(self._on_viz_changed)
        lay.addWidget(self.viz_combo)
        self._refresh_viz_combo()
        self.viz_random = QCheckBox("Trocar de visualizador a cada música")
        self.viz_random.setChecked(self.s["viz_random"])
        self.viz_random.toggled.connect(lambda v: self._set("viz_random", bool(v)))
        lay.addWidget(self.viz_random)

        self.show_cover = QCheckBox("Mostrar a capa do álbum no visor (quando a música tiver uma)")
        self.show_cover.setChecked(bool(self.s["show_cover"]))
        self.show_cover.toggled.connect(self._on_show_cover)
        lay.addWidget(self.show_cover)

        lay.addWidget(QLabel("Suavidade da animação:"))
        self.fps = QComboBox()
        self.fps.addItems(["Normal (30 quadros por segundo)", "Suave (60 quadros por segundo)"])
        self.fps.setCurrentIndex(1 if self.s["fps"] >= 60 else 0)
        self.fps.currentIndexChanged.connect(self._on_fps)
        lay.addWidget(self.fps)

        self.sens_label = QLabel()
        lay.addWidget(self.sens_label)
        self.sens = QSlider(Qt.Orientation.Horizontal)
        self.sens.setRange(50, 250)
        self.sens.setValue(self.s["sens"])
        self.sens.valueChanged.connect(self._on_sens)
        lay.addWidget(self.sens)
        self._on_sens(self.s["sens"], save=False)

        self.top = QCheckBox("Manter o player sempre por cima das outras janelas")
        self.top.setChecked(self.s["top"])
        self.top.toggled.connect(self.main.set_always_on_top)
        lay.addWidget(self.top)
        lay.addWidget(self._dim("Para trocar o visual do player, use a aba “Skins e pacotes” "
                                "ou o botão meio preto e branco no topo da janela."))
        lay.addStretch()
        return w

    def _tab_packages(self):
        w, lay = self._page()
        lay.addWidget(self._bold("Skins (o visual do player)"))
        self.skin_list = QListWidget()
        self.skin_list.setMaximumHeight(150)
        self.skin_list.currentItemChanged.connect(self._on_skin_picked)
        lay.addWidget(self.skin_list)
        row = QHBoxLayout()
        for text, fn in (("Instalar skin…", self._install_skin_file), ("De uma pasta…", self._install_skin_folder),
                         ("Remover", self._remove_skin), ("Abrir pasta", lambda: self._open_dir(self.main.skins.user_dir))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        self.skin_errors = self._dim("")
        lay.addWidget(self.skin_errors)

        lay.addSpacing(8)
        lay.addWidget(self._bold("Pacotes de visualizadores"))
        warn = self._dim("Atenção: um pacote de visualizador é um pequeno programa e roda dentro do player. "
                         "Só ative pacotes de quem você confia. Skins não têm esse risco: são só imagens e configurações.")
        warn.setStyleSheet("font-weight: 600;")
        lay.addWidget(warn)
        self.pack_list = QListWidget()
        self.pack_list.setMaximumHeight(130)
        self.pack_list.itemChanged.connect(self._on_pack_toggled)
        lay.addWidget(self.pack_list)
        row = QHBoxLayout()
        for text, fn in (("Instalar pacote…", self._install_pack_file), ("De uma pasta…", self._install_pack_folder),
                         ("Remover", self._remove_pack), ("Abrir pasta", lambda: self._open_dir(self.main.vizpacks.dir))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        self.pack_errors = self._dim("")
        lay.addWidget(self.pack_errors)
        lay.addStretch()
        self._reload_skins()
        self._reload_packs()
        return w

    def _tab_playback(self):
        w, lay = self._page()
        self.resume = QCheckBox("Voltar para a última música de onde parei ao abrir o programa")
        self.resume.setChecked(self.s["resume"])
        self.resume.toggled.connect(lambda v: self._set("resume", bool(v)))
        lay.addWidget(self.resume)
        row = QHBoxLayout()
        eq = QPushButton("Abrir o equalizador…")
        eq.clicked.connect(self.main.open_eq)
        mini = QPushButton("Alternar modo mini")
        mini.clicked.connect(self.main.toggle_mini)
        row.addWidget(eq)
        row.addWidget(mini)
        row.addStretch()
        lay.addLayout(row)
        lay.addWidget(self._dim("Atalhos: Ctrl+E abre o equalizador e Ctrl+M liga ou desliga o modo mini. "
                                "Clicar com o botão direito na janela do player também mostra essas opções."))
        lay.addWidget(self._dim("O modo aleatório e o modo repetir ficam nos botões ao lado do play."))
        lay.addWidget(self._dim("Atalhos: Espaço toca ou pausa · Ctrl+Setas troca de faixa · "
                                "Alt+Setas avança ou volta 5 segundos · Ctrl+Cima/Baixo muda o volume · "
                                "F11 abre o vídeo em tela cheia · Ctrl+O abre arquivos · Ctrl+F busca."))
        lay.addStretch()
        return w

    def _tab_library(self):
        w, lay = self._page()
        lay.addWidget(self._bold("Pastas escaneadas em busca de músicas e vídeos"))
        self.folders = QListWidget()
        self.folders.addItems(self.s["folders"])
        lay.addWidget(self.folders, 1)
        row = QHBoxLayout()
        add = QPushButton("Adicionar pasta…")
        add.clicked.connect(self._add_folder)
        rem = QPushButton("Remover selecionada")
        rem.clicked.connect(self._remove_folder)
        scan = QPushButton("Escanear agora")
        scan.clicked.connect(lambda: self.main.scan(manual=True))
        for b in (add, rem, scan):
            row.addWidget(b)
        lay.addLayout(row)
        self.scan_start = QCheckBox("Procurar mídias novas sempre que o programa abrir")
        self.scan_start.setChecked(self.s["scan_on_start"])
        self.scan_start.toggled.connect(lambda v: self._set("scan_on_start", bool(v)))
        lay.addWidget(self.scan_start)
        self.scan_status = QLabel("As subpastas também são escaneadas.")
        self.scan_status.setWordWrap(True)
        lay.addWidget(self.scan_status)
        return w

    def _tab_about(self):
        w, lay = self._page()
        lay.addWidget(self._bold(f"Retro Boom Box {__version__}"))
        lay.addWidget(self._dim("Um player de músicas e vídeos com a cara dos anos 2000."))
        lay.addWidget(self._dim("Áudio: " + ", ".join(sorted(e.lstrip(".") for e in AUDIO_EXTS))))
        lay.addWidget(self._dim("Vídeo: " + ", ".join(sorted(e.lstrip(".") for e in VIDEO_EXTS))))
        lay.addWidget(self._dim("Seus dados (biblioteca, playlists, configurações, skins e visualizadores instalados) "
                                "ficam na pasta RetroBoomBox, dentro de AppData."))
        lay.addSpacing(8)
        lay.addWidget(self._bold("Atualizações"))
        self.upd_check = QCheckBox("Procurar versões novas ao abrir o programa (no máximo uma vez por dia)")
        self.upd_check.setChecked(self.s["update_check"])
        self.upd_check.toggled.connect(lambda v: self._set("update_check", bool(v)))
        lay.addWidget(self.upd_check)
        row = QHBoxLayout()
        self.upd_btn = QPushButton("Procurar agora")
        self.upd_btn.clicked.connect(lambda: self.main.check_updates(manual=True))
        row.addWidget(self.upd_btn)
        row.addStretch()
        lay.addLayout(row)
        self.upd_status = QLabel("")
        self.upd_status.setWordWrap(True)
        lay.addWidget(self.upd_status)
        lay.addWidget(self._dim("Só consulta a página das versões. Nada é baixado nem instalado sozinho, "
                                "e nenhum dado seu é enviado."))
        self.main.updateStatus.connect(self._on_update_status)
        lay.addSpacing(8)
        lay.addWidget(self._bold("Licença e projeto"))
        lay.addWidget(self._dim(f"{LICENSE_NAME}: use, modifique e compartilhe de graça, mantendo o aviso do "
                                "projeto original. Venda e uso comercial não são permitidos."))
        row2 = QHBoxLayout()
        self.lic_btn = QPushButton("Ler a licença")
        self.lic_btn.clicked.connect(lambda: LicenseDialog(self).exec())
        self.repo_btn = QPushButton("Abrir o projeto original")
        self.repo_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        row2.addWidget(self.lic_btn)
        row2.addWidget(self.repo_btn)
        row2.addStretch()
        lay.addLayout(row2)
        lay.addWidget(self._dim(REPO_URL))
        lay.addStretch()
        return w

    # ------------------------------------------------------------ utilidades
    def _bold(self, text):
        l = QLabel(text)
        l.setStyleSheet("font-weight: 700; font-size: 14px;")
        return l

    def _dim(self, text):
        l = QLabel(text)
        l.setWordWrap(True)
        return l

    def _set(self, key, value):
        self.s[key] = value
        self.s.save()

    def _open_dir(self, path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _on_fps(self, index):
        fps = 60 if index == 1 else 30
        self._set("fps", fps)
        self.main.engine.set_fps(fps)

    def _on_sens(self, value, save=True):
        self.sens_label.setText(f"Sensibilidade do visualizador: {value}%")
        self.main.engine.sens = value / 100.0
        if save:
            self._set("sens", int(value))

    # ------------------------------------------------------------ visualizadores
    def _refresh_viz_combo(self):
        self.viz_combo.blockSignals(True)
        self.viz_combo.clear()
        self.viz_combo.addItems(self.main.viz.names)
        name = self.s["viz"]
        if name in self.main.viz.names:
            self.viz_combo.setCurrentText(name)
        self.viz_combo.blockSignals(False)

    def _on_viz_changed(self, name):
        if name:
            self.main.set_viz(name)

    # ------------------------------------------------------------ skins
    def _reload_skins(self):
        self.skin_list.blockSignals(True)
        self.skin_list.clear()
        for sid, skin in self.main.skins.skins.items():
            extra = "  ·  já vem com o programa" if skin.builtin else (f"  ·  de {skin.author}" if skin.author else "")
            it = QListWidgetItem(f"{skin.name}{extra}")
            it.setData(Qt.ItemDataRole.UserRole, sid)
            if skin.description:
                it.setToolTip(skin.description)
            self.skin_list.addItem(it)
            if sid == self.main.skin.id:
                self.skin_list.setCurrentItem(it)
        self.skin_list.blockSignals(False)
        errs = self.main.skins.errors
        self.skin_errors.setText("" if not errs else "Skins com problema (não foram carregadas): " + ", ".join(errs))
        self.skin_errors.setToolTip("\n\n".join(f"{k}:\n{v}" for k, v in errs.items()))

    def _on_update_status(self, text):
        self.upd_status.setText(text)
        self.upd_btn.setEnabled(not text.startswith("Procurando"))

    def _on_show_cover(self, on):
        self._set("show_cover", bool(on))
        self.main.info.set_show_cover(bool(on))

    def sync_skin(self):
        if hasattr(self, "skin_list"):
            self._reload_skins()

    def _on_skin_picked(self, item, _prev=None):
        if item is not None:
            self.main.apply_skin_id(item.data(Qt.ItemDataRole.UserRole))

    def _install_skin_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Escolha o arquivo da skin", "", "Skin (*.rbbskin *.zip)")
        if f:
            self._install_skin(f)

    def _install_skin_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Escolha a pasta da skin")
        if d:
            self._install_skin(d)

    def _install_skin(self, source, overwrite=False):
        try:
            skin = self.main.skins.install(source, overwrite=overwrite)
        except PackError as exc:
            msg = str(exc)
            if msg.startswith("EXISTS:"):
                ask = QMessageBox.question(self, "Skin já instalada", "Já existe uma skin com esse id. Substituir pela nova?")
                if ask == QMessageBox.StandardButton.Yes:
                    self._install_skin(source, overwrite=True)
                return
            QMessageBox.warning(self, "Não consegui instalar a skin", msg)
            return
        self.main.apply_skin(skin)
        self._reload_skins()
        QMessageBox.information(self, "Skin instalada", f"A skin “{skin.name}” foi instalada e já está em uso.")

    def _remove_skin(self):
        item = self.skin_list.currentItem()
        if item is None:
            return
        sid = item.data(Qt.ItemDataRole.UserRole)
        skin = self.main.skins.skins.get(sid)
        if skin is None or skin.builtin:
            QMessageBox.information(self, "Remover skin", "As skins que vêm com o programa não podem ser removidas.")
            return
        if QMessageBox.question(self, "Remover skin", f"Remover a skin “{skin.name}”?") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.main.skins.remove(sid)
        except PackError as exc:
            QMessageBox.warning(self, "Remover skin", str(exc))
        self.main.reload_skins()
        self._reload_skins()

    # ------------------------------------------------------------ pacotes de visualizadores
    def _reload_packs(self):
        self.pack_list.blockSignals(True)
        self.pack_list.clear()
        for pid, pack in self.main.vizpacks.packs.items():
            it = QListWidgetItem(f"{pack.name}" + (f"  ·  de {pack.author}" if pack.author else ""))
            it.setData(Qt.ItemDataRole.UserRole, pid)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if pid in self.s["viz_packs"] else Qt.CheckState.Unchecked)
            if pack.description:
                it.setToolTip(pack.description)
            self.pack_list.addItem(it)
        self.pack_list.blockSignals(False)
        errs = dict(self.main.vizpacks.errors)
        errs.update({k: v for k, v in self.main.viz_pack_errors.items()})
        self.pack_errors.setText("" if not errs else "Pacotes com problema: " + "; ".join(f"{k} ({v})" for k, v in errs.items()))
        self._refresh_viz_combo()

    def _on_pack_toggled(self, item):
        pid = item.data(Qt.ItemDataRole.UserRole)
        enabled = list(self.s["viz_packs"])
        if item.checkState() == Qt.CheckState.Checked:
            ask = QMessageBox.question(
                self, "Ativar visualizador",
                "Este pacote contém um programa que vai rodar dentro do player, com os mesmos acessos que ele tem "
                "ao seu computador.\n\nAtive só se você confia em quem criou. Ativar?")
            if ask != QMessageBox.StandardButton.Yes:
                self.pack_list.blockSignals(True)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.pack_list.blockSignals(False)
                return
            if pid not in enabled:
                enabled.append(pid)
        else:
            enabled = [e for e in enabled if e != pid]
        self._set("viz_packs", enabled)
        self.main.reload_viz_packs()
        self._reload_packs()

    def _install_pack_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Escolha o arquivo do visualizador", "", "Visualizador (*.rbbviz *.zip)")
        if f:
            self._install_pack(f)

    def _install_pack_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Escolha a pasta do visualizador")
        if d:
            self._install_pack(d)

    def _install_pack(self, source, overwrite=False):
        try:
            pack = self.main.vizpacks.install(source, overwrite=overwrite)
        except PackError as exc:
            msg = str(exc)
            if msg.startswith("EXISTS:"):
                ask = QMessageBox.question(self, "Visualizador já instalado", "Já existe um pacote com esse id. Substituir pelo novo?")
                if ask == QMessageBox.StandardButton.Yes:
                    self._install_pack(source, overwrite=True)
                return
            QMessageBox.warning(self, "Não consegui instalar o visualizador", msg)
            return
        self._reload_packs()
        QMessageBox.information(self, "Visualizador instalado",
                                f"“{pack.name}” foi instalado, mas ainda está desligado.\n"
                                "Marque a caixinha ao lado do nome para ativá-lo.")

    def _remove_pack(self):
        item = self.pack_list.currentItem()
        if item is None:
            return
        pid = item.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Remover visualizador", "Remover este pacote?") != QMessageBox.StandardButton.Yes:
            return
        self._set("viz_packs", [e for e in self.s["viz_packs"] if e != pid])
        self.main.vizpacks.remove(pid)
        self.main.reload_viz_packs()
        self._reload_packs()

    # ------------------------------------------------------------ biblioteca
    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Escolha uma pasta com músicas e vídeos")
        if folder:
            self.main.add_folder(folder)
            self._reload_folders()

    def _remove_folder(self):
        for item in self.folders.selectedItems():
            self.main.remove_folder(item.text())
        self._reload_folders()

    def _reload_folders(self):
        self.folders.clear()
        self.folders.addItems(self.s["folders"])

    def _on_scan_message(self, text):
        self.scan_status.setText(text)
