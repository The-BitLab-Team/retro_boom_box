"""Ponto de partida do programa: `python -m app.main` (ou o RetroBoomBox.exe).

Também aceita arquivos e pastas como argumentos (é assim que funciona "Abrir com" e
arrastar um arquivo em cima do programa) e a opção --autoteste, usada na montagem do
instalador para conferir se o programa montado consegue abrir e tocar som.
"""
import faulthandler
import os
import sys
import tempfile
import threading
import time
import traceback
import wave
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from . import __version__

ASSETS = Path(__file__).parent / "assets"
_keep = []                 # mantém o arquivo do registro de erros aberto
_last_dialog = [0.0]


_ffmpeg_libs = {}          # cópias da biblioteca do FFmpeg já ajustadas (caminho -> biblioteca)


def _quiet_ffmpeg():
    """Esconde as mensagens do FFmpeg no console.

    O FFmpeg escreve avisos inofensivos, em vermelho, ao sondar o computador, como
    "[av1_mf] could not find any MFT for the given media type", e também despeja os dados de
    cada arquivo aberto. Aqui pedimos à biblioteca que fique em silêncio. Erros de verdade
    continuam chegando ao programa pelo próprio Qt (sinal "failed" do motor).
    Para ver essas mensagens de novo (por exemplo, para investigar um arquivo que não toca),
    abra o programa com a variável de ambiente RBB_FFMPEG_LOG=1.
    Pode ser chamada várias vezes (a biblioteca só existe de verdade depois que o Qt a carrega,
    em alguns sistemas). Devolve quantas cópias estão em silêncio.
    """
    if os.environ.get("RBB_FFMPEG_LOG"):
        return 0
    try:
        import ctypes
        import PySide6
        base = Path(PySide6.__file__).parent
        dirs = [base, base / "Qt" / "lib"]
        meipass = getattr(sys, "_MEIPASS", None)       # programa montado com PyInstaller
        if meipass:
            dirs += [Path(meipass), Path(meipass) / "PySide6", Path(meipass) / "PySide6" / "Qt" / "lib"]
        for d in dirs:
            for pattern in ("avutil-*.dll", "libavutil.so.[0-9]*", "libavutil.*.dylib"):
                for f in d.glob(pattern):
                    key = str(f.resolve())
                    if key in _ffmpeg_libs:
                        continue
                    try:
                        lib = ctypes.CDLL(key)
                        lib.av_log_set_level.argtypes = [ctypes.c_int]
                        lib.av_log_set_level(-8)           # AV_LOG_QUIET
                        _ffmpeg_libs[key] = lib
                    except Exception:
                        pass                               # tenta de novo na próxima chamada
    except Exception:
        pass
    return len(_ffmpeg_libs)


def _log_file():
    from .library import data_dir
    return data_dir() / "erro.log"


def _report_error(text):
    """Guarda o erro em erro.log (na pasta de dados) e avisa a pessoa, sem encher a tela de janelas."""
    try:
        with open(_log_file(), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  Retro Boom Box {__version__}\n{text}\n")
    except OSError:
        pass
    if sys.__stderr__ is not None:
        try:
            sys.__stderr__.write(text)
        except Exception:
            pass
    now = time.time()
    if QApplication.instance() is not None and threading.current_thread() is threading.main_thread() \
            and now - _last_dialog[0] > 30:
        _last_dialog[0] = now
        try:
            QMessageBox.warning(None, "Retro Boom Box", "Algo inesperado aconteceu, mas o programa continua aberto.\n\n"
                                f"Se o problema se repetir, envie o arquivo abaixo para quem faz o programa:\n{_log_file()}")
        except Exception:
            pass


def _install_error_log():
    try:
        fh = open(_log_file(), "a", encoding="utf-8")
        faulthandler.enable(fh)        # se o programa "fechar do nada", o motivo vai para o mesmo arquivo
        _keep.append(fh)
    except Exception:
        pass
    sys.excepthook = lambda t, e, tb: _report_error("".join(traceback.format_exception(t, e, tb)))
    threading.excepthook = lambda a: _report_error("".join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)))


def _selftest(window):
    """Confere o essencial e escreve autoteste.txt na pasta atual. Devolve 0 se tudo certo."""
    import numpy as np
    from .equalizer import EqProcessor

    lines, ok = [f"Retro Boom Box {__version__} ({'programa montado' if getattr(sys, 'frozen', False) else 'python'})"], True

    def note(text, good=True):
        nonlocal ok
        ok = ok and good
        lines.append(("OK    " if good else "FALHOU ") + text)

    ids = window.skins.ids()
    note(f"skins carregadas: {', '.join(ids)}", "aero" in ids and "metal" in ids)
    note(f"skins com erro: {list(window.skins.errors) or 'nenhuma'}", not window.skins.errors)
    note(f"ícone encontrado: {(ASSETS / 'icone.png').exists()}", (ASSETS / "icone.png").exists())
    n = _quiet_ffmpeg()
    note(f"mensagens do FFmpeg silenciadas (bibliotecas ajustadas: {n}; se for 0, só o console fica mais barulhento)")
    from . import updater
    try:
        import ssl
        https = ssl.OPENSSL_VERSION
    except Exception as e:
        https = f"NÃO disponível ({e})"
    note(f"busca de versões: {'configurada' if updater.configured_url() else 'ainda sem endereço'}; "
         f"https: {https}; comparação 0.10.0 > 0.9.9: {updater.is_newer('v0.10.0', '0.9.9')}",
         updater.is_newer("v0.10.0", "0.9.9") and not updater.is_newer("0.9", "0.9.0"))
    eq = EqProcessor(44100)
    eq.set_gains([3] * 10, 0)
    out = eq.process(np.random.default_rng(1).standard_normal((20000, 2)).astype(np.float32) * 0.1)
    note(f"equalizador (numpy) processou {len(out)} quadros", len(out) > 10000)

    tmp = Path(tempfile.mkdtemp()) / "teste.wav"
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        t = np.arange(44100 * 2) / 44100
        w.writeframes((np.sin(2 * np.pi * 440 * t) * 8000).astype("<i2").tobytes())
    got = {"pos": 0, "err": ""}
    eng = window.engine
    eng.positionChanged.connect(lambda ms: got.__setitem__("pos", max(got["pos"], ms)))
    eng.failed.connect(lambda m: got.__setitem__("err", m))
    eng.load(str(tmp), autoplay=True)
    loop = QEventLoop()
    poll = QTimer()
    poll.setInterval(100)
    deadline = time.time() + 6
    poll.timeout.connect(lambda: loop.quit() if (got["pos"] > 300 or got["err"] or time.time() > deadline) else None)
    poll.start()
    loop.exec()
    poll.stop()
    eng.stop()
    note(f"tocar áudio (posição chegou a {got['pos']} ms{', erro: ' + got['err'] if got['err'] else ''})", got["pos"] > 300)

    text = "\n".join(lines) + "\n"
    try:
        Path("autoteste.txt").write_text(text, encoding="utf-8")
    except OSError:
        pass
    if sys.stdout is not None:
        print(text)
    return 0 if ok else 1


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    selftest = "--autoteste" in argv
    if not os.environ.get("RBB_FFMPEG_LOG"):
        os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg.info=false")
    _quiet_ffmpeg()
    if selftest:                      # o teste não mexe nas suas configurações de verdade
        os.environ["APPDATA"] = tempfile.mkdtemp(prefix="rbb-teste-")
    app = QApplication(argv)
    app.setApplicationName("Retro Boom Box")
    app.setOrganizationName("RetroBoomBox")
    if (ASSETS / "icone.png").exists():
        app.setWindowIcon(QIcon(str(ASSETS / "icone.png")))
    _install_error_log()

    from .mainwindow import MainWindow
    window = MainWindow()
    window.show()
    _quiet_ffmpeg()                   # de novo: agora o Qt já carregou o FFmpeg
    if selftest:
        code = _selftest(window)
        window.close()
        return code
    QTimer.singleShot(4000, window.check_updates)     # busca de versão nova, em segundo plano e sem pressa
    files = [a for a in argv[1:] if not a.startswith("--") and os.path.exists(a)]
    if files:
        window.open_paths(files)
    else:
        window.restore_session()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
