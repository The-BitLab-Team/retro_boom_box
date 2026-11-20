"""Busca de versões novas do programa.

O programa consulta uma página na internet (por padrão, a de "Releases" do GitHub) e, se
houver uma versão maior que a instalada, avisa a pessoa. Ele NUNCA baixa nem instala nada
sozinho: só abre a página da versão nova no navegador, para a pessoa baixar o instalador.
Nada da pessoa é enviado: vai só o pedido comum de uma página, com o nome e a versão do programa.

COMO CONFIGURAR (veja também o ATUALIZACOES.txt): preencha UMA das duas linhas abaixo e
monte o programa de novo.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from . import __version__

# ===================================================================== CONFIGURE AQUI
GITHUB_REPO = "The-BitLab-Team/retro_boom_box"   # Opção 1 (a mais fácil): o repositório no GitHub, no formato "usuario/repositorio"
JSON_URL = ""           # Opção 2: o endereço (https) de um arquivo .json no seu site (formato no ATUALIZACOES.txt)
# =====================================================================

TIMEOUT = 8                         # segundos esperando a resposta
MAX_BYTES = 256 * 1024              # resposta maior que isso é recusada
CHECK_EVERY = 24 * 3600             # a busca automática acontece no máximo uma vez por dia
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")      # só para testes: aceita http daqui
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_VERSION_RE = re.compile(r"^[vV]?(\d{1,6})(?:\.(\d{1,6}))?(?:\.(\d{1,6}))?$")


@dataclass
class Release:
    version: str            # "0.5.0"
    url: str                # página da versão (sempre https), onde a pessoa baixa o instalador
    notes: str = ""         # o que mudou (texto simples)


@dataclass
class Result:
    status: str             # newer, current, notfound, error ou unconfigured
    message: str            # frase pronta para mostrar à pessoa
    release: Release = None


# ------------------------------------------------------------------ configuração e versões
def configured_url():
    """Endereço que será consultado, ou None se ninguém configurou (ou se está escrito errado)."""
    env = os.environ.get("RBB_UPDATE_URL", "").strip()      # só para testes
    if env:
        return env
    repo = GITHUB_REPO.strip().strip("/")
    if repo:
        return f"https://api.github.com/repos/{repo}/releases/latest" if _REPO_RE.match(repo) else None
    return JSON_URL.strip() or None


def parse_version(text):
    """"v0.5.0" -> (0, 5, 0). Só versões estáveis do tipo X, X.Y ou X.Y.Z; o resto (como "0.5.0-beta") vira None."""
    if not isinstance(text, str):
        return None
    m = _VERSION_RE.match(text.strip())
    return tuple(int(g or 0) for g in m.groups()) if m else None


def is_newer(candidate, current=None):
    a, b = parse_version(candidate), parse_version(current or __version__)
    return a is not None and b is not None and a > b


def _is_https(url):
    p = urllib.parse.urlparse(url) if isinstance(url, str) else None
    return bool(p and p.scheme == "https" and p.hostname)


def _allowed(url):
    """https sempre; http só para o próprio computador (testes)."""
    if _is_https(url):
        return True
    p = urllib.parse.urlparse(url) if isinstance(url, str) else None
    return bool(p and p.scheme == "http" and p.hostname in LOCAL_HOSTS)


# ------------------------------------------------------------------ leitura da resposta
def _releases_page(url):
    """Para um endereço da API do GitHub, a página normal das versões (usada se a resposta não trouxer o link)."""
    p = urllib.parse.urlparse(url)
    m = re.match(r"^/repos/([^/]+/[^/]+)/releases", p.path)
    return f"https://github.com/{m.group(1)}/releases" if p.hostname == "api.github.com" and m else ""


def parse_release(data, page_fallback=""):
    """Entende a resposta do GitHub ({"tag_name", "html_url", "body"}) ou o formato simples
    ({"version", "url", "notes"}). Devolve um Release ou None se não entender."""
    if not isinstance(data, dict):
        return None
    if "tag_name" in data:
        if data.get("draft") or data.get("prerelease"):
            return None
        raw, url, notes = data.get("tag_name"), data.get("html_url"), data.get("body")
    elif "version" in data:
        raw, url, notes = data.get("version"), data.get("url"), data.get("notes")
    else:
        return None
    ver = parse_version(raw)
    if ver is None:
        return None
    if not _is_https(url):
        url = page_fallback
    notes = notes.strip()[:1500] if isinstance(notes, str) else ""
    return Release(".".join(str(n) for n in ver), url or "", notes)


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Não deixa um redirecionamento levar a um endereço sem https."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _allowed(newurl):
            raise urllib.error.URLError("redirecionamento recusado")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url):
    request = urllib.request.Request(url, headers={
        "User-Agent": f"RetroBoomBox/{__version__} (verificacao de versao)",
        "Accept": "application/vnd.github+json, application/json",
    })
    with urllib.request.build_opener(_SafeRedirect()).open(request, timeout=TIMEOUT) as resp:
        data = resp.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("resposta grande demais")
    return data


def check(current=None, url=None):
    """Faz a consulta e devolve um Result. Nunca levanta erro (roda em segundo plano)."""
    current = current or __version__
    url = configured_url() if url is None else url
    if not url:
        return Result("unconfigured", "A busca por versões novas ainda não foi configurada. "
                      "Se já preencheu o repositório, confira se está no formato usuario/repositorio. "
                      "Veja o arquivo ATUALIZACOES.txt.")
    if not _allowed(url):
        return Result("error", "O endereço de busca de versões precisa começar com https://.")
    try:
        data = json.loads(_fetch(url).decode("utf-8-sig"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return Result("notfound", "Nenhuma versão foi encontrada nesse endereço. Confira o nome do repositório, "
                          "se ele é público e se já existe pelo menos uma versão publicada.")
        if e.code in (403, 429):
            return Result("error", "O site pediu para esperar um pouco antes de consultar de novo. Tente mais tarde.")
        return Result("error", f"O servidor respondeu com erro {e.code}.")
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return Result("error", "Não foi possível verificar agora (sem internet ou o servidor não respondeu).")
    except (ValueError, UnicodeDecodeError):
        return Result("error", "A resposta do servidor não foi entendida.")
    release = parse_release(data, _releases_page(url))
    if release is None:
        return Result("error", "A resposta do servidor não foi entendida (veja o formato no ATUALIZACOES.txt).")
    if is_newer(release.version, current):
        return Result("newer", f"Há uma versão nova: {release.version} (você usa a {current}).", release)
    return Result("current", f"Você está usando a versão mais recente ({current}).", release)


class UpdateChecker(QObject):
    """Roda `check` em segundo plano, sem travar a janela. O resultado chega pelo sinal `done`."""
    done = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False

    def start(self, url=None):
        self.running = True
        threading.Thread(target=self._run, args=(url,), daemon=True, name="rbb-update").start()

    def _run(self, url):
        try:
            result = check(url=url)
        except Exception as e:                       # não deve acontecer, mas não pode derrubar nada
            result = Result("error", f"Não foi possível verificar agora ({type(e).__name__}).")
        try:
            self.done.emit(result)
        except RuntimeError:                         # a janela já foi fechada
            pass


def due(last_check, now=None):
    """Já passou um dia desde a última busca automática? (relógio mudado para trás também conta como sim)"""
    elapsed = (time.time() if now is None else now) - (last_check if isinstance(last_check, (int, float)) else 0)
    return elapsed >= CHECK_EVERY or elapsed < 0
