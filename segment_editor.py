"""
segment_editor.py - Optimalizovaný editor nalezených momentů (Pecislav Studio).

Architektura pro maximální výkon na notebooku:
- SEZNAM: Tkinter Canvas s textem (ne CTk widgety na každý řádek).
  Canvas.coords/itemconfig jsou ~100× rychlejší než CTk Frame.configure().
  Scrollování je okamžité - jen posun yview.
- PŘEHRÁVAČ: konverze PIL->PhotoImage proběhne v background threadu.
  Main thread dostane hotový PhotoImage objekt a jen zavolá itemconfig() -> nulová práce.
- Žádné pack_forget/pack při scrollu, žádné CTkFrame.configure na každý řádek.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw

from ffmpeg_utils import find_binary, get_base_dir

try:
    ctk.DrawEngine.preferred_drawing_method = "polygon_shapes"
except Exception:
    pass


def apply_inter_to_tk_fonts(family: Optional[str] = None, root: Optional[tk.Misc] = None):
    """Configures all default Tkinter named fonts to use the specified font family."""
    fam = family or "Inter"
    try:
        import tkinter.font as tkfont
        for name in [
            "TkDefaultFont", "TkTextFont", "TkFixedFont", "TkMenuFont",
            "TkHeadingFont", "TkCaptionFont", "TkSmallCaptionFont",
            "TkIconFont", "TkTooltipFont"
        ]:
            try:
                tkfont.nametofont(name, root=root).configure(family=fam)
            except Exception:
                pass
    except Exception:
        pass


def _init_fonts(font_override: Optional[str] = None) -> str:
    chosen = font_override or "Inter"
    fonts_added = False
    try:
        fonts_dir = get_base_dir() / "assets" / "fonts"
        if fonts_dir.is_dir():
            for f in fonts_dir.glob("*.ttf"):
                try:
                    ctk.FontManager.load_font(str(f))
                except Exception:
                    pass
                if sys.platform.startswith("win"):
                    try:
                        import ctypes
                        res = ctypes.windll.gdi32.AddFontResourceExW(str(f), 0x10, 0)
                        if res > 0:
                            fonts_added = True
                    except Exception:
                        pass
        if sys.platform.startswith("win") and fonts_added:
            try:
                import ctypes
                ctypes.windll.user32.SendMessageW(0xFFFF, 0x001D, 0, 0)  # WM_FONTCHANGE
            except Exception:
                pass
    except Exception:
        pass
    try:
        import tkinter.font as tkfont
        temp = None
        if not getattr(tk, "_default_root", None):
            temp = tk.Tk()
            temp.withdraw()
        fams = set(tkfont.families())
        pref_list = [font_override] if font_override else []
        pref_list.extend(["Inter", "Segoe UI Variable Text", "Segoe UI", "Poppins", "Montserrat"])
        for pref in pref_list:
            if pref and pref in fams:
                chosen = pref
                break
        if temp:
            temp.destroy()
    except Exception:
        chosen = "Inter" if sys.platform.startswith("win") else "Segoe UI"
    try:
        ctk.ThemeManager.theme["CTkFont"]["family"] = chosen
    except Exception:
        pass
    apply_inter_to_tk_fonts(chosen)
    return chosen

APP_FONT = _init_fonts()


# ---------------------------------------------------------------------------
# Barvy (hex stringy, ne tuple - rychlejší pro Canvas)
# ---------------------------------------------------------------------------
_MODE = ctk.get_appearance_mode()  # "Dark" nebo "Light"

def _c(light: str, dark: str) -> str:
    return dark if ctk.get_appearance_mode() == "Dark" else light

BG_WIN       = _c("#F0F2F5", "#0F1013")
BG_CARD      = _c("#FFFFFF", "#181920")
BG_ROW       = _c("#F8F9FA", "#141519")
BG_ROW_SEL   = _c("#FFF7ED", "#24170E")
BD_ROW       = _c("#CBD5E1", "#333338")
BD_ROW_SEL   = "#FF6D00"
ORANGE       = "#FF6D00"
ORANGE_HV    = "#E66200"
TXT_MAIN     = _c("#111827", "#F9FAFB")
TXT_MUTED    = _c("#6B7280", "#71717A")
TXT_BODY     = _c("#4B5563", "#9CA3AF")
TXT_ORANGE   = "#FF6D00"
BADGE_AI_BG  = _c("#FEF3C7", "#2D2411")
BADGE_AI_FG  = _c("#D97706", "#FBBF24")
CHIP_BG      = _c("#EDF0F4", "#1E2028")
BG_PLAYER    = "#0B0C10"

# CTkFrame-kompatibilní tuple barvy pro widgety mimo Canvas
BG_WIN_T     = ("#F0F2F5", "#0F1013")
BG_CARD_T    = ("#FFFFFF", "#181920")
BG_INNER_T   = ("#F8F9FA", "#141519")
BD_CARD_T    = ("#CBD5E1", "#333338")
BD_ACT_T     = ("#FF6D00", "#FF6D00")
TXT_TITLE_T  = ("#111827", "#F9FAFB")
TXT_BODY_T   = ("#4B5563", "#9CA3AF")
TXT_MUTED_T  = ("#6B7280", "#71717A")
OBG_T        = ("#FFF7ED", "#26170E")
BADGE_BG_T   = ("#FEF3C7", "#2D2411")
BADGE_FG_T   = ("#D97706", "#FBBF24")

# ---------------------------------------------------------------------------
# Video přehrávač - rozlišení
# ---------------------------------------------------------------------------
PREV_W = 448
PREV_H = 252
PLAY_FPS = 18          # Snímky za sekundu (notebook-friendly)
DISP_MS  = 25          # Display timer interval (~40 Hz) - plynulý náhled bez trhání

# ---------------------------------------------------------------------------
# Canvas seznam - geometrie jednoho řádku
# ---------------------------------------------------------------------------
ROW_H     = 48          # výška jednoho řádku v px
ROW_PAD_X = 10
ROW_PAD_Y = 3


# ---------------------------------------------------------------------------
# Pomocné funkce
# ---------------------------------------------------------------------------

def format_moments_count(count: int, lang: str = "cs") -> str:
    if lang == "en":
        return f"{count} clip" if count == 1 else f"{count} clips"
    n = abs(count)
    if n % 100 in (11, 12, 13, 14):
        return f"{count} momentů"
    r = n % 10
    if r == 1:
        return f"{count} moment"
    if r in (2, 3, 4):
        return f"{count} momenty"
    return f"{count} momentů"


def fmt_t(sec: float) -> str:
    sec = max(0.0, sec)
    s = int(round(sec))
    h, rem = divmod(s, 3600)
    m, s2 = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s2:02d}" if h else f"{m:02d}:{s2:02d}"


def _grab_frame(video_path: Path, ts: float, w: int = PREV_W, h: int = PREV_H) -> Optional[Image.Image]:
    """Extrahuje jeden snímek jako čistý PIL Image (bezpečné volat z background threadu)."""
    ffmpeg = find_binary("ffmpeg")
    if not ffmpeg or not video_path.is_file():
        return None
    cmd = [
        str(ffmpeg), "-ss", f"{ts:.2f}", "-i", str(video_path),
        "-vframes", "1", "-vf", f"scale={w}:{h}",
        "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
    ]
    try:
        cflags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
        sinfo = None
        if sys.platform.startswith("win"):
            sinfo = subprocess.STARTUPINFO()
            sinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            sinfo.wShowWindow = 0
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            startupinfo=sinfo,
            creationflags=cflags,
        )
        data, _ = p.communicate(timeout=4.0)
        if data:
            return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        pass
    return None


def _load_ctk_icon(name: str, size: Tuple[int, int] = (20, 20)) -> Optional[ctk.CTkImage]:
    """Loads a PNG icon from assets/icons/ as CTkImage with automatic optical trimming and centering."""
    icon_path = Path(__file__).parent / "assets" / "icons" / f"{name}.png"
    if icon_path.is_file():
        try:
            im = Image.open(icon_path)
            bbox = im.getbbox()
            if bbox:
                bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
                max_dim = max(bw, bh)
                cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
                pad = max_dim * 0.10
                half = (max_dim / 2) + pad
                crop_box = (
                    max(0, int(cx - half)),
                    max(0, int(cy - half)),
                    min(im.width, int(cx + half)),
                    min(im.height, int(cy + half)),
                )
                im = im.crop(crop_box)
            return ctk.CTkImage(light_image=im, dark_image=im, size=size)
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Modern Anti-Aliased Checkbox (Identical to Facecam AI)
# ---------------------------------------------------------------------------

class ModernCheckBox(ctk.CTkFrame):
    """
    Pixel-perfect, anti-aliased modern rounded checkbox matching Facecam AI.
    Features 4x supersampling with Lanczos downscaling, signature orange fill,
    crisp checkmark, full-frame clickability, and hover states.
    """
    _icon_cache: Dict[int, Dict[str, ctk.CTkImage]] = {}

    @classmethod
    def _get_icons(cls, size: int = 22) -> Dict[str, ctk.CTkImage]:
        if size in cls._icon_cache:
            return cls._icon_cache[size]

        scale = 4
        s = size * scale
        r = int(5.5 * scale)
        bw = int(1.8 * scale)

        def make_box(fill, outline, is_checked=False, bg=(30, 32, 43)):
            img = Image.new("RGBA", (s, s), (*bg, 255))
            d = ImageDraw.Draw(img)
            if outline:
                d.rounded_rectangle(
                    [bw // 2, bw // 2, s - 1 - bw // 2, s - 1 - bw // 2],
                    radius=r,
                    fill=fill,
                    outline=outline,
                    width=bw
                )
            else:
                d.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=fill)
            if is_checked:
                cw = int(2.4 * scale)
                p1 = (s * 0.27, s * 0.50)
                p2 = (s * 0.44, s * 0.69)
                p3 = (s * 0.74, s * 0.31)
                d.line([p1, p2, p3], fill=(255, 255, 255, 255), width=cw, joint="curve")
            return img.resize((size, size), Image.Resampling.LANCZOS)

        bg_d = (30, 32, 43)
        bg_l = (255, 255, 255)

        u_dark = make_box((28, 30, 39, 255), (66, 72, 92, 255), bg=bg_d)
        u_dark_h = make_box((35, 38, 50, 255), (255, 109, 0, 255), bg=bg_d)
        u_light = make_box((255, 255, 255, 255), (203, 213, 225, 255), bg=bg_l)
        u_light_h = make_box((248, 250, 252, 255), (255, 109, 0, 255), bg=bg_l)

        c_dark = make_box((255, 109, 0, 255), None, is_checked=True, bg=bg_d)
        c_dark_h = make_box((255, 133, 40, 255), None, is_checked=True, bg=bg_d)
        c_light = make_box((255, 109, 0, 255), None, is_checked=True, bg=bg_l)
        c_light_h = make_box((255, 133, 40, 255), None, is_checked=True, bg=bg_l)

        icons = {
            "unchecked": ctk.CTkImage(light_image=u_light, dark_image=u_dark, size=(size, size)),
            "unchecked_hover": ctk.CTkImage(light_image=u_light_h, dark_image=u_dark_h, size=(size, size)),
            "checked": ctk.CTkImage(light_image=c_light, dark_image=c_dark, size=(size, size)),
            "checked_hover": ctk.CTkImage(light_image=c_light_h, dark_image=c_dark_h, size=(size, size))
        }
        cls._icon_cache[size] = icons
        return icons

    def __init__(
        self,
        parent,
        text: str = "",
        checked: bool = True,
        variable: Optional[Any] = None,
        command: Optional[Callable] = None,
        size: int = 22,
        bg_color: Optional[str] = None,
        sel_bg_color: Optional[str] = None,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", cursor="hand2")
        self.variable = variable if variable is not None else ctk.BooleanVar(value=checked)
        if variable is not None and checked is not None:
            self.variable.set(checked)
        self.command = command
        self._size = size
        self._icons = self._get_icons(size)
        self._hovered = False
        self._state = kwargs.get("state", "normal")
        self.bg_color = bg_color
        self.sel_bg_color = sel_bg_color
        self.is_selected = False

        self._box_lbl = ctk.CTkLabel(
            self,
            text="",
            image=self._get_current_image(),
            width=size,
            height=size,
            cursor="hand2"
        )
        self._box_lbl.pack(side="left", padx=0)

        if text:
            self._text_lbl = ctk.CTkLabel(
                self,
                text=text,
                anchor="w",
                cursor="hand2"
            )
            self._text_lbl.pack(side="left", padx=(8, 0))
            self._text_lbl.bind("<Button-1>", self._on_click)
            self._text_lbl.bind("<Enter>", self._on_enter)
            self._text_lbl.bind("<Leave>", self._on_leave)

        for w in (self, self._box_lbl):
            w.bind("<Button-1>", self._on_click, add="+")
            w.bind("<Enter>", self._on_enter, add="+")
            w.bind("<Leave>", self._on_leave, add="+")

        if hasattr(self.variable, "trace_add"):
            self._trace_id = self.variable.trace_add("write", lambda *_: self._update_image())
        elif hasattr(self.variable, "trace"):
            self._trace_id = self.variable.trace("w", lambda *_: self._update_image())

    def bind(self, sequence=None, command=None, add="+"):
        effective_add = "+" if (add is None or add is True) else add
        res = super().bind(sequence, command, add=effective_add)
        if sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            if hasattr(self, "_box_lbl"):
                try:
                    self._box_lbl.bind(sequence, command, add=effective_add)
                except Exception:
                    pass
            if hasattr(self, "_text_lbl"):
                try:
                    self._text_lbl.bind(sequence, command, add=effective_add)
                except Exception:
                    pass
        return res

    @property
    def checked(self) -> bool:
        return bool(self.variable.get())

    @checked.setter
    def checked(self, value: bool):
        self.set(value)

    def set_checked(self, value: bool):
        self.set(value)

    def draw(self, is_selected: Optional[bool] = None):
        if is_selected is not None:
            self.is_selected = is_selected

    def set_colors(self, bg_color: str, sel_bg_color: str):
        self.bg_color = bg_color
        self.sel_bg_color = sel_bg_color

    def _get_current_image(self) -> ctk.CTkImage:
        val = bool(self.variable.get()) if self.variable else False
        if val:
            return self._icons["checked_hover"] if self._hovered else self._icons["checked"]
        else:
            return self._icons["unchecked_hover"] if self._hovered else self._icons["unchecked"]

    def _update_image(self):
        if hasattr(self, "_box_lbl") and self._box_lbl.winfo_exists():
            self._box_lbl.configure(image=self._get_current_image())

    def _on_enter(self, event=None):
        if self._state == "disabled":
            return
        self._hovered = True
        self._update_image()

    def _on_leave(self, event=None):
        self._hovered = False
        self._update_image()

    def _on_click(self, event=None):
        if self._state == "disabled":
            return "break"
        new_val = not bool(self.variable.get())
        self.variable.set(new_val)
        self._update_image()
        if callable(self.command):
            try:
                self.command(new_val)
            except TypeError:
                self.command()
        return "break"

    def get(self) -> bool:
        return bool(self.variable.get())

    def set(self, value: bool):
        self.variable.set(bool(value))
        self._update_image()

    def select(self):
        self.set(True)

    def deselect(self):
        self.set(False)

    def toggle(self):
        self._on_click()


ModernCheckCircle = ModernCheckBox


# ===========================================================================
# Velký náhled (Large Theater Preview)
# ===========================================================================

LARGE_PREV_W = 960
LARGE_PREV_H = 540
LARGE_PLAY_FPS = 30
LARGE_DISP_MS = 16


class LargePreviewDialog(ctk.CTkToplevel):
    """
    Samostatné zvětšené okno náhledu segmentu ve vysokém rozlišení (960x540).
    Poskytuje plnohodnotné ovládání přehrávání: Play/Pause, Replay, interaktivní Scrubber,
    přepínání zahrnutí do výsledného videa a klávesové zkratky (Mezerník, Esc, Šipky).
    """

    def __init__(
        self,
        parent: ctk.CTkToplevel | ctk.CTk,
        video_path: Path,
        seg: Tuple,
        seg_idx: int,
        is_included: bool,
        lang: str = "cs",
        on_toggle_inc: Optional[Callable[[int, bool], None]] = None,
    ):
        super().__init__(parent)
        self._parent = parent
        self.video_path = video_path
        self.seg = seg
        self.seg_idx = seg_idx
        self.is_included = is_included
        self.lang = lang
        self.on_toggle_inc = on_toggle_inc

        self.s0 = float(seg[0])
        self.s1 = float(seg[1])
        self.dur = max(0.1, self.s1 - self.s0)

        # Okno setup
        title = (
            f"SnapCut • Velký náhled #{seg_idx + 1:02d} ({fmt_t(self.s0)} → {fmt_t(self.s1)})"
            if self.lang == "cs"
            else f"SnapCut • Large Preview #{seg_idx + 1:02d} ({fmt_t(self.s0)} → {fmt_t(self.s1)})"
        )
        self.title(title)
        self.geometry("1020x710")
        self.minsize(980, 680)
        self.configure(fg_color=BG_WIN_T)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Klávesové zkratky
        self.bind("<Escape>", lambda _: self._on_close())
        self.bind("<space>", lambda _: self._toggle_play())
        self.bind("<Left>", lambda _: self._seek_relative(-2.0))
        self.bind("<Right>", lambda _: self._seek_relative(2.0))

        # Ikony
        self._icon_play = _load_ctk_icon("play", (22, 22))
        self._icon_pause = _load_ctk_icon("pause", (22, 22))
        self._icon_check = _load_ctk_icon("check", (20, 20))
        self._icon_reload = _load_ctk_icon("reload", (20, 20))
        self._icon_close = _load_ctk_icon("close", (18, 18))

        # Stav přehrávače
        self._playing = False
        self._closing = False
        self._stop_ev = threading.Event()
        self._ended_ev = threading.Event()
        self._vid_proc: Optional[subprocess.Popen] = None
        self._aud_proc: Optional[subprocess.Popen] = None
        self._frame_lock = threading.Lock()
        self._next_frame: Optional[Tuple[Image.Image, float]] = None
        self._cur_photo: Optional[ImageTk.PhotoImage] = None
        self._canvas_img: Optional[int] = None
        self._disp_id: Optional[str] = None
        self._play_session_id: int = 0
        self._cur_play_offset: float = 0.0

        self._center()
        self._apply_titlebar()
        self._build_ui()

        # Po otevření zobraz úvodní snímek a začni přehrávat
        self.after(50, self._init_preview)

    def _center(self):
        try:
            self.update_idletasks()
            w, h = 1020, 710
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            px = self._parent.winfo_x()
            py = self._parent.winfo_y()
            pw = self._parent.winfo_width()
            ph = self._parent.winfo_height()
            if pw > 100 and ph > 100:
                cx = px + pw // 2
                cy = py + ph // 2
                x = max(10, min(sw - w - 10, cx - w // 2))
                y = max(10, min(sh - h - 10, cy - h // 2))
            else:
                x = max(10, (sw - w) // 2)
                y = max(10, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _apply_titlebar(self):
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if not hwnd:
                hwnd = self.winfo_id()
            is_dark = (ctk.get_appearance_mode().lower() == "dark")
            val = ctypes.c_int(1 if is_dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
        except Exception:
            pass

    def _build_ui(self):
        # 1. Horní záhlaví
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(12, 8))

        t_title = (
            f"● Moment #{self.seg_idx + 1:02d} • Velký náhled"
            if self.lang == "cs"
            else f"● Moment #{self.seg_idx + 1:02d} • Large Preview"
        )
        t_sub = (
            f"{fmt_t(self.s0)}  →  {fmt_t(self.s1)}   (Délka momentu: {fmt_t(self.dur)})"
            if self.lang == "cs"
            else f"{fmt_t(self.s0)}  →  {fmt_t(self.s1)}   (Duration: {fmt_t(self.dur)})"
        )

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            left, text=t_title, font=ctk.CTkFont(size=16, weight="bold"), text_color=TXT_TITLE_T
        ).pack(anchor="w")
        ctk.CTkLabel(
            left, text=t_sub, font=ctk.CTkFont(size=12, weight="bold"), text_color=ORANGE
        ).pack(anchor="w")

        # Tlačítko zavřít
        btn_close = ctk.CTkButton(
            hdr,
            text="  Zavřít (Esc)" if self.lang == "cs" else "  Close (Esc)",
            image=self._icon_close,
            compound="left",
            command=self._on_close,
            height=32,
            width=120,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=BG_INNER_T,
            hover_color=("#E5E7EB", "#252834"),
            text_color=TXT_TITLE_T,
            border_width=1,
            border_color=BD_CARD_T,
            corner_radius=8,
        )
        btn_close.pack(side="right")

        # 2. Velké video plátno (960x540)
        cframe = ctk.CTkFrame(
            self,
            fg_color=BG_PLAYER,
            corner_radius=12,
            border_width=1,
            border_color=BD_CARD_T,
        )
        cframe.pack(padx=20, pady=(0, 10))

        self._vcanvas = ctk.CTkCanvas(
            cframe,
            width=LARGE_PREV_W,
            height=LARGE_PREV_H,
            bg="#000000",
            highlightthickness=0,
            cursor="hand2",
        )
        self._vcanvas.pack(padx=2, pady=2)
        self._vcanvas.bind("<Button-1>", lambda _: self._toggle_play())

        # 3. Scrubber časová osa
        sb = ctk.CTkFrame(self, fg_color="transparent")
        sb.pack(fill="x", padx=24, pady=(0, 10))

        self._lbl_ct = ctk.CTkLabel(
            sb, text="00:00", font=ctk.CTkFont(size=12, weight="bold"), text_color=TXT_TITLE_T, width=50
        )
        self._lbl_ct.pack(side="left")

        self._pbar = ctk.CTkProgressBar(
            sb, height=8, progress_color=ORANGE, fg_color=BG_INNER_T, corner_radius=4
        )
        self._pbar.pack(side="left", fill="x", expand=True, padx=8)
        self._pbar.set(0.0)
        self._pbar.bind("<Button-1>", self._on_scrubber_click)

        self._lbl_tt = ctk.CTkLabel(
            sb, text=fmt_t(self.dur), font=ctk.CTkFont(size=12), text_color=TXT_MUTED_T, width=50
        )
        self._lbl_tt.pack(side="right")

        # 4. Spodní lišta s ovládacími prvky
        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.pack(fill="x", padx=24, pady=(0, 12))

        # Play / Pause
        self._btn_pp = ctk.CTkButton(
            ctrl,
            text="Přehrát náhled (Mezerník)" if self.lang == "cs" else "Play Preview (Space)",
            image=self._icon_play,
            compound="left",
            command=self._toggle_play,
            height=38,
            width=190,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ORANGE,
            hover_color=ORANGE_HV,
            text_color="#FFFFFF",
            corner_radius=8,
        )
        self._btn_pp.pack(side="left", padx=(0, 8))

        # Replay
        self._btn_replay = ctk.CTkButton(
            ctrl,
            text="Znovu" if self.lang == "cs" else "Replay",
            image=self._icon_reload,
            compound="left",
            command=self._restart_play,
            height=38,
            width=100,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=BG_INNER_T,
            hover_color=("#E5E7EB", "#252834"),
            text_color=TXT_TITLE_T,
            border_width=1,
            border_color=BD_CARD_T,
            corner_radius=8,
        )
        self._btn_replay.pack(side="left", padx=(0, 8))

        # Zahrnutí do výsledného videa
        self._btn_inc = ctk.CTkButton(
            ctrl,
            text="",
            command=self._toggle_inc,
            height=38,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=8,
        )
        self._btn_inc.pack(side="left", padx=(0, 8))
        self._update_inc_btn()

        # Nápověda kláves
        hint_text = (
            "Mezerník: Přehrát/Pauza  •  ← / → : Posun ±2s  •  Esc: Zavřít"
            if self.lang == "cs"
            else "Space: Play/Pause  •  ← / → : Seek ±2s  •  Esc: Close"
        )
        ctk.CTkLabel(
            ctrl, text=hint_text, font=ctk.CTkFont(size=11), text_color=TXT_MUTED_T
        ).pack(side="right")

    def _update_inc_btn(self):
        if self.is_included:
            t = "Zahrnuto do výsledného videa" if self.lang == "cs" else "Included in Cut"
            self._btn_inc.configure(
                text=t,
                image=self._icon_check,
                compound="left",
                fg_color=("#ECFDF5", "#062E1E"),
                hover_color=("#D1FAE5", "#0F4733"),
                text_color=("#059669", "#34D399"),
                border_width=1,
                border_color=("#10B981", "#059669"),
            )
        else:
            t = "  Vyřazeno ze sestřihu" if self.lang == "cs" else "  Excluded from Cut"
            self._btn_inc.configure(
                text=t,
                image=self._icon_close,
                compound="left",
                fg_color=("#FEF2F2", "#261316"),
                hover_color=("#FEE2E2", "#3B1B20"),
                text_color=("#DC2626", "#F87171"),
                border_width=1,
                border_color=("#F87171", "#DC2626"),
            )

    def _toggle_inc(self):
        self.is_included = not self.is_included
        self._update_inc_btn()
        if self.on_toggle_inc:
            try:
                self.on_toggle_inc(self.seg_idx, self.is_included)
            except Exception:
                pass

    def _init_preview(self):
        if self._closing:
            return
        def bg_load():
            img = _grab_frame(self.video_path, self.s0, w=LARGE_PREV_W, h=LARGE_PREV_H)
            if img and not self._closing:
                self.after(0, lambda: self._show_static_frame(img))
                self.after(100, self._start_play)

        threading.Thread(target=bg_load, daemon=True).start()

    def _show_static_frame(self, img: Image.Image):
        if self._closing:
            return
        try:
            photo = ImageTk.PhotoImage(img)
            self._cur_photo = photo
            if self._canvas_img is None:
                self._canvas_img = self._vcanvas.create_image(0, 0, image=photo, anchor="nw")
            else:
                self._vcanvas.itemconfig(self._canvas_img, image=photo)
        except Exception:
            pass

    def _toggle_play(self):
        if self._playing:
            self._pause_play()
        else:
            self._start_play()

    def _restart_play(self):
        self._stop_play()
        self._cur_play_offset = 0.0
        self._start_play()

    def _seek_relative(self, delta: float):
        new_off = max(0.0, min(self.dur - 0.1, self._cur_play_offset + delta))
        self._seek_to(new_off)

    def _on_scrubber_click(self, event):
        try:
            bar_w = self._pbar.winfo_width()
            if bar_w > 0:
                frac = max(0.0, min(1.0, event.x / bar_w))
                self._seek_to(frac * self.dur)
        except Exception:
            pass

    def _seek_to(self, target_offset: float):
        clamped = max(0.0, min(self.dur - 0.1, target_offset))
        self._cur_play_offset = clamped
        was_playing = self._playing
        self._stop_play()
        self._lbl_ct.configure(text=fmt_t(clamped))
        self._pbar.set(clamped / self.dur)

        if was_playing:
            self._start_play()
        else:
            def bg_load():
                img = _grab_frame(self.video_path, self.s0 + clamped, w=LARGE_PREV_W, h=LARGE_PREV_H)
                if img and not self._closing:
                    self.after(0, lambda: self._show_static_frame(img))
            threading.Thread(target=bg_load, daemon=True).start()

    def _kill_procs(self):
        for attr in ("_aud_proc", "_vid_proc"):
            proc = getattr(self, attr, None)
            if proc:
                try:
                    if hasattr(proc, "stdout") and proc.stdout:
                        try:
                            proc.stdout.close()
                        except Exception:
                            pass
                    if proc.poll() is None:
                        proc.terminate()
                        proc.wait(timeout=0.15)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            setattr(self, attr, None)

    def _stop_play(self):
        was = self._playing
        self._playing = False
        self._stop_ev.set()

        if self._disp_id:
            try:
                self.after_cancel(self._disp_id)
            except Exception:
                pass
            self._disp_id = None

        self._kill_procs()
        with self._frame_lock:
            self._next_frame = None

        if was and not self._closing:
            try:
                t = "Přehrát náhled (Mezerník)" if self.lang == "cs" else "Play Preview (Space)"
                self._btn_pp.configure(text=t, image=self._icon_play, fg_color=ORANGE)
            except Exception:
                pass

    def _pause_play(self):
        self._stop_play()

    def _start_play(self):
        if self._closing:
            return
        self._stop_play()
        self._play_session_id += 1
        curr_session = self._play_session_id

        if self._cur_play_offset >= self.dur - 0.2:
            self._cur_play_offset = 0.0

        resume_start = self.s0 + self._cur_play_offset
        resume_dur = max(0.2, self.dur - self._cur_play_offset)

        ffplay = find_binary("ffplay")
        ffmpeg = find_binary("ffmpeg")
        if not ffplay or not ffmpeg:
            return

        self._playing = True
        self._stop_ev.clear()
        self._ended_ev.clear()
        with self._frame_lock:
            self._next_frame = None

        t = "Pozastavit (Mezerník)" if self.lang == "cs" else "Pause (Space)"
        self._btn_pp.configure(text=t, image=self._icon_pause, fg_color="#DC2626")

        cflags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
        sinfo = None
        if sys.platform.startswith("win"):
            sinfo = subprocess.STARTUPINFO()
            sinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            sinfo.wShowWindow = 0

        audio_t0 = time.monotonic()
        # Audio stream (audio-only decode without video overhead for zero buffer delay)
        self._aud_proc = subprocess.Popen(
            [
                str(ffplay), "-nodisp", "-vn", "-sn", "-fast",
                "-ss", f"{resume_start:.3f}", "-t", f"{resume_dur:.3f}",
                "-autoexit", str(self.video_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=sinfo,
            creationflags=cflags,
        )

        # Video stream with multithreaded fast scaling
        self._vid_proc = subprocess.Popen(
            [
                str(ffmpeg),
                "-ss", f"{resume_start:.3f}", "-t", f"{resume_dur:.3f}",
                "-threads", "2",
                "-flags2", "+fast",
                "-i", str(self.video_path),
                "-vf", f"scale={LARGE_PREV_W}:{LARGE_PREV_H}:flags=fast_bilinear,fps={LARGE_PLAY_FPS}",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            startupinfo=sinfo,
            creationflags=cflags,
        )

        base_offset = self._cur_play_offset
        threading.Thread(target=self._reader, args=(curr_session, base_offset, audio_t0), daemon=True).start()
        self._disp_id = self.after(LARGE_DISP_MS, self._disp_tick)

    def _reader(self, session_id: int, base_offset: float = 0.0, audio_t0: float = 0.0):
        fsize = LARGE_PREV_W * LARGE_PREV_H * 3
        fi = 0
        frame_dur = 1.0 / LARGE_PLAY_FPS
        audio_hw_latency = 0.08 if sys.platform.startswith("win") else 0.02
        clock_start = (audio_t0 if audio_t0 > 0 else time.monotonic()) + audio_hw_latency

        try:
            while not self._stop_ev.is_set() and session_id == self._play_session_id:
                if not self._vid_proc or not self._vid_proc.stdout:
                    break
                raw = self._vid_proc.stdout.read(fsize)
                if len(raw) < fsize:
                    break

                fi += 1
                now = time.monotonic()
                audio_elapsed = max(0.0, now - clock_start)
                frame_pts = fi * frame_dur
                time_diff = frame_pts - audio_elapsed

                # Hard framedrop: skip behind frames immediately to match audio clock
                if time_diff < -frame_dur:
                    frames_behind = int((-time_diff) / frame_dur)
                    if frames_behind > 0:
                        bytes_to_skip = min(frames_behind, 30) * fsize
                        discarded = self._vid_proc.stdout.read(bytes_to_skip)
                        skipped_actual = len(discarded) // fsize
                        fi += skipped_actual
                        if skipped_actual > 0:
                            raw = self._vid_proc.stdout.read(fsize)
                            if len(raw) < fsize:
                                break
                            fi += 1
                            now = time.monotonic()
                            audio_elapsed = max(0.0, now - clock_start)
                            frame_pts = fi * frame_dur
                            time_diff = frame_pts - audio_elapsed

                ft = base_offset + (fi * frame_dur)

                try:
                    img = Image.frombytes("RGB", (LARGE_PREV_W, LARGE_PREV_H), raw)
                except Exception:
                    continue

                with self._frame_lock:
                    self._next_frame = (img, ft)

                if time_diff > 0.002:
                    time.sleep(time_diff)
        except Exception:
            pass
        finally:
            if session_id == self._play_session_id:
                self._ended_ev.set()

    def _disp_tick(self):
        if not self._playing or self._closing:
            return

        if self._ended_ev.is_set():
            self._stop_play()
            self._cur_play_offset = 0.0
            self._lbl_ct.configure(text="00:00")
            self._pbar.set(0.0)
            return

        with self._frame_lock:
            item = self._next_frame
            self._next_frame = None

        if item is not None:
            img, ft = item
            try:
                photo = ImageTk.PhotoImage(img)
                self._cur_photo = photo
                self._cur_play_offset = ft

                if self._canvas_img is None:
                    self._canvas_img = self._vcanvas.create_image(0, 0, image=photo, anchor="nw")
                else:
                    self._vcanvas.itemconfig(self._canvas_img, image=photo)

                self._lbl_ct.configure(text=fmt_t(ft))
                if self.dur > 0:
                    self._pbar.set(min(1.0, ft / self.dur))
            except Exception:
                pass

        self._disp_id = self.after(LARGE_DISP_MS, self._disp_tick)

    def _on_close(self):
        self._closing = True
        self._stop_play()
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


# ===========================================================================
# Dialog
# ===========================================================================

class SegmentReviewDialog(ctk.CTkToplevel):

    def __init__(
        self,
        parent: ctk.CTk,
        video_path: Path,
        all_segments: List[Tuple],
        recommended_segments: List[Tuple],
        target_duration_sec: Optional[float] = None,
        current_lang: str = "cs",
        on_confirm: Optional[Callable[[List[Tuple]], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)

        self._parent = parent
        self.video_path = video_path
        self.segs = list(all_segments)
        self._rec_set: Set[Tuple[float, float]] = {
            (round(s[0], 2), round(s[1], 2)) for s in recommended_segments
        }
        self.target_dur = target_duration_sec
        self.lang = current_lang if current_lang in ("cs", "en") else "cs"
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

        # Stav zahrnutí: prostý bool list (bez BooleanVar - rychlejší)
        self._inc: List[bool] = [
            (round(s[0], 2), round(s[1], 2)) in self._rec_set for s in self.segs
        ]

        # UI stav
        self._sel: int = 0           # aktuálně vybraný index
        self._closing = False

        # Přehrávač
        self._playing = False
        self._stop_ev = threading.Event()
        self._ended_ev = threading.Event()
        self._aud_proc: Optional[subprocess.Popen] = None
        self._frame_lock = threading.Lock()
        self._next_frame: Optional[Tuple[Image.Image, float]] = None  # (PIL Image, ft) předávané z bg threadu
        self._cur_photo: Optional[ImageTk.PhotoImage] = None          # reference bránící GC (VÝHRADNĚ na main threadu)
        self._play_session_id: int = 0                                # ochrana proti překrývání přehrávacích vláken
        self._still_req_id: int = 0                                   # ochrana proti zastaralým požadavkům na statický náhled
        self._pending_play_id: Optional[str] = None
        self._play_dur: float = 0.0
        self._cur_play_offset: float = 0.0                             # aktuální pozice pro pauzu / pokračování
        self._canvas_img: Optional[int] = None
        self._disp_id: Optional[str] = None

        # Canvas seznam - stav scrollu
        self._list_canvas: Optional[tk.Canvas] = None
        self._row_items: List[dict] = []  # canvas item IDs pro každý řádek
        self._chk_widgets: List[ModernCheckBox] = []
        self._chk_windows: List[int] = []  # canvas window IDs pro checkboxy

        # Ikony pro ovládací prvky přehrávače
        self._icon_play = _load_ctk_icon("play", (22, 22))
        self._icon_pause = _load_ctk_icon("pause", (22, 22))
        self._icon_stop = _load_ctk_icon("stop", (20, 20))
        self._icon_expand = _load_ctk_icon("expand", (20, 20))
        self._icon_check = _load_ctk_icon("check", (20, 20))
        self._icon_plus = _load_ctk_icon("plus", (20, 20))
        self._icon_trash = _load_ctk_icon("trash", (20, 20))
        self._icon_star = _load_ctk_icon("star", (20, 20))
        self._icon_play_row = _load_ctk_icon("play", (15, 15))
        self._icon_volume = _load_ctk_icon("volume", (18, 18))
        self._icon_facecam = _load_ctk_icon("facecam", (18, 18))
        self._icon_close = _load_ctk_icon("close", (18, 18))

        # Okno
        title = ("SnapCut • Editor"
                 if self.lang == "cs" else "SnapCut • Editor")
        self.title(title)
        self.geometry("1140x760")
        self.minsize(1060, 680)
        self.configure(fg_color=BG_WIN_T)
        apply_inter_to_tk_fonts(APP_FONT, root=self)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Klávesová zkratka F11 pro fullscreen / maximize a sledování stavu okna
        self.bind("<F11>", lambda _: self._toggle_maximize())
        self.bind("<Configure>", self._on_window_configure)

        self._center()
        self._set_app_icon()
        self._resolve_theme_colors()
        self.after(30, self._apply_windows_titlebar_theme)
        self._build()
        self._update_summary()

        if self.segs:
            self.after(80, lambda: self._select(0))

    def _resolve_theme_colors(self):
        """Resolves dynamic colors for Tk canvas and native Tk rows matching current appearance mode."""
        mode = ctk.get_appearance_mode().lower()
        self.is_dark = (mode == "dark")

        self.c_bg_win = "#0F1013" if self.is_dark else "#F0F2F5"
        self.c_bg_card = "#181920" if self.is_dark else "#FFFFFF"
        self.c_bg_row = "#141519" if self.is_dark else "#F8F9FA"
        self.c_bg_row_sel = "#24170E" if self.is_dark else "#FFF7ED"
        self.c_bd_row = "#333338" if self.is_dark else "#CBD5E1"
        self.c_bd_row_sel = ORANGE

        self.c_stat_inc_bg = "#062E1E" if self.is_dark else "#ECFDF5"
        self.c_stat_inc_fg = "#34D399" if self.is_dark else "#059669"
        self.c_stat_exc_bg = "#261316" if self.is_dark else "#FEF2F2"
        self.c_stat_exc_fg = "#F87171" if self.is_dark else "#DC2626"

        self.c_txt_main = "#F9FAFB" if self.is_dark else "#111827"
        self.c_txt_body = "#9CA3AF" if self.is_dark else "#4B5563"
        self.c_txt_muted = "#71717A" if self.is_dark else "#6B7280"

        self.c_chip_bg = "#1E2028" if self.is_dark else "#EDF0F4"
        self.c_badge_ai_bg = "#2D2411" if self.is_dark else "#FEF3C7"
        self.c_badge_ai_fg = "#FBBF24" if self.is_dark else "#D97706"

        self.c_pbtn_bg = "#1E2028" if self.is_dark else "#E5E7EB"
        self.c_pbtn_sel_bg = "#361D0C" if self.is_dark else "#FFEDD5"

    # ------------------------------------------------------------------
    def _set_app_icon(self):
        """Loads and sets the window icon."""
        try:
            assets_dir = get_base_dir() / "assets"
            ico_file = assets_dir / "app_icon.ico"
            png_file = assets_dir / "app_icon.png"
            logo_file = assets_dir / "logo.png"

            if sys.platform.startswith("win") and ico_file.is_file():
                try:
                    self.iconbitmap(str(ico_file))
                    return
                except Exception:
                    pass

            target_png = png_file if png_file.is_file() else (logo_file if logo_file.is_file() else None)
            if target_png:
                try:
                    pil_icon = Image.open(target_png)
                    self._app_window_icon = ImageTk.PhotoImage(pil_icon)
                    self.wm_iconphoto(True, self._app_window_icon)  # type: ignore
                except Exception:
                    pass
        except Exception:
            pass

    def _apply_windows_titlebar_theme(self):
        """Sets immersive dark mode or light mode for the Windows title bar via DwmSetWindowAttribute and restores maximize box."""
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            from ctypes import c_int, byref, sizeof
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if not hwnd:
                hwnd = self.winfo_id()

            # Tkinter transient(parent) strips WS_MAXIMIZEBOX by default.
            # Restore WS_MAXIMIZEBOX and WS_MINIMIZEBOX so users can maximize,
            # double-click titlebar, or snap the editor window on Windows.
            GWL_STYLE = -16
            WS_MAXIMIZEBOX = 0x00010000
            WS_MINIMIZEBOX = 0x00020000
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            cur_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, cur_style | WS_MAXIMIZEBOX | WS_MINIMIZEBOX)
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)

            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            mode = ctk.get_appearance_mode().lower()
            dark_flag = c_int(1 if mode == "dark" else 0)
            res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, byref(dark_flag), sizeof(dark_flag)
            )
            if res != 0:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 19, byref(dark_flag), sizeof(dark_flag)
                )
            if mode == "dark":
                caption_color = c_int(0x00181211)  # #111218
                text_color = c_int(0x00FFFFFF)
            else:
                caption_color = c_int(0x00FAFAF8)
                text_color = c_int(0x0010181A)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 35, byref(caption_color), sizeof(caption_color)
            )
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 36, byref(text_color), sizeof(text_color)
            )
        except Exception:
            pass

    def _toggle_maximize(self):
        """Prepne maximalizaci okna editoru."""
        try:
            if self.state() == "zoomed":
                self.state("normal")
            else:
                self.state("zoomed")
        except Exception:
            pass

    def _on_window_configure(self, event):
        """Reaguje na zmenu rozmeru / stavu okna."""
        pass

    def _center(self):
        self.update_idletasks()
        try:
            w, h = 1140, 760
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            px, py = self._parent.winfo_x(), self._parent.winfo_y()
            pw, ph = self._parent.winfo_width(), self._parent.winfo_height()
            if pw > 100 and ph > 100:
                cx = px + pw // 2
                cy = py + ph // 2
                x = max(10, min(sw - w - 10, cx - w // 2))
                y = max(10, min(sh - h - 10, cy - h // 2))
            else:
                x = max(10, (sw - w) // 2)
                y = max(10, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    # ==================================================================
    # Stavba UI
    # ==================================================================

    def _build(self):
        self._build_header()
        self._build_footer()
        split = ctk.CTkFrame(self, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self._build_player(split)
        self._build_list(split)

    # --- Hlavička ---

    def _build_header(self):
        hdr = ctk.CTkFrame(self, corner_radius=12, fg_color=BG_CARD_T,
                           border_width=1, border_color=BD_CARD_T)
        hdr.pack(fill="x", padx=16, pady=(12, 8))

        row = ctk.CTkFrame(hdr, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=8)

        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)

        t = "Editor"
        ctk.CTkLabel(left, text=t, font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=TXT_TITLE_T).pack(anchor="w")

        s = ("Kontrola a výběr nejlepších momentů pro finální sestřih videa"
             if self.lang == "cs"
             else "Review and select the best moments for the final video cut")
        ctk.CTkLabel(left, text=s, font=ctk.CTkFont(size=11), text_color=TXT_BODY_T).pack(anchor="w")

        pill = ctk.CTkFrame(row, fg_color=BG_INNER_T, corner_radius=8,
                            border_width=1, border_color=BD_CARD_T)
        pill.pack(side="right")

        pi = ctk.CTkFrame(pill, fg_color="transparent")
        pi.pack(padx=12, pady=6)

        self._lbl_count = ctk.CTkLabel(pi, text="", font=ctk.CTkFont(size=12, weight="bold"),
                                        text_color=("#EA580C", "#FF8533"))
        self._lbl_count.pack(anchor="e")
        self._lbl_dur = ctk.CTkLabel(pi, text="", font=ctk.CTkFont(size=11), text_color=TXT_BODY_T)
        self._lbl_dur.pack(anchor="e")

    # --- Levý panel: Přehrávač ---

    def _build_player(self, parent):
        box = ctk.CTkFrame(parent, width=488, corner_radius=12, fg_color=BG_CARD_T,
                           border_width=1, border_color=BD_CARD_T)
        box.pack(side="left", fill="y", padx=(0, 8))
        box.pack_propagate(False)

        p = ctk.CTkFrame(box, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=12, pady=10)

        # Titulek
        th = ctk.CTkFrame(p, fg_color="transparent")
        th.pack(fill="x", pady=(0, 6))

        self._lbl_ptitle = ctk.CTkLabel(th, text="● Moment #01",
                                         font=ctk.CTkFont(size=14, weight="bold"),
                                         text_color=TXT_TITLE_T)
        self._lbl_ptitle.pack(side="left")

        self._lbl_ptc = ctk.CTkLabel(th, text="00:00  →  00:00",
                                      font=ctk.CTkFont(size=12, weight="bold"),
                                      text_color=ORANGE)
        self._lbl_ptc.pack(side="right")

        # Video canvas
        sc = ctk.CTkFrame(p, fg_color=BG_PLAYER, corner_radius=8,
                          border_width=1, border_color=BD_CARD_T)
        sc.pack(fill="x", pady=(0, 6))

        self._vcanvas = ctk.CTkCanvas(sc, width=PREV_W, height=PREV_H,
                                       bg="#000000", highlightthickness=0, cursor="hand2")
        self._vcanvas.pack(padx=2, pady=2)
        self._vcanvas.bind("<Button-1>", lambda _: self._toggle_play())
        self._vcanvas.bind("<Double-Button-1>", lambda _: self._open_large_preview())

        # Scrubber
        sb = ctk.CTkFrame(p, fg_color="transparent")
        sb.pack(fill="x", pady=(0, 6))

        self._lbl_ct = ctk.CTkLabel(sb, text="00:00", font=ctk.CTkFont(size=11, weight="bold"),
                                     text_color=TXT_TITLE_T, width=44)
        self._lbl_ct.pack(side="left")

        self._pbar = ctk.CTkProgressBar(sb, height=6, progress_color=ORANGE,
                                         fg_color=BG_INNER_T)
        self._pbar.pack(side="left", fill="x", expand=True, padx=6)
        self._pbar.set(0.0)

        self._lbl_tt = ctk.CTkLabel(sb, text="00:00", font=ctk.CTkFont(size=11),
                                     text_color=TXT_MUTED_T, width=44)
        self._lbl_tt.pack(side="right")

        # Tlačítka přehrávače: velké Play/Pause vlevo + zvětšit náhled vpravo
        cb = ctk.CTkFrame(p, fg_color="transparent")
        cb.pack(fill="x", pady=(0, 6))

        self._btn_pp = ctk.CTkButton(
            cb, text="Přehrát náhled" if self.lang == "cs" else "Play Preview",
            image=self._icon_play, compound="left",
            command=self._toggle_play, height=36, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ORANGE, hover_color=ORANGE_HV, text_color="#FFF", corner_radius=8)
        self._btn_pp.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._btn_ext = ctk.CTkButton(
            cb, text="⛶" if not self._icon_expand else "",
            image=self._icon_expand,
            command=self._open_large_preview,
            height=36, width=44,
            fg_color=BG_INNER_T, hover_color=("#E5E7EB", "#252834"),
            border_width=1, border_color=BD_CARD_T, corner_radius=8)
        self._btn_ext.pack(side="right")

        # Akční tlačítko pro střih: Smazat moment
        self._btn_del = ctk.CTkButton(
            p, text="Smazat moment" if self.lang == "cs" else "Delete moment",
            image=self._icon_trash, compound="left",
            command=self._delete_selected_segment,
            height=34, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#FEF2F2", "#241416"), hover_color=("#FEE2E2", "#351B1F"),
            text_color=("#DC2626", "#F87171"), border_width=1, border_color=("#FCA5A5", "#5C1D24"),
            corner_radius=8)
        self._btn_del.pack(fill="x", pady=(0, 6))

        # Velké tlačítko zahrnutí/vynechání
        self._btn_inc = ctk.CTkButton(
            p, text="",
            command=self._toggle_inc,
            height=38, font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=8)
        self._btn_inc.pack(fill="x", pady=(0, 8))

        # Info box – elegantní strukturované metriky momentu
        ib = ctk.CTkFrame(p, fg_color=BG_INNER_T, corner_radius=8,
                          border_width=1, border_color=BD_CARD_T)
        ib.pack(fill="both", expand=True)

        ibi = ctk.CTkFrame(ib, fg_color="transparent")
        ibi.pack(fill="both", expand=True, padx=10, pady=8)

        self._lbl_loud = ctk.CTkLabel(
            ibi, text="  Hlasitost špičky: -",
            image=self._icon_volume,
            compound="left",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TXT_TITLE_T,
            anchor="w"
        )
        self._lbl_loud.pack(fill="x", pady=(0, 4))

        self._lbl_face = ctk.CTkLabel(
            ibi, text="  Detekce obličeje: N/A",
            image=self._icon_facecam,
            compound="left",
            font=ctk.CTkFont(size=12),
            text_color=TXT_BODY_T,
            anchor="w"
        )
        self._lbl_face.pack(fill="x", pady=(0, 4))

        self._lbl_ai = ctk.CTkLabel(
            ibi, text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=BADGE_FG_T,
            anchor="w"
        )
        self._lbl_ai.pack(fill="x")

    # --- Pravý panel: Canvas seznam ---

    def _build_list(self, parent):
        box = ctk.CTkFrame(parent, corner_radius=12, fg_color=BG_CARD_T,
                           border_width=1, border_color=BD_CARD_T)
        box.pack(side="right", fill="both", expand=True)

        # Toolbar
        self._build_toolbar(box)

        # Rámeček pro Canvas + scrollbar
        lf = ctk.CTkFrame(box, fg_color="transparent")
        lf.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        self._list_canvas = tk.Canvas(
            lf,
            bg=self.c_bg_card,
            highlightthickness=0,
        )
        self._list_canvas.pack(side="left", fill="both", expand=True)

        sb_v = ctk.CTkScrollbar(
            lf,
            orientation="vertical",
            command=self._list_canvas.yview,
            fg_color=BG_INNER_T,
            button_color=("#9CA3AF", "#3A3D4D"),
            button_hover_color=("#6B7280", "#FF6D00"),
        )
        sb_v.pack(side="right", fill="y")
        self._list_canvas.configure(yscrollcommand=sb_v.set)

        # Vnější frame uvnitř canvasu (pro embed checkboxů)
        self._inner_frame = tk.Frame(self._list_canvas, bg=self.c_bg_card)
        self._inner_frame_id = self._list_canvas.create_window(
            0, 0, window=self._inner_frame, anchor="nw")

        # Naplnění řádky
        self._build_canvas_rows()

        # Aktualizace scroll region po vykreslení
        if self._list_canvas is not None and self._inner_frame is not None:
            canvas = self._list_canvas
            inner = self._inner_frame
            inner_id = self._inner_frame_id
            inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.bind("<Configure>", lambda e: canvas.itemconfig(inner_id, width=e.width))

            # Mousewheel - nad listcanvas i celým dialogem
            canvas.bind("<MouseWheel>", self._on_wheel)
            inner.bind("<MouseWheel>", self._on_wheel)

        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Button-4>", self._on_wheel)
        self.bind("<Button-5>", self._on_wheel)

        # Klávesové šipky
        self.bind("<Up>", lambda _: self._kb_nav(-1))
        self.bind("<Down>", lambda _: self._kb_nav(1))

    def _build_canvas_rows(self):
        """Vytvoří moderní strukturované řádky momentů se zaoblenými kartami a dokonale vycentrovanými prvky."""
        for i, seg in enumerate(self.segs):
            start, end = seg[0], seg[1]
            dur = max(0.1, end - start)
            peak = seg[2] if len(seg) >= 3 else -14.0
            is_rec = (round(start, 2), round(end, 2)) in self._rec_set
            is_inc = self._inc[i]

            # Řádkový frame (CTkFrame pro elegantní zaoblené rohy a čistý obrys)
            row_f = ctk.CTkFrame(
                self._inner_frame,
                corner_radius=10,
                fg_color=self.c_bg_row,
                border_width=1,
                border_color=self.c_bd_row,
                height=ROW_H
            )
            row_f.pack(fill="x", padx=6, pady=3)
            row_f.pack_propagate(False)

            # 1. Moderní elegantní zaoblený checkbox výběru (Facecam AI styl, 4x anti-aliasing)
            chk = ModernCheckBox(
                row_f,
                checked=is_inc,
                command=lambda c, idx=i: self._on_chk(idx, c),
                bg_color=self.c_bg_row,
                sel_bg_color=self.c_bg_row_sel,
                size=22
            )
            chk.pack(side="left", padx=(10, 6))
            self._chk_widgets.append(chk)

            # 2. Číslo momentu (#01, #02, ...)
            lbl_num = ctk.CTkLabel(
                row_f,
                text=f"#{i+1:02d}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=self.c_txt_main,
                width=36,
                anchor="w",
                cursor="hand2"
            )
            lbl_num.pack(side="left", padx=(0, 6))

            # 3. Časový rozsah se šipkou
            lbl_time = ctk.CTkLabel(
                row_f,
                text=f"{fmt_t(start)}  →  {fmt_t(end)}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=self.c_txt_main if is_inc else self.c_txt_muted,
                anchor="w",
                cursor="hand2"
            )
            lbl_time.pack(side="left", padx=(0, 8))

            # 4. Délka v zaobleném chipu
            lbl_dur = ctk.CTkLabel(
                row_f,
                text=f"{dur:.1f}s",
                font=ctk.CTkFont(size=11),
                text_color=self.c_txt_body,
                fg_color=self.c_chip_bg,
                corner_radius=6,
                padx=8,
                pady=2,
                cursor="hand2"
            )
            lbl_dur.pack(side="left", padx=(0, 5))

            # 5. Špička hlasitosti v zaobleném chipu
            lbl_peak = ctk.CTkLabel(
                row_f,
                text=f"{peak:.1f} dB",
                font=ctk.CTkFont(size=11),
                text_color=self.c_txt_muted,
                fg_color=self.c_chip_bg,
                corner_radius=6,
                padx=8,
                pady=2,
                cursor="hand2"
            )
            lbl_peak.pack(side="left", padx=(0, 5))

            # 6. AI doporučení badge
            lbl_ai = None
            if is_rec:
                lbl_ai = ctk.CTkLabel(
                    row_f,
                    text="★ AI",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=self.c_badge_ai_fg,
                    fg_color=self.c_badge_ai_bg,
                    corner_radius=6,
                    padx=8,
                    pady=2,
                    cursor="hand2"
                )
                lbl_ai.pack(side="left", padx=(0, 5))

            # 7. Stav momentu (Zahrnuto do sestřihu vs Vyřazeno)
            stat_text = "✓ V sestřihu" if (self.lang == "cs" and is_inc) else ("✓ In Cut" if is_inc else ("✕ Vyřazeno" if self.lang == "cs" else "✕ Excluded"))
            stat_bg = self.c_stat_inc_bg if is_inc else self.c_stat_exc_bg
            stat_fg = self.c_stat_inc_fg if is_inc else self.c_stat_exc_fg

            lbl_stat = ctk.CTkLabel(
                row_f,
                text=stat_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=stat_fg,
                fg_color=stat_bg,
                corner_radius=6,
                padx=8,
                pady=2,
                cursor="hand2"
            )
            lbl_stat.pack(side="left", padx=(0, 6))

            # 8. Zaoblené a vycentrované tlačítko přehrání náhledu vpravo
            pbtn = ctk.CTkButton(
                row_f,
                text="",
                image=self._icon_play_row,
                width=34,
                height=28,
                corner_radius=8,
                fg_color=self.c_pbtn_bg,
                hover_color=ORANGE,
                command=lambda idx=i: self._sel_and_play(idx)
            )
            pbtn.pack(side="right", padx=(0, 8))

            # Kliknutí na řádek -> výběr
            clickable = [row_f, lbl_num, lbl_time, lbl_dur, lbl_peak, lbl_stat]
            if lbl_ai:
                clickable.append(lbl_ai)
            for w in clickable:
                w.bind("<Button-1>", lambda _, idx=i: self._select(idx))
            for w in clickable + [chk, pbtn]:
                w.bind("<MouseWheel>", self._on_wheel)

            self._row_items.append({
                "frame": row_f, "lbl_num": lbl_num, "lbl_time": lbl_time,
                "lbl_dur": lbl_dur, "lbl_peak": lbl_peak, "lbl_ai": lbl_ai,
                "lbl_stat": lbl_stat, "chk": chk, "pbtn": pbtn
            })

    def _highlight_row(self, idx: int, selected: bool):
        if not (0 <= idx < len(self._row_items)):
            return
        row = self._row_items[idx]
        is_inc = self._inc[idx] if idx < len(self._inc) else True
        bg = self.c_bg_row_sel if selected else self.c_bg_row
        bd = self.c_bd_row_sel if selected else self.c_bd_row
        row["frame"].configure(fg_color=bg, border_color=bd)
        row["lbl_num"].configure(text_color=ORANGE if selected else self.c_txt_main)
        time_color = self.c_txt_main if is_inc else self.c_txt_muted
        row["lbl_time"].configure(text_color=time_color)
        row["chk"].draw(is_selected=selected)
        btn_bg = self.c_pbtn_sel_bg if selected else self.c_pbtn_bg
        row["pbtn"].configure(fg_color=btn_bg)

    def _update_row_stat(self, idx: int):
        if not (0 <= idx < len(self._row_items)):
            return
        row = self._row_items[idx]
        is_inc = self._inc[idx] if idx < len(self._inc) else True
        stat_text = "✓ V sestřihu" if (self.lang == "cs" and is_inc) else ("✓ In Cut" if is_inc else ("✕ Vyřazeno" if self.lang == "cs" else "✕ Excluded"))
        stat_bg = self.c_stat_inc_bg if is_inc else self.c_stat_exc_bg
        stat_fg = self.c_stat_inc_fg if is_inc else self.c_stat_exc_fg
        time_color = self.c_txt_main if is_inc else self.c_txt_muted

        if "lbl_stat" in row and row["lbl_stat"]:
            row["lbl_stat"].configure(text=stat_text, fg_color=stat_bg, text_color=stat_fg)
        if "lbl_time" in row and row["lbl_time"]:
            row["lbl_time"].configure(text_color=time_color)

    def _rebuild_rows(self, keep_sel: int = 0):
        """Přebuduje všechny řádky v seznamu po rozdělení nebo smazání segmentu."""
        if not self._inner_frame:
            return
        for widget in self._inner_frame.winfo_children():
            try:
                widget.destroy()
            except Exception:
                pass
        self._row_items.clear()
        self._chk_widgets.clear()
        self._chk_windows.clear()
        self._build_canvas_rows()
        if self._list_canvas and self._inner_frame:
            self._list_canvas.update_idletasks()
            self._list_canvas.configure(scrollregion=self._list_canvas.bbox("all"))
        if self.segs:
            new_sel = max(0, min(keep_sel, len(self.segs) - 1))
            self._select(new_sel)
        self._update_summary()


    def _delete_selected_segment(self):
        """Odstraní aktuálně vybraný moment ze seznamu."""
        if not self.segs or not (0 <= self._sel < len(self.segs)):
            return
        if len(self.segs) <= 1:
            if self._inc[self._sel]:
                self._toggle_inc()
            return

        self._stop_play()
        self._cur_play_offset = 0.0
        del_idx = self._sel

        self.segs.pop(del_idx)
        if del_idx < len(self._inc):
            self._inc.pop(del_idx)

        new_sel = min(del_idx, len(self.segs) - 1)
        self._sel = new_sel
        self._rebuild_rows(keep_sel=new_sel)

    def _build_toolbar(self, parent):
        tb = ctk.CTkFrame(parent, fg_color="transparent")
        tb.pack(fill="x", padx=12, pady=(10, 6))

        def _b(txt, cmd, **kw):
            return ctk.CTkButton(tb, text=txt, command=cmd, height=30,
                                 font=ctk.CTkFont(size=12, weight="bold"),
                                 border_width=1, corner_radius=8, **kw)

        t_ai = "AI výběr" if self.lang == "cs" else "AI Picks"
        _b(t_ai, self._reset_ai,
           image=self._icon_star, compound="left",
           fg_color=BADGE_BG_T, hover_color=("#FDE68A", "#3D3016"),
           text_color=BADGE_FG_T, border_color=("#F59E0B", "#B45309")
           ).pack(side="left", padx=(0, 6))

        _b("Vše" if self.lang == "cs" else "All", self._sel_all,
           image=self._icon_check, compound="left",
           fg_color=BG_INNER_T, hover_color=("#E5E7EB", "#252834"),
           text_color=TXT_TITLE_T, border_color=BD_CARD_T
           ).pack(side="left", padx=(0, 6))

        _b("Nic" if self.lang == "cs" else "None", self._desel_all,
           image=self._icon_close, compound="left",
           fg_color=BG_INNER_T, hover_color=("#E5E7EB", "#252834"),
           text_color=TXT_TITLE_T, border_color=BD_CARD_T
           ).pack(side="left", padx=(0, 10))

        _b("Smazat" if self.lang == "cs" else "Delete", self._delete_selected_segment,
           image=self._icon_trash, compound="left",
           fg_color=("#FEF2F2", "#241416"), hover_color=("#FEE2E2", "#351B1F"),
           text_color=("#DC2626", "#F87171"), border_color=("#FCA5A5", "#5C1D24")
           ).pack(side="left")

        if self.target_dur and self.target_dur > 0:
            tp = ctk.CTkFrame(tb, fg_color="transparent")
            tp.pack(side="right")
            self._tpbar = ctk.CTkProgressBar(tp, width=110, height=6,
                                              progress_color=ORANGE, fg_color=BG_INNER_T)
            self._tpbar.pack(side="right", padx=(4, 0))
            self._lbl_tpct = ctk.CTkLabel(tp, text="0%",
                                           font=ctk.CTkFont(size=11, weight="bold"),
                                           text_color=TXT_TITLE_T)
            self._lbl_tpct.pack(side="right")
        else:
            self._tpbar = None
            self._lbl_tpct = None

    # --- Patička ---

    def _build_footer(self):
        f = ctk.CTkFrame(self, corner_radius=12, fg_color=BG_CARD_T,
                         border_width=1, border_color=BD_CARD_T)
        f.pack(fill="x", side="bottom", padx=16, pady=(0, 12))

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=10)

        self._lbl_foot = ctk.CTkLabel(row, text="", font=ctk.CTkFont(size=12, weight="bold"),
                                       text_color=TXT_TITLE_T)
        self._lbl_foot.pack(side="left")

        self._btn_conf = ctk.CTkButton(
            row, text="", command=self._on_confirm,
            height=38, width=220, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=ORANGE, hover_color=ORANGE_HV, text_color="#FFF", corner_radius=8)
        self._btn_conf.pack(side="right", padx=(8, 0))

        t_c = "Zrušit" if self.lang == "cs" else "Cancel"
        ctk.CTkButton(row, text=t_c, command=self._on_cancel,
                      height=38, width=100, font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color=BG_INNER_T, hover_color=("#E5E7EB", "#2B2E3B"),
                      text_color=TXT_TITLE_T, border_width=1, border_color=BD_CARD_T,
                      corner_radius=8).pack(side="right")

    # ==================================================================
    # Výběr segmentu
    # ==================================================================

    def _select(self, idx: int):
        if not (0 <= idx < len(self.segs)):
            return

        self._stop_play()
        self._cur_play_offset = 0.0

        old = self._sel
        self._sel = idx

        # Zvýraznění řádků (pouze aktualizujeme starý a nový)
        if 0 <= old < len(self._row_items):
            self._highlight_row(old, False)
        self._highlight_row(idx, True)

        # Scroll řádku do pohledu
        self._scroll_into_view(idx)

        seg = self.segs[idx]
        start, end = seg[0], seg[1]
        dur = max(0.1, end - start)
        peak = seg[2] if len(seg) >= 3 else -14.0
        face = seg[3] if len(seg) >= 4 else 0.0
        is_rec = (round(start, 2), round(end, 2)) in self._rec_set

        self._lbl_ptitle.configure(text=f"● Moment #{idx+1:02d}")
        self._lbl_ptc.configure(text=f"{fmt_t(start)}  →  {fmt_t(end)}  •  {dur:.1f}s")
        self._lbl_ct.configure(text="00:00")
        self._lbl_tt.configure(text=fmt_t(dur))
        self._pbar.set(0.0)

        t = "Přehrát náhled" if self.lang == "cs" else "Play Preview"
        self._btn_pp.configure(text=t, image=self._icon_play, fg_color=ORANGE)

        self._update_inc_btn(self._inc[idx])

        self._lbl_loud.configure(image=self._icon_volume, compound="left", text=f"  Hlasitost špičky: {peak:.1f} dBFS")
        fc = (f"  Facecam reakce: {int(face*100)}%" if face > 0.05
              else ("  Facecam: Bez reakce" if self.lang == "cs"
                    else "  Facecam: No reaction"))
        self._lbl_face.configure(image=self._icon_facecam, compound="left", text=fc)

        if is_rec:
            ai = "  AI doporučení pro cílovou délku" if self.lang == "cs" else "  AI recommended pick"
            self._lbl_ai.configure(image=self._icon_star, compound="left", text=ai, text_color=BADGE_FG_T)
        else:
            ai = "Doplňkový moment (volitelné)" if self.lang == "cs" else "Optional moment"
            self._lbl_ai.configure(image=None, text=ai, text_color=TXT_MUTED_T)

        # Načti náhledový snímek v bg threadu (s unikátním ID požadavku)
        self._still_req_id += 1
        req_id = self._still_req_id
        threading.Thread(target=self._load_still, args=(req_id, start), daemon=True).start()

    def _sel_and_play(self, idx: int):
        self._select(idx)
        if self._pending_play_id:
            try:
                self.after_cancel(self._pending_play_id)
            except Exception:
                pass
        self._pending_play_id = self.after(80, self._start_play)

    def _scroll_into_view(self, idx: int):
        """Scrolluje canvas seznam tak, aby byl řádek idx viditelný."""
        if not self._row_items or idx >= len(self._row_items):
            return
        try:
            if self._list_canvas is None or self._inner_frame is None:
                return
            canvas = self._list_canvas
            inner = self._inner_frame
            row_f = self._row_items[idx]["frame"]
            row_f.update_idletasks()
            y = row_f.winfo_y()
            vh = canvas.winfo_height()
            total_h = inner.winfo_height()
            if total_h <= vh:
                return
            # Scroll tak, aby byl řádek uprostřed
            center = y + ROW_H // 2
            new_top = max(0, center - vh // 2)
            frac = new_top / total_h
            canvas.yview_moveto(frac)
        except Exception:
            pass

    def _on_wheel(self, event):
        """Scrolluje Canvas seznam pomocí kolečka myši."""
        try:
            if self._list_canvas is None:
                return
            canvas = self._list_canvas
            if sys.platform.startswith("win"):
                units = -int(event.delta / 40)
            elif sys.platform == "darwin":
                units = -int(event.delta)
            else:
                units = -1 if event.delta > 0 else 1
            canvas.yview_scroll(units, "units")
            return "break"
        except Exception:
            pass

    def _kb_nav(self, delta: int):
        new = max(0, min(self._sel + delta, len(self.segs) - 1))
        self._select(new)

    # ==================================================================
    # Přehrávač
    # ==================================================================

    def _load_still(self, req_id: int, ts: float):
        """Volat z bg threadu: načte snímek jako PIL Image bez volání Tcl/Tk."""
        img = _grab_frame(self.video_path, ts)
        if img and not self._closing:
            # Bezpečně předat čistý PIL Image do main threadu
            self.after(0, lambda im=img, rid=req_id: self._show_still(im, rid))

    def _show_still(self, img: Image.Image, req_id: int):
        if self._closing or not self.winfo_exists():
            return
        if req_id != self._still_req_id:
            return
        try:
            photo = ImageTk.PhotoImage(img)
            self._cur_photo = photo
            self._vcanvas.delete("all")
            self._canvas_img = self._vcanvas.create_image(0, 0, image=photo, anchor="nw")
            # Play overlay
            cx, cy = PREV_W // 2, PREV_H // 2
            self._vcanvas.create_oval(cx-26, cy-26, cx+26, cy+26,
                                       fill="#00000088", outline="#FFFFFF", width=2)
            self._vcanvas.create_polygon(cx-8, cy-13, cx+14, cy, cx-8, cy+13, fill="#FFFFFF")
        except Exception:
            pass

    def _toggle_play(self):
        if self._playing:
            self._pause_play()
        else:
            self._start_play()

    def _pause_play(self):
        """Pozastaví přehrávání na aktuálním čase a zachová zobrazený snímek."""
        self._playing = False
        self._stop_ev.set()

        if self._disp_id:
            try:
                self.after_cancel(self._disp_id)
            except Exception:
                pass
            self._disp_id = None

        self._kill_playback_procs()

        with self._frame_lock:
            self._next_frame = None

        try:
            if self._btn_pp.winfo_exists():
                t = "Pokračovat v přehrávání" if self.lang == "cs" else "Resume Preview"
                self._btn_pp.configure(text=t, image=self._icon_play, fg_color=ORANGE)
        except Exception:
            pass

    def _start_play(self):
        """Spustí přehrávání od aktuálního času (buď od začátku, nebo naváže po pauze)."""
        if self._pending_play_id:
            try:
                self.after_cancel(self._pending_play_id)
            except Exception:
                pass
            self._pending_play_id = None

        self._play_session_id += 1
        curr_session = self._play_session_id

        self._stop_ev.set()
        self._kill_playback_procs()
        if not self.segs:
            return

        seg = self.segs[self._sel]
        s0, s1 = seg[0], seg[1]
        self._play_dur = max(0.5, s1 - s0)

        # Pokud jsme na konci nebo těsně před ním, začneme od začátku
        if self._cur_play_offset >= (self._play_dur - 0.25):
            self._cur_play_offset = 0.0
            self._vcanvas.delete("all")
            self._canvas_img = None

        resume_start = s0 + self._cur_play_offset
        resume_dur = max(0.2, self._play_dur - self._cur_play_offset)

        ffplay = find_binary("ffplay")
        ffmpeg = find_binary("ffmpeg")
        if not ffplay or not ffmpeg:
            return

        self._playing = True
        self._stop_ev.clear()
        self._ended_ev.clear()
        with self._frame_lock:
            self._next_frame = None

        t = "Pozastavit" if self.lang == "cs" else "Pause"
        self._btn_pp.configure(text=t, image=self._icon_pause, fg_color="#DC2626")

        cflags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
        sinfo = None
        if sys.platform.startswith("win"):
            sinfo = subprocess.STARTUPINFO()
            sinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            sinfo.wShowWindow = 0

        audio_t0 = time.monotonic()
        # Audio: ffplay od navázané pozice (čisté audio bez dekódování videa pro nulový buffer delay)
        self._aud_proc = subprocess.Popen(
            [str(ffplay), "-nodisp", "-vn", "-sn", "-fast",
             "-ss", f"{resume_start:.3f}", "-t", f"{resume_dur:.3f}",
             "-autoexit", str(self.video_path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            startupinfo=sinfo, creationflags=cflags)

        # Video: ffmpeg raw RGB pipe s multithreaded fast-bilinear scalerem
        self._vid_proc = subprocess.Popen(
            [str(ffmpeg),
             "-ss", f"{resume_start:.3f}", "-t", f"{resume_dur:.3f}",
             "-threads", "2",
             "-flags2", "+fast",
             "-i", str(self.video_path),
             "-vf", f"scale={PREV_W}:{PREV_H}:flags=fast_bilinear,fps={PLAY_FPS}",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            startupinfo=sinfo, creationflags=cflags)

        # Reader thread s počátečním offsetem, session ID a audio_t0
        base_offset = self._cur_play_offset
        threading.Thread(target=self._reader, args=(curr_session, base_offset, audio_t0), daemon=True).start()
        # Display timer
        self._disp_id = self.after(DISP_MS, self._disp_tick)

    def _reader(self, session_id: int, base_offset: float = 0.0, audio_t0: float = 0.0):
        """Čte snímky z ffmpeg s pevnou synchronizací na audio clock a okamžitým framedropem."""
        fsize = PREV_W * PREV_H * 3
        fi = 0
        frame_dur = 1.0 / PLAY_FPS
        audio_hw_latency = 0.08 if sys.platform.startswith("win") else 0.02
        clock_start = (audio_t0 if audio_t0 > 0 else time.monotonic()) + audio_hw_latency

        try:
            while not self._stop_ev.is_set() and session_id == self._play_session_id:
                if not self._vid_proc or not self._vid_proc.stdout:
                    break
                raw = self._vid_proc.stdout.read(fsize)
                if len(raw) < fsize:
                    break

                fi += 1
                now = time.monotonic()
                audio_elapsed = max(0.0, now - clock_start)
                frame_pts = fi * frame_dur
                time_diff = frame_pts - audio_elapsed

                # Hard framedrop: pokud video zaostává za audiem, ihned zahoď zpožděné snímky z roury
                if time_diff < -frame_dur:
                    frames_behind = int((-time_diff) / frame_dur)
                    if frames_behind > 0:
                        bytes_to_skip = min(frames_behind, 30) * fsize
                        discarded = self._vid_proc.stdout.read(bytes_to_skip)
                        skipped_actual = len(discarded) // fsize
                        fi += skipped_actual
                        if skipped_actual > 0:
                            raw = self._vid_proc.stdout.read(fsize)
                            if len(raw) < fsize:
                                break
                            fi += 1
                            now = time.monotonic()
                            audio_elapsed = max(0.0, now - clock_start)
                            frame_pts = fi * frame_dur
                            time_diff = frame_pts - audio_elapsed

                ft = base_offset + (fi * frame_dur)

                try:
                    img = Image.frombytes("RGB", (PREV_W, PREV_H), raw)
                except Exception:
                    continue

                with self._frame_lock:
                    self._next_frame = (img, ft)

                if time_diff > 0.002:
                    time.sleep(time_diff)

        except Exception:
            pass
        finally:
            if session_id == self._play_session_id:
                self._ended_ev.set()

    def _disp_tick(self):
        """Tick v main threadu: převezme PIL Image, vytvoří PhotoImage a vykreslí ho."""
        if not self._playing or self._closing:
            return

        if self._ended_ev.is_set():
            self._on_play_end()
            return

        with self._frame_lock:
            item = self._next_frame
            self._next_frame = None

        if item is not None:
            img, ft = item
            try:
                photo = ImageTk.PhotoImage(img)
                self._cur_photo = photo  # GC reference na main threadu
                self._cur_play_offset = ft

                if self._canvas_img is None:
                    self._canvas_img = self._vcanvas.create_image(0, 0, image=photo, anchor="nw")
                else:
                    self._vcanvas.itemconfig(self._canvas_img, image=photo)

                self._lbl_ct.configure(text=fmt_t(ft))
                if self._play_dur > 0:
                    self._pbar.set(min(1.0, ft / self._play_dur))
            except Exception:
                pass

        # Naplánuj další tick
        self._disp_id = self.after(DISP_MS, self._disp_tick)

    def _on_play_end(self):
        self._stop_play()
        self._cur_play_offset = 0.0
        self._lbl_ct.configure(text="00:00")
        self._pbar.set(0.0)
        t = "Přehrát náhled" if self.lang == "cs" else "Play Preview"
        self._btn_pp.configure(text=t, image=self._icon_play, fg_color=ORANGE)
        if 0 <= self._sel < len(self.segs):
            self._still_req_id += 1
            req_id = self._still_req_id
            threading.Thread(target=self._load_still, args=(req_id, self.segs[self._sel][0]),
                             daemon=True).start()

    def _kill_playback_procs(self):
        for attr in ("_aud_proc", "_vid_proc"):
            proc = getattr(self, attr, None)
            if proc:
                try:
                    if hasattr(proc, "stdout") and proc.stdout:
                        try:
                            proc.stdout.close()
                        except Exception:
                            pass
                    if proc.poll() is None:
                        proc.terminate()
                        proc.wait(timeout=0.15)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            setattr(self, attr, None)

    def _stop_play(self):
        """Úplné zastavení přehrávání a reset pozice."""
        was = self._playing
        self._playing = False
        self._stop_ev.set()

        if self._disp_id:
            try:
                self.after_cancel(self._disp_id)
            except Exception:
                pass
            self._disp_id = None

        self._kill_playback_procs()

        with self._frame_lock:
            self._next_frame = None
        self._canvas_img = None

        if was:
            try:
                if self._btn_pp.winfo_exists():
                    t = "Přehrát náhled" if self.lang == "cs" else "Play Preview"
                    self._btn_pp.configure(text=t, image=self._icon_play, fg_color=ORANGE)
            except Exception:
                pass

    def _open_large_preview(self):
        """Otevře samostatné velké okno náhledu segmentu ve vysokém rozlišení (960x540)."""
        if not self.segs or self._sel < 0 or self._sel >= len(self.segs):
            return
        self._stop_play()

        seg = self.segs[self._sel]
        idx = self._sel
        is_inc = self._inc[idx] if idx < len(self._inc) else True

        LargePreviewDialog(
            parent=self,
            video_path=self.video_path,
            seg=seg,
            seg_idx=idx,
            is_included=is_inc,
            lang=self.lang,
            on_toggle_inc=self._on_large_preview_toggle_inc,
        )

    def _on_large_preview_toggle_inc(self, idx: int, state: bool):
        """Synchronizuje stav zahrnutí momentu z velkého náhledu zpět do editoru."""
        if 0 <= idx < len(self._inc):
            self._inc[idx] = state
            if idx < len(self._chk_widgets):
                self._chk_widgets[idx].set_checked(state)
            self._update_row_stat(idx)
            if idx == self._sel:
                self._update_inc_btn(state)
            self._update_summary()

    def _ext_player(self):
        self._open_large_preview()

    # ==================================================================
    # Zahrnutí / vyloučení
    # ==================================================================

    def _toggle_inc(self):
        idx = self._sel
        if 0 <= idx < len(self._inc):
            self._inc[idx] = not self._inc[idx]
            if idx < len(self._chk_widgets):
                self._chk_widgets[idx].set_checked(self._inc[idx])
            self._update_row_stat(idx)
            self._update_inc_btn(self._inc[idx])
            self._update_summary()

    def _update_inc_btn(self, inc: bool):
        if inc:
            t = "Zahrnuto do výsledného videa" if self.lang == "cs" else "Included in Cut"
            self._btn_inc.configure(
                text=t,
                image=self._icon_check,
                compound="left",
                fg_color=("#ECFDF5", "#062E1E"),
                hover_color=("#D1FAE5", "#0F4733"),
                text_color=("#059669", "#34D399"),
                border_color=("#10B981", "#059669"),
                border_width=1
            )
        else:
            t = "✕  Vyřazeno ze sestřihu" if self.lang == "cs" else "✕  Excluded from Cut"
            self._btn_inc.configure(
                text=t,
                image=None,
                fg_color=("#FEF2F2", "#261316"),
                hover_color=("#FEE2E2", "#3B1B20"),
                text_color=("#DC2626", "#F87171"),
                border_color=("#F87171", "#DC2626"),
                border_width=1
            )

    def _on_chk(self, idx: int, checked: Optional[bool] = None):
        if checked is not None:
            self._inc[idx] = checked
        elif 0 <= idx < len(self._chk_widgets):
            self._inc[idx] = self._chk_widgets[idx].checked
        self._update_row_stat(idx)
        if idx == self._sel:
            self._update_inc_btn(self._inc[idx])
        self._update_summary()

    def _sel_all(self):
        self._inc = [True] * len(self._inc)
        for i, w in enumerate(self._chk_widgets):
            w.set_checked(True)
            self._update_row_stat(i)
        self._update_inc_btn(True)
        self._update_summary()

    def _desel_all(self):
        self._inc = [False] * len(self._inc)
        for i, w in enumerate(self._chk_widgets):
            w.set_checked(False)
            self._update_row_stat(i)
        self._update_inc_btn(False)
        self._update_summary()

    def _reset_ai(self):
        for i, seg in enumerate(self.segs):
            val = (round(seg[0], 2), round(seg[1], 2)) in self._rec_set
            self._inc[i] = val
            if i < len(self._chk_widgets):
                self._chk_widgets[i].set_checked(val)
            self._update_row_stat(i)
        self._update_inc_btn(self._inc[self._sel] if self.segs else False)
        self._update_summary()

    # ==================================================================
    # Live souhrn
    # ==================================================================

    def _update_summary(self):
        sc = sum(1 for x in self._inc if x)
        sd = sum((self.segs[i][1] - self.segs[i][0]) for i, x in enumerate(self._inc) if x)
        total = len(self.segs)
        d_str = fmt_t(sd)
        c_str = format_moments_count(sc, self.lang)

        if self.lang == "cs":
            self._lbl_count.configure(text=f"Vybráno: {c_str} (celkem: {total})")
        else:
            self._lbl_count.configure(text=f"Selected: {sc} of {total} clips")

        if self.target_dur and self.target_dur > 0:
            t_str = fmt_t(self.target_dur)
            if sd < self.target_dur * 0.9:
                # Celkova delka mensi nez cil - informuj uzivatele
                note = " (video kratsi nez cilova delka)" if self.lang == "cs" else " (video shorter than target)"
            else:
                note = ""
            dt = f"Délka: {d_str} / Cíl: {t_str}{note}" if self.lang == "cs" else f"Duration: {d_str} / Target: {t_str}{note}"
            self._lbl_dur.configure(text=dt)
            pct = min(1.0, sd / self.target_dur)
            if self._tpbar:
                self._tpbar.set(pct)
            if self._lbl_tpct:
                self._lbl_tpct.configure(text=f"{int(pct*100)}%")
        else:
            dt = f"Celková délka: {d_str}" if self.lang == "cs" else f"Total duration: {d_str}"
            self._lbl_dur.configure(text=dt)

        if self.lang == "cs":
            self._lbl_foot.configure(text=f"Celkem vybráno {c_str} ({d_str})")
            self._btn_conf.configure(text=f"Sestříhat {c_str}")
        else:
            self._lbl_foot.configure(text=f"{sc} clips selected ({d_str})")
            self._btn_conf.configure(text=f"Export {sc} clips")

    # ==================================================================
    # Potvrzení / Zrušení
    # ==================================================================

    def _on_confirm(self):
        chosen = [self.segs[i] for i, x in enumerate(self._inc) if x]
        if not chosen:
            from tkinter import messagebox
            t = "Žádný výběr" if self.lang == "cs" else "No Selection"
            m = ("Vyber alespoň 1 moment." if self.lang == "cs"
                 else "Please select at least 1 moment.")
            messagebox.showwarning(t, m)
            return
        self._cleanup()
        if self.on_confirm:
            self.on_confirm(chosen)
        self.destroy()

    def _on_cancel(self):
        self._cleanup()
        if self.on_cancel:
            self.on_cancel()
        self.destroy()

    def _cleanup(self):
        self._closing = True
        self._play_session_id += 1
        self._still_req_id += 1
        if self._pending_play_id:
            try:
                self.after_cancel(self._pending_play_id)
            except Exception:
                pass
            self._pending_play_id = None
        self._stop_play()
