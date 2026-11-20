"""Ferramentas comuns para instalar pacotes (skins e visualizadores) com segurança.

Um pacote é uma pasta, ou essa pasta compactada em .zip (as skins usam a extensão
.rbbskin e os visualizadores .rbbviz, mas é só um .zip com outro nome).
Antes de copiar qualquer coisa para o computador, conferimos:
  - só tipos de arquivo permitidos entram (nada de .exe, .bat, .dll...);
  - nenhum arquivo pode "escapar" da pasta do pacote (caminhos com ".." ou absolutos);
  - limite de quantidade de arquivos e de tamanho total.
"""
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


class PackError(Exception):
    """Erro com mensagem já pronta para mostrar à pessoa."""


ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def check_id(value, what="pacote"):
    if not isinstance(value, str) or not ID_RE.match(value):
        raise PackError(f'O campo "id" do {what} deve ter só letras minúsculas, números, "-" e "_" (até 40 caracteres).')
    return value


def _clean_member(name: str) -> PurePosixPath:
    name = name.replace("\\", "/")
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or ":" in name or name.startswith("/"):
        raise PackError(f"Caminho de arquivo suspeito dentro do pacote: {name}")
    return p


def safe_extract(zip_path, dest: Path, allowed_ext, max_files=300, max_bytes=60 * 1024 * 1024):
    """Descompacta o .zip em `dest` aplicando todas as verificações de segurança."""
    try:
        zf = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError):
        raise PackError("Este arquivo não é um pacote válido (não consegui abrir o .zip).")
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > max_files:
            raise PackError(f"Pacote com arquivos demais ({len(infos)}). O limite é {max_files}.")
        if sum(i.file_size for i in infos) > max_bytes:
            raise PackError("Pacote grande demais (mais de %d MB descompactado)." % (max_bytes // 1024 // 1024))
        dest = dest.resolve()
        for info in infos:
            rel = _clean_member(info.filename)
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise PackError(f"Atalhos não são permitidos dentro de pacotes: {info.filename}")
            if rel.suffix.lower() not in allowed_ext:
                raise PackError(f"Tipo de arquivo não permitido no pacote: {info.filename}")
            target = (dest / Path(*rel.parts)).resolve()
            if dest not in target.parents:
                raise PackError(f"Caminho de arquivo suspeito dentro do pacote: {info.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


def find_root(folder: Path, manifest_name: str) -> Path:
    """Acha a pasta que contém o arquivo de manifesto (na raiz ou numa subpasta só)."""
    if (folder / manifest_name).is_file():
        return folder
    subs = [p for p in folder.iterdir() if p.is_dir()]
    if len(subs) == 1 and (subs[0] / manifest_name).is_file():
        return subs[0]
    raise PackError(f"Não encontrei o arquivo {manifest_name} no pacote.")


def copy_checked(src: Path, dest: Path, allowed_ext, max_files=300, max_bytes=60 * 1024 * 1024):
    """Copia uma pasta de pacote (sem zip) conferindo tipos e tamanhos."""
    files = [p for p in src.rglob("*") if p.is_file()]
    if len(files) > max_files:
        raise PackError(f"Pacote com arquivos demais ({len(files)}). O limite é {max_files}.")
    if sum(p.stat().st_size for p in files) > max_bytes:
        raise PackError("Pacote grande demais.")
    for p in files:
        if p.is_symlink():
            raise PackError(f"Atalhos não são permitidos dentro de pacotes: {p.name}")
        if p.suffix.lower() not in allowed_ext:
            raise PackError(f"Tipo de arquivo não permitido no pacote: {p.name}")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for p in files:
        target = dest / p.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)


def stage_package(source, manifest_name, allowed_ext, **limits):
    """Prepara um pacote (pasta ou .zip) numa pasta temporária segura. Devolve (raiz, pasta_temp)."""
    source = Path(source)
    tmp = Path(tempfile.mkdtemp(prefix="rbb_pack_"))
    try:
        if source.is_dir():
            copy_checked(source, tmp / "pkg", allowed_ext, **limits)
        elif source.is_file():
            safe_extract(source, tmp / "pkg", allowed_ext, **limits)
        else:
            raise PackError("Arquivo ou pasta não encontrado.")
        return find_root(tmp / "pkg", manifest_name), tmp
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
