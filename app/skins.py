"""Skins: o visual do player vive em pastas, não no código.

Uma skin é uma pasta com um arquivo `skin.json` e, se quiser, imagens (.png).
O guia completo, em português, está em GUIA-DE-SKINS.txt.

Resumo do skin.json:
  format       sempre 1
  id, name, author, version, description
  base         "aero" ou "metal": qual visual desenha o que a skin não definir
  theme        (opcional) cores e fontes que trocam as da base
  body         (opcional) imagem PNG do corpo da janela; o que for transparente fica vazio,
               então a janela pode ter qualquer formato
  layout       (opcional) onde fica cada peça. Sem layout, usa o da base.
  fonts        (opcional) arquivos .ttf/.otf da própria skin
  mini         (opcional) visual próprio do modo mini: {"body": "mini.png", "layout": {...}}
Imagens opcionais ao lado do skin.json:
  buttons/<botao>.png, <botao>_hover.png, <botao>_down.png, <botao>_on.png
  sliders/groove.png, sliders/fill.png, sliders/handle.png
"""
import dataclasses
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtGui import QFontDatabase, QPixmap

from .library import data_dir
from .packs import HEX_RE, PackError, check_id, stage_package
from .themes import THEMES, Theme
from .widgets import SIZES

SKIN_EXTS = {".json", ".png", ".jpg", ".jpeg", ".ttf", ".otf", ".txt", ".md"}
BUTTON_NAMES = ("theme", "gear", "min", "close", "left", "right", "video", "plus", "dots", "folder",
                "shuffle", "prev", "play", "stop", "next", "repeat", "mute", "playlist", "eq", "mini")
BUTTON_KINDS = BUTTON_NAMES + ("pause",)
RECT_NAMES = ("logo", "lcd", "info", "stage", "viz_label", "source", "search", "list", "status", "seek", "volume")
REQUIRED_RECTS = ("info", "stage", "seek")
REQUIRED_BUTTONS = ("prev", "play", "stop", "next")
MINI_REQUIRED_RECTS = ("info", "seek")
MINI_REQUIRED_BUTTONS = ("prev", "play", "next")
MINI_SIZE = (640, 184)
COLOR_FIELDS = ("text", "text_dim", "glyph", "accent", "lcd_top", "lcd_bottom", "lcd_border", "lcd_text",
                "lcd_dim", "list_bg", "list_text", "list_dim", "list_sel_top", "list_sel_bottom", "list_sel_text",
                "list_border", "dialog_bg", "dialog_text", "field_bg", "field_border", "viz_bg",
                "btn_top", "btn_mid", "btn_low", "btn_end", "btn_border", "play_light", "play_mid", "play_dark",
                "groove_a", "groove_b", "fill_a", "fill_b", "knob_a", "knob_b")
DEFAULT_SIZE = (1020, 730)
MAX_BODY = (2400, 1600)


@dataclass
class Skin:
    id: str
    name: str
    author: str
    version: str
    description: str
    base: str
    theme: Theme
    layout: dict
    size: tuple
    body: object = None            # QPixmap ou None (corpo desenhado pelo programa)
    button_images: dict = field(default_factory=dict)   # tipo -> {"": pm, "hover": pm, "down": pm, "on": pm}
    slider_images: dict = field(default_factory=dict)
    path: Path = None
    builtin: bool = False
    mini_layout: dict = None       # layout próprio do modo mini (ou None: usa o padrão da base)
    mini_body: object = None

    @property
    def has_list(self) -> bool:
        return "list" in self.layout

    def view_layout(self, mini: bool) -> dict:
        """Layout em uso: o normal, ou o do modo mini (da skin ou o padrão da base)."""
        if not mini:
            return self.layout
        return self.mini_layout or default_mini_layout(self.base)


# --------------------------------------------------------------------------- layout padrão
def default_layout(base: str) -> dict:
    """Posição de cada peça no visual padrão (janela de 1020x730)."""
    t = THEMES[base]
    ri = 0 if t.button_style == "round" else 1
    sz = lambda c: SIZES[c][ri]
    W, H, S = DEFAULT_SIZE[0], DEFAULT_SIZE[1], 28
    ml, mt, mr, mb = t.margins
    x0, y0, x1, y1 = S + ml, S + mt, W - S - mr, H - S - mb
    cw = x1 - x0
    btn = {}
    L = {"window": [W, H], "buttons": btn}

    xw, xh = sz("xs")
    L["logo"] = [x0, y0, 300, xh]
    x = x1
    for name in ("close", "min", "mini", "gear", "theme"):
        x -= xw
        btn[name] = [x, y0, xw, xh]
        x -= 6

    lw, lh = sz("lg")
    ty = y1 - lh
    seek_y = ty - 12 - 28
    mid_top = y0 + xh + 12
    mid_h = seek_y - 12 - mid_top
    side_w = 340
    lcd_w = cw - 16 - side_w
    L["lcd"] = [x0, mid_top, lcd_w, mid_h]
    ix, iw = x0 + 20, lcd_w - 40
    L["info"] = [ix, mid_top + 14, iw, 124]
    vb_y = mid_top + mid_h - 12 - xh
    st_y = mid_top + 14 + 124 + 8
    L["stage"] = [ix, st_y, iw, vb_y - 8 - st_y]
    btn["left"] = [ix, vb_y, xw, xh]
    btn["video"] = [ix + iw - xw, vb_y, xw, xh]
    btn["right"] = [ix + iw - 2 * xw - 4, vb_y, xw, xh]
    L["viz_label"] = [ix + xw + 4, vb_y, iw - 3 * xw - 12, xh]

    sx = x0 + lcd_w + 16
    sw, sh = sz("sm")
    row_h = max(34, sh)
    by = mid_top + (row_h - sh) // 2
    btn["folder"] = [sx + side_w - sw, by, sw, sh]
    btn["dots"] = [sx + side_w - 2 * sw - 6, by, sw, sh]
    btn["plus"] = [sx + side_w - 3 * sw - 12, by, sw, sh]
    L["source"] = [sx, mid_top, side_w - 3 * sw - 18, row_h]
    L["search"] = [sx, mid_top + row_h + 8, side_w, 32]
    status_h = 36
    L["status"] = [sx, mid_top + mid_h - status_h, side_w, status_h]
    list_y = mid_top + row_h + 8 + 32 + 8
    L["list"] = [sx, list_y, side_w, mid_top + mid_h - status_h - 8 - list_y]

    L["seek"] = [x0, seek_y, cw, 28]
    order = [("shuffle", "sm"), ("prev", "md"), ("play", "lg"), ("stop", "md"), ("next", "md"), ("repeat", "sm")]
    total = sum(sz(c)[0] for _n, c in order) + 10 * (len(order) - 1)
    x = x0 + (cw - total) // 2
    for name, c in order:
        w, h = sz(c)
        btn[name] = [x, ty + (lh - h) // 2, w, h]
        x += w + 10
    vol_w = 150
    L["volume"] = [x1 - vol_w, ty + (lh - 28) // 2, vol_w, 28]
    btn["mute"] = [x1 - vol_w - 10 - sw, ty + (lh - sh) // 2, sw, sh]
    btn["eq"] = [x1 - vol_w - 20 - 2 * sw, ty + (lh - sh) // 2, sw, sh]
    return L


def default_mini_layout(base: str) -> dict:
    """Modo mini padrão (640x184): visor com título e tempo, barra de tempo e os controles principais."""
    t = THEMES[base]
    ri = 0 if t.button_style == "round" else 1
    sz = lambda c: SIZES[c][ri]
    W, H = MINI_SIZE
    x0, x1 = 44, W - 44
    btn = {}
    L = {"window": [W, H], "buttons": btn}
    xw, xh = sz("xs")
    L["lcd"] = [x0 - 8, 26, 398, 62]
    L["info"] = [x0 + 2, 30, 378, 54]
    x = x1
    for name in ("close", "min", "mini", "eq", "gear"):
        x -= xw
        btn[name] = [x, 30, xw, xh]
        x -= 6
    L["seek"] = [x0, 94, x1 - x0, 22]
    order = [("shuffle", "sm"), ("prev", "md"), ("play", "lg"), ("stop", "md"), ("next", "md"), ("repeat", "sm")]
    small = {"md": (34, 34), "lg": (44, 44), "sm": (30, 30)} if ri == 0 else {"md": (40, 30), "lg": (50, 38), "sm": (30, 24)}
    cy = 140
    x = x0
    for name, c in order:
        w, h = small[c]
        btn[name] = [x, cy - h // 2, w, h]
        x += w + 8
    sw, sh = small["sm"]
    vol_w = 134
    mute_x = x1 - vol_w - 6 - sw
    L["stage"] = [x + 8, 120, max(60, min(118, mute_x - 8 - (x + 8))), 40]
    L["volume"] = [x1 - vol_w, cy - 14, vol_w, 28]
    btn["mute"] = [mute_x, cy - sh // 2, sw, sh]
    return L


# --------------------------------------------------------------------------- leitura e validação
def _rect(value, what, window, errors):
    if (not isinstance(value, (list, tuple)) or len(value) != 4
            or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)):
        errors.append(f'"{what}" deve ser uma lista de 4 números: [x, y, largura, altura].')
        return None
    x, y, w, h = (int(v) for v in value)
    if w < 4 or h < 4 or w > 4000 or h > 4000:
        errors.append(f'"{what}": largura e altura devem ficar entre 4 e 4000.')
        return None
    if x < -50 or y < -50 or x + w > window[0] + 50 or y + h > window[1] + 50:
        errors.append(f'"{what}" ficou fora da janela ({window[0]}x{window[1]}).')
        return None
    return [x, y, w, h]


def _theme_overrides(raw, base_theme, errors):
    if raw is None:
        return base_theme
    if not isinstance(raw, dict):
        errors.append('"theme" deve ser um bloco { ... } com cores e fontes.')
        return base_theme
    changes = {}
    for key, value in raw.items():
        if key in COLOR_FIELDS:
            if isinstance(value, str) and HEX_RE.match(value):
                changes[key] = value
            else:
                errors.append(f'theme.{key}: use uma cor no formato "#RRGGBB" (ou "#RRGGBBAA").')
        elif key in ("font", "mono"):
            if isinstance(value, str) and 0 < len(value) <= 60:
                changes[key] = value
            else:
                errors.append(f"theme.{key}: nome de fonte inválido.")
        elif key == "button_style":
            if value in ("round", "rect"):
                changes[key] = value
            else:
                errors.append('theme.button_style deve ser "round" ou "rect".')
        elif key == "viz_style":
            if value in ("glass", "lcd"):
                changes[key] = value
            else:
                errors.append('theme.viz_style deve ser "glass" ou "lcd".')
        elif key == "viz_colors":
            if isinstance(value, list) and len(value) == 3 and all(isinstance(c, str) and HEX_RE.match(c) for c in value):
                changes[key] = tuple(value)
            else:
                errors.append('theme.viz_colors deve ter 3 cores: ["#graves", "#médios", "#agudos"].')
        elif key == "radius":
            if isinstance(value, int) and 0 <= value <= 400:
                changes[key] = value
            else:
                errors.append("theme.radius deve ser um número inteiro de 0 a 400.")
        # chaves desconhecidas são simplesmente ignoradas
    return dataclasses.replace(base_theme, **changes)


def _load_pixmap(path: Path, errors, what):
    pm = QPixmap(str(path))
    if pm.isNull():
        errors.append(f"Não consegui abrir a imagem {what}.")
        return None
    return pm


def load_skin(folder: Path, builtin=False) -> Skin:
    """Lê e valida uma skin. Em caso de problema, levanta PackError com todas as mensagens."""
    folder = Path(folder)
    manifest = folder / "skin.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise PackError("A pasta não tem um arquivo skin.json.")
    except (ValueError, OSError) as exc:
        raise PackError(f"O arquivo skin.json está com erro de escrita: {exc}")
    if not isinstance(data, dict):
        raise PackError("O skin.json precisa começar com { e terminar com }.")

    errors = []
    if data.get("format") != 1:
        errors.append('O campo "format" deve ser 1.')
    try:
        sid = check_id(data.get("id"), "skin")
    except PackError as exc:
        errors.append(str(exc))
        sid = ""
    name = str(data.get("name") or "").strip()
    if not name or len(name) > 60:
        errors.append('O campo "name" é obrigatório (até 60 caracteres).')
    base = data.get("base", "aero")
    if base not in THEMES:
        errors.append(f'O campo "base" deve ser um destes: {", ".join(THEMES)}.')
        base = "aero"
    theme = _theme_overrides(data.get("theme"), THEMES[base], errors)
    theme = dataclasses.replace(theme, label=name or theme.label)

    fonts = data.get("fonts", [])
    if not isinstance(fonts, list) or not all(isinstance(f, str) for f in fonts):
        errors.append('"fonts" deve ser uma lista de nomes de arquivo.')
        fonts = []
    for f in fonts:
        fp = folder / f
        if fp.suffix.lower() not in (".ttf", ".otf") or not fp.is_file() or folder.resolve() not in fp.resolve().parents:
            errors.append(f"Fonte não encontrada ou inválida: {f}")
        else:
            QFontDatabase.addApplicationFont(str(fp))

    body = None
    body_name = data.get("body")
    if body_name is not None:
        bp = (folder / str(body_name))
        if not bp.is_file() or folder.resolve() not in bp.resolve().parents or bp.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            errors.append(f'A imagem do corpo ("body") não foi encontrada: {body_name}')
        else:
            body = _load_pixmap(bp, errors, f'do corpo ("{body_name}")')
            if body is not None and (body.width() > MAX_BODY[0] or body.height() > MAX_BODY[1]):
                errors.append(f"A imagem do corpo é grande demais (máximo {MAX_BODY[0]}x{MAX_BODY[1]}).")
                body = None

    raw_layout = data.get("layout")
    if raw_layout is None:
        if body_name is not None:
            errors.append('Uma skin com imagem de corpo ("body") precisa também do bloco "layout".')
        layout = default_layout(base)
        size = tuple(layout["window"])
    else:
        layout, size = _validate_layout(raw_layout, body, errors)

    mini_layout, mini_body = None, None
    raw_mini = data.get("mini")
    if raw_mini is not None:
        mini_layout, mini_body = _load_mini(folder, raw_mini, errors)

    if errors:
        raise PackError("Esta skin tem problemas:\n- " + "\n- ".join(errors))

    skin = Skin(id=sid, name=name, author=str(data.get("author") or "")[:60], version=str(data.get("version") or "")[:20],
                description=str(data.get("description") or "")[:300], base=base, theme=theme,
                layout=layout, size=size, body=body, path=folder, builtin=builtin,
                mini_layout=mini_layout, mini_body=mini_body)
    _load_images(skin)
    return skin


def _load_mini(folder, raw, errors):
    """Lê o bloco "mini" da skin: imagem de corpo opcional e layout (obrigatório)."""
    if not isinstance(raw, dict) or not isinstance(raw.get("layout"), dict):
        errors.append('"mini" deve ser um bloco { "body": "mini.png", "layout": { ... } }.')
        return None, None
    body = None
    name = raw.get("body")
    if name is not None:
        bp = folder / str(name)
        if not bp.is_file() or folder.resolve() not in bp.resolve().parents or bp.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            errors.append(f'mini.body: imagem não encontrada: {name}')
        else:
            body = _load_pixmap(bp, errors, f'do modo mini ("{name}")')
            if body is not None and (body.width() > MAX_BODY[0] or body.height() > MAX_BODY[1]):
                errors.append("mini.body: imagem grande demais.")
                body = None
    sub = []
    layout, _size = _validate_layout(raw["layout"], body, sub, mini=True)
    errors.extend(f"mini: {m}" for m in sub)
    return layout, body


def _validate_layout(raw, body, errors, mini=False):
    if not isinstance(raw, dict):
        errors.append('"layout" deve ser um bloco { ... }.')
        return default_layout("aero"), DEFAULT_SIZE
    default_size = MINI_SIZE if mini else DEFAULT_SIZE
    lo = (200, 60) if mini else (300, 150)
    win = raw.get("window")
    if win is None:
        size = (body.width(), body.height()) if body is not None else default_size
    elif (isinstance(win, list) and len(win) == 2 and all(isinstance(v, int) and not isinstance(v, bool) for v in win)
          and lo[0] <= win[0] <= 2400 and lo[1] <= win[1] <= 1600):
        size = (win[0], win[1])
    else:
        errors.append(f'layout.window deve ser [largura, altura] (de {lo[0]}x{lo[1]} até 2400x1600).')
        size = default_size
    layout = {"window": list(size), "buttons": {}}
    for key in RECT_NAMES:
        if key in raw and raw[key] is not None:
            r = _rect(raw[key], f"layout.{key}", size, errors)
            if r:
                layout[key] = r
    buttons = raw.get("buttons", {})
    if not isinstance(buttons, dict):
        errors.append('"layout.buttons" deve ser um bloco { "play": [x, y, l, a], ... }.')
        buttons = {}
    for key, value in buttons.items():
        if key not in BUTTON_NAMES:
            continue
        r = _rect(value, f"layout.buttons.{key}", size, errors)
        if r:
            layout["buttons"][key] = r
    for key in (MINI_REQUIRED_RECTS if mini else REQUIRED_RECTS):
        if key not in layout:
            errors.append(f'Falta "{key}" no layout.')
    for key in (MINI_REQUIRED_BUTTONS if mini else REQUIRED_BUTTONS):
        if key not in layout["buttons"]:
            errors.append(f'Falta o botão "{key}" no layout.')
    if not mini and "list" not in layout and "playlist" not in layout["buttons"]:
        errors.append('Sem "list" no layout, é preciso ter o botão "playlist" para abrir a lista numa janela à parte.')
    return layout, size


def _load_images(skin: Skin):
    folder = skin.path
    errs = []
    for kind in BUTTON_KINDS:
        states = {}
        for state, suffix in (("", ""), ("hover", "_hover"), ("down", "_down"), ("on", "_on")):
            p = folder / "buttons" / f"{kind}{suffix}.png"
            if p.is_file():
                pm = _load_pixmap(p, errs, f"buttons/{p.name}")
                if pm is not None:
                    states[state] = pm
        if states:
            skin.button_images[kind] = states
    for part in ("groove", "fill", "handle"):
        p = folder / "sliders" / f"{part}.png"
        if p.is_file():
            pm = _load_pixmap(p, errs, f"sliders/{part}.png")
            if pm is not None:
                skin.slider_images[part] = pm


# --------------------------------------------------------------------------- gerenciador
class SkinManager:
    def __init__(self):
        self.builtin_dir = Path(__file__).parent / "builtin_skins"
        self.user_dir = data_dir() / "skins"
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.skins = {}
        self.errors = {}

    def scan(self):
        self.skins, self.errors = {}, {}
        for builtin, root in ((True, self.builtin_dir), (False, self.user_dir)):
            if not root.is_dir():
                continue
            for folder in sorted(p for p in root.iterdir() if p.is_dir()):
                try:
                    skin = load_skin(folder, builtin=builtin)
                except PackError as exc:
                    self.errors[folder.name] = str(exc)
                    continue
                if skin.id in self.skins:
                    self.errors[folder.name] = f'O id "{skin.id}" já está em uso por outra skin.'
                    continue
                self.skins[skin.id] = skin
        return self.skins

    def get(self, skin_id):
        return self.skins.get(skin_id) or self.skins.get("aero")

    def ids(self):
        return list(self.skins)

    def exists_user(self, skin_id):
        return (self.user_dir / skin_id).exists()

    def install(self, source, overwrite=False) -> Skin:
        root, tmp = stage_package(source, "skin.json", SKIN_EXTS)
        try:
            skin = load_skin(root)
            if skin.id in {s.id for s in self.skins.values() if s.builtin}:
                raise PackError(f'O id "{skin.id}" é reservado para uma skin que já vem com o programa. Troque o "id".')
            target = self.user_dir / skin.id
            if target.exists() and not overwrite:
                raise PackError(f'EXISTS:{skin.id}')
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(root, target)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.scan()
        return self.skins[skin.id]

    def remove(self, skin_id):
        skin = self.skins.get(skin_id)
        if skin is None or skin.builtin:
            raise PackError("Esta skin faz parte do programa e não pode ser removida.")
        shutil.rmtree(skin.path, ignore_errors=True)
        self.scan()
