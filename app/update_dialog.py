"""Janela que avisa que existe uma versão nova do programa."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout


class UpdateDialog(QDialog):
    """Depois de fechar, `choice` é "download", "later" (lembrar depois) ou "skip" (ignorar esta versão)."""

    def __init__(self, parent, release, current):
        super().__init__(parent)
        self.choice = "later"
        self.setWindowTitle("Nova versão disponível")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)

        self.title = QLabel(f"A versão {release.version} do Retro Boom Box está disponível.")
        self.title.setStyleSheet("font-weight: 700; font-size: 14px;")
        self.title.setWordWrap(True)
        lay.addWidget(self.title)
        lay.addWidget(QLabel(f"Você está usando a versão {current}."))

        self.notes = None
        if release.notes:
            lay.addWidget(QLabel("O que mudou:"))
            self.notes = QPlainTextEdit(release.notes)
            self.notes.setReadOnly(True)
            self.notes.setMaximumHeight(150)
            lay.addWidget(self.notes)

        how = QLabel("Clique em “Baixar” para abrir a página da versão no navegador e baixar o instalador. "
                     "Nada é instalado sozinho." if release.url else
                     "Peça a nova versão a quem distribui o programa. Nada é instalado sozinho.")
        how.setWordWrap(True)
        lay.addWidget(how)

        row = QHBoxLayout()
        self.btn_download = QPushButton("Baixar")
        self.btn_download.setDefault(True)
        self.btn_download.setVisible(bool(release.url))
        self.btn_later = QPushButton("Lembrar depois")
        self.btn_skip = QPushButton("Ignorar esta versão")
        self.btn_download.clicked.connect(lambda: self._pick("download"))
        self.btn_later.clicked.connect(lambda: self._pick("later"))
        self.btn_skip.clicked.connect(lambda: self._pick("skip"))
        row.addStretch()
        for b in (self.btn_download, self.btn_skip, self.btn_later):
            row.addWidget(b)
        lay.addLayout(row)

    def _pick(self, choice):
        self.choice = choice
        self.accept()
