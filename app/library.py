"""Biblioteca de mídias, escaneamento de pastas, playlists e configurações.

Tudo é salvo em arquivos .json dentro da pasta de dados do programa
(no Windows: %APPDATA%\\RetroBoomBox), então nada se perde ao fechar.
"""
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal

try:  # leitura de tags (título, artista, duração). Opcional, mas recomendado.
    import mutagen
except Exception:  # pragma: no cover
    mutagen = None

AUDIO_EXTS = {".mp3", ".flac", ".wav", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wma", ".aiff", ".aif", ".mka"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".m4v", ".mpg", ".mpeg", ".flv", ".3gp"}
MEDIA_EXTS = AUDIO_EXTS | VIDEO_EXTS


def data_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.join(Path.home(), ".config")
    path = Path(base) / "RetroBoomBox"
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_media(path) -> bool:
    return Path(path).suffix.lower() in MEDIA_EXTS


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


# --------------------------------------------------------------------------- faixas
@dataclass
class Track:
    path: str
    title: str
    artist: str = ""
    album: str = ""
    duration: float = 0.0   # segundos
    bitrate: int = 0        # kbps
    kind: str = "audio"     # "audio" ou "video"

    @property
    def tag(self) -> str:
        return Path(self.path).suffix.lstrip(".").upper()

    @property
    def label(self) -> str:
        return f"{self.artist} - {self.title}" if self.artist else self.title


def fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def read_track(path: str) -> Track:
    """Cria uma Track lendo as tags do arquivo (ou adivinhando pelo nome)."""
    p = Path(path)
    kind = "video" if p.suffix.lower() in VIDEO_EXTS else "audio"
    stem = p.stem
    title, artist = stem, ""
    m = re.match(r"^\s*(.+?)\s+-\s+(.+?)\s*$", stem)
    if m:
        artist, title = m.group(1), m.group(2)
    album, duration, bitrate = "", 0.0, 0
    if mutagen is not None:
        try:
            f = mutagen.File(path, easy=True)
            if f is not None:
                if f.info is not None:
                    duration = float(getattr(f.info, "length", 0) or 0)
                    bitrate = int((getattr(f.info, "bitrate", 0) or 0) / 1000)
                tags = f.tags or {}
                title = (tags.get("title") or [title])[0] or title
                artist = (tags.get("artist") or [artist])[0] or artist
                album = (tags.get("album") or [""])[0]
        except Exception:
            pass
    return Track(path=str(path), title=title, artist=artist, album=album,
                 duration=duration, bitrate=bitrate, kind=kind)


def walk_media(folder: str):
    for root, _dirs, files in os.walk(folder):
        for name in files:
            if is_media(name):
                yield os.path.join(root, name)


# --------------------------------------------------------------------------- escaneamento
class ScanThread(QThread):
    """Varre as pastas em segundo plano para não travar o player."""
    progress = Signal(int, str)       # arquivos encontrados até agora, pasta atual
    done = Signal(list, int, list)    # novas faixas, total encontrado, caminhos que sumiram

    def __init__(self, folders, known_paths, parent=None):
        super().__init__(parent)
        self.folders = list(folders)
        self.known = set(known_paths)
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        found, new_tracks, seen = 0, [], set()
        for folder in self.folders:
            if not os.path.isdir(folder):
                continue
            for path in walk_media(folder):
                if self._stop:
                    return
                found += 1
                seen.add(path)
                if path not in self.known:
                    new_tracks.append(read_track(path))
                if found % 25 == 0:
                    self.progress.emit(found, os.path.dirname(path))
        folders_norm = tuple(os.path.normcase(f) for f in self.folders)
        gone = [p for p in self.known
                if p not in seen and os.path.normcase(p).startswith(folders_norm)
                and not os.path.exists(p)]
        self.done.emit(new_tracks, found, gone)


class Library:
    def __init__(self):
        self.file = data_dir() / "library.json"
        self.tracks = {}
        for d in _read_json(self.file, []):
            try:
                t = Track(**d)
                self.tracks[t.path] = t
            except TypeError:
                continue

    def save(self):
        _write_json(self.file, [asdict(t) for t in self.tracks.values()])

    def add(self, tracks):
        for t in tracks:
            self.tracks[t.path] = t

    def remove(self, paths):
        for p in paths:
            self.tracks.pop(p, None)

    def get(self, path):
        return self.tracks.get(path)

    def sorted_paths(self):
        key = lambda t: (t.artist.lower() or "￿", t.album.lower(), t.title.lower())
        return [t.path for t in sorted(self.tracks.values(), key=key)]


# --------------------------------------------------------------------------- playlists
class Playlists:
    def __init__(self):
        self.file = data_dir() / "playlists.json"
        data = _read_json(self.file, {})
        self.lists = {str(k): [str(p) for p in v] for k, v in data.items()} if isinstance(data, dict) else {}

    def save(self):
        _write_json(self.file, self.lists)

    def names(self):
        return sorted(self.lists, key=str.lower)

    def unique_name(self, wanted: str) -> str:
        wanted = wanted.strip() or "Nova playlist"
        name, n = wanted, 2
        while name in self.lists:
            name, n = f"{wanted} ({n})", n + 1
        return name

    def create(self, name: str, paths=()) -> str:
        name = self.unique_name(name)
        self.lists[name] = list(paths)
        self.save()
        return name

    def rename(self, old: str, new: str) -> str:
        new = new.strip()
        if not new or new == old:
            return old
        new = self.unique_name(new)
        self.lists[new] = self.lists.pop(old)
        self.save()
        return new

    def delete(self, name: str):
        self.lists.pop(name, None)
        self.save()

    def add(self, name: str, paths) -> int:
        cur = self.lists.setdefault(name, [])
        added = 0
        for p in paths:
            if p not in cur:
                cur.append(p)
                added += 1
        self.save()
        return added

    def remove_paths(self, name: str, paths):
        drop = set(paths)
        self.lists[name] = [p for p in self.lists.get(name, []) if p not in drop]
        self.save()

    def set_order(self, name: str, paths):
        self.lists[name] = list(paths)
        self.save()

    def export_m3u(self, name: str, file: str):
        lines = ["#EXTM3U"] + self.lists.get(name, [])
        Path(file).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def import_m3u(self, file: str) -> str:
        base = Path(file).parent
        paths = []
        for line in Path(file).read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = Path(line)
            if not p.is_absolute():
                p = base / p
            if p.exists() and is_media(p):
                paths.append(str(p))
        return self.create(Path(file).stem, paths)


# --------------------------------------------------------------------------- configurações
LEGACY_VIZ = ["Barras", "Espelho", "Onda", "Montanhas", "Pontos", "Círculos", "Anéis", "Faíscas"]

DEFAULT_SETTINGS = {
    "skin": "aero",
    "viz": "Barras",
    "viz_packs": [],          # ids dos pacotes de visualizador ativados
    "viz_random": False,
    "fps": 30,
    "sens": 100,
    "top": False,
    "resume": True,
    "scan_on_start": True,
    "folders": [],
    "volume": 70,
    "shuffle": False,
    "repeat": "off",          # off, all, one
    "last_path": "",
    "last_pos": 0,
    "source": "",
    "show_cover": True,       # capa do álbum no visor
    "mini": False,            # abrir no modo mini
    "eq_on": False,           # equalizador ligado
    "eq_gains": [0.0] * 10,   # ganho (dB) de cada faixa
    "eq_preamp": 0.0,
    "eq_preset": "Plano",
    "eq_user": {},            # presets salvos pela pessoa: nome -> 10 ganhos
    "update_check": True,     # procurar versões novas ao abrir (no máximo uma vez por dia)
    "update_last_check": 0,   # quando foi a última busca que deu certo (segundos desde 1970)
    "update_skip": "",        # versão que a pessoa escolheu "ignorar"
}


class Settings:
    def __init__(self):
        self.file = data_dir() / "settings.json"
        self.data = dict(DEFAULT_SETTINGS)
        stored = _read_json(self.file, {})
        if isinstance(stored, dict):
            self.data.update({k: v for k, v in stored.items() if k in DEFAULT_SETTINGS})
            # versões antigas guardavam o tema em "theme" e o visualizador como número
            if "skin" not in stored and stored.get("theme") in ("aero", "metal"):
                self.data["skin"] = stored["theme"]
            if isinstance(self.data["viz"], int):
                v = self.data["viz"]
                self.data["viz"] = LEGACY_VIZ[v] if 0 <= v < len(LEGACY_VIZ) else "Barras"
        self._sanitize_eq()

    def _sanitize_eq(self):
        """Arquivo de configurações editado à mão ou antigo: garante valores do equalizador utilizáveis."""
        num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
        d = self.data
        d["eq_gains"] = ([max(-12.0, min(12.0, float(v))) for v in d["eq_gains"]]
                         if isinstance(d["eq_gains"], list) and len(d["eq_gains"]) == 10 and all(num(v) for v in d["eq_gains"])
                         else [0.0] * 10)
        d["eq_preamp"] = max(-12.0, min(12.0, float(d["eq_preamp"]))) if num(d["eq_preamp"]) else 0.0
        user = d["eq_user"] if isinstance(d["eq_user"], dict) else {}
        d["eq_user"] = {str(k)[:40]: [max(-12.0, min(12.0, float(v))) for v in g] for k, g in user.items()
                        if isinstance(g, list) and len(g) == 10 and all(num(v) for v in g)}
        d["eq_on"] = bool(d["eq_on"])
        d["eq_preset"] = str(d["eq_preset"])[:40]
        d["update_check"] = bool(d["update_check"])
        d["update_last_check"] = float(d["update_last_check"]) if num(d["update_last_check"]) else 0
        d["update_skip"] = str(d["update_skip"])[:30]

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def save(self):
        _write_json(self.file, self.data)

    def reset_appearance(self):
        for k in ("skin", "viz", "viz_random", "fps", "sens", "top"):
            self.data[k] = DEFAULT_SETTINGS[k]
