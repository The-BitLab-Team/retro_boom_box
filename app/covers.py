"""Capa do álbum: procura a imagem dentro das tags da música ou numa imagem da pasta.

A ordem é: capa embutida no arquivo (mp3, flac, m4a, ogg...) e, se não tiver,
um arquivo de imagem na mesma pasta com nome de capa (cover.jpg, folder.png...).
"""
import base64
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

try:
    import mutagen
except Exception:      # o player funciona sem as tags, só não mostra capas embutidas
    mutagen = None

MAX_BYTES = 12 * 1024 * 1024       # ignora imagens absurdamente grandes
MAX_SIDE = 480                      # a capa é guardada pequena: basta para o visor
FOLDER_NAMES = ("cover", "folder", "front", "album", "albumart", "capa", "artwork")
FOLDER_EXTS = (".jpg", ".jpeg", ".png")
_cache = OrderedDict()
_CACHE_MAX = 24


def _from_bytes(data):
    if not data or len(data) > MAX_BYTES:
        return None
    img = QImage()
    if not img.loadFromData(bytes(data)) or img.isNull():
        return None
    if max(img.width(), img.height()) > MAX_SIDE:
        img = img.scaled(MAX_SIDE, MAX_SIDE, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    return img


def _embedded(path):
    """Devolve os bytes da primeira imagem embutida no arquivo, ou None."""
    if mutagen is None:
        return None
    try:
        f = mutagen.File(path)
    except Exception:
        return None
    if f is None:
        return None
    try:
        pics = getattr(f, "pictures", None)          # FLAC, Ogg Opus/Vorbis (após leitura)
        if pics:
            front = [p for p in pics if getattr(p, "type", 3) == 3]
            return (front or pics)[0].data
        tags = f.tags
        if tags is None:
            return None
        # MP3 (ID3): quadros APIC
        if hasattr(tags, "getall"):
            apics = tags.getall("APIC")
            if apics:
                front = [a for a in apics if getattr(a, "type", 3) == 3]
                return (front or apics)[0].data
        # M4A / MP4
        covr = tags.get("covr") if hasattr(tags, "get") else None
        if covr:
            return bytes(covr[0])
        # Ogg: imagem em base64 dentro da tag
        if hasattr(tags, "get"):
            blocks = tags.get("metadata_block_picture")
            if blocks:
                from mutagen.flac import Picture
                return Picture(base64.b64decode(blocks[0])).data
    except Exception:
        return None
    return None


def _from_folder(path):
    folder = Path(path).parent
    try:
        files = {p.name.lower(): p for p in folder.iterdir() if p.is_file()}
    except OSError:
        return None
    for stem in FOLDER_NAMES:
        for ext in FOLDER_EXTS:
            p = files.get(stem + ext)
            if p is not None:
                try:
                    if p.stat().st_size <= MAX_BYTES:
                        return _from_bytes(p.read_bytes())
                except OSError:
                    pass
    return None


def load_cover(path):
    """Devolve um QImage com a capa da música, ou None se não houver."""
    key = str(path)
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    img = _from_bytes(_embedded(key)) or _from_folder(key)
    _cache[key] = img
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)
    return img
