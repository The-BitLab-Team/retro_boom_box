"""Pacotes de visualizadores.

ATENÇÃO: diferente das skins (que são só imagens e configurações), um pacote de
visualizador contém um programinha em Python (viz.py) que roda dentro do player.
Por isso ele só é carregado depois que a pessoa ativa o pacote nas configurações,
com um aviso. Instale pacotes apenas de quem você confia.

Estrutura de um pacote (pasta ou .rbbviz, que é um .zip):
    viz.json   {"format": 1, "id": "chuva-neon", "name": "Chuva Neon", "author": "...", "version": "1.0"}
    viz.py     precisa ter a função  draw(p, w, h, v)
O guia completo está em GUIA-DE-SKINS.txt.
"""
import importlib.util
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .library import data_dir
from .packs import PackError, check_id, stage_package

VIZ_EXTS = {".py", ".json", ".png", ".txt", ".md"}


@dataclass
class VizPack:
    id: str
    name: str
    author: str
    version: str
    description: str
    path: Path


def read_manifest(folder: Path) -> VizPack:
    try:
        data = json.loads((folder / "viz.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise PackError("A pasta não tem um arquivo viz.json.")
    except (ValueError, OSError) as exc:
        raise PackError(f"O arquivo viz.json está com erro de escrita: {exc}")
    if not isinstance(data, dict) or data.get("format") != 1:
        raise PackError('O viz.json precisa ser um bloco { ... } com "format": 1.')
    pid = check_id(data.get("id"), "visualizador")
    name = str(data.get("name") or "").strip()
    if not name or len(name) > 40:
        raise PackError('O campo "name" é obrigatório (até 40 caracteres).')
    if not (folder / "viz.py").is_file():
        raise PackError("O pacote não tem o arquivo viz.py.")
    return VizPack(id=pid, name=name, author=str(data.get("author") or "")[:60],
                   version=str(data.get("version") or "")[:20],
                   description=str(data.get("description") or "")[:300], path=folder)


class VizPackManager:
    def __init__(self):
        self.dir = data_dir() / "visualizers"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.packs = {}
        self.errors = {}

    def scan(self):
        """Só lê os viz.json. Nenhum código de pacote é executado aqui."""
        self.packs, self.errors = {}, {}
        for folder in sorted(p for p in self.dir.iterdir() if p.is_dir()):
            try:
                pack = read_manifest(folder)
            except PackError as exc:
                self.errors[folder.name] = str(exc)
                continue
            self.packs[pack.id] = pack
        return self.packs

    def load_draw(self, pack_id):
        """Executa o viz.py do pacote e devolve a função draw. Só chame para pacotes ativados."""
        pack = self.packs[pack_id]
        spec = importlib.util.spec_from_file_location(f"rbb_viz_{pack.id.replace('-', '_')}", pack.path / "viz.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        draw = getattr(module, "draw", None)
        if not callable(draw):
            raise PackError('O viz.py precisa ter a função "draw(p, w, h, v)".')
        return draw

    def exists(self, pack_id):
        return (self.dir / pack_id).exists()

    def install(self, source, overwrite=False) -> VizPack:
        root, tmp = stage_package(source, "viz.json", VIZ_EXTS, max_files=40, max_bytes=10 * 1024 * 1024)
        try:
            pack = read_manifest(root)
            target = self.dir / pack.id
            if target.exists() and not overwrite:
                raise PackError(f"EXISTS:{pack.id}")
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(root, target)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.scan()
        return self.packs[pack.id]

    def remove(self, pack_id):
        pack = self.packs.get(pack_id)
        if pack is None:
            return
        shutil.rmtree(pack.path, ignore_errors=True)
        self.scan()
