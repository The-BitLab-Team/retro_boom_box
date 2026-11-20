# -*- mode: python ; coding: utf-8 -*-
# Receita do PyInstaller: transforma o programa numa pasta com RetroBoomBox.exe que
# funciona sem Python instalado. Uso:  pyinstaller RetroBoomBox.spec --noconfirm --clean

# Módulos "de casa" do Python que os pacotes de visualizadores costumam usar. O PyInstaller
# só leva o que o programa usa; sem esta lista, um pacote que faça `import colorsys`
# daria erro no programa montado.
PARA_PACOTES = [
    "math", "random", "colorsys", "itertools", "collections", "functools", "dataclasses",
    "json", "time", "re", "string", "bisect", "heapq", "statistics", "cmath", "fractions",
    "decimal", "array", "struct", "operator", "typing", "enum", "copy", "numbers",
]

a = Analysis(
    ["iniciar_exe.py"],
    pathex=["."],
    datas=[
        ("app/builtin_skins", "app/builtin_skins"),
        ("app/assets", "app/assets"),
        ("LICENSE", "."),
    ],
    hiddenimports=PARA_PACOTES + ["mutagen.mp3", "mutagen.flac", "mutagen.mp4", "mutagen.oggvorbis",
                                   "mutagen.oggopus", "mutagen.asf", "mutagen.wave", "mutagen.aiff"],
    excludes=["tkinter", "unittest", "pytest", "matplotlib", "scipy", "PIL",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick",
              "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtPdf", "PySide6.QtSql"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RetroBoomBox",
    console=False,                  # sem a janela preta
    icon="app/assets/icone.ico",
    disable_windowed_traceback=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="RetroBoomBox",
)
