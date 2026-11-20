"""Janela com a licença do programa: resumo em português e o texto oficial (em inglês)."""
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout

from . import LICENSE_NAME, LICENSE_URL, REPO_URL

RESUMO = (
    "Você pode usar, copiar, estudar e modificar o programa, e passar cópias para outras pessoas de graça, "
    "desde que mantenha este aviso e o endereço do projeto original.\n"
    "Não é permitido vender o programa (nem versões modificadas) nem usá-lo para ganhar dinheiro.\n"
    "Este resumo é só para ajudar. Vale o texto oficial abaixo, que está em inglês."
)


def license_text():
    """Lê o arquivo LICENSE (na pasta do programa ou dentro do programa montado). None se não achar."""
    bases = [Path(__file__).resolve().parent.parent]
    if getattr(sys, "frozen", False):
        bases = [Path(getattr(sys, "_MEIPASS", "")), Path(sys.executable).resolve().parent] + bases
    for base in bases:
        for name in ("LICENSE", "LICENSE.txt"):
            try:
                return (base / name).read_text(encoding="utf-8")
            except OSError:
                continue
    return None


class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Licença")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(620, 520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)

        title = QLabel(f"Licença: {LICENSE_NAME}")
        title.setStyleSheet("font-weight: 700; font-size: 14px;")
        lay.addWidget(title)
        resumo = QLabel(RESUMO)
        resumo.setWordWrap(True)
        lay.addWidget(resumo)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        body = license_text()
        self.text.setPlainText(body if body else
                               f"O arquivo LICENSE não foi encontrado nesta instalação.\nTexto oficial: {LICENSE_URL}\n"
                               f"Projeto original: {REPO_URL}")
        lay.addWidget(self.text, 1)

        row = QHBoxLayout()
        self.btn_repo = QPushButton("Abrir o projeto original")
        self.btn_repo.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        self.btn_close = QPushButton("Fechar")
        self.btn_close.setDefault(True)
        self.btn_close.clicked.connect(self.accept)
        row.addWidget(self.btn_repo)
        row.addStretch()
        row.addWidget(self.btn_close)
        lay.addLayout(row)
