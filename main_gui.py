"""
main_gui.py - Pecislav Studio: Creator Suite with modern CustomTkinter GUI.

Modules:
- SnapCut: Creator-focused video highlight cutter with Facecam AI and audio hype detection.
- Target duration limitation (e.g. 5, 10, 15, 20, 30 min or unlimited), prioritizing loudest hype moments.
- Recommended initial values clearly stated under every single setting.
- Interactive question mark (?) help buttons explaining each feature in plain language.
- Pixel-perfect vertical centering of the "PRO CREATOR" badge.
- 1-click automatic FFmpeg downloader & status indicator with X / feedback.
- Clean dropdown selectors for mode, duration, and output format.
- Sliders protected against accidental mousewheel/trackpad scrolling.
- Branded as Pecislav Studio by Pecislav with custom Twitch/YouTube creator theme.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
if sys.platform.startswith("win"):
    # Initialize COM in STA (Single-Threaded Apartment) mode before Win32 common dialogs load
    setattr(sys, "coinit_flags", 2)

import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageTk


def safe_ask_directory(
    parent: Optional[tk.Misc] = None,
    title: str = "",
    initialdir: Optional[str | Path] = None
) -> str:
    """Safely opens folder picker without COM or Tk modal locks."""
    if parent is not None:
        try:
            parent.update_idletasks()
        except Exception:
            pass

    clean_dir = None
    if initialdir:
        try:
            p = Path(initialdir).resolve()
            if p.is_dir():
                clean_dir = p.as_posix()
            elif p.parent.is_dir():
                clean_dir = p.parent.as_posix()
        except Exception:
            clean_dir = None

    result = ""
    try:
        result = filedialog.askdirectory(parent=parent, title=title, initialdir=clean_dir)
    except Exception:
        try:
            result = filedialog.askdirectory(parent=None, title=title, initialdir=clean_dir)
        except Exception:
            result = ""

    if parent is not None:
        try:
            parent.update_idletasks()
            parent.focus_force()
        except Exception:
            pass

    return result or ""


def safe_ask_open_file(
    parent: Optional[tk.Misc] = None,
    title: str = "",
    filetypes: Optional[List[Tuple[str, str]]] = None,
    initialdir: Optional[str | Path] = None
) -> str:
    """Safely opens file picker without COM or Tk modal locks."""
    if parent is not None:
        try:
            parent.update_idletasks()
        except Exception:
            pass

    clean_dir = None
    if initialdir:
        try:
            p = Path(initialdir).resolve()
            if p.is_dir():
                clean_dir = p.as_posix()
            elif p.parent.is_dir():
                clean_dir = p.parent.as_posix()
        except Exception:
            clean_dir = None

    result = ""
    try:
        result = filedialog.askopenfilename(
            parent=parent,
            title=title,
            filetypes=filetypes or [("All files", "*.*")],
            initialdir=clean_dir
        )
    except Exception:
        try:
            result = filedialog.askopenfilename(
                parent=None,
                title=title,
                filetypes=filetypes or [("All files", "*.*")],
                initialdir=clean_dir
            )
        except Exception:
            result = ""

    if parent is not None:
        try:
            parent.update_idletasks()
            parent.focus_force()
        except Exception:
            pass

    return result or ""

# Use circle_shapes for smooth, continuous rounded corners without pixelated polygon bevels
try:
    ctk.DrawEngine.preferred_drawing_method = "circle_shapes"
except Exception:
    pass


def load_app_icon(name: str, size: Tuple[int, int] = (20, 20), tint: Optional[str] = None) -> Optional[ctk.CTkImage]:
    """Loads a PNG icon from assets/icons/ as CTkImage with automatic optical trimming and centering."""
    icon_path = Path(__file__).resolve().parent / "assets" / "icons" / f"{name}.png"
    if icon_path.is_file():
        try:
            im = Image.open(icon_path).convert("RGBA")
            if tint == "white":
                r, g, b, a = im.split()
                im = Image.merge("RGBA", (Image.new("L", im.size, 255), Image.new("L", im.size, 255), Image.new("L", im.size, 255), a))
            bbox = im.getbbox()
            if bbox:
                bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
                max_dim = max(bw, bh)
                cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
                pad = max_dim * 0.08
                half = (max_dim / 2) + pad
                crop_box = (
                    int(cx - half),
                    int(cy - half),
                    int(cx + half),
                    int(cy + half),
                )
                w_sq = crop_box[2] - crop_box[0]
                h_sq = crop_box[3] - crop_box[1]
                sq_im = Image.new("RGBA", (w_sq, h_sq), (0, 0, 0, 0))
                sq_im.paste(im, (-crop_box[0], -crop_box[1]))
                im = sq_im
            return ctk.CTkImage(light_image=im, dark_image=im, size=size)
        except Exception:
            pass
    return None



def apply_font_to_tk_fonts(family: str = "Poppins", root: Optional[tk.Misc] = None):
    """Configures all default Tkinter named fonts to use the specified font family."""
    try:
        import tkinter.font as tkfont
        for name in [
            "TkDefaultFont", "TkTextFont", "TkFixedFont", "TkMenuFont",
            "TkHeadingFont", "TkCaptionFont", "TkSmallCaptionFont",
            "TkIconFont", "TkTooltipFont"
        ]:
            try:
                tkfont.nametofont(name, root=root).configure(family=family)
            except Exception:
                pass
    except Exception:
        pass

# Backward compatibility alias
apply_inter_to_tk_fonts = apply_font_to_tk_fonts


def init_custom_fonts(font_override: Optional[str] = None) -> str:
    """
    Registers bundled Inter and Poppins fonts directly on Windows using AddFontResourceExW,
    broadcasts WM_FONTCHANGE, and configures CustomTkinter and Tkinter default font family.
    Returns the chosen font family name.
    """
    chosen = font_override or "Inter"
    try:
        base_candidates = [
            Path(__file__).resolve().parent,
            Path(sys.executable).parent,
        ]
        if hasattr(sys, "_MEIPASS"):
            base_candidates.insert(0, Path(getattr(sys, "_MEIPASS")))
        fonts_dir = None
        for b in base_candidates:
            candidate = b / "assets" / "fonts"
            if candidate.is_dir():
                fonts_dir = candidate
                break
        if not fonts_dir:
            fonts_dir = Path(__file__).resolve().parent / "assets" / "fonts"
            fonts_dir.mkdir(parents=True, exist_ok=True)

        required_fonts = [
            "Inter-Medium.ttf", "Inter-Bold.ttf", "Inter-Regular.ttf", "Inter-SemiBold.ttf",
            "Poppins-Medium.ttf", "Poppins-Bold.ttf", "Poppins-Regular.ttf", "Poppins-SemiBold.ttf"
        ]
        missing = [f for f in required_fonts if not (fonts_dir / f).exists()]
        if missing:
            try:
                import urllib.request, zipfile, io
                req = urllib.request.Request(
                    "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    zdata = resp.read()
                    with zipfile.ZipFile(io.BytesIO(zdata)) as z:
                        for m in missing:
                            zip_entry = f"extras/ttf/{m}"
                            if zip_entry in z.namelist():
                                (fonts_dir / m).write_bytes(z.read(zip_entry))
            except Exception:
                pass

        fonts_added = False
        for font_name in required_fonts:
            fp = fonts_dir / font_name
            if fp.is_file():
                try:
                    ctk.FontManager.load_font(str(fp.resolve()))
                except Exception:
                    pass
                if sys.platform.startswith("win"):
                    try:
                        import ctypes
                        res = ctypes.windll.gdi32.AddFontResourceExW(str(fp.resolve()), 0x10, 0)
                        if res > 0:
                            fonts_added = True
                    except Exception:
                        pass

        if fonts_dir.is_dir():
            for fp in fonts_dir.glob("*.ttf"):
                try:
                    ctk.FontManager.load_font(str(fp.resolve()))
                except Exception:
                    pass
                if sys.platform.startswith("win"):
                    try:
                        import ctypes
                        res = ctypes.windll.gdi32.AddFontResourceExW(str(fp.resolve()), 0x10, 0)
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
        temp_root = None
        if not getattr(tk, "_default_root", None):
            temp_root = tk.Tk()
            temp_root.withdraw()
        fams = set(tkfont.families())
        pref_list = [font_override] if font_override else []
        pref_list.extend(["Inter", "Segoe UI Variable Text", "Segoe UI", "Poppins", "Montserrat"])
        for preferred in pref_list:
            if preferred and preferred in fams:
                chosen = preferred
                break
        if temp_root:
            temp_root.destroy()
    except Exception:
        chosen = "Inter" if sys.platform.startswith("win") else "Segoe UI"

    try:
        ctk.ThemeManager.theme["CTkFont"]["family"] = chosen
    except Exception:
        pass
    apply_font_to_tk_fonts(chosen)
    return chosen

APP_FONT_FAMILY = init_custom_fonts()


from ffmpeg_utils import (
    download_ffmpeg_auto,
    find_binary,
    get_base_dir,
    get_ffmpeg_paths,
    open_folder_in_file_manager,
    verify_binaries,
)
from audio_analyzer import analyze_audio_stream, get_video_metadata
from edl_generator import generate_cmx3600_edl
from facecam_ai import (
    FacecamAnalyzer,
    analyze_candidate_facecam_segments,
    ensure_ai_models_present,
)
from video_cutter import (
    calculate_cut_statistics,
    cut_video_lossless,
    limit_segments_to_target_duration,
    merge_overlapping_segments,
)
from segment_editor import SegmentReviewDialog

APP_VERSION = "1.1.0"

# -----------------------------------------------------------------------------
# Configuration Management & Defaults (Bulletproof persistence)
# -----------------------------------------------------------------------------
def get_config_file_path() -> Path:
    """
    Returns path to persistent config.json in user AppData directory.
    Guarantees settings are NEVER written into PyInstaller's temporary _MEIPASS folder.
    """
    if platform.system().lower() == "windows":
        app_data = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA")
        if app_data:
            cfg_dir = Path(app_data) / "PecislavStudio"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            appdata_cfg = cfg_dir / "config.json"

            # One-time migration: If local config exists in source directory, seed APPDATA
            base_dir = get_base_dir()
            is_temp = hasattr(sys, "_MEIPASS") or "temp" in str(base_dir).lower() or "_mei" in str(base_dir).lower()
            if not is_temp:
                local_cfg = base_dir / "config.json"
                if local_cfg.is_file() and not appdata_cfg.is_file():
                    try:
                        shutil.copy2(local_cfg, appdata_cfg)
                    except Exception:
                        pass
            return appdata_cfg

    cfg_dir = Path.home() / ".pecislavstudio"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "config.json"


CONFIG_FILE = get_config_file_path()
DEFAULT_CONFIG = {
    "language": "cs",
    "theme": "dark",
    "font_family": "Inter",
    "default_export_dir": "",
    "auto_open_folder": True,
    "detection_mode": "highlights", # "highlights" or "silence"
    "target_duration": "none",       # "none", "5min", "10min", "15min", "20min", "30min"
    "crop_style": "original",       # "original", "shorts", "square"
    "export_format": "mp4",         # "mp4" or "edl"
    "facecam_enabled": True,
    "review_segments": True,
    "sound_threshold": -14.0,
    "pad_before": 4.0,
    "pad_after": 2.0,
    "min_gap": 2.0,
    "history": []          # list of {"video": str, "output": str, "date": str, "stats": dict}
}


def load_app_config() -> dict:
    """Loads configuration from config.json, merged with default values."""
    cfg_file = get_config_file_path()
    if cfg_file.is_file():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cfg = DEFAULT_CONFIG.copy()
                    cfg.update(data)
                    return cfg
        except Exception as e:
            print(f"[Config] Error reading config.json from {cfg_file}: {e}")

    # Fallback to local config.json if AppData is not yet created
    base_dir = get_base_dir()
    is_temp = hasattr(sys, "_MEIPASS") or "temp" in str(base_dir).lower() or "_mei" in str(base_dir).lower()
    if not is_temp:
        local_cfg = base_dir / "config.json"
        if local_cfg.is_file():
            try:
                with open(local_cfg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        cfg = DEFAULT_CONFIG.copy()
                        cfg.update(data)
                        return cfg
            except Exception:
                pass
    return DEFAULT_CONFIG.copy()


def save_app_config(config: dict):
    """Saves configuration dictionary to config.json in AppData and local folder if writable."""
    cfg_file = get_config_file_path()
    try:
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Config] Error saving config.json: {e}")

    # Also sync to local directory if running from non-temp development folder
    try:
        base_dir = get_base_dir()
        is_temp = hasattr(sys, "_MEIPASS") or "temp" in str(base_dir).lower() or "_mei" in str(base_dir).lower()
        if not is_temp:
            local_cfg = base_dir / "config.json"
            if local_cfg != cfg_file:
                with open(local_cfg, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Cache & Maintenance Utilities
# -----------------------------------------------------------------------------
def get_app_cache_info() -> Tuple[int, List[Path]]:
    """
    Finds all temporary chunk directories, temp files, and caches created by Pecislav Studio.
    Returns (total_bytes, list_of_paths_to_clean).
    """
    paths_to_clean: List[Path] = []
    total_bytes = 0

    # 1. System temp files with autoclip_ or peci prefix
    tmp_dir = Path(tempfile.gettempdir())
    if tmp_dir.is_dir():
        try:
            for p in tmp_dir.iterdir():
                try:
                    if p.name.startswith(("autoclip_", "peci_", "pecicut_", "snapcut_", "pecislav_")):
                        paths_to_clean.append(p)
                        if p.is_file():
                            total_bytes += p.stat().st_size
                        elif p.is_dir():
                            for f in p.rglob("*"):
                                if f.is_file():
                                    total_bytes += f.stat().st_size
                except Exception:
                    pass
        except Exception:
            pass

    # 2. Local app cache directory if exists
    local_cache = get_base_dir() / "cache"
    if local_cache.is_dir():
        try:
            for f in local_cache.rglob("*"):
                try:
                    if f.is_file():
                        total_bytes += f.stat().st_size
                        paths_to_clean.append(f)
                except Exception:
                    pass
        except Exception:
            pass

    # 3. Local __pycache__ in base directory
    try:
        for pyc in get_base_dir().rglob("__pycache__"):
            paths_to_clean.append(pyc)
            for f in pyc.rglob("*"):
                if f.is_file():
                    total_bytes += f.stat().st_size
    except Exception:
        pass

    return total_bytes, paths_to_clean


def clear_app_cache() -> Tuple[int, int]:
    """
    Deletes temporary files and returns (freed_bytes, cleaned_count).
    """
    total_bytes, paths = get_app_cache_info()
    cleaned_count = 0
    freed_bytes = 0

    for p in paths:
        try:
            if p.is_file():
                sz = p.stat().st_size
                p.unlink(missing_ok=True)
                freed_bytes += sz
                cleaned_count += 1
            elif p.is_dir():
                for f in p.rglob("*"):
                    if f.is_file():
                        freed_bytes += f.stat().st_size
                        cleaned_count += 1
                shutil.rmtree(p, ignore_errors=True)
        except Exception:
            pass

    return freed_bytes, cleaned_count


# -----------------------------------------------------------------------------
# Bilingual UI Translations (Čeština / English)
# -----------------------------------------------------------------------------
TRANSLATIONS = {
    "cs": {
        # App Shell & Navigation
        "app_title": "Pecislav Studio • Pro Creator",
        "brand_title": "Pecislav Studio",
        "nav_modules": "MODULY",
        "nav_snapcut": "  SnapCut",
        "nav_pecicut": "  SnapCut",
        "nav_history": "  Historie projektů",
        "nav_system": "SYSTÉM",
        "nav_settings": "  Nastavení",
        "header_snapcut_title": "SnapCut",
        "header_snapcut_subtitle": "Automatický střih dlouhých záznamů (2-6h) z Twitch & YouTube dle mikrofonu",
        "header_pecicut_title": "SnapCut",
        "header_pecicut_subtitle": "Automatický střih dlouhých záznamů (2-6h) z Twitch & YouTube dle mikrofonu",
        "header_settings_title": "Nastavení Studia",
        "header_settings_subtitle": "Barevný motiv, jazyk, export a aktualizace Pecislav Studio",
        "footer_text": f"Pecislav Studio v{APP_VERSION} • Creator Suite by Pecislav • Lossless FFmpeg Engine",

        # PeciCut Section 1: File selection
        "sec_file_title": "1. Výběr zdrojového video záznamu",
        "btn_select_file": "Procházet soubory...",
        "no_file_selected": "Zatím nebyl vybrán žádný soubor (.mp4, .mkv, .mov)",
        "meta_info_placeholder": "Po výběru souboru se zde zobrazí délka, FPS, rozlišení a nalezené audio stopy.",

        # PeciCut Section 2: Audio Track
        "sec_audio_title": "2. Výběr audio stopy pro analýzu (Mikrofon / Hlas)",
        "sec_audio_sub": "Vyberte stopu s vaším hlasem, aby se detekoval váš křik a reakce namísto zvuků ze hry.",

        # PeciCut Section 3: Detection Parameters
        "sec_params_title": "3. Režim detekce a parametry střihu",
        "mode_highlights": "Akční highlighty (výkřiky, smích, hlasité momenty)",
        "mode_nosilence": "Celý stream bez hluchých míst (odstranění ticha)",
        "lbl_target_dur_title": "Cílová maximální délka sestřihu:",
        "lbl_threshold": "Práh hlasitosti / řevu (dBFS):",
        "lbl_pad_before": "Délka náběhu před momentem (Padding Before):",
        "lbl_pad_after": "Délka doznívání po momentu (Padding After):",
        "lbl_gap": "Minimální ticho pro rozdělení (Min Gap):",
        "chk_facecam": "Facecam AI (Analýza výrazu obličeje a smíchu z webkamery)",
        "sub_facecam": "Kombinuje audio analýzu s počítačovým viděním — prioritizuje nejlepší reakce obličeje, smích a leknutí.",

        # PeciCut Section 4: Export
        "sec_export_title": "4. Formát výstupu a cílová složka",
        "btn_change_out": "Změnit výstupní složku...",
        "btn_reveal_out": "Otevřít složku",
        "out_dir_default": "Výstup: Automaticky ve složce se zdrojovým videem",
        "out_dir_custom": "Výstup: ",
        "chk_review_segments": "Před exportem otevřít editor momentů a náhledy",
        "sub_review_segments": "Umožní přehrát nalezené momenty a ručně upravit, co se má sestříhat.",

        # PeciCut Section 5: Progress & Results
        "btn_process": "Spustit zpracování záznamu",
        "btn_cancel": "Zrušit",
        "status_ready": "Video připraveno. Nastavte parametry a klikněte na 'Spustit zpracování'.",
        "status_waiting_editor": "Čekám na schválení momentů v editoru...",
        "btn_open_folder": "Otevřít složku s výsledkem",
        "lbl_done": "Hotovo!",

        # Settings Card 1: Themes
        "card_theme_title": " Barevný motiv aplikace",
        "card_theme_sub": "Vyberte vizuální styl studia (kliknutím na náhled):",
        "theme_system": "Systémová",
        "theme_light": "Bílá",
        "theme_dark": "Černá",

        # Settings Card 2: Language
        "card_lang_title": " Jazyk aplikace / Language",
        "card_lang_sub": "Zvolte preferovaný jazyk uživatelského rozhraní Pecislav Studio:",
        "lbl_select_language": "Aktivní jazyk rozhraní:",

        # Settings Card 3: Default Export & Folder Behavior
        "card_export_title": "Výchozí export a chování složek",
        "card_export_sub": "Nastavte kam se mají ukládat hotové sestřihy a chování po dokončení:",
        "lbl_default_folder": "Výchozí složka pro export:",
        "lbl_folder_beside": "(Automaticky ve složce se zdrojovým videem)",
        "btn_set_export_folder": "Změnit složku...",
        "btn_reset_export_folder": " Resetovat",
        "chk_auto_open_folder": "Automaticky otevřít cílovou složku po dokončení střihu",

        # Settings Card 4: Performance / CPU
        "card_perf_title": " Výkon a vytížení procesoru (CPU)",
        "card_perf_sub": "Přizpůsobte vytížení procesoru při renderování a AI analýze:",
        "perf_cores_detected": "Detekováno: {cores} jader CPU",
        "perf_max_opt": "Maximální výkon (všechna jádra)",
        "perf_balanced_opt": "Vyvážený / Herní režim (šetří CPU)",
        "perf_max_desc": "• Využívá 100% dostupných CPU jader pro nejrychlejší možný střih a detekci obličeje.",
        "perf_balanced_desc": "• Omezuje vytížení na polovinu jader ({half_cores}). Šetří procesor a grafiku pro plynulé hraní či streamování na Twitch/YouTube.",

        # Settings Card 5: Maintenance / Cache
        "card_cache_title": " Údržba a dočasná data (Cache)",
        "card_cache_sub": "Vyčistěte dočasné video segmenty, fragmenty a mezipaměť po předchozích střizích:",
        "lbl_cache_heading": "Stav dočasné mezipaměti:",
        "btn_clear_cache": "Promazat mezipaměť",
        "cache_clean": "Mezipaměť je čistá (0.0 MB)",
        "cache_found": "Nalezeno {size_mb} MB dočasných dat",
        "cache_cleared_msg": "Mezipaměť byla úspěšně promazána (uvolněno {freed_mb} MB).",

        # Settings Card 6: Components
        "card_comp_title": " Kontrola stažených součástí",
        "btn_recheck": " Zkontrolovat",
        "comp_ffmpeg_ok": "FFmpeg & FFprobe: Připraveno",
        "comp_ffmpeg_fail": "X FFmpeg & FFprobe: Chybí",
        "comp_ffmpeg_downloading": "Stahuji balíček FFmpeg & FFprobe...",
        "comp_ffmpeg_desc_ok": "Nalezeno v systému: {name}",
        "comp_ffmpeg_desc_fail": "Potřebné pro analýzu audia a střih videa",
        "comp_models_ok": "Facecam AI modely: Připraveno (3/3)",
        "comp_models_fail": "X Facecam AI modely: Nalezeno {cnt}/3",
        "comp_models_downloading": "Stahuji Facecam AI modely...",
        "comp_models_desc_ok": "YuNet ONNX & Haar Cascades v models/ pro detekci obličeje a reakcí",
        "comp_models_desc_fail": "Modely chybí pro analýzu webkamery",
        "comp_dirs_ok": "Pracovní adresáře aplikace: V pořádku",
        "comp_dirs_desc": "models/, assets/, bin/ jsou připraveny k použití",

        # Settings Card 7: Version & Updates
        "card_ver_title": "Verze aplikace a aktualizace",
        "btn_check_updates": "Zkontrolovat aktualizace",
        "btn_install_update": "Stáhnout a aktualizovat",
        "installed_ver": f"Nainstalovaná verze: Pecislav Studio v{APP_VERSION} (by Pecislav)",
        "update_status_latest": "Používáte nejnovější verzi aplikace.",
        "dnd_drop_hint": "Přetáhněte video sem (Drag & Drop) nebo vyberte soubor  •  MP4, MKV, MOV, WebM",
        "dnd_ready_hint": "Velikost: {size} MB  •  Připraveno k analýze  •  Přetažením nahradíte",
        "btn_change_file": "Změnit video",
    },
    "en": {
        # App Shell & Navigation
        "app_title": "Pecislav Studio • Pro Creator",
        "brand_title": "Pecislav Studio",
        "nav_modules": "MODULES",
        "nav_snapcut": "  SnapCut",
        "nav_pecicut": "  SnapCut",
        "nav_history": "  Project History",
        "nav_system": "SYSTEM",
        "nav_settings": "  Settings",
        "header_snapcut_title": "SnapCut",
        "header_snapcut_subtitle": "Automated highlight cutter for long Twitch & YouTube recordings (2-6h) based on mic audio",
        "header_pecicut_title": "SnapCut",
        "header_pecicut_subtitle": "Automated highlight cutter for long Twitch & YouTube recordings (2-6h) based on mic audio",
        "header_settings_title": "Studio Settings",
        "header_settings_subtitle": "Color theme, language, export and updates for Pecislav Studio",
        "footer_text": f"Pecislav Studio v{APP_VERSION} • Creator Suite by Pecislav • Lossless FFmpeg Engine",

        # PeciCut Section 1: File selection
        "sec_file_title": "1. Select Source Video Recording",
        "btn_select_file": "Browse files...",
        "no_file_selected": "No file selected yet (.mp4, .mkv, .mov)",
        "meta_info_placeholder": "File duration, FPS, resolution, and audio tracks will appear here after selection.",

        # PeciCut Section 2: Audio Track
        "sec_audio_title": "2. Select Audio Track for Analysis (Microphone / Voice)",
        "sec_audio_sub": "Select the track containing your voice so screams and reactions are analyzed instead of game audio.",

        # PeciCut Section 3: Detection Parameters
        "sec_params_title": "3. Detection Mode & Cutting Parameters",
        "mode_highlights": "Action Highlights (screams, laughter, hype moments)",
        "mode_nosilence": "Full Stream without Silence (remove quiet pauses)",
        "lbl_target_dur_title": "Target maximum video duration:",
        "lbl_threshold": "Loudness / Scream threshold (dBFS):",
        "lbl_pad_before": "Padding before highlight (Padding Before):",
        "lbl_pad_after": "Padding after highlight (Padding After):",
        "lbl_gap": "Minimum silence to split (Min Gap):",
        "chk_facecam": "Facecam AI (Facial expression & laughter analysis from webcam)",
        "sub_facecam": "Combines audio analysis with computer vision — prioritizes highest facial reactions, laughs and screams.",

        # PeciCut Section 4: Export
        "sec_export_title": "4. Output Format & Destination Directory",
        "btn_change_out": "Change output folder...",
        "btn_reveal_out": "Open folder",
        "out_dir_default": "Output: Automatically in source video directory",
        "out_dir_custom": "Output: ",
        "chk_review_segments": "Open interactive editor & video preview before export",
        "sub_review_segments": "Allows you to preview detected moments and customize which clips to export.",

        # PeciCut Section 5: Progress & Results
        "btn_process": "Start Processing Recording",
        "btn_cancel": "Cancel",
        "status_ready": "Video ready. Configure parameters and click 'Start Processing'.",
        "status_waiting_editor": "Waiting for moment selection in editor...",
        "btn_open_folder": "Open Destination Folder",
        "lbl_done": "Done!",

        # Settings Card 1: Themes
        "card_theme_title": " Application Color Theme",
        "card_theme_sub": "Select studio visual style (click on preview):",
        "theme_system": "System",
        "theme_light": "Light",
        "theme_dark": "Dark",

        # Settings Card 2: Language
        "card_lang_title": " Application Language / Jazyk",
        "card_lang_sub": "Select your preferred user interface language for Pecislav Studio:",
        "lbl_select_language": "Active UI Language:",

        # Settings Card 3: Default Export & Folder Behavior
        "card_export_title": "Default Export & Folder Behavior",
        "card_export_sub": "Set where exported highlights are saved and how the studio behaves upon completion:",
        "lbl_default_folder": "Default export folder:",
        "lbl_folder_beside": "(Automatically in source video folder)",
        "btn_set_export_folder": "Change folder...",
        "btn_reset_export_folder": " Reset",
        "chk_auto_open_folder": "Automatically open destination folder when export completes",

        # Settings Card 4: Performance / CPU
        "card_perf_title": " Performance & CPU Load",
        "card_perf_sub": "Adjust CPU utilization during video rendering and AI facecam analysis:",
        "perf_cores_detected": "Detected: {cores} CPU cores",
        "perf_max_opt": "Maximum Performance (all cores)",
        "perf_balanced_opt": "Balanced / Gaming Mode (saves CPU)",
        "perf_max_desc": "• Utilizes 100% of available CPU cores for fastest possible highlight cutting and facecam analysis.",
        "perf_balanced_desc": "• Limits processing to half the CPU cores ({half_cores}). Preserves CPU and GPU for smooth gaming or streaming on Twitch/YouTube.",

        # Settings Card 5: Maintenance / Cache
        "card_cache_title": " Maintenance & Temporary Cache",
        "card_cache_sub": "Clean up temporary video segments, chunks, and cache from previous cut sessions:",
        "lbl_cache_heading": "Temporary cache status:",
        "btn_clear_cache": "Clear Cache",
        "cache_clean": "Cache is clean (0.0 MB)",
        "cache_found": "Found {size_mb} MB of temporary data",
        "cache_cleared_msg": "Cache cleared successfully (freed {freed_mb} MB).",

        # Settings Card 6: Components
        "card_comp_title": " Component Health Check",
        "btn_recheck": " Recheck",
        "comp_ffmpeg_ok": "FFmpeg & FFprobe: Ready",
        "comp_ffmpeg_fail": "X FFmpeg & FFprobe: Missing",
        "comp_ffmpeg_downloading": "Downloading FFmpeg & FFprobe package...",
        "comp_ffmpeg_desc_ok": "Found on system: {name}",
        "comp_ffmpeg_desc_fail": "Required for audio analysis and video cutting",
        "comp_models_ok": "Facecam AI models: Ready (3/3)",
        "comp_models_fail": "X Facecam AI models: Found {cnt}/3",
        "comp_models_downloading": "Downloading Facecam AI models...",
        "comp_models_desc_ok": "YuNet ONNX & Haar Cascades in models/ for face reaction detection",
        "comp_models_desc_fail": "Models missing for webcam reaction analysis",
        "comp_dirs_ok": "Application Working Directories: OK",
        "comp_dirs_desc": "models/, assets/, bin/ ready for use",

        # Settings Card 7: Version & Updates
        "card_ver_title": "Application Version & Updates",
        "btn_check_updates": "Check for Updates",
        "btn_install_update": "Download & Update",
        "installed_ver": f"Installed version: Pecislav Studio v{APP_VERSION} (by Pecislav)",
        "update_status_latest": "You are running the latest version.",
        "dnd_drop_hint": "Drag and drop video file here or click Browse  •  MP4, MKV, MOV, WebM",
        "dnd_ready_hint": "Size: {size} MB  •  Ready for analysis  •  Drag & drop to replace",
        "btn_change_file": "Change Video",
    }
}

# -----------------------------------------------------------------------------
# Logi Options+ & High-End Creator Studio Theme Colors (Multi-Tonal Dark Palette)
# -----------------------------------------------------------------------------
BG_WINDOW = ("#F4F6F9", "#0B0C10")          # Hluboké obsidianové pozadí okna
BG_HEADER = ("#FFFFFF", "#10121A")          # Záhlaví a horní panel
BG_SIDEBAR = ("#FFFFFF", "#0D0E14")         # Postranní panel modulu
BG_CARD = ("#FFFFFF", "#14161F")            # Základní karta sekce
BG_CARD_ALT = ("#FFFFFF", "#161824")        # Alternativní odstín pro vstupní/exportní karty
BG_CARD_INNER = ("#F1F5F9", "#1A1D28")      # Vnitřní vnořené zóny a panely
BORDER_CARD = ("#E2E8F0", "#242736")        # Hladké, přirozeně zaoblené ohraničení bez pixelace
BORDER_SUBTLE = ("#E2E8F0", "#1E212E")      # Jemné linky a vnitřní oddělovače

ORANGE_PRIMARY = "#FF6D00"                  # Výrazná tvůrčí oranžová (Logi Options+ signature accent)
ORANGE_HOVER = "#FF7E1A"                    # Zářivější hover oranžová
ORANGE_ACTIVE = "#E65A00"                   # Aktivní kliknutí
ORANGE_SUBTLE = ("#FFF7ED", "#26150B")      # Tmavě jantarové podbarvení odznaků a pill tagů
ORANGE_ACCENT_TEXT = ("#C2410C", "#FFA04D") # Oranžový text hodnot s vysokým kontrastem
CHIP_BG = ("#F1F5F9", "#1B1E29")            # Digitální čipy hodnot
CHIP_BORDER = ("#E2E8F0", "#282C3D")        # Rámeček čipů

TEXT_TITLE = ("#0F172A", "#F8FAFC")         # Čistý kontrastní nadpis
TEXT_BODY = ("#475569", "#94A3B8")          # Přehledný sekundární text (Slate)
TEXT_MUTED = ("#64748B", "#64748B")         # Tlumené popisky a pomocné texty
TEXT_REC = ("#C25E00", "#FF9933")           # Zlatavá oranžová pro doporučení
TRACK_COLOR = ("#94A3B8", "#2D3346")        # Moderní dráha posuvníků

# -----------------------------------------------------------------------------
# Logi Options+ Studio Theme Preview Window Generator
# -----------------------------------------------------------------------------

def create_logi_theme_preview_image(theme_type: str, w: int = 130, h: int = 56, r: int = 8) -> Image.Image:
    """
    Generates an elegant Logi Options+ style miniature studio window mockup:
    - Titlebar with clean window dots
    - Inner card with content placeholders
    - Signature orange accent pill (#FF6D00)
    - 'system': Split-screen preview (Light on left, Dark on right)
    - 'light': Crisp clean light studio mockup
    - 'dark': Deep matte obsidian studio mockup
    """
    scale = 3
    sw, sh = w * scale, h * scale
    sr = r * scale

    img = Image.new('RGBA', (sw, sh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    orange = (255, 109, 0, 255)

    def draw_window_part(box, bg_win, bg_card, border_card, bar_color, pill_color, dots_color):
        x0, y0, x1, y1 = box
        draw.rectangle([x0, y0, x1, y1], fill=bg_win)

        # Titlebar dots (3 dots)
        dot_r = 2.2 * scale
        dot_y = y0 + 6.5 * scale
        for i in range(3):
            dx = x0 + 8 * scale + i * 6.5 * scale
            if dx + dot_r < x1 - 4 * scale:
                draw.ellipse([dx - dot_r, dot_y - dot_r, dx + dot_r, dot_y + dot_r], fill=dots_color)

        # Card inside window
        cx0 = x0 + 7 * scale
        cy0 = y0 + 14 * scale
        cx1 = x1 - 7 * scale
        cy1 = y1 - 7 * scale
        if cx1 > cx0 + 10 * scale and cy1 > cy0 + 10 * scale:
            draw.rounded_rectangle([cx0, cy0, cx1, cy1], radius=4 * scale, fill=bg_card, outline=border_card, width=int(1.2 * scale))

            # Orange accent pill
            draw.rounded_rectangle([cx0 + 5 * scale, cy0 + 5 * scale, cx0 + 24 * scale, cy0 + 9 * scale], radius=2 * scale, fill=pill_color)
            # Content bars
            draw.rounded_rectangle([cx0 + 5 * scale, cy0 + 13 * scale, cx1 - 8 * scale, cy0 + 16 * scale], radius=1.5 * scale, fill=bar_color)
            draw.rounded_rectangle([cx0 + 5 * scale, cy0 + 19 * scale, cx1 - 16 * scale, cy0 + 22 * scale], radius=1.5 * scale, fill=bar_color)

    c_dark_win = (24, 25, 32, 255)
    c_dark_card = (32, 34, 44, 255)
    c_dark_bd = (46, 50, 64, 255)
    c_dark_bar = (60, 64, 80, 255)
    c_dark_dots = (78, 83, 104, 255)

    c_light_win = (240, 242, 245, 255)
    c_light_card = (255, 255, 255, 255)
    c_light_bd = (226, 228, 232, 255)
    c_light_bar = (208, 212, 220, 255)
    c_light_dots = (184, 188, 198, 255)

    if theme_type == 'dark':
        draw_window_part((0, 0, sw, sh), c_dark_win, c_dark_card, c_dark_bd, c_dark_bar, orange, c_dark_dots)
    elif theme_type == 'light':
        draw_window_part((0, 0, sw, sh), c_light_win, c_light_card, c_light_bd, c_light_bar, orange, c_light_dots)
    elif theme_type == 'system':
        mid_x = sw // 2
        # Left half Light
        draw_window_part((0, 0, mid_x, sh), c_light_win, c_light_card, c_light_bd, c_light_bar, orange, c_light_dots)
        # Right half Dark
        draw_window_part((mid_x, 0, sw, sh), c_dark_win, c_dark_card, c_dark_bd, c_dark_bar, orange, c_dark_dots)
        # Divider down middle
        draw.line([(mid_x, 0), (mid_x, sh)], fill=(120, 125, 140, 140), width=int(1.5 * scale))

    # Mask to rounded rectangle
    mask = Image.new('L', (sw, sh), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=sr, fill=255)

    out = Image.new('RGBA', (sw, sh), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask=mask)

    # Subtle outer border
    draw_out = ImageDraw.Draw(out)
    draw_out.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=sr, outline=(100, 105, 120, 120), width=max(1, int(1.2 * scale)))

    return out.resize((w, h), Image.Resampling.LANCZOS)

# Backward-compatibility alias
create_slanted_theme_image = create_logi_theme_preview_image

# -----------------------------------------------------------------------------
# Floating Modern Tooltip (Hover Overlay - Zero Layout Shift, Rounded Card)
# -----------------------------------------------------------------------------

class ModernTooltip:
    """
    Floating overlay tooltip that appears next to a widget on hover without shifting layout.
    Displays a modern rounded card with Segoe UI typography, distinct bullet hierarchy,
    and an elegant warm recommendation pill.
    """
    active_tooltip: Optional['ModernTooltip'] = None

    def __init__(self, widget, text: str, recommendation: Optional[str] = None, max_width: int = 420):
        self.widget = widget
        self.text = text.strip()
        self.recommendation = recommendation.strip() if recommendation else None
        self.max_width = max_width
        self.tip_window: Optional[ctk.CTkToplevel] = None
        self.after_id = None
        self.hide_after_id = None
        self._root_binds: List[Tuple[Any, str, str]] = []
        self._heartbeat_id: Optional[str] = None

        targets = [self.widget]
        try:
            targets.extend(self.widget.winfo_children())
        except Exception:
            pass
        if hasattr(self.widget, "_canvas") and self.widget._canvas not in targets:
            targets.append(self.widget._canvas)
        if hasattr(self.widget, "_text_label") and self.widget._text_label not in targets:
            targets.append(self.widget._text_label)

        for w in targets:
            w.bind("<Enter>", self.on_enter, add="+")
            w.bind("<Leave>", self.on_leave, add="+")
            w.bind("<Button-1>", self.on_click, add="+")

    def set_recommendation(self, recommendation: Optional[str]):
        """Dynamically update recommendation text (e.g. when changing mode)."""
        self.recommendation = recommendation.strip() if recommendation else None

    def on_enter(self, event=None):
        if ModernTooltip.active_tooltip and ModernTooltip.active_tooltip != self:
            ModernTooltip.active_tooltip.hide()
        self.cancel_schedule()
        self.after_id = self.widget.after(80, self.show)

    def on_leave(self, event=None):
        self.cancel_schedule()
        self.hide_after_id = self.widget.after(150, self.hide)

    def on_click(self, event=None):
        self.cancel_schedule()
        self.hide()

    def cancel_schedule(self):
        if self.after_id:
            try:
                self.widget.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None
        if self.hide_after_id:
            try:
                self.widget.after_cancel(self.hide_after_id)
            except Exception:
                pass
            self.hide_after_id = None

    def show(self):
        if self.tip_window or not self.widget.winfo_exists():
            return

        ModernTooltip.active_tooltip = self

        self.tip_window = tw = ctk.CTkToplevel(self.widget)
        root = self.widget.winfo_toplevel()
        try:
            tw.transient(root)
        except Exception:
            pass
        tw.wm_overrideredirect(True)
        tw.lift()
        try:
            if sys.platform.startswith("win"):
                tw.attributes("-transparentcolor", "#000001")
                tw.configure(fg_color="#000001")
            else:
                tw.configure(fg_color="transparent")
        except Exception:
            pass

        card = ctk.CTkFrame(
            tw,
            corner_radius=12,
            border_width=1,
            border_color=("#E2E8F0", "#313547"),
            fg_color=("#FFFFFF", "#1E202C")
        )
        card.pack(padx=2, pady=2)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=16, pady=14)

        hover_targets = [tw, card, inner]

        lines = self.text.split("\n\n")
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.startswith("• "):
                content = line_str[2:].strip()
                if ":" in content:
                    title, desc = content.split(":", 1)
                    item_box = ctk.CTkFrame(inner, fg_color="transparent")
                    item_box.pack(fill="x", pady=(0, 6))
                    hover_targets.append(item_box)

                    lbl_t = ctk.CTkLabel(
                        item_box,
                        text=f"●  {title.strip()}:",
                        font=ctk.CTkFont(size=12, weight="bold"),
                        text_color=TEXT_TITLE,
                        anchor="w"
                    )
                    lbl_t.pack(anchor="w")
                    hover_targets.append(lbl_t)

                    lbl_d = ctk.CTkLabel(
                        item_box,
                        text=desc.strip(),
                        font=ctk.CTkFont(size=11),
                        text_color=TEXT_BODY,
                        wraplength=self.max_width,
                        justify="left",
                        anchor="w"
                    )
                    lbl_d.pack(anchor="w", padx=(14, 0))
                    hover_targets.append(lbl_d)
                else:
                    lbl_item = ctk.CTkLabel(
                        inner,
                        text=line_str,
                        font=ctk.CTkFont(size=11),
                        text_color=TEXT_BODY,
                        wraplength=self.max_width,
                        justify="left",
                        anchor="w"
                    )
                    lbl_item.pack(anchor="w", pady=(0, 6))
                    hover_targets.append(lbl_item)
            else:
                lbl_para = ctk.CTkLabel(
                    inner,
                    text=line_str,
                    font=ctk.CTkFont(size=11),
                    text_color=TEXT_BODY,
                    wraplength=self.max_width,
                    justify="left",
                    anchor="w"
                )
                lbl_para.pack(anchor="w", pady=(0, 6))
                hover_targets.append(lbl_para)

        if self.recommendation:
            rec_card = ctk.CTkFrame(
                inner,
                corner_radius=8,
                fg_color=("#FFF7ED", "#231B16"),
                border_width=1,
                border_color=("#FED7AA", "#3D2A1C")
            )
            rec_card.pack(fill="x", pady=(6, 0))
            hover_targets.append(rec_card)

            rec_text = self.recommendation
            icon_bulb = load_app_icon("lightbulb", size=(16, 16))
            lbl_rec = ctk.CTkLabel(
                rec_card,
                text=f"  Doporučení: {rec_text}",
                image=icon_bulb,
                compound="left",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=("#EA580C", "#FB923C"),
                wraplength=self.max_width - 24,
                justify="left"
            )
            lbl_rec.pack(padx=12, pady=8, anchor="w")
            hover_targets.append(lbl_rec)

        def keep_open(e):
            self.cancel_schedule()

        for widget_item in hover_targets:
            widget_item.bind("<Enter>", keep_open, add="+")
            widget_item.bind("<Leave>", self.on_leave, add="+")

        tw.update_idletasks()
        w_tip = tw.winfo_width()
        h_tip = tw.winfo_height()
        screen_w = tw.winfo_screenwidth()
        screen_h = tw.winfo_screenheight()

        root_x = self.widget.winfo_rootx()
        root_y = self.widget.winfo_rooty()
        btn_w = self.widget.winfo_width()

        x = root_x + btn_w + 8
        y = root_y - 4

        if x + w_tip > screen_w - 12:
            x = max(8, root_x - w_tip - 8)
        if y + h_tip > screen_h - 15:
            y = max(8, screen_h - h_tip - 15)

        tw.wm_geometry(f"+{x}+{y}")

        # Root dismiss listeners
        self._root_binds = []
        try:
            for seq in ("<Button-1>", "<Button-2>", "<Button-3>", "<Deactivate>", "<Unmap>", "<MouseWheel>"):
                bid = root.bind(seq, lambda _: self.hide(), add="+")
                self._root_binds.append((root, seq, bid))
        except Exception:
            pass

    def hide(self):
        self.cancel_schedule()
        if hasattr(self, "_heartbeat_id") and self._heartbeat_id:
            try:
                self.widget.after_cancel(self._heartbeat_id)
            except Exception:
                pass
            self._heartbeat_id = None
        if hasattr(self, "_root_binds"):
            for target, seq, bid in self._root_binds:
                try:
                    target.unbind(seq, bid)
                except Exception:
                    pass
            self._root_binds.clear()
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None
        if ModernTooltip.active_tooltip == self:
            ModernTooltip.active_tooltip = None

    @classmethod
    def hide_all(cls):
        if cls.active_tooltip:
            cls.active_tooltip.hide()


# -----------------------------------------------------------------------------
# Color Resolution and Anti-Aliased Graphics Helpers
# -----------------------------------------------------------------------------

def _resolve_color(col: Any) -> Optional[str]:
    """Resolves CustomTkinter color tuple (light, dark) or single color based on active appearance mode."""
    if col is None:
        return None
    if isinstance(col, (tuple, list)):
        mode = ctk.get_appearance_mode()
        val = col[0] if mode == "Light" else col[1]
    else:
        val = col
    if val == "transparent":
        return None
    return str(val)


def _hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Converts a 6-character hex color string to an (R, G, B) tuple."""
    c = hex_str.strip().lstrip("#")
    if len(c) == 3:
        c = "".join([x * 2 for x in c])
    if len(c) == 6:
        try:
            return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
        except ValueError:
            pass
    return (15, 16, 22)


def _get_widget_bg_rgb(widget) -> Tuple[int, int, int]:
    """
    Walks up the widget hierarchy starting from the parent to find the first
    non-transparent background color. Returns an (R, G, B) tuple used as the
    canvas background when rendering PIL rounded widgets, so anti-aliased corner
    pixels blend seamlessly into the parent container instead of showing gray/dark artifacts.
    """
    try:
        w = getattr(widget, "master", None)
        for _ in range(14):
            if w is None:
                break
            try:
                fg = w.cget("fg_color")
                if fg and fg not in ("transparent", "", None):
                    resolved = _resolve_color(fg)
                    if resolved and resolved != "transparent":
                        return _hex_to_rgb(resolved)
            except Exception:
                pass
            try:
                w = getattr(w, "master", None)
            except Exception:
                break
    except Exception:
        pass
    if ctk.get_appearance_mode() == "Light":
        return (246, 247, 250)
    return (15, 16, 22)


def _color_to_rgba(col: Any, alpha: int = 255) -> Tuple[int, int, int, int]:
    """Converts a hex color string, color name, or tuple into an RGBA integer 4-tuple."""
    if not col or col == "transparent":
        return (0, 0, 0, 0)
    resolved = _resolve_color(col)
    if not resolved:
        return (0, 0, 0, 0)
    if isinstance(resolved, (tuple, list)) and len(resolved) in (3, 4):
        return tuple(resolved) if len(resolved) == 4 else (*resolved, alpha)  # type: ignore
    c = str(resolved).strip().lstrip("#")
    if len(c) == 3:
        c = "".join([x * 2 for x in c])
    if len(c) == 6:
        try:
            return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), alpha)
        except ValueError:
            pass
    if len(c) == 8:
        try:
            return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), int(c[6:8], 16))
        except ValueError:
            pass
    return (255, 255, 255, alpha)


# -----------------------------------------------------------------------------
# Modern Floating Rounded Option Menu (Replaces ancient Windows 95 tk.Menu)
# -----------------------------------------------------------------------------

class ModernOptionMenu(ctk.CTkLabel):
    """
    Sleek modern dropdown replacement for CTkOptionMenu.
    Renders an ultra-smooth, 4x supersampled anti-aliased rounded card trigger with
    subtle 1px border, Inter typography, and floating rounded popup menu.
    Eliminates all jagged staircases and pixelated edges on Windows.
    """
    active_menu: Optional['ModernOptionMenu'] = None

    def __init__(
        self,
        parent,
        values: Optional[List[str]] = None,
        variable: Optional[ctk.StringVar] = None,
        command: Optional[Callable[[str], None]] = None,
        width: int = 400,
        height: int = 38,
        fg_color: Optional[Tuple[str, str]] = None,
        text_color: Optional[Tuple[str, str]] = None,
        button_color: Optional[str] = None,
        button_hover_color: Optional[str] = None,
        dynamic_resizing: bool = False,
        **kwargs
    ):
        super().__init__(
            parent,
            text="",
            width=width,
            height=height,
            fg_color="transparent",
            corner_radius=0,
            cursor="hand2"
        )
        self.values = list(values) if values else []
        self.command = command
        self.variable = variable
        self._target_w = width
        self._height = height
        self._current_w = width
        self._fg_color = fg_color or ("#FFFFFF", "#1E202B")
        self._text_color = text_color or TEXT_TITLE
        self._state = "normal"
        self._current_value = ""
        if variable and variable.get():
            self._current_value = variable.get()
        elif self.values:
            self._current_value = self.values[0]

        self._popup: Optional[ctk.CTkToplevel] = None
        self._hovered = False
        self._bound_handlers: List[Tuple[Any, str, str]] = []
        self._heartbeat_id: Optional[str] = None

        self.bind("<Button-1>", self._on_toggle)
        self.bind("<Enter>", self._on_hover_enter)
        self.bind("<Leave>", self._on_hover_leave)
        self.bind("<Configure>", self._on_configure)
        self.bind("<Destroy>", self._on_destroy)
        self._redraw()

    def _on_destroy(self, event=None):
        self._unbind_events()
        if self._popup and self._popup.winfo_exists():
            try:
                self._popup.destroy()
            except Exception:
                pass
        self._popup = None
        if ModernOptionMenu.active_menu == self:
            ModernOptionMenu.active_menu = None

    def _on_configure(self, event):
        if not self.winfo_exists():
            return
        if event.width > 20 and event.width != self._current_w:
            self._current_w = event.width
            self._redraw()

    def _on_hover_enter(self, event=None):
        if not self.winfo_exists() or self._state == "disabled":
            return
        self._hovered = True
        self._redraw()

    def _on_hover_leave(self, event=None):
        if not self.winfo_exists():
            return
        self._hovered = False
        self._redraw()

    def _on_toggle(self, event=None):
        if not self.winfo_exists() or self._state == "disabled":
            return
        now = time.time()
        if getattr(self, "_last_close_time", 0) and (now - self._last_close_time < 0.25):
            return
        if self._popup and self._popup.winfo_exists():
            self._close_popup()
        else:
            self._open_popup()

    def _redraw(self):
        if not self.winfo_exists():
            return
        w = max(50, self._current_w)
        h = self._height
        scale = 4
        sw, sh = w * scale, h * scale
        r = 8 * scale
        bw = 1 * scale

        is_open = bool(self._popup and self._popup.winfo_exists())
        if is_open:
            border = _color_to_rgba(ORANGE_PRIMARY, 255)
            chevron_c = _color_to_rgba(ORANGE_PRIMARY, 255)
        elif self._hovered:
            border = _color_to_rgba(("#9CA3AF", "#4B5568"), 255)
            chevron_c = _color_to_rgba(ORANGE_PRIMARY, 255)
        else:
            border = _color_to_rgba(BORDER_CARD, 255)
            chevron_c = _color_to_rgba(("#64748B", "#818898"), 255)

        bg = _color_to_rgba(self._fg_color, 255)
        txt_c = _color_to_rgba(TEXT_MUTED if self._state == "disabled" else self._text_color, 255)

        bg_rgb = _get_widget_bg_rgb(self)
        img = Image.new("RGBA", (sw, sh), (*bg_rgb, 255))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([bw // 2, bw // 2, sw - 1 - bw // 2, sh - 1 - bw // 2], radius=r, fill=bg, outline=border, width=bw)

        # Label text
        font_path = Path(__file__).resolve().parent / "assets" / "fonts" / "Inter-Regular.ttf"
        try:
            font = ImageFont.truetype(str(font_path), int(12 * scale))
        except Exception:
            try:
                font = ImageFont.truetype("arial.ttf", int(12 * scale))
            except Exception:
                font = ImageFont.load_default()

        val_str = str(self._current_value) if self._current_value else ""
        if val_str:
            bbox = d.textbbox((0, 0), val_str, font=font)
            th = bbox[3] - bbox[1]
            tx = 16 * scale
            ty = (sh - th) // 2 - bbox[1]
            max_text_w = sw - (45 * scale)
            if (bbox[2] - bbox[0]) > max_text_w:
                while len(val_str) > 3 and (bbox[2] - bbox[0]) > max_text_w:
                    val_str = val_str[:-4] + "..."
                    bbox = d.textbbox((0, 0), val_str, font=font)
            d.text((tx, ty), val_str, fill=txt_c, font=font)

        # Crisp anti-aliased vector chevron (eliminates missing font glyph box on Windows)
        chv_size = int(3.8 * scale)
        chv_cx = sw - int(20 * scale)
        chv_cy = sh // 2
        chv_w = max(1, int(1.8 * scale))
        if is_open:
            p1 = (chv_cx - chv_size, chv_cy + int(1.8 * scale))
            p2 = (chv_cx, chv_cy - int(1.8 * scale))
            p3 = (chv_cx + chv_size, chv_cy + int(1.8 * scale))
        else:
            p1 = (chv_cx - chv_size, chv_cy - int(1.8 * scale))
            p2 = (chv_cx, chv_cy + int(1.8 * scale))
            p3 = (chv_cx + chv_size, chv_cy - int(1.8 * scale))
        d.line([p1, p2, p3], fill=chevron_c, width=chv_w, joint="round")

        res = img.resize((w, h), Image.Resampling.LANCZOS)
        ci = ctk.CTkImage(light_image=res, dark_image=res, size=(w, h))
        super().configure(image=ci)

    def _set_appearance_mode(self, mode_string):
        super()._set_appearance_mode(mode_string)
        self._redraw()

    def _open_popup(self):
        if ModernOptionMenu.active_menu and ModernOptionMenu.active_menu != self:
            ModernOptionMenu.active_menu._close_popup()
        ModernOptionMenu.active_menu = self

        self._popup = tw = ctk.CTkToplevel(self)
        self.update_idletasks()
        if self.winfo_exists():
            self._redraw()

        root = self.winfo_toplevel()

        try:
            tw.transient(root)
        except Exception:
            pass
        tw.wm_overrideredirect(True)
        tw.lift()

        # Sleek modern card with refined subtle dark border
        tw.configure(fg_color=("#FFFFFF", "#1E202B"))
        card = ctk.CTkFrame(
            tw,
            corner_radius=10,
            fg_color=("#FFFFFF", "#1E202B"),
            border_width=1,
            border_color=("#D1D5DB", "#373C4D")
        )
        card.pack(fill="both", expand=True)

        use_scroll = len(self.values) > 6
        if use_scroll:
            container = ctk.CTkScrollableFrame(card, fg_color="transparent", height=240)
            container.pack(fill="both", expand=True, padx=4, pady=4)
        else:
            container = ctk.CTkFrame(card, fg_color="transparent")
            container.pack(fill="both", expand=True, padx=4, pady=4)

        for val in self.values:
            is_sel = (val == self._current_value)
            bg_norm = "transparent"
            bg_hover = ("#F1F5F9", "#282B37")
            fg_norm = ORANGE_PRIMARY if is_sel else TEXT_TITLE
            fg_hover = ORANGE_PRIMARY if is_sel else ("#0F172A", "#FFFFFF")

            row = ctk.CTkFrame(
                container,
                height=38,
                corner_radius=6,
                fg_color=bg_norm,
                cursor="hand2"
            )
            row.pack(fill="x", padx=2, pady=2)
            row.pack_propagate(False)

            lbl = ctk.CTkLabel(
                row,
                text=val,
                anchor="w",
                font=ctk.CTkFont(family=APP_FONT_FAMILY, size=12, weight="bold" if is_sel else "normal"),
                text_color=fg_norm,
                cursor="hand2"
            )
            lbl.pack(side="left", fill="both", expand=True, padx=(12, 6))

            chk = None
            if is_sel:
                chk = ctk.CTkLabel(
                    row,
                    text="✓",
                    font=ctk.CTkFont(family=APP_FONT_FAMILY, size=13, weight="bold"),
                    text_color=ORANGE_PRIMARY,
                    cursor="hand2"
                )
                chk.pack(side="right", padx=(0, 12))

            items_to_bind = [row, lbl]
            if chk:
                items_to_bind.append(chk)

            def make_hover_handlers(r=row, l=lbl, bn=bg_norm, bh=bg_hover, fn=fg_norm, fh=fg_hover):
                def _enter(e=None):
                    if r.winfo_exists():
                        r.configure(fg_color=bh)
                    if l.winfo_exists():
                        l.configure(text_color=fh)
                def _leave(e=None):
                    if not r.winfo_exists():
                        return
                    if e is not None:
                        try:
                            rx = r.winfo_rootx()
                            ry = r.winfo_rooty()
                            rw = r.winfo_width()
                            rh = r.winfo_height()
                            if rx <= e.x_root < rx + rw and ry <= e.y_root < ry + rh:
                                return
                        except Exception:
                            pass
                    r.configure(fg_color=bn)
                    if l.winfo_exists():
                        l.configure(text_color=fn)
                return _enter, _leave

            _ent, _lev = make_hover_handlers()
            for w in items_to_bind:
                w.bind("<Enter>", _ent)
                w.bind("<Leave>", _lev)
                w.bind("<Button-1>", lambda _, v=val: self._on_user_select(v))

        btn_w = self.winfo_width()
        btn_h = self.winfo_height()
        rx = self.winfo_rootx()
        ry = self.winfo_rooty()

        calc_h = min(len(self.values) * 42 + 12, 260 if use_scroll else 400)
        pop_w = max(btn_w, 200)

        screen_h = self.winfo_screenheight()
        target_y = ry + btn_h + 3
        if target_y + calc_h > screen_h - 20:
            target_y = max(8, ry - calc_h - 3)

        tw.geometry(f"{pop_w}x{calc_h}+{rx}+{target_y}")

        # Cleanup existing bindings
        self._unbind_events()

        def on_global_click(event):
            if not self._popup or not self._popup.winfo_exists():
                return
            try:
                px = self._popup.winfo_rootx()
                py = self._popup.winfo_rooty()
                pw = self._popup.winfo_width()
                ph = self._popup.winfo_height()
                if px <= event.x_root <= px + pw and py <= event.y_root <= py + ph:
                    return

                bx = self.winfo_rootx()
                by = self.winfo_rooty()
                bw = self.winfo_width()
                bh = self.winfo_height()
                if bx <= event.x_root <= bx + bw and by <= event.y_root <= by + bh:
                    self._close_popup()
                    return

                self._close_popup()
            except Exception:
                self._close_popup()

        def on_root_unmap(e):
            if e.widget == root and root.state() == "iconic":
                self._close_popup()

        def add_b(target, seq, func):
            try:
                bid = target.bind(seq, func, add="+")
                self._bound_handlers.append((target, seq, bid))
            except Exception:
                pass

        # Global event listeners across root
        add_b(root, "<Button-1>", on_global_click)
        add_b(root, "<Button-2>", on_global_click)
        add_b(root, "<Button-3>", on_global_click)
        add_b(root, "<MouseWheel>", lambda _: self._close_popup())
        add_b(root, "<Escape>", lambda _: self._close_popup())
        add_b(root, "<Unmap>", on_root_unmap)
        add_b(root, "<Deactivate>", lambda _: self._close_popup())

        add_b(tw, "<Escape>", lambda _: self._close_popup())

    def _unbind_events(self):
        if hasattr(self, "_heartbeat_id") and self._heartbeat_id:
            try:
                self.after_cancel(self._heartbeat_id)
            except Exception:
                pass
            self._heartbeat_id = None

        if hasattr(self, "_bound_handlers"):
            for target, seq, bid in self._bound_handlers:
                try:
                    target.unbind(seq, bid)
                except Exception:
                    pass
            self._bound_handlers.clear()

    def _on_user_select(self, value: str):
        self.set(value)
        if callable(self.command):
            try:
                self.command(value)
            except Exception as e:
                print(f"[ModernOptionMenu] Error in command callback: {e}")

    def set(self, value: str):
        self._current_value = value
        if self.variable and self.variable.get() != value:
            self.variable.set(value)
        self._close_popup()
        if self.winfo_exists():
            self._redraw()

    def get(self) -> str:
        return self._current_value

    def configure(self, require_redraw=False, **kwargs):
        if "values" in kwargs:
            self.values = list(kwargs.pop("values"))
            if self._current_value not in self.values and self.values:
                self.set(self.values[0])
            elif not self.values:
                self.set("")
        if "state" in kwargs:
            self._state = kwargs.pop("state")
            cursor = "arrow" if self._state == "disabled" else "hand2"
            super().configure(cursor=cursor)
        if "command" in kwargs:
            self.command = kwargs.pop("command")
        if "variable" in kwargs:
            self.variable = kwargs.pop("variable")
        if kwargs:
            super().configure(**kwargs)
        if self.winfo_exists():
            self._redraw()

    def cget(self, attribute_name: str):
        if attribute_name == "values":
            return self.values
        if attribute_name == "state":
            return self._state
        return super().cget(attribute_name)

    def _close_popup(self):
        self._last_close_time = time.time()
        self._unbind_events()

        if self._popup and self._popup.winfo_exists():
            try:
                self._popup.grab_release()
            except Exception:
                pass
            try:
                self._popup.destroy()
            except Exception:
                pass
        self._popup = None
        if ModernOptionMenu.active_menu == self:
            ModernOptionMenu.active_menu = None
        try:
            if self.winfo_exists():
                self._redraw()
        except Exception:
            pass


# -----------------------------------------------------------------------------
# Modern Rounded Anti-Aliased CheckBox (Replaces distorted CTkCheckBox)
# -----------------------------------------------------------------------------

class ModernCheckBox(ctk.CTkFrame):
    """
    Pixel-perfect, anti-aliased modern rounded checkbox.
    Replaces CustomTkinter's font-shapes CTkCheckBox which produces jagged,
    distorted corners and bulging curves on Windows.
    Provides mathematically smooth rounded corners (4x supersampling with Lanczos),
    crisp checkmark geometry, full-row clickability, and hover feedback.
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

        def make_box(fill, outline, is_checked=False, bg=(23, 24, 33)):
            img = Image.new("RGBA", (s, s), (*bg, 255))
            d = ImageDraw.Draw(img)
            if outline:
                d.rounded_rectangle([bw // 2, bw // 2, s - 1 - bw // 2, s - 1 - bw // 2], radius=r, fill=fill, outline=outline, width=bw)
            else:
                d.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=fill)
            if is_checked:
                cw = int(2.4 * scale)
                p1 = (s * 0.27, s * 0.50)
                p2 = (s * 0.44, s * 0.69)
                p3 = (s * 0.74, s * 0.31)
                d.line([p1, p2, p3], fill=(255, 255, 255, 255), width=cw, joint="curve")
            return img.resize((size, size), Image.Resampling.LANCZOS)

        bg_d = (23, 24, 33)
        bg_l = (241, 243, 247)

        u_dark = make_box((28, 30, 39, 255), (66, 72, 92, 255), bg=bg_d)
        u_dark_h = make_box((35, 38, 50, 255), (255, 87, 34, 255), bg=bg_d)
        u_light = make_box((255, 255, 255, 255), (203, 213, 225, 255), bg=bg_l)
        u_light_h = make_box((248, 250, 252, 255), (255, 87, 34, 255), bg=bg_l)

        c_dark = make_box((255, 87, 34, 255), None, is_checked=True, bg=bg_d)
        c_dark_h = make_box((255, 110, 64, 255), None, is_checked=True, bg=bg_d)
        c_light = make_box((255, 87, 34, 255), None, is_checked=True, bg=bg_l)
        c_light_h = make_box((255, 110, 64, 255), None, is_checked=True, bg=bg_l)

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
        variable: Optional[Any] = None,
        command: Optional[Callable] = None,
        font: Optional[ctk.CTkFont] = None,
        text_color: Optional[Any] = None,
        size: int = 22,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", cursor="hand2")
        self.variable = variable if variable is not None else ctk.BooleanVar(value=False)
        self.command = command
        self._size = size
        self._icons = self._get_icons(size)
        self._hovered = False
        self._state = kwargs.get("state", "normal")

        # Checkbox square icon
        self._box_lbl = ctk.CTkLabel(
            self,
            text="",
            image=self._get_current_image(),
            width=size,
            height=size,
            cursor="hand2"
        )
        self._box_lbl.pack(side="left", padx=(0, 10))

        # Checkbox label text
        self._text_lbl = ctk.CTkLabel(
            self,
            text=text,
            font=font or ctk.CTkFont(family=APP_FONT_FAMILY, size=13, weight="bold"),
            text_color=text_color or TEXT_TITLE,
            anchor="w",
            cursor="hand2"
        )
        self._text_lbl.pack(side="left")

        for w in (self, self._box_lbl, self._text_lbl):
            w.bind("<Button-1>", self._on_click)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

        if hasattr(self.variable, "trace_add"):
            self._trace_id = self.variable.trace_add("write", lambda *_: self._update_image())
        elif hasattr(self.variable, "trace"):
            self._trace_id = self.variable.trace("w", lambda *_: self._update_image())

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
            return
        new_val = not bool(self.variable.get())
        self.variable.set(new_val)
        self._update_image()
        if callable(self.command):
            try:
                self.command()
            except Exception as e:
                print(f"[ModernCheckBox] Error in callback: {e}")

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

    def configure(self, require_redraw=False, **kwargs):
        if "text" in kwargs:
            self._text_lbl.configure(text=kwargs.pop("text"))
        if "font" in kwargs:
            self._text_lbl.configure(font=kwargs.pop("font"))
        if "text_color" in kwargs:
            self._text_lbl.configure(text_color=kwargs.pop("text_color"))
        if "command" in kwargs:
            self.command = kwargs.pop("command")
        if "state" in kwargs:
            self._state = kwargs.pop("state")
            cursor = "arrow" if self._state == "disabled" else "hand2"
            self._box_lbl.configure(cursor=cursor)
            self._text_lbl.configure(cursor=cursor)
            super().configure(require_redraw=require_redraw, cursor=cursor)
        if "variable" in kwargs:
            self.variable = kwargs.pop("variable")
            self._update_image()
        kwargs.pop("fg_color", None)
        kwargs.pop("hover_color", None)
        kwargs.pop("border_color", None)
        if kwargs:
            super().configure(require_redraw=require_redraw, **kwargs)

    def cget(self, attribute_name: str):
        if attribute_name == "text":
            return self._text_lbl.cget("text")
        if attribute_name == "state":
            return self._state
        return super().cget(attribute_name)


# -----------------------------------------------------------------------------
# Modern Rounded Anti-Aliased Button (Replaces pixelated CTkButton)
# -----------------------------------------------------------------------------

class ModernButton(ctk.CTkLabel):
    """
    Ultra-smooth, anti-aliased modern rounded button.
    Replaces CustomTkinter's CTkButton which suffers from pixelated GDI font-shapes staircase artifacts on Windows.
    Provides true 4x Lanczos anti-aliased rounded corners, crisp vector outlines,
    proper optical icon+text layout, smooth hover states, and dynamic width expansion.
    """
    def __init__(
        self,
        parent,
        text: str = "",
        command: Optional[Callable] = None,
        image: Optional[ctk.CTkImage] = None,
        compound: str = "left",
        width: int = 140,
        height: int = 38,
        corner_radius: int = 8,
        fg_color: Any = ORANGE_PRIMARY,
        hover_color: Any = ORANGE_HOVER,
        border_color: Any = None,
        border_width: int = 0,
        text_color: Any = "#FFFFFF",
        hover_text_color: Optional[Any] = None,
        font: Any = None,
        state: str = "normal",
        circle_mode: bool = False,
        **kwargs
    ):
        cursor = "arrow" if state == "disabled" else "hand2"
        super().__init__(
            parent,
            text="",
            width=width,
            height=height,
            fg_color="transparent",
            corner_radius=0,
            cursor=cursor,
            **kwargs
        )
        self._text = text
        self.command = command
        self._image_prop = image
        self._compound = compound
        self._target_w = width
        self._height = height
        self._current_w = width
        self._corner_radius = corner_radius
        self._fg_color = fg_color
        self._hover_color = hover_color
        self._border_color = border_color
        self._border_width = border_width
        self._text_color = text_color
        self._hover_text_color = hover_text_color
        self._font_prop = font
        self._state = state
        self._hovered = False
        self._circle_mode = circle_mode

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Configure>", self._on_configure)
        self._redraw()

    def _create_grid(self):
        self._label.grid(row=0, column=0, sticky="", padx=0, pady=0)

    def _on_enter(self, event=None):
        if not self.winfo_exists() or self._state == "disabled":
            return
        self._hovered = True
        self._redraw()

    def _on_leave(self, event=None):
        if not self.winfo_exists():
            return
        self._hovered = False
        self._redraw()

    def _on_click(self, event=None):
        if not self.winfo_exists() or self._state == "disabled":
            return
        if callable(self.command):
            try:
                self.command()
            except Exception as err:
                print(f"[ModernButton] Error in callback: {err}")

    def _on_configure(self, event):
        if not self.winfo_exists():
            return
        if getattr(self, "_circle_mode", False):
            return
        if event.width > 20 and event.width != self._current_w:
            self._current_w = event.width
            self._redraw()

    def _set_appearance_mode(self, mode_string):
        super()._set_appearance_mode(mode_string)
        self._redraw()

    def configure(self, require_redraw=False, **kwargs):
        if "text" in kwargs:
            self._text = kwargs.pop("text")
        if "image" in kwargs:
            self._image_prop = kwargs.pop("image")
        if "command" in kwargs:
            self.command = kwargs.pop("command")
        if "fg_color" in kwargs:
            self._fg_color = kwargs.pop("fg_color")
        if "hover_color" in kwargs:
            self._hover_color = kwargs.pop("hover_color")
        if "border_color" in kwargs:
            self._border_color = kwargs.pop("border_color")
        if "border_width" in kwargs:
            self._border_width = kwargs.pop("border_width")
        if "text_color" in kwargs:
            self._text_color = kwargs.pop("text_color")
        if "corner_radius" in kwargs:
            self._corner_radius = kwargs.pop("corner_radius")
        if "state" in kwargs:
            self._state = kwargs.pop("state")
            cursor = "arrow" if self._state == "disabled" else "hand2"
            super().configure(cursor=cursor)
        if kwargs:
            super().configure(**kwargs)
        if self.winfo_exists():
            self._redraw()

    def cget(self, attribute_name: str):
        if attribute_name == "text":
            return self._text
        if attribute_name == "state":
            return self._state
        if attribute_name == "fg_color":
            return self._fg_color
        return super().cget(attribute_name)

    def _redraw(self):
        if not self.winfo_exists():
            return
        if getattr(self, "_circle_mode", False):
            w = self._height
            h = self._height
        else:
            w = max(30, self._current_w)
            h = self._height
        scale = 4
        sw, sh = w * scale, h * scale
        r = self._corner_radius * scale
        bw = self._border_width * scale

        is_disabled = (self._state == "disabled")
        if is_disabled:
            fill_c = _color_to_rgba(self._fg_color, 110)
            border_c = _color_to_rgba(self._border_color, 90) if self._border_width > 0 else None
            txt_c = _color_to_rgba(self._text_color, 110)
        elif self._hovered and self._hover_color:
            fill_c = _color_to_rgba(self._hover_color, 255)
            border_c = _color_to_rgba(self._border_color, 255) if self._border_width > 0 else None
            txt_c = _color_to_rgba(self._hover_text_color if self._hover_text_color else self._text_color, 255)
        else:
            fill_c = _color_to_rgba(self._fg_color, 255)
            border_c = _color_to_rgba(self._border_color, 255) if self._border_width > 0 else None
            txt_c = _color_to_rgba(self._text_color, 255)


        bg_rgb = _get_widget_bg_rgb(self)
        img = Image.new("RGBA", (sw, sh), (*bg_rgb, 255))
        d = ImageDraw.Draw(img)
        if getattr(self, "_circle_mode", False):
            if border_c and bw > 0:
                d.ellipse([bw // 2, bw // 2, sw - 1 - bw // 2, sh - 1 - bw // 2], fill=fill_c, outline=border_c, width=bw)
            else:
                d.ellipse([0, 0, sw - 1, sh - 1], fill=fill_c)
        else:
            if border_c and bw > 0:
                d.rounded_rectangle([bw // 2, bw // 2, sw - 1 - bw // 2, sh - 1 - bw // 2], radius=r, fill=fill_c, outline=border_c, width=bw)
            else:
                d.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=r, fill=fill_c)


        # Font
        f_size = 13
        f_weight = "normal"
        if self._font_prop:
            try:
                if hasattr(self._font_prop, "cget"):
                    f_size = self._font_prop.cget("size")
                    f_weight = self._font_prop.cget("weight")
                elif isinstance(self._font_prop, tuple):
                    if len(self._font_prop) > 1:
                        f_size = self._font_prop[1]
                    if len(self._font_prop) > 2:
                        f_weight = self._font_prop[2]
            except Exception:
                pass
        f_file = "Inter-Bold.ttf" if str(f_weight).lower() in ("bold", "700") else "Inter-Regular.ttf"
        font_path = Path(__file__).resolve().parent / "assets" / "fonts" / f_file
        try:
            font = ImageFont.truetype(str(font_path), int(f_size * scale))
        except Exception:
            try:
                fb = "arialbd.ttf" if "bold" in str(f_weight).lower() else "arial.ttf"
                font = ImageFont.truetype(fb, int(f_size * scale))
            except Exception:
                font = ImageFont.load_default()

        # Icon extraction
        icon_img = None
        icon_w, icon_h = 0, 0
        if self._image_prop and isinstance(self._image_prop, ctk.CTkImage):
            mode = ctk.get_appearance_mode()
            raw_im = self._image_prop._dark_image if (mode == "Dark" and self._image_prop._dark_image) else self._image_prop._light_image
            if raw_im:
                isize = getattr(self._image_prop, "_size", (20, 20))
                icon_w, icon_h = int(isize[0] * scale), int(isize[1] * scale)
                icon_img = raw_im.resize((icon_w, icon_h), Image.Resampling.LANCZOS)
                if is_disabled:
                    r_ch, g_ch, b_ch, a_ch = icon_img.split()
                    a_dim = a_ch.point(lambda p: int(p * 0.45))
                    icon_img = Image.merge("RGBA", (r_ch, g_ch, b_ch, a_dim))

        # Text measurement
        tw, th, tx_off, ty_off = 0, 0, 0, 0
        if self._text:
            bbox = d.textbbox((0, 0), self._text, font=font)
            tw = int(bbox[2] - bbox[0])
            th = int(bbox[3] - bbox[1])
            tx_off, ty_off = int(bbox[0]), int(bbox[1])

        spacing = int(8 * scale) if (icon_img and self._text) else 0
        total_content_w = icon_w + spacing + tw
        start_x = int((sw - total_content_w) // 2)

        if icon_img:
            img.paste(icon_img, (int(start_x), int((sh - icon_h) // 2)), icon_img)
            start_x = int(start_x + icon_w + spacing)

        if self._text:
            text_y = int((sh - th) // 2 - ty_off)
            d.text((int(start_x - tx_off), text_y), self._text, fill=txt_c, font=font)

        res = img.resize((w, h), Image.Resampling.LANCZOS)
        ci = ctk.CTkImage(light_image=res, dark_image=res, size=(w, h))
        super().configure(width=w, height=h, image=ci)


# -----------------------------------------------------------------------------
# Modern Smooth Anti-Aliased Progress Bar (Replaces glitchy CTkProgressBar)
# -----------------------------------------------------------------------------

class ModernProgressBar(ctk.CTkLabel):
    """
    Silky-smooth, anti-aliased modern progress bar.
    Replaces CTkProgressBar which suffers from a flat, cut-off chunk on low values
    and pixelated edges on Windows.
    At 0% (val <= 0.001), only the clean dark rounded track is drawn.
    When progress starts (> 0.001), it starts as a perfect circle and smoothly expands into a rounded capsule.
    """
    def __init__(
        self,
        parent,
        height: int = 14,
        fg_color: Any = None,
        progress_color: Any = None,
        **kwargs
    ):
        super().__init__(
            parent,
            text="",
            height=height,
            fg_color="transparent",
            **kwargs
        )
        self._height = height
        self._val = 0.0
        self._width = 200
        self._fg_color = fg_color or TRACK_COLOR
        self._progress_color = progress_color or ORANGE_PRIMARY
        self.bind("<Configure>", self._on_configure)
        self._redraw()

    def _on_configure(self, event):
        if not self.winfo_exists():
            return
        if event.width > 20 and event.width != self._width:
            self._width = event.width
            self._redraw()

    def set(self, val: float):
        self._val = max(0.0, min(1.0, float(val)))
        if self.winfo_exists():
            self._redraw()

    def get(self) -> float:
        return self._val

    def configure(self, require_redraw=False, **kwargs):
        if "fg_color" in kwargs:
            self._fg_color = kwargs.pop("fg_color")
        if "progress_color" in kwargs:
            self._progress_color = kwargs.pop("progress_color")
        if "height" in kwargs:
            self._height = kwargs.pop("height")
        if kwargs:
            super().configure(**kwargs)
        if self.winfo_exists():
            self._redraw()

    def cget(self, attribute_name: str):
        if attribute_name == "fg_color":
            return self._fg_color
        if attribute_name == "progress_color":
            return self._progress_color
        return super().cget(attribute_name)

    def _redraw(self):
        if not self.winfo_exists():
            return
        w = max(20, self._width)
        h = self._height
        scale = 4
        sw, sh = w * scale, h * scale
        r = sh // 2

        track_c = _color_to_rgba(self._fg_color, 255)
        prog_c = _color_to_rgba(self._progress_color, 255)

        bg_rgb = _get_widget_bg_rgb(self)
        img = Image.new("RGBA", (sw, sh), (*bg_rgb, 255))
        d = ImageDraw.Draw(img)
        # Smooth anti-aliased track
        d.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=r, fill=track_c)

        # Smooth anti-aliased progress fill
        # At 0%, no orange fill is drawn at all (clean track).
        # At > 0%, starts as a clean circle (diameter = height) and smoothly expands.
        if self._val > 0.001:
            fw = max(sh, int(sw * self._val))
            fw = min(fw, sw)
            d.rounded_rectangle([0, 0, fw - 1, sh - 1], radius=r, fill=prog_c)

        res = img.resize((w, h), Image.Resampling.LANCZOS)
        ci = ctk.CTkImage(light_image=res, dark_image=res, size=(w, h))
        super().configure(image=ci)

    def _set_appearance_mode(self, mode_string):
        super()._set_appearance_mode(mode_string)
        self._redraw()


# -----------------------------------------------------------------------------
# Modern Smooth Anti-Aliased Slider (Replaces pixelated CTkSlider knob)
# -----------------------------------------------------------------------------

class ModernSlider(ctk.CTkSlider):
    """
    Silky-smooth modern slider with a 4x supersampled anti-aliased circular knob.
    Completely eliminates CustomTkinter's pixelated / octagonal knob rendering.
    """
    def __init__(self, *args, **kwargs):
        self._knob_normal_img: Optional[ImageTk.PhotoImage] = None
        self._knob_hover_img: Optional[ImageTk.PhotoImage] = None
        self._knob_rendered_size: int = 0
        self._knob_canvas_img_id: Optional[int] = None
        self._is_dragging: bool = False
        super().__init__(*args, **kwargs)
        self._ensure_knob_images()
        self._canvas.bind("<Button-1>", self._on_drag_start, add="+")
        self._canvas.bind("<ButtonRelease-1>", self._on_drag_end, add="+")

    def _set_appearance_mode(self, mode_string):
        super()._set_appearance_mode(mode_string)
        if hasattr(self, "_canvas"):
            self._canvas.delete("modern_knob")
        self._knob_canvas_img_id = None
        self._knob_normal_img = None
        self._knob_hover_img = None
        self._knob_rendered_size = 0
        self._ensure_knob_images()
        self._draw()

    def _on_enter(self, event=0):
        super()._on_enter(event)
        if hasattr(self, "_canvas"):
            self._canvas.itemconfig("slider_parts", state="hidden")

    def _on_leave(self, event=0):
        super()._on_leave(event)
        if hasattr(self, "_canvas"):
            self._canvas.itemconfig("slider_parts", state="hidden")

    def _on_drag_start(self, event=None):
        self._is_dragging = True
        self._draw()

    def _on_drag_end(self, event=None):
        self._is_dragging = False
        self._draw()

    def _ensure_knob_images(self):
        if not hasattr(self, '_knob_rendered_size'):
            self._knob_rendered_size = 0
            self._knob_normal_img = None
            self._knob_hover_img = None
            self._knob_canvas_img_id = None
            self._is_dragging = False

        base_size = int(self._apply_widget_scaling(18))
        if base_size < 12:
            base_size = 18
        if base_size == self._knob_rendered_size and self._knob_normal_img is not None:
            return

        scale = 4
        s = base_size * scale
        pad = int(2.0 * scale)

        # Normal knob: crisp clean circular orange button with NO glow
        img_n = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d_n = ImageDraw.Draw(img_n)
        d_n.ellipse([pad, pad, s - 1 - pad, s - 1 - pad], fill=(255, 87, 34, 255), outline=(255, 125, 80, 255), width=int(1.2 * scale))
        knob_n = img_n.resize((base_size, base_size), Image.Resampling.LANCZOS)
        self._knob_normal_img = ImageTk.PhotoImage(knob_n)

        # Active dragging knob: beautiful warm glowing aura ring
        img_h = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d_h = ImageDraw.Draw(img_h)
        d_h.ellipse([0, 0, s - 1, s - 1], fill=(255, 112, 67, 85))
        d_h.ellipse([pad // 2, pad // 2, s - 1 - pad // 2, s - 1 - pad // 2], fill=(255, 112, 67, 140))
        d_h.ellipse([pad, pad, s - 1 - pad, s - 1 - pad], fill=(255, 100, 50, 255), outline=(255, 150, 110, 255), width=int(1.5 * scale))
        knob_h = img_h.resize((base_size, base_size), Image.Resampling.LANCZOS)
        self._knob_hover_img = ImageTk.PhotoImage(knob_h)

        self._knob_rendered_size = base_size

    def _draw(self, no_color_updates: bool = False):
        super()._draw(no_color_updates=no_color_updates)
        self._canvas.itemconfig("slider_parts", state="hidden")
        self._ensure_knob_images()
        is_active = getattr(self, "_is_dragging", False)
        knob_img = self._knob_hover_img if (is_active and self._knob_hover_img) else self._knob_normal_img
        if knob_img is None:
            return

        w_scaled = self._apply_widget_scaling(self._current_width)
        h_scaled = self._apply_widget_scaling(self._current_height)
        cr = min(w_scaled / 2.0, h_scaled / 2.0)

        val = float(self._value) if hasattr(self, "_value") else 0.5
        val = max(0.0, min(1.0, val))

        if self._orientation.lower() == "horizontal":
            cx = cr + (w_scaled - 2.0 * cr) * val
            cy = h_scaled / 2.0
        else:
            cx = w_scaled / 2.0
            cy = cr + (h_scaled - 2.0 * cr) * (1.0 - val)

        knob_items = self._canvas.find_withtag("modern_knob")
        if not knob_items:
            self._knob_canvas_img_id = self._canvas.create_image(
                cx, cy, image=knob_img, anchor="center", tags="modern_knob"
            )
        else:
            for extra in knob_items[1:]:
                self._canvas.delete(extra)
            self._knob_canvas_img_id = knob_items[0]
            self._canvas.coords(self._knob_canvas_img_id, cx, cy)
            self._canvas.itemconfig(self._knob_canvas_img_id, image=knob_img, state="normal")
            self._canvas.tag_raise(self._knob_canvas_img_id)



# -----------------------------------------------------------------------------
# Settings Dialog Compatibility Stub (Now integrated natively into Pecislav Studio)
# -----------------------------------------------------------------------------

class SettingsDialog:
    """Compatibility stub — switches to Pecislav Studio's integrated settings view."""
    def __init__(self, parent: 'AutoClipApp'):
        parent._switch_view("settings")


# -----------------------------------------------------------------------------
# Dedicated Project History Dialog
# -----------------------------------------------------------------------------

class ProjectHistoryDialog(ctk.CTkToplevel):
    """Dedicated modal dialog for managing and reopening previously processed projects."""

    def __init__(
        self,
        parent: "AutoClipApp",
        config: Dict,
        on_open_project: Callable[[Dict], None],
        on_clear_history: Callable[[], None],
        on_close: Optional[Callable[[], None]] = None,
        current_lang: str = "cs"
    ):
        super().__init__(parent)
        self.parent_app = parent
        self.config = config
        self.on_open_project = on_open_project
        self.on_clear_history = on_clear_history
        self.on_close = on_close
        self.current_lang = current_lang if current_lang in ("cs", "en") else "cs"

        title = "Historie projektů • Pecislav Studio" if self.current_lang == "cs" else "Project History • Pecislav Studio"
        self.title(title)
        self.geometry("960x620")
        self.minsize(940, 500)
        self.configure(fg_color=BG_WINDOW)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close_window)

        self._center()
        self._set_app_icon()
        self.after(50, self._apply_windows_titlebar_theme)
        self._build_ui()
        self._setup_dialog_scrolling()

    def _set_app_icon(self):
        """Loads and sets the window icon."""
        try:
            assets_dir = get_base_dir() / "assets"
            ico_file = assets_dir / "app_icon.ico"
            png_file = assets_dir / "app_icon.png"

            if sys.platform.startswith("win") and ico_file.is_file():
                try:
                    self.iconbitmap(str(ico_file))
                    return
                except Exception:
                    pass

            target_png = png_file if png_file.is_file() else None
            if target_png:
                try:
                    from PIL import Image, ImageTk
                    pil_icon = Image.open(target_png)
                    self._app_window_icon = ImageTk.PhotoImage(pil_icon)
                    self.wm_iconphoto(True, self._app_window_icon)  # type: ignore
                except Exception:
                    pass
        except Exception:
            pass

    def _apply_windows_titlebar_theme(self):
        """Sets immersive dark mode or light mode for the Windows title bar via DwmSetWindowAttribute."""
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            from ctypes import c_int, byref, sizeof
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if not hwnd:
                hwnd = self.winfo_id()
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

    def _center(self):
        self.update_idletasks()
        try:
            w, h = 920, 620
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            px, py = self.parent_app.winfo_x(), self.parent_app.winfo_y()
            pw, ph = self.parent_app.winfo_width(), self.parent_app.winfo_height()
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

    def _setup_dialog_scrolling(self):
        def _on_wheel(event):
            try:
                canvas = getattr(self.scroll_list, "_parent_canvas", None)
                if not canvas or not canvas.winfo_exists():
                    return
                if sys.platform.startswith("win"):
                    steps = -int(event.delta / 1.5)
                elif sys.platform == "darwin":
                    steps = -int(event.delta * 2)
                else:
                    num = getattr(event, "num", None)
                    steps = -60 if num == 4 else 60
                canvas.yview_scroll(steps, "units")
                return "break"
            except Exception:
                pass

        self.bind("<MouseWheel>", _on_wheel)
        self.bind("<Button-4>", _on_wheel)
        self.bind("<Button-5>", _on_wheel)

    def _on_close_window(self):
        cb = self.on_close
        self.on_close = None
        try:
            self.destroy()
        finally:
            if callable(cb):
                cb()

    def _build_ui(self):
        for w in self.winfo_children():
            w.destroy()

        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 14))

        t_title = "Historie zpracovaných projektů" if self.current_lang == "cs" else "Processed Projects History"
        t_sub = ("Videa, která prošla analýzou a střihem v modulu SnapCut. Kliknutím na projekt se okamžitě vrátíte do editoru momentů."
                 if self.current_lang == "cs"
                 else "Videos processed by SnapCut. Click any project to open the moment editor immediately.")

        lbl_t = ctk.CTkLabel(hdr, text=t_title, font=ctk.CTkFont(size=18, weight="bold"), text_color=TEXT_TITLE)
        lbl_t.pack(anchor="w")
        lbl_s = ctk.CTkLabel(hdr, text=t_sub, font=ctk.CTkFont(size=12), text_color=TEXT_MUTED)
        lbl_s.pack(anchor="w", pady=(3, 0))

        # Scrollable container for history items (recessed background)
        self.scroll_list = ctk.CTkScrollableFrame(
            self,
            fg_color=("#E5E7EB", "#111217"),
            corner_radius=12,
            border_width=1,
            border_color=("#CBD5E1", "#22242D")
        )
        self.scroll_list.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        history = self.config.get("history", [])
        valid_entries = [h for h in history if h.get("video")]

        if not valid_entries:
            empty_box = ctk.CTkFrame(self.scroll_list, fg_color="transparent")
            empty_box.pack(expand=True, fill="both", pady=80)

            msg1 = "Zatím žádná historie projektů" if self.current_lang == "cs" else "No project history yet"
            msg2 = ("Až dokončíte analýzu videa nebo střih, projekt se zde automaticky uloží.\n"
                    "Budete se k němu moci kdykoliv vrátit a znovu otevřít editor bez nutnosti re-analyzovat audio."
                    if self.current_lang == "cs"
                    else "Completed video analyses and cuts will be stored here.\nYou can return anytime to review moments without re-analyzing audio.")
            ctk.CTkLabel(
                empty_box,
                text=msg1,
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=TEXT_TITLE
            ).pack(pady=(0, 8))
            ctk.CTkLabel(
                empty_box,
                text=msg2,
                font=ctk.CTkFont(size=12),
                text_color=TEXT_MUTED,
                justify="center"
            ).pack()
        else:
            for item in reversed(valid_entries):
                self._render_item(item)

        # Footer
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(0, 18))

        if valid_entries:
            t_clr = "Vymazat celou historii" if self.current_lang == "cs" else "Clear All History"
            ctk.CTkButton(
                footer,
                text=t_clr,
                image=getattr(self.parent_app, "icon_trash", None),
                compound="left",
                command=self._on_clear_clicked,
                height=34,
                font=ctk.CTkFont(size=12),
                fg_color=("#FEF2F2", "#221316"),
                hover_color=("#FEE2E2", "#351A1E"),
                text_color=("#DC2626", "#F87171"),
                border_width=1,
                border_color=("#FCA5A5", "#4B1B21"),
                corner_radius=8
            ).pack(side="left")

        t_close = "Zavřít" if self.current_lang == "cs" else "Close"
        ctk.CTkButton(
            footer,
            text=t_close,
            command=self._on_close_window,
            height=34,
            width=110,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ORANGE_PRIMARY,
            hover_color=ORANGE_HOVER,
            text_color="#FFFFFF",
            corner_radius=8
        ).pack(side="right")

    def _render_item(self, item: Dict):
        card = ctk.CTkFrame(
            self.scroll_list,
            fg_color=("#FFFFFF", "#1E202B"),
            corner_radius=12,
            border_width=1,
            border_color=("#CBD5E1", "#333748")
        )
        card.pack(fill="x", padx=8, pady=5)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)

        video_path_str = item.get("video", "")
        v_path = Path(video_path_str)
        date_str = item.get("date", "")
        stats = item.get("stats", {})
        output_path = item.get("output", "")

        segs = stats.get("total_segments", 0)
        dur_in = stats.get("original_duration_min", 0.0)
        dur_out = stats.get("output_duration_min", 0.0)

        # 1. Action buttons FIRST on the right to guarantee they never get squeezed or truncated
        btns = ctk.CTkFrame(inner, fg_color="transparent")
        btns.pack(side="right", padx=(14, 0))

        # Otevřít v editoru
        t_edit = "Otevřít v editoru" if self.current_lang == "cs" else "Open in Editor"
        btn_open = ctk.CTkButton(
            btns,
            text=t_edit,
            command=lambda it=item: self._select_project(it),
            height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=ORANGE_PRIMARY,
            hover_color=ORANGE_HOVER,
            text_color="#FFFFFF",
            corner_radius=8,
            width=130
        )
        btn_open.pack(side="left", padx=(0, 6))

        if output_path and Path(output_path).parent.is_dir():
            t_f = "Složka" if self.current_lang == "cs" else "Folder"
            btn_folder = ctk.CTkButton(
                btns,
                text=t_f,
                image=getattr(self.parent_app, "icon_folder", None),
                compound="left",
                command=lambda p=Path(output_path).parent: self.parent_app._open_folder(p),
                height=34,
                width=80,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=("#F1F5F9", "#282B3A"),
                hover_color=("#E2E8F0", "#34384A"),
                text_color=TEXT_TITLE,
                border_width=1,
                border_color=("#CBD5E1", "#3F455A"),
                corner_radius=8
            )
            btn_folder.pack(side="left", padx=(0, 6))

        t_del = "Smazat" if self.current_lang == "cs" else "Delete"
        btn_del = ctk.CTkButton(
            btns,
            text=t_del,
            image=getattr(self.parent_app, "icon_trash", None),
            compound="left",
            command=lambda it=item: self._confirm_and_delete_item(it),
            height=34,
            width=80,
            font=ctk.CTkFont(size=11),
            fg_color=("#FEF2F2", "#261517"),
            hover_color=("#FEE2E2", "#38191C"),
            text_color=("#DC2626", "#F87171"),
            border_width=1,
            border_color=("#FCA5A5", "#4D1D22"),
            corner_radius=8
        )
        btn_del.pack(side="left")

        # 2. Left side info fills remaining space cleanly
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)

        # File name
        ctk.CTkLabel(
            left,
            text=v_path.name,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_TITLE,
            anchor="w"
        ).pack(anchor="w")

        # Details
        if dur_out > 0.05:
            cut_str = f"Sestřih: {dur_out:.1f} min" if self.current_lang == "cs" else f"Cut: {dur_out:.1f} min"
        else:
            cut_str = "Připraveno k sestřihu" if self.current_lang == "cs" else "Ready to cut"

        if self.current_lang == "cs":
            det = f"{date_str}  •  {segs} momentů  •  Původní: {dur_in:.1f} min  •  {cut_str}"
        else:
            det = f"{date_str}  •  {segs} clips  •  Original: {dur_in:.1f} min  •  {cut_str}"
        ctk.CTkLabel(
            left,
            text=det,
            font=ctk.CTkFont(size=11),
            text_color=ORANGE_PRIMARY if segs > 0 else TEXT_MUTED,
            anchor="w"
        ).pack(anchor="w", pady=(3, 2))

        # Path muted
        disp_path = str(v_path.parent)
        if len(disp_path) > 65:
            disp_path = disp_path[:30] + "..." + disp_path[-30:]
        ctk.CTkLabel(
            left,
            text=disp_path,
            font=ctk.CTkFont(size=10),
            text_color=TEXT_MUTED,
            anchor="w"
        ).pack(anchor="w")

    def _select_project(self, item: Dict):
        self.on_close = None
        self.destroy()
        self.on_open_project(item)

    def _confirm_and_delete_item(self, item: Dict):
        v_name = Path(item.get("video", "")).name or "projekt"
        title = "Potvrdit smazání" if self.current_lang == "cs" else "Confirm Delete"
        msg = (f"Opravdu si přejete smazat projekt z historie?\n\n{v_name}"
               if self.current_lang == "cs"
               else f"Are you sure you want to remove this project from history?\n\n{v_name}")
        if messagebox.askyesno(title, msg, parent=self):
            self._delete_item(item)

    def _delete_item(self, item: Dict):
        history = self.config.get("history", [])
        self.config["history"] = [h for h in history if h.get("video") != item.get("video")]
        save_app_config(self.config)
        self._build_ui()

    def _on_clear_clicked(self):
        title = "Vymazat historii" if self.current_lang == "cs" else "Clear History"
        msg = ("Opravdu si přejete vymazat celou historii projektů?"
               if self.current_lang == "cs"
               else "Are you sure you want to clear all project history?")
        if messagebox.askyesno(title, msg, parent=self):
            self.on_clear_history()
            self._build_ui()


try:
    from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore
    _DnDBase = TkinterDnD.DnDWrapper
    HAS_TKDND = True
except (ImportError, Exception):
    HAS_TKDND = False
    DND_FILES = None
    TkinterDnD = None
    _DnDBase = object  # type: ignore


class BaseApp(ctk.CTk, _DnDBase):  # type: ignore
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dnd_ready = False
        if HAS_TKDND and TkinterDnD is not None:
            try:
                self.TkdndVersion = getattr(TkinterDnD, "_require")(self)
                self._dnd_ready = True
            except Exception:
                self._dnd_ready = False


class AutoClipApp(BaseApp):
    _SPINNER = ("⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷")

    def __init__(self):
        super().__init__()
        apply_inter_to_tk_fonts(self)

        # Configuration
        self.config = load_app_config()
        self.current_language = self.config.get("language", "en")
        self.auto_open_folder = bool(self.config.get("auto_open_folder", True))
        self.default_export_dir = self.config.get("default_export_dir", "")
        self.saved_theme = self.config.get("theme", "system")

        if self.saved_theme in ["light", "dark", "system"]:
            ctk.set_appearance_mode(self.saved_theme.capitalize())

        # Windows taskbar grouping & icon registration
        if sys.platform.startswith("win"):
            try:
                import ctypes
                myappid = "pecislav.studio.creator.1.0"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass

        # Window settings
        self.title(self.tr("app_title"))
        w, h = 1080, 860
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(20, (sw - w) // 2)
        y = max(20, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(1060, 720)
        self.configure(fg_color=BG_WINDOW)
        self._set_app_icon()
        self.after(50, self._apply_windows_titlebar_theme)

        # Application state
        self.current_video_path: Optional[Path] = None
        if self.default_export_dir and Path(self.default_export_dir).is_dir():
            self.output_directory = Path(self.default_export_dir)
        else:
            self.output_directory = None
        self.video_metadata: Optional[Dict] = None
        self.processing_thread: Optional[threading.Thread] = None
        self.download_thread: Optional[threading.Thread] = None
        self.cancel_event = threading.Event()
        self.is_processing = False
        self.is_downloading_ffmpeg = False
        self.last_output_path: Optional[Path] = None
        self.settings_dialog = None
        self.current_view = "snapcut"
        self._dim_overlay: Optional[ctk.CTkFrame] = None

        # Load user-crafted high quality icons from assets/icons/
        self.icon_folder = load_app_icon("folder", (20, 20))
        self.icon_folder_white = load_app_icon("folder", (20, 20), tint="white")
        self.icon_check = load_app_icon("check", (20, 20))
        self.icon_trash = load_app_icon("trash", (20, 20))
        self.icon_reload = load_app_icon("reload", (20, 20))
        self.icon_star = load_app_icon("star", (20, 20))
        self.icon_play = load_app_icon("play", (20, 20))
        self.icon_pause = load_app_icon("pause", (20, 20))
        self.icon_expand = load_app_icon("expand", (20, 20))
        self.icon_hourglass = load_app_icon("hourglass", (18, 18))
        self.icon_lightbulb = load_app_icon("lightbulb", (18, 18))
        self.icon_volume = load_app_icon("volume", (18, 18))
        self.icon_facecam = load_app_icon("facecam", (18, 18))
        self.icon_close = load_app_icon("close", (18, 18))
        self.icon_info = load_app_icon("info", (20, 20))

        # Build Studio Shell: Left Sidebar + Right Pages Container
        self._build_app_shell()
        self._setup_smooth_scrolling()

        # Handle clean exit & bulletproof settings persistence
        self.protocol("WM_DELETE_WINDOW", self._on_app_exit)

        # Check FFmpeg availability at launch
        self._check_ffmpeg_status()

    def _set_app_icon(self):
        """Loads and sets the window icon across Windows and macOS/Linux."""
        try:
            assets_dir = get_base_dir() / "assets"
            ico_file = assets_dir / "app_icon.ico"
            png_file = assets_dir / "app_icon.png"
            logo_file = assets_dir / "logo.png"

            # On Windows, try iconbitmap with .ico first
            if sys.platform.startswith("win") and ico_file.is_file():
                try:
                    self.iconbitmap(str(ico_file))
                    return
                except Exception:
                    pass

            # Cross-platform wm_iconphoto
            target_png = png_file if png_file.is_file() else (logo_file if logo_file.is_file() else None)
            if target_png:
                try:
                    from PIL import Image, ImageTk
                    pil_icon = Image.open(target_png)
                    self._app_window_icon = ImageTk.PhotoImage(pil_icon)
                    self.wm_iconphoto(True, self._app_window_icon)  # type: ignore
                except Exception:
                    pass
        except Exception:
            pass

    def _apply_windows_titlebar_theme(self):
        """Sets immersive dark mode or light mode for the Windows title bar via DwmSetWindowAttribute."""
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            from ctypes import c_int, byref, sizeof
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if not hwnd:
                hwnd = self.winfo_id()
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
                caption_color = c_int(0x00181211)  # #111218 (0x00BBGGRR)
                text_color = c_int(0x00FFFFFF)
            else:
                caption_color = c_int(0x00FAFAF8)  # #F8FAFA
                text_color = c_int(0x0010181A)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 35, byref(caption_color), sizeof(caption_color)
            )
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 36, byref(text_color), sizeof(text_color)
            )
        except Exception:
            pass

    def tr(self, key: str, **kwargs) -> str:
        """Retrieves localized text for the given translation key based on self.current_language."""
        lang = getattr(self, "current_language", "cs")
        text_dict = TRANSLATIONS.get(lang, TRANSLATIONS["cs"])
        val = text_dict.get(key, TRANSLATIONS["cs"].get(key, key))
        if kwargs:
            try:
                return val.format(**kwargs)
            except Exception:
                return val
        return val

    def _get_configured_threads(self) -> int:
        """Returns optimal thread count for FFmpeg and OpenCV (0 = all cores automatically)."""
        return 0


    # -------------------------------------------------------------------------
    # Helper: Interactive (?) Help Button Builder
    # -------------------------------------------------------------------------

    def _create_help_btn(self, parent_row, target_container=None, text: str = "", recommendation: Optional[str] = None) -> ModernButton:
        """
        Creates a clean (?) hover button with a floating tooltip overlay.
        The text floats cleanly next to the button on hover without shifting or jumping
        any widgets below, with a distinct bold warm-tinted recommendation badge.
        """
        btn = ModernButton(
            parent_row,
            text="?",
            width=22,
            height=22,
            corner_radius=11,
            circle_mode=True,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=("#E5E7EB", "#262833"),
            hover_color=ORANGE_PRIMARY,
            text_color=("#4B5568", "#B4B9C7"),
            hover_text_color="#FFFFFF"
        )
        tooltip = ModernTooltip(btn, text=text, recommendation=recommendation)
        setattr(btn, "_tooltip", tooltip)
        return btn

    _step_badge_cache: Dict[str, ctk.CTkImage] = {}

    def _get_step_badge_image(self, text: str) -> Optional[ctk.CTkImage]:
        if text in self._step_badge_cache:
            return self._step_badge_cache[text]

        base_dir = get_base_dir()
        icons_dir = base_dir / "assets" / "icons"
        assets_dir = base_dir / "assets"
        custom_candidates = [
            icons_dir / "steps" / f"step_{text}.png",
            icons_dir / "steps" / f"step{text}.png",
            icons_dir / f"step_{text}.png",
            icons_dir / f"step{text}.png",
            assets_dir / f"step_{text}.png",
            assets_dir / f"step{text}.png"
        ]
        for c in custom_candidates:
            if c.is_file():
                try:
                    img = Image.open(c).convert("RGBA")
                    ci = ctk.CTkImage(light_image=img, dark_image=img, size=(30, 30))
                    self._step_badge_cache[text] = ci
                    return ci
                except Exception:
                    pass

        try:
            size = 30
            scale = 4
            s = size * scale
            circle_pad = 4
            r_box = [circle_pad, circle_pad, s - 1 - circle_pad, s - 1 - circle_pad]

            font_path = assets_dir / "fonts" / "Inter-Bold.ttf"
            f_size = int(17 * scale)
            try:
                font = ImageFont.truetype(str(font_path), f_size)
            except Exception:
                try:
                    font = ImageFont.truetype("arialbd.ttf", f_size)
                except Exception:
                    font = ImageFont.load_default()

            tmp = Image.new("RGBA", (s * 2, s * 2), (0, 0, 0, 0))
            ImageDraw.Draw(tmp).text((s, s), text, fill=(255, 255, 255, 255), font=font)
            gb = tmp.getbbox()
            if gb:
                gw = gb[2] - gb[0]
                gh = gb[3] - gb[1]
                tx = (s - gw) // 2 - (gb[0] - s)
                ty = (s - gh) // 2 - (gb[1] - s)
            else:
                tx = ty = 0

            img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.ellipse(r_box, fill=(255, 87, 34, 255))
            d.text((tx, ty), text, fill=(255, 255, 255, 255), font=font)

            res = img.resize((size, size), Image.Resampling.LANCZOS)
            ci = ctk.CTkImage(light_image=res, dark_image=res, size=(size, size))
            self._step_badge_cache[text] = ci
            return ci
        except Exception:
            return None

    def _create_step_badge(self, parent_row, text: str) -> ctk.CTkLabel:
        """
        Creates a crisp, perfectly circular step badge (1, 2, 3, etc.).
        If custom PNGs exist in assets/icons/steps/step_{text}.png,
        it automatically loads and uses them.
        Otherwise dynamically renders an ultra-smooth high-DPI anti-aliased circular
        badge with Inter Bold typography.
        """
        badge_img = self._get_step_badge_image(text)
        if badge_img:
            badge = ctk.CTkLabel(
                parent_row,
                text="",
                image=badge_img,
                fg_color="transparent"
            )
        else:
            badge = ctk.CTkLabel(
                parent_row,
                text=text,
                font=ctk.CTkFont(family=APP_FONT_FAMILY, size=15, weight="bold"),
                fg_color=ORANGE_PRIMARY,
                text_color="#FFFFFF",
                corner_radius=15,
                width=30,
                height=30
            )
            badge._label.grid(padx=0)
        return badge

    def _setup_smooth_scrolling(self):
        """
        Configures smooth, fast web-like scrolling across the entire application interface.
        Allows scrolling everywhere across the page (over cards, buttons, labels, sliders, empty space)
        at a natural web-like speed (~80px per wheel notch).
        """
        def web_scroll(event):
            try:
                w = getattr(event, "widget", None)
                if not w or not hasattr(w, "winfo_toplevel"):
                    return

                top = w.winfo_toplevel()
                if not top or not top.winfo_exists():
                    return

                # Calculate scroll steps
                if sys.platform.startswith("win"):
                    steps = -int(event.delta / 1.5)
                elif sys.platform == "darwin":
                    steps = -int(event.delta * 2)
                else:
                    num = getattr(event, "num", None)
                    steps = -60 if num == 4 else 60

                # 1. If mouse is in a modal dialog (SegmentReviewDialog or ProjectHistoryDialog)
                if top != self:
                    # SegmentReviewDialog with list canvas
                    list_canvas = getattr(top, "_list_canvas", None)
                    if list_canvas and list_canvas.winfo_exists():
                        seg_units = -int(event.delta / 40) if sys.platform.startswith("win") else steps
                        list_canvas.yview_scroll(seg_units, "units")
                        return "break"

                    # Dialog with scroll_list (e.g. ProjectHistoryDialog)
                    scroll_list = getattr(top, "scroll_list", None)
                    if scroll_list and scroll_list.winfo_exists():
                        sc = getattr(scroll_list, "_parent_canvas", None)
                        if sc and sc.winfo_exists():
                            sc.yview_scroll(steps, "units")
                            return "break"
                    return

                if isinstance(w, ctk.CTkScrollbar):
                    return

                # 2. Determine currently active scrollable page in main window
                active_page = self.page_snapcut if self.current_view in ("snapcut", "pecicut") else getattr(self, "page_settings", None)
                if not active_page or not active_page.winfo_exists():
                    return

                canvas = getattr(active_page, "_parent_canvas", None)
                if not canvas or not canvas.winfo_exists():
                    return

                # Hide floating tooltips on scroll
                ModernTooltip.hide_all()

                canvas.yview_scroll(steps, "units")
                return "break"
            except Exception:
                pass

        # Global bind to root window replacing default sluggish CTk scroll
        self.bind_all("<MouseWheel>", web_scroll, add=False)
        self.bind_all("<Button-4>", web_scroll, add=False)
        self.bind_all("<Button-5>", web_scroll, add=False)

    def _disable_slider_mousewheel(self, slider: ctk.CTkSlider):
        """
        Disables value modification on mouse wheel scroll for a slider.
        Sliders will ONLY change values when clicked and dragged with the mouse.
        Mouse wheel scroll over sliders will NEVER modify the slider value.
        """
        for seq in (
            "<MouseWheel>",
            "<Button-4>",
            "<Button-5>",
            "<Shift-MouseWheel>",
            "<Shift-Button-4>",
            "<Shift-Button-5>",
        ):
            try:
                slider._canvas.unbind(seq)
            except Exception:
                pass

        slider._scroll_step = 0.0
        slider._mouse_scroll_event = lambda event: None

    # -------------------------------------------------------------------------
    # UI Builder Methods
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Pecislav Studio Architecture & Layout (All-in-One Shell)
    # -------------------------------------------------------------------------

    def _build_app_shell(self):
        """Constructs the master layout: Sidebar on the left, Header & Pages on the right."""
        # Main outer container
        self.shell_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.shell_container.pack(fill="both", expand=True)

        # 1. Left Navigation Sidebar
        self._build_sidebar(self.shell_container)

        # 2. Right Content Wrapper (Header + Active View + Footer)
        self.right_wrapper = ctk.CTkFrame(self.shell_container, fg_color="transparent", corner_radius=0)
        self.right_wrapper.pack(side="left", fill="both", expand=True)

        # Header bar inside right wrapper
        self._build_header(self.right_wrapper)

        # Container where page views are switched
        self.pages_container = ctk.CTkFrame(self.right_wrapper, fg_color="transparent", corner_radius=0)
        self.pages_container.pack(fill="both", expand=True, padx=0, pady=0)

        # Build View 1: SnapCut (Highlight Cutter)
        self._build_snapcut_view(self.pages_container)

        # Build View 2: Nastavení Studia
        self._build_settings_view(self.pages_container)

        # Build Bottom Status Footer
        self._build_footer(self.right_wrapper)

        # Default active module: SnapCut
        self._switch_view("snapcut")

    def _build_sidebar(self, parent):
        """Constructs the left modern navigation bar for Pecislav Studio."""
        self.sidebar_frame = ctk.CTkFrame(parent, width=230, corner_radius=0, fg_color=BG_HEADER)
        self.sidebar_frame.pack(side="left", fill="y", padx=0, pady=0)
        self.sidebar_frame.pack_propagate(False)

        # Brand header with perfectly aligned two-line typography and refined edition badge
        brand_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        brand_frame.pack(fill="x", padx=16, pady=(18, 12))

        brand_top_row = ctk.CTkFrame(brand_frame, fg_color="transparent")
        brand_top_row.pack(fill="x")

        # Studio logo if present
        assets_dir = get_base_dir() / "assets"
        logo_path = assets_dir / "logo.png"
        if not logo_path.is_file():
            logo_path = assets_dir / "app_icon.png"

        self.logo_image = None
        if logo_path.is_file():
            try:
                from PIL import Image
                pil_img = Image.open(logo_path)
                self.logo_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(38, 38))
                lbl_logo = ctk.CTkLabel(brand_top_row, text="", image=self.logo_image, width=38, height=38)
                lbl_logo.pack(side="left", padx=(0, 10))
            except Exception:
                pass

        # Two-line brand typography (Pecislav on top, Studio + sleek Pro Creator tag directly underneath)
        brand_text_box = ctk.CTkFrame(brand_top_row, fg_color="transparent")
        brand_text_box.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            brand_text_box,
            text="Pecislav",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_TITLE,
            height=19
        ).pack(anchor="w", pady=(0, 1))

        row_studio = ctk.CTkFrame(brand_text_box, fg_color="transparent", height=18)
        row_studio.pack(anchor="w", fill="x")

        ctk.CTkLabel(
            row_studio,
            text="Studio",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_TITLE,
            height=18
        ).pack(side="left", padx=(0, 6))

        badge_tag = ctk.CTkLabel(
            row_studio,
            text="PRO CREATOR",
            font=ctk.CTkFont(size=8, weight="bold"),
            text_color=("#C2410C", "#FF8C26"),
            fg_color=("#FFEDD5", "#26170E"),
            corner_radius=4,
            padx=5,
            pady=0,
            height=16
        )
        badge_tag.pack(side="left")

        # Divider
        ctk.CTkFrame(self.sidebar_frame, height=1, fg_color=BORDER_CARD).pack(fill="x", padx=16, pady=12)

        # Navigation Label
        self.lbl_sidebar_modules = ctk.CTkLabel(
            self.sidebar_frame,
            text=self.tr("nav_modules"),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_MUTED
        )
        self.lbl_sidebar_modules.pack(anchor="w", padx=18, pady=(4, 6))

        # Nav 1: SnapCut (Modern pill tab)
        self.nav_row_snapcut = ctk.CTkFrame(self.sidebar_frame, height=40, corner_radius=10, fg_color=("#FFEDE5", "#2C1E18"))
        self.nav_row_snapcut.pack(fill="x", padx=10, pady=2)
        self.nav_row_snapcut.pack_propagate(False)
        self.nav_row_pecicut = self.nav_row_snapcut

        self.btn_nav_snapcut = ctk.CTkButton(
            self.nav_row_snapcut,
            text=self.tr("nav_snapcut"),
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="transparent",
            text_color=ORANGE_PRIMARY,
            hover=False,
            command=lambda: self._switch_view("snapcut")
        )
        self.btn_nav_snapcut.pack(fill="both", expand=True, padx=14)
        self.btn_nav_pecicut = self.btn_nav_snapcut

        # System Section Label
        self.lbl_sidebar_system = ctk.CTkLabel(
            self.sidebar_frame,
            text=self.tr("nav_system"),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_MUTED
        )
        self.lbl_sidebar_system.pack(anchor="w", padx=18, pady=(14, 6))

        # Nav 2: Settings (Modern pill tab)
        self.nav_row_settings = ctk.CTkFrame(self.sidebar_frame, height=40, corner_radius=10, fg_color="transparent")
        self.nav_row_settings.pack(fill="x", padx=10, pady=2)
        self.nav_row_settings.pack_propagate(False)

        self.btn_nav_settings = ctk.CTkButton(
            self.nav_row_settings,
            text=self.tr("nav_settings"),
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="transparent",
            text_color=TEXT_MUTED,
            hover=False,
            command=lambda: self._switch_view("settings")
        )
        self.btn_nav_settings.pack(fill="both", expand=True, padx=14)

        self._setup_nav_hover_events()

        # Spacer pushes footer to the bottom
        ctk.CTkFrame(self.sidebar_frame, fg_color="transparent").pack(fill="both", expand=True)

        # Bottom Sidebar Box
        bottom_box = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        bottom_box.pack(fill="x", padx=14, pady=(0, 16))

        # Interactive FFmpeg health indicator pill
        self.sidebar_ffmpeg_pill = ctk.CTkButton(
            bottom_box,
            text="● FFmpeg: Ověřuji...",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=28,
            corner_radius=6,
            fg_color=("#E5E7EB", "#1C1E27"),
            text_color=TEXT_BODY,
            hover_color=("#D1D5DB", "#2B2E3B"),
            command=lambda: self._switch_view("settings")
        )
        self.sidebar_ffmpeg_pill.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            bottom_box,
            text=f"Pecislav Studio v{APP_VERSION}\nby Pecislav",
            font=ctk.CTkFont(size=10),
            text_color=TEXT_MUTED,
            justify="center"
        ).pack(fill="x")

    def _build_header(self, parent):
        """Top banner inside right wrapper displaying active module info."""
        self.header_frame = ctk.CTkFrame(parent, corner_radius=0, fg_color=BG_HEADER)
        self.header_frame.pack(fill="x", padx=0, pady=0)

        header_row = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        header_row.pack(fill="x", padx=24, pady=14)

        left_box = ctk.CTkFrame(header_row, fg_color="transparent")
        left_box.pack(side="left", fill="x", expand=True)

        title_row = ctk.CTkFrame(left_box, fg_color="transparent")
        title_row.pack(anchor="w")

        self.lbl_header_title = ctk.CTkLabel(
            title_row,
            text=self.tr("header_snapcut_title"),
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_header_title.pack(side="left")

        self.lbl_header_subtitle = ctk.CTkLabel(
            left_box,
            text=self.tr("header_snapcut_subtitle"),
            font=ctk.CTkFont(size=12),
            text_color=TEXT_BODY
        )
        self.lbl_header_subtitle.pack(anchor="w", pady=(3, 0))

    def _build_snapcut_view(self, parent):
        """Builds the SnapCut Highlight Cutter view inside the main pages container."""
        self.page_snapcut = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")
        self.page_pecicut = self.page_snapcut
        self.scroll_frame = self.page_snapcut  # Preserve self.scroll_frame for existing callbacks

        # 1. Výběr souboru
        self._build_file_section(self.page_snapcut)
        # 2. Audio stopa
        self._build_audio_track_section(self.page_snapcut)
        # 3. Parametry detekce
        self._build_parameters_section(self.page_snapcut)
        # 4. Export
        self._build_export_section(self.page_snapcut)
        # 5. Průběh a výsledky
        self._build_progress_section(self.page_snapcut)

    def _build_pecicut_view(self, parent):
        self._build_snapcut_view(parent)

    def _build_settings_view(self, parent):
        """Builds the native Settings view for Pecislav Studio with all configuration cards."""
        self.page_settings = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")

        # ---------------------------------------------------------------------
        # 1. Barevný režim aplikace (Obrázky se skosením: Systémová / Bílá / Černá)
        # ---------------------------------------------------------------------
        theme_card = ctk.CTkFrame(self.page_settings, corner_radius=12, fg_color=BG_CARD, border_width=1, border_color=BORDER_CARD)
        theme_card.pack(fill="x", pady=(0, 12))

        self.lbl_theme_title = ctk.CTkLabel(
            theme_card,
            text=self.tr("card_theme_title"),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_theme_title.pack(anchor="w", padx=16, pady=(14, 2))

        self.lbl_theme_sub = ctk.CTkLabel(
            theme_card,
            text=self.tr("card_theme_sub"),
            font=ctk.CTkFont(size=12),
            text_color=TEXT_BODY
        )
        self.lbl_theme_sub.pack(anchor="w", padx=16, pady=(0, 12))

        themes_row = ctk.CTkFrame(theme_card, fg_color="transparent")
        themes_row.pack(fill="x", padx=16, pady=(0, 16))

        # 3 theme previews with Logi Options+ miniature window mockups
        self.theme_images = {}
        theme_modes = [
            ("system", self.tr("theme_system")),
            ("light", self.tr("theme_light")),
            ("dark", self.tr("theme_dark"))
        ]
        for mode_key, _ in theme_modes:
            pil_img = create_logi_theme_preview_image(mode_key, w=130, h=56, r=8)
            self.theme_images[mode_key] = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(130, 56))

        self.theme_buttons = {}
        for idx, (mode_key, label_text) in enumerate(theme_modes):
            btn = ctk.CTkButton(
                themes_row,
                image=self.theme_images[mode_key],
                text=label_text,
                compound="top",
                font=ctk.CTkFont(size=12, weight="bold"),
                width=165,
                height=90,
                corner_radius=12,
                fg_color=BG_CARD_INNER,
                text_color=TEXT_TITLE,
                border_width=1,
                border_color=BORDER_CARD,
                hover_color=("#E5E7EB", "#222530"),
                command=lambda m=mode_key: self._on_theme_select(m)
            )
            btn.pack(side="left", padx=(0 if idx == 0 else 12, 0))
            self.theme_buttons[mode_key] = btn

        current_mode = ctk.get_appearance_mode().lower()
        if current_mode not in ["light", "dark"]:
            current_mode = "system"
        self._highlight_selected_theme(current_mode)

        # ---------------------------------------------------------------------
        # 2. Jazyk aplikace / Language
        # ---------------------------------------------------------------------
        lang_card = ctk.CTkFrame(self.page_settings, corner_radius=12, fg_color=BG_CARD, border_width=1, border_color=BORDER_CARD)
        lang_card.pack(fill="x", pady=(0, 12))

        self.lbl_lang_title = ctk.CTkLabel(
            lang_card,
            text=self.tr("card_lang_title"),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_lang_title.pack(anchor="w", padx=16, pady=(14, 2))

        self.lbl_lang_sub = ctk.CTkLabel(
            lang_card,
            text=self.tr("card_lang_sub"),
            font=ctk.CTkFont(size=12),
            text_color=TEXT_BODY
        )
        self.lbl_lang_sub.pack(anchor="w", padx=16, pady=(0, 10))

        lang_box = ctk.CTkFrame(lang_card, fg_color=BG_CARD_INNER, corner_radius=10, border_width=0)
        lang_box.pack(fill="x", padx=16, pady=(0, 16))

        l_inner = ctk.CTkFrame(lang_box, fg_color="transparent")
        l_inner.pack(fill="x", padx=14, pady=12)

        self.lbl_lang_select = ctk.CTkLabel(
            l_inner,
            text=self.tr("lbl_select_language"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_lang_select.pack(side="left")

        self.lang_menu = ModernOptionMenu(
            l_inner,
            values=["English", "Čeština"],
            command=self._on_language_select,
            width=180,
            height=38
        )
        self.lang_menu.pack(side="right")
        self.lang_menu.set("English" if self.current_language == "en" else "Čeština")

        # ---------------------------------------------------------------------
        # 3. Výchozí export a chování složek
        # ---------------------------------------------------------------------
        export_card = ctk.CTkFrame(self.page_settings, corner_radius=12, fg_color=BG_CARD, border_width=1, border_color=BORDER_CARD)
        export_card.pack(fill="x", pady=(0, 12))

        self.lbl_export_title = ctk.CTkLabel(
            export_card,
            text=self.tr("card_export_title"),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_export_title.pack(anchor="w", padx=16, pady=(14, 2))

        self.lbl_export_sub = ctk.CTkLabel(
            export_card,
            text=self.tr("card_export_sub"),
            font=ctk.CTkFont(size=12),
            text_color=TEXT_BODY
        )
        self.lbl_export_sub.pack(anchor="w", padx=16, pady=(0, 10))

        # Folder location row
        folder_box = ctk.CTkFrame(export_card, fg_color=BG_CARD_INNER, corner_radius=10, border_width=0)
        folder_box.pack(fill="x", padx=16, pady=(0, 10))

        f_inner = ctk.CTkFrame(folder_box, fg_color="transparent")
        f_inner.pack(fill="x", padx=12, pady=10)

        self.lbl_def_folder_title = ctk.CTkLabel(
            f_inner,
            text=self.tr("lbl_default_folder"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_def_folder_title.pack(anchor="w")

        curr_def_text = self.default_export_dir if (self.default_export_dir and Path(self.default_export_dir).is_dir()) else self.tr("lbl_folder_beside")
        curr_def_color = TEXT_TITLE if (self.default_export_dir and Path(self.default_export_dir).is_dir()) else TEXT_MUTED

        self.lbl_def_folder_path = ctk.CTkLabel(
            f_inner,
            text=curr_def_text,
            font=ctk.CTkFont(size=12),
            text_color=curr_def_color,
            anchor="w"
        )
        self.lbl_def_folder_path.pack(fill="x", pady=(2, 8))

        f_btn_row = ctk.CTkFrame(f_inner, fg_color="transparent")
        f_btn_row.pack(fill="x")

        self.btn_change_default_export = ctk.CTkButton(
            f_btn_row,
            text=self.tr("btn_set_export_folder"),
            image=self.icon_folder,
            compound="left",
            command=self._on_change_default_export,
            width=160,
            height=30,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=ORANGE_PRIMARY,
            hover_color=ORANGE_HOVER,
            text_color="#FFFFFF"
        )
        self.btn_change_default_export.pack(side="left", padx=(0, 8))

        self.btn_reset_default_export = ctk.CTkButton(
            f_btn_row,
            text=self.tr("btn_reset_export_folder"),
            command=self._on_reset_default_export,
            width=110,
            height=30,
            font=ctk.CTkFont(size=11),
            fg_color=("#E5E7EB", "#20222B"),
            hover_color=("#D1D5DB", "#2B2E3B"),
            text_color=TEXT_TITLE
        )
        self.btn_reset_default_export.pack(side="left")

        # Auto open checkbox
        self.auto_open_folder_var = ctk.BooleanVar(value=self.auto_open_folder)
        self.chk_auto_open_folder = ModernCheckBox(
            export_card,
            text=self.tr("chk_auto_open_folder"),
            variable=self.auto_open_folder_var,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_TITLE,
            command=self._on_toggle_auto_open
        )
        self.chk_auto_open_folder.pack(anchor="w", padx=16, pady=(0, 16))

        # ---------------------------------------------------------------------
        # 4. Údržba a dočasná data (Cache)
        # ---------------------------------------------------------------------
        cache_card = ctk.CTkFrame(self.page_settings, corner_radius=12, fg_color=BG_CARD, border_width=1, border_color=BORDER_CARD)
        cache_card.pack(fill="x", pady=(0, 12))

        self.lbl_cache_title = ctk.CTkLabel(
            cache_card,
            text=self.tr("card_cache_title"),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_cache_title.pack(anchor="w", padx=16, pady=(14, 2))

        self.lbl_cache_sub = ctk.CTkLabel(
            cache_card,
            text=self.tr("card_cache_sub"),
            font=ctk.CTkFont(size=12),
            text_color=TEXT_BODY
        )
        self.lbl_cache_sub.pack(anchor="w", padx=16, pady=(0, 12))

        cache_box = ctk.CTkFrame(cache_card, fg_color=BG_CARD_INNER, corner_radius=10, border_width=0)
        cache_box.pack(fill="x", padx=16, pady=(0, 16))

        c_inner = ctk.CTkFrame(cache_box, fg_color="transparent")
        c_inner.pack(fill="x", padx=14, pady=12)

        c_info = ctk.CTkFrame(c_inner, fg_color="transparent")
        c_info.pack(side="left", fill="x", expand=True)

        self.lbl_cache_heading = ctk.CTkLabel(
            c_info,
            text=self.tr("lbl_cache_heading"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_cache_heading.pack(anchor="w")

        self.lbl_cache_status = ctk.CTkLabel(
            c_info,
            text=self.tr("cache_clean"),
            font=ctk.CTkFont(size=11),
            text_color="#22C55E"
        )
        self.lbl_cache_status.pack(anchor="w", pady=(2, 0))

        self.btn_clean_cache = ctk.CTkButton(
            c_inner,
            text=self.tr("btn_clear_cache"),
            image=self.icon_trash,
            compound="left",
            command=self._on_clear_cache_click,
            width=185,
            height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#FEE2E2", "#2B1616"),
            hover_color=("#FECACA", "#3E1E1E"),
            text_color=("#DC2626", "#FF6B6B"),
            border_width=1,
            border_color=("#FCA5A5", "#5E2222"),
            corner_radius=8
        )
        self.btn_clean_cache.pack(side="right")

        # ---------------------------------------------------------------------
        # 6. Kontrola stažených součástí
        # ---------------------------------------------------------------------
        comp_card = ctk.CTkFrame(self.page_settings, corner_radius=12, fg_color=BG_CARD, border_width=1, border_color=BORDER_CARD)
        comp_card.pack(fill="x", pady=(0, 12))

        comp_hdr = ctk.CTkFrame(comp_card, fg_color="transparent")
        comp_hdr.pack(fill="x", padx=16, pady=(14, 8))

        self.lbl_comp_title = ctk.CTkLabel(
            comp_hdr,
            text=self.tr("card_comp_title"),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_comp_title.pack(side="left")

        self.btn_recheck = ctk.CTkButton(
            comp_hdr,
            text=self.tr("btn_recheck"),
            image=self.icon_reload,
            compound="left",
            width=120,
            height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#E5E7EB", "#20222B"),
            hover_color=("#D1D5DB", "#2B2E3B"),
            text_color=TEXT_TITLE,
            border_width=1,
            border_color=BORDER_CARD,
            corner_radius=8,
            command=self._refresh_settings_components
        )
        self.btn_recheck.pack(side="right")

        self.comp_rows_frame = ctk.CTkFrame(comp_card, fg_color="transparent")
        self.comp_rows_frame.pack(fill="x", padx=16, pady=(0, 14))

        # ---------------------------------------------------------------------
        # 7. Verze aplikace a aktualizace
        # ---------------------------------------------------------------------
        ver_card = ctk.CTkFrame(self.page_settings, corner_radius=12, fg_color=BG_CARD, border_width=1, border_color=BORDER_CARD)
        ver_card.pack(fill="x", pady=(0, 12))

        ver_hdr = ctk.CTkFrame(ver_card, fg_color="transparent")
        ver_hdr.pack(fill="x", padx=16, pady=(14, 8))

        self.lbl_ver_title = ctk.CTkLabel(
            ver_hdr,
            text=self.tr("card_ver_title"),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_ver_title.pack(side="left")

        ver_btns = ctk.CTkFrame(ver_hdr, fg_color="transparent")
        ver_btns.pack(side="right")

        self.btn_update = ctk.CTkButton(
            ver_btns,
            text=self.tr("btn_check_updates"),
            width=165,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=ORANGE_PRIMARY,
            hover_color=ORANGE_HOVER,
            text_color="#FFFFFF",
            corner_radius=8,
            command=self._check_for_updates
        )
        self.btn_update.pack(side="left", padx=(0, 8))

        self.btn_install_update = ctk.CTkButton(
            ver_btns,
            text=self.tr("btn_install_update"),
            width=165,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=BG_CARD_INNER,
            hover_color=("#E5E7EB", "#252834"),
            text_color=ORANGE_PRIMARY,
            border_width=1,
            border_color=BORDER_CARD,
            corner_radius=8,
            command=self._perform_auto_update
        )
        self.btn_install_update.pack(side="left")

        ver_body = ctk.CTkFrame(ver_card, fg_color="transparent")
        ver_body.pack(fill="x", padx=16, pady=(0, 16))

        self.lbl_installed_ver = ctk.CTkLabel(
            ver_body,
            text=self.tr("installed_ver"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_installed_ver.pack(anchor="w")

        self.lbl_update_status = ctk.CTkLabel(
            ver_body,
            text=self.tr("update_status_latest"),
            font=ctk.CTkFont(size=11),
            text_color="#22C55E"
        )
        self.lbl_update_status.pack(anchor="w", pady=(4, 0))

        # Initial quiet renders
        self._refresh_cache_display()
        self._render_components_static()

    def _on_language_select(self, choice: str):
        """Switches active studio language, updates config, and refreshes UI."""
        if "English" in choice:
            self.current_language = "en"
        else:
            self.current_language = "cs"
        self.config["language"] = self.current_language
        save_app_config(self.config)
        self._apply_translations()

    def _on_change_default_export(self):
        """Allows user to select a default export directory for all projects."""
        initial = self.default_export_dir if (self.default_export_dir and Path(self.default_export_dir).is_dir()) else None
        folder = safe_ask_directory(parent=self, title=self.tr("card_export_title"), initialdir=initial)
        if folder:
            self.default_export_dir = folder
            self.config["default_export_dir"] = folder
            save_app_config(self.config)
            self.lbl_def_folder_path.configure(text=folder, text_color=TEXT_TITLE)
            if not self.current_video_path or not self.output_directory:
                self.output_directory = Path(folder)
                if hasattr(self, "lbl_output_dir"):
                    self.lbl_output_dir.configure(
                        text=f"{self.tr('out_dir_custom')}{folder}",
                        text_color=TEXT_TITLE
                    )

    def _on_reset_default_export(self):
        """Resets default export directory to save beside the original video."""
        self.default_export_dir = ""
        self.config["default_export_dir"] = ""
        save_app_config(self.config)
        self.lbl_def_folder_path.configure(
            text=self.tr("lbl_folder_beside"),
            text_color=TEXT_MUTED
        )
        if not self.current_video_path:
            self.output_directory = None
            if hasattr(self, "lbl_output_dir"):
                self.lbl_output_dir.configure(
                    text=self.tr("out_dir_default"),
                    text_color=TEXT_BODY
                )

    def _on_toggle_auto_open(self):
        """Toggles automatic destination folder opening upon export completion."""
        self.auto_open_folder = bool(self.auto_open_folder_var.get())
        self.config["auto_open_folder"] = self.auto_open_folder
        save_app_config(self.config)

    def _refresh_cache_display(self):
        """Updates temporary cache size indicator."""
        if not hasattr(self, "lbl_cache_status") or not self.lbl_cache_status.winfo_exists():
            return
        total_bytes, paths = get_app_cache_info()
        if total_bytes > 0:
            mb = total_bytes / (1024 * 1024)
            self.lbl_cache_status.configure(
                text=self.tr("cache_found", size_mb=f"{mb:.1f}"),
                text_color=ORANGE_ACCENT_TEXT
            )
        else:
            self.lbl_cache_status.configure(
                text=self.tr("cache_clean"),
                text_color="#22C55E"
            )

    def _on_clear_cache_click(self):
        """Cleans temporary files and reports freed space."""
        freed, cnt = clear_app_cache()
        freed_mb = freed / (1024 * 1024)
        if freed_mb < 0.1 and freed > 0:
            freed_str = f"{freed / 1024:.1f} KB"
        else:
            freed_str = f"{freed_mb:.1f} MB"
        self.lbl_cache_status.configure(
            text=self.tr("cache_cleared_msg", freed_mb=freed_str),
            text_color="#22C55E"
        )

    def _apply_translations(self):
        """Refreshes all texts across navigation, headers, and cards to match self.current_language."""
        # 1. Window & Sidebar
        self.title(self.tr("app_title"))
        if hasattr(self, "lbl_sidebar_modules"):
            self.lbl_sidebar_modules.configure(text=self.tr("nav_modules"))
        if hasattr(self, "btn_nav_snapcut"):
            self.btn_nav_snapcut.configure(text=self.tr("nav_snapcut"))
        if hasattr(self, "btn_nav_pecicut") and self.btn_nav_pecicut != getattr(self, "btn_nav_snapcut", None):
            self.btn_nav_pecicut.configure(text=self.tr("nav_snapcut"))
        if hasattr(self, "lbl_sidebar_system"):
            self.lbl_sidebar_system.configure(text=self.tr("nav_system"))
        if hasattr(self, "btn_nav_settings"):
            self.btn_nav_settings.configure(text=self.tr("nav_settings"))
        if hasattr(self, "btn_open_history"):
            self.btn_open_history.configure(text=self.tr("nav_history"))
        if hasattr(self, "lbl_footer"):
            self.lbl_footer.configure(text=self.tr("footer_text"))

        # 2. Header
        if self.current_view in ("snapcut", "pecicut"):
            self.lbl_header_title.configure(text=self.tr("header_snapcut_title"))
            self.lbl_header_subtitle.configure(text=self.tr("header_snapcut_subtitle"))
        else:
            self.lbl_header_title.configure(text=self.tr("header_settings_title"))
            self.lbl_header_subtitle.configure(text=self.tr("header_settings_subtitle"))

        # 3. Settings View
        if hasattr(self, "lbl_theme_title"):
            self.lbl_theme_title.configure(text=self.tr("card_theme_title"))
            self.lbl_theme_sub.configure(text=self.tr("card_theme_sub"))
            current_t = self.config.get("theme", ctk.get_appearance_mode().lower())
            if current_t not in ["light", "dark"]:
                current_t = "system"
            self._highlight_selected_theme(current_t)

        if hasattr(self, "lbl_lang_title"):
            self.lbl_lang_title.configure(text=self.tr("card_lang_title"))
            self.lbl_lang_sub.configure(text=self.tr("card_lang_sub"))
            if hasattr(self, "lbl_lang_select"):
                self.lbl_lang_select.configure(text=self.tr("lbl_select_language"))
            if hasattr(self, "lang_menu"):
                self.lang_menu.set("English" if self.current_language == "en" else "Čeština")

        if hasattr(self, "lbl_export_title"):
            self.lbl_export_title.configure(text=self.tr("card_export_title"))
            self.lbl_export_sub.configure(text=self.tr("card_export_sub"))
            self.lbl_def_folder_title.configure(text=self.tr("lbl_default_folder"))
            if not self.default_export_dir or not Path(self.default_export_dir).is_dir():
                self.lbl_def_folder_path.configure(text=self.tr("lbl_folder_beside"))
            self.btn_change_default_export.configure(text=self.tr("btn_set_export_folder"))
            self.btn_reset_default_export.configure(text=self.tr("btn_reset_export_folder"))
            self.chk_auto_open_folder.configure(text=self.tr("chk_auto_open_folder"))

        if hasattr(self, "lbl_cache_title"):
            self.lbl_cache_title.configure(text=self.tr("card_cache_title"))
            self.lbl_cache_sub.configure(text=self.tr("card_cache_sub"))
            self.lbl_cache_heading.configure(text=self.tr("lbl_cache_heading"))
            self.btn_clean_cache.configure(text=self.tr("btn_clear_cache"))
            self._refresh_cache_display()

        if hasattr(self, "lbl_comp_title"):
            self.lbl_comp_title.configure(text=self.tr("card_comp_title"))
            self.btn_recheck.configure(text=self.tr("btn_recheck"))
            self._render_components_static()

        if hasattr(self, "lbl_ver_title"):
            self.lbl_ver_title.configure(text=self.tr("card_ver_title"))
            self.btn_update.configure(text=self.tr("btn_check_updates"))
            if hasattr(self, "btn_install_update"):
                self.btn_install_update.configure(text=self.tr("btn_install_update"))
            self.lbl_installed_ver.configure(text=self.tr("installed_ver"))

        # 4. PeciCut View
        if hasattr(self, "lbl_sec_file"):
            self.lbl_sec_file.configure(text=self.tr("sec_file_title"))
        if hasattr(self, "btn_select_file"):
            btn_txt = self.tr("btn_change_file") if self.current_video_path else self.tr("btn_select_file")
            self.btn_select_file.configure(text=btn_txt)
        if hasattr(self, "lbl_file_path") and not self.current_video_path:
            self.lbl_file_path.configure(text=self.tr("no_file_selected"))
        if hasattr(self, "lbl_dnd_hint"):
            if not self.current_video_path:
                self.lbl_dnd_hint.configure(text=self.tr("dnd_drop_hint"), text_color=TEXT_MUTED)
            else:
                self._update_drop_zone_labels()
        if hasattr(self, "lbl_meta_info") and not self.video_metadata:
            self.lbl_meta_info.configure(text=self.tr("meta_info_placeholder"))

        if hasattr(self, "lbl_sec_audio"):
            self.lbl_sec_audio.configure(text=self.tr("sec_audio_title"))
            self.lbl_sec_audio_sub.configure(text=self.tr("sec_audio_sub"))

        if hasattr(self, "lbl_sec_params"):
            self.lbl_sec_params.configure(text=self.tr("sec_params_title"))
        if hasattr(self, "lbl_dur_heading"):
            self.lbl_dur_heading.configure(text=self.tr("lbl_target_dur_title"))
        if hasattr(self, "lbl_thresh_heading"):
            self.lbl_thresh_heading.configure(text=self.tr("lbl_threshold"))
        if hasattr(self, "lbl_pad_before_heading"):
            self.lbl_pad_before_heading.configure(text=self.tr("lbl_pad_before"))
        if hasattr(self, "lbl_pad_after_heading"):
            self.lbl_pad_after_heading.configure(text=self.tr("lbl_pad_after"))
        if hasattr(self, "lbl_gap_heading"):
            self.lbl_gap_heading.configure(text=self.tr("lbl_gap"))
        if hasattr(self, "chk_facecam_ai"):
            self.chk_facecam_ai.configure(text=self.tr("chk_facecam"))
            self.sub_facecam.configure(text=self.tr("sub_facecam"))

        if hasattr(self, "lbl_sec_export"):
            self.lbl_sec_export.configure(text=self.tr("sec_export_title"))
            self.btn_change_out.configure(text=self.tr("btn_change_out"))
            if hasattr(self, "btn_reveal_out"):
                self.btn_reveal_out.configure(text=self.tr("btn_reveal_out"))
            if not self.output_directory or (self.current_video_path and self.output_directory == self.current_video_path.parent):
                self.lbl_output_dir.configure(text=self.tr("out_dir_default"))
            if hasattr(self, "chk_review_segments"):
                self.chk_review_segments.configure(text=self.tr("chk_review_segments"))
            if hasattr(self, "sub_review_segments"):
                self.sub_review_segments.configure(text=self.tr("sub_review_segments"))

        if hasattr(self, "btn_process"):
            self.btn_process.configure(text=self.tr("btn_process"))
            self.btn_cancel.configure(text=self.tr("btn_cancel"))
            self.btn_open_folder.configure(text=self.tr("btn_open_folder"))
            self.lbl_result_check.configure(text=self.tr("lbl_done"))
            if not self.is_processing and not self.current_video_path:
                self.lbl_status.configure(text=self.tr("status_ready"))

    def _render_components_static(self):
        """Renders component rows statically in their current state without running animation/spinner."""
        if not hasattr(self, "comp_rows_frame") or not self.comp_rows_frame.winfo_exists():
            return

        for child in self.comp_rows_frame.winfo_children():
            child.destroy()

        # --- Row 0: FFmpeg & FFprobe ---
        ffmpeg_path, ffprobe_path = get_ffmpeg_paths()
        ffmpeg_ok = bool(ffmpeg_path and ffprobe_path)
        row0 = ctk.CTkFrame(self.comp_rows_frame, fg_color=BG_CARD_INNER, corner_radius=8, border_width=0)
        row0.pack(fill="x", pady=4)
        info0 = ctk.CTkFrame(row0, fg_color="transparent")
        info0.pack(side="left", fill="x", expand=True, padx=12, pady=8)
        if ffmpeg_ok:
            ctk.CTkLabel(info0, text=self.tr("comp_ffmpeg_ok"), font=ctk.CTkFont(size=12, weight="bold"), text_color="#22C55E").pack(anchor="w")
            ctk.CTkLabel(info0, text=self.tr("comp_ffmpeg_desc_ok", name=ffmpeg_path.name if ffmpeg_path else ''), font=ctk.CTkFont(size=11), text_color=TEXT_BODY).pack(anchor="w")
        elif getattr(self, "_is_downloading_comp_ffmpeg", False):
            ctk.CTkLabel(info0, text=f"  {self.tr('comp_ffmpeg_downloading')}", image=self.icon_hourglass, compound="left", font=ctk.CTkFont(size=12, weight="bold"), text_color=ORANGE_PRIMARY).pack(anchor="w")
            self._comp_ffmpeg_sub_lbl = ctk.CTkLabel(info0, text=getattr(self, "_comp_ffmpeg_last_msg", "Připojuji k serveru..."), font=ctk.CTkFont(size=11), text_color=TEXT_BODY)
            self._comp_ffmpeg_sub_lbl.pack(anchor="w")
            act_box0 = ctk.CTkFrame(row0, fg_color="transparent")
            act_box0.pack(side="right", padx=12)
            self._comp_ffmpeg_pbar = ctk.CTkProgressBar(act_box0, width=130, height=8, fg_color=TRACK_COLOR, progress_color=ORANGE_PRIMARY)
            self._comp_ffmpeg_pbar.pack(side="left", padx=(0, 8))
            self._comp_ffmpeg_pbar.set(getattr(self, "_comp_ffmpeg_frac", 0.05))
            self._comp_ffmpeg_pct_lbl = ctk.CTkLabel(act_box0, text=f"{int(getattr(self, '_comp_ffmpeg_frac', 0.05) * 100)} %", font=ctk.CTkFont(size=12, weight="bold"), text_color=ORANGE_PRIMARY, width=42)
            self._comp_ffmpeg_pct_lbl.pack(side="right")
        else:
            ctk.CTkLabel(info0, text=self.tr("comp_ffmpeg_fail"), font=ctk.CTkFont(size=12, weight="bold"), text_color="#EF4444").pack(anchor="w")
            ctk.CTkLabel(info0, text=self.tr("comp_ffmpeg_desc_fail"), font=ctk.CTkFont(size=11), text_color=TEXT_BODY).pack(anchor="w")
            ctk.CTkButton(
                row0, text="" + ("Stáhnout FFmpeg" if self.current_language == "cs" else "Download FFmpeg"),
                width=135, height=26,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=ORANGE_PRIMARY, hover_color=ORANGE_HOVER,
                text_color="#FFFFFF", corner_radius=8, command=self._settings_download_ffmpeg_action
            ).pack(side="right", padx=12)

        # --- Row 1: Facecam AI modely ---
        mdir = get_base_dir() / "models"
        yn = (mdir / "face_detection_yunet_2023mar.onnx").is_file()
        sm = (mdir / "haarcascade_smile.xml").is_file()
        fc = (mdir / "haarcascade_frontalface_default.xml").is_file()
        cnt = sum([yn, sm, fc])
        models_ok = (cnt == 3)
        row1 = ctk.CTkFrame(self.comp_rows_frame, fg_color=BG_CARD_INNER, corner_radius=8, border_width=0)
        row1.pack(fill="x", pady=4)
        info1 = ctk.CTkFrame(row1, fg_color="transparent")
        info1.pack(side="left", fill="x", expand=True, padx=12, pady=8)
        if models_ok:
            ctk.CTkLabel(info1, text=self.tr("comp_models_ok"), font=ctk.CTkFont(size=12, weight="bold"), text_color="#22C55E").pack(anchor="w")
            ctk.CTkLabel(info1, text=self.tr("comp_models_desc_ok"), font=ctk.CTkFont(size=11), text_color=TEXT_BODY).pack(anchor="w")
        elif getattr(self, "_is_downloading_comp_models", False):
            ctk.CTkLabel(info1, text=f"  {self.tr('comp_models_downloading')}", image=self.icon_hourglass, compound="left", font=ctk.CTkFont(size=12, weight="bold"), text_color=ORANGE_PRIMARY).pack(anchor="w")
            self._comp_models_sub_lbl = ctk.CTkLabel(info1, text=getattr(self, "_comp_models_last_msg", "Připojuji k serveru..."), font=ctk.CTkFont(size=11), text_color=TEXT_BODY)
            self._comp_models_sub_lbl.pack(anchor="w")
            act_box1 = ctk.CTkFrame(row1, fg_color="transparent")
            act_box1.pack(side="right", padx=12)
            self._comp_models_pbar = ctk.CTkProgressBar(act_box1, width=130, height=8, fg_color=TRACK_COLOR, progress_color=ORANGE_PRIMARY)
            self._comp_models_pbar.pack(side="left", padx=(0, 8))
            self._comp_models_pbar.set(getattr(self, "_comp_models_frac", 0.0))
            self._comp_models_pct_lbl = ctk.CTkLabel(act_box1, text=f"{int(getattr(self, '_comp_models_frac', 0.0) * 100)} %", font=ctk.CTkFont(size=12, weight="bold"), text_color=ORANGE_PRIMARY, width=42)
            self._comp_models_pct_lbl.pack(side="right")
        else:
            ctk.CTkLabel(info1, text=self.tr("comp_models_fail", cnt=cnt), font=ctk.CTkFont(size=12, weight="bold"), text_color="#EF4444").pack(anchor="w")
            ctk.CTkLabel(info1, text=self.tr("comp_models_desc_fail"), font=ctk.CTkFont(size=11), text_color=TEXT_BODY).pack(anchor="w")
            ctk.CTkButton(
                row1, text="" + ("Stáhnout modely" if self.current_language == "cs" else "Download models"),
                width=135, height=26,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=ORANGE_PRIMARY, hover_color=ORANGE_HOVER,
                text_color="#FFFFFF", corner_radius=8, command=self._settings_download_models_action
            ).pack(side="right", padx=12)

        # --- Row 2: Pracovní adresáře ---
        row2 = ctk.CTkFrame(self.comp_rows_frame, fg_color=BG_CARD_INNER, corner_radius=8, border_width=0)
        row2.pack(fill="x", pady=4)
        info2 = ctk.CTkFrame(row2, fg_color="transparent")
        info2.pack(side="left", fill="x", expand=True, padx=12, pady=8)
        ctk.CTkLabel(info2, text=self.tr("comp_dirs_ok"), font=ctk.CTkFont(size=12, weight="bold"), text_color="#22C55E").pack(anchor="w")
        ctk.CTkLabel(info2, text=self.tr("comp_dirs_desc"), font=ctk.CTkFont(size=11), text_color=TEXT_BODY).pack(anchor="w")

    def _setup_nav_hover_events(self):
        """Binds responsive hover highlighting across navigation rows."""
        def bind_row(row, btn, vname):
            def on_enter(_):
                if getattr(self, "current_view", None) != vname:
                    row.configure(fg_color=("#F3F4F6", "#202330"))
                    btn.configure(text_color=TEXT_TITLE)
            def on_leave(_):
                if getattr(self, "current_view", None) != vname:
                    row.configure(fg_color="transparent")
                    btn.configure(text_color=TEXT_MUTED)
            def on_click(_):
                self._switch_view(vname)

            for w in (row, btn):
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                w.bind("<Button-1>", on_click)

        bind_row(self.nav_row_snapcut, self.btn_nav_snapcut, "snapcut")
        bind_row(self.nav_row_settings, self.btn_nav_settings, "settings")

    def _switch_view(self, view_name: str):
        """Switches the active view in Pecislav Studio between SnapCut and Nastavení."""
        if view_name == "pecicut":
            view_name = "snapcut"
        self.current_view = view_name
        if view_name == "snapcut":
            self.page_settings.pack_forget()
            self.page_snapcut.pack(fill="both", expand=True, padx=20, pady=12)
            if hasattr(self, "nav_row_snapcut"):
                self.nav_row_snapcut.configure(fg_color=("#FFEDE5", "#2C1E18"))
                self.btn_nav_snapcut.configure(text_color=ORANGE_PRIMARY)

                self.nav_row_settings.configure(fg_color="transparent")
                self.btn_nav_settings.configure(text_color=TEXT_MUTED)

            self.lbl_header_title.configure(text=self.tr("header_snapcut_title"))
            self.lbl_header_subtitle.configure(text=self.tr("header_snapcut_subtitle"))
        elif view_name == "settings":
            self.page_snapcut.pack_forget()
            self.page_settings.pack(fill="both", expand=True, padx=20, pady=12)
            if hasattr(self, "nav_row_settings"):
                self.nav_row_settings.configure(fg_color=("#FFEDE5", "#2C1E18"))
                self.btn_nav_settings.configure(text_color=ORANGE_PRIMARY)

                self.nav_row_snapcut.configure(fg_color="transparent")
                self.btn_nav_snapcut.configure(text_color=TEXT_MUTED)

            self.lbl_header_title.configure(text=self.tr("header_settings_title"))
            self.lbl_header_subtitle.configure(text=self.tr("header_settings_subtitle"))
            self._refresh_cache_display()

    def _on_theme_select(self, mode_key: str):
        if mode_key == "light":
            ctk.set_appearance_mode("Light")
        elif mode_key == "dark":
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("System")
        self.config["theme"] = mode_key
        save_app_config(self.config)
        self._highlight_selected_theme(mode_key)
        self.after(50, self._apply_windows_titlebar_theme)

    def _highlight_selected_theme(self, active_mode: str):
        label_map = {
            "system": self.tr("theme_system"),
            "light": self.tr("theme_light"),
            "dark": self.tr("theme_dark")
        }
        for mode_key, btn in getattr(self, "theme_buttons", {}).items():
            base_label = label_map.get(mode_key, mode_key.capitalize())
            if mode_key == active_mode:
                btn.configure(
                    text=f"✓  {base_label}",
                    border_width=2,
                    border_color=ORANGE_PRIMARY,
                    fg_color=("#F3F4F6", "#1B1C24"),
                    text_color=ORANGE_PRIMARY
                )
            else:
                btn.configure(
                    text=f"○  {base_label}",
                    border_width=1,
                    border_color=BORDER_CARD,
                    fg_color=BG_CARD_INNER,
                    text_color=TEXT_MUTED
                )

    def _on_theme_change(self, choice: str):
        mode_map = {"Systémová": "system", "Bílá": "light", "Černá": "dark"}
        self._on_theme_select(mode_map.get(choice, "system"))

    def _refresh_settings_components(self):
        """Animated component check with spinner per row, then green/red results."""
        if not hasattr(self, "comp_rows_frame") or not self.comp_rows_frame.winfo_exists():
            return

        if getattr(self, "_is_downloading_comp_ffmpeg", False) or getattr(self, "_is_downloading_comp_models", False):
            self._render_components_static()
            return

        self._check_gen = getattr(self, "_check_gen", 0) + 1
        my_gen = self._check_gen

        # Clear existing rows
        for child in self.comp_rows_frame.winfo_children():
            child.destroy()

        loading_bg = ("#E5E7EB", "#1C1E27")
        comps = [
            "FFmpeg & FFprobe",
            "Facecam AI modely" if self.current_language == "cs" else "Facecam AI models",
            "Pracovní adresáře aplikace" if self.current_language == "cs" else "App working directories",
        ]
        row_refs = []
        for name in comps:
            row = ctk.CTkFrame(
                self.comp_rows_frame,
                fg_color=loading_bg, corner_radius=8,
                border_width=0
            )
            row.pack(fill="x", pady=4)
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=12, pady=8)
            t_lbl = ctk.CTkLabel(
                info,
                text=f"⣾  {name}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=TEXT_MUTED
            )
            t_lbl.pack(anchor="w")
            s_lbl = ctk.CTkLabel(
                info,
                text="Kontroluji..." if self.current_language == "cs" else "Checking...",
                font=ctk.CTkFont(size=11),
                text_color=TEXT_MUTED
            )
            s_lbl.pack(anchor="w")
            row_refs.append((row, t_lbl, s_lbl))

        spin_idx = [0]

        def tick():
            if not self.winfo_exists() or self._check_gen != my_gen:
                return
            spin_idx[0] = (spin_idx[0] + 1) % len(self._SPINNER)
            f = self._SPINNER[spin_idx[0]]
            for i, (_, t_lbl, _) in enumerate(row_refs):
                try:
                    cur = t_lbl.cget("text")
                    if any(sf in cur for sf in self._SPINNER):
                        t_lbl.configure(text=f"  {comps[i]}".replace("  ", f"{f}  "))
                except Exception:
                    pass
            self.after(80, tick)

        self.after(80, tick)

        results = {}

        def worker():
            import time
            ffp, ffpp = get_ffmpeg_paths()
            results["ffmpeg"] = (bool(ffp and ffpp), ffp, ffpp)
            time.sleep(0.25)

            mdir = get_base_dir() / "models"
            yn = (mdir / "face_detection_yunet_2023mar.onnx").is_file()
            sm = (mdir / "haarcascade_smile.xml").is_file()
            fc = (mdir / "haarcascade_frontalface_default.xml").is_file()
            cnt = sum([yn, sm, fc])
            results["models"] = (cnt == 3, cnt)
            time.sleep(0.15)

            results["dirs"] = True
            results["done"] = True

        threading.Thread(target=worker, daemon=True).start()

        def finalize():
            if not self.winfo_exists() or self._check_gen != my_gen:
                return
            if "done" not in results:
                self.after(80, finalize)
                return

            if getattr(self, "_is_downloading_comp_ffmpeg", False) or getattr(self, "_is_downloading_comp_models", False):
                self._render_components_static()
                return

            # --- Row 0: FFmpeg & FFprobe ---
            ffmpeg_ok, fp, fpp = results["ffmpeg"]
            row, t_lbl, s_lbl = row_refs[0]
            row.configure(fg_color=BG_CARD_INNER)
            if ffmpeg_ok:
                t_lbl.configure(text=self.tr("comp_ffmpeg_ok"), text_color="#22C55E")
                s_lbl.configure(text=self.tr("comp_ffmpeg_desc_ok", name=fp.name if fp else ''), text_color=TEXT_BODY)
            else:
                t_lbl.configure(text=self.tr("comp_ffmpeg_fail"), text_color="#EF4444")
                s_lbl.configure(text=self.tr("comp_ffmpeg_desc_fail"), text_color=TEXT_BODY)
                ctk.CTkButton(
                    row, text="" + ("Stáhnout FFmpeg" if self.current_language == "cs" else "Download FFmpeg"),
                    width=135, height=26,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    fg_color=ORANGE_PRIMARY, hover_color=ORANGE_HOVER,
                    text_color="#FFFFFF", command=self._settings_download_ffmpeg_action
                ).pack(side="right", padx=12)

            # --- Row 1: Facecam AI modely ---
            models_ok, models_cnt = results["models"]
            row, t_lbl, s_lbl = row_refs[1]
            row.configure(fg_color=BG_CARD_INNER)
            if models_ok:
                t_lbl.configure(text=self.tr("comp_models_ok"), text_color="#22C55E")
                s_lbl.configure(text=self.tr("comp_models_desc_ok"), text_color=TEXT_BODY)
            else:
                t_lbl.configure(text=self.tr("comp_models_fail", cnt=models_cnt), text_color="#EF4444")
                s_lbl.configure(text=self.tr("comp_models_desc_fail"), text_color=TEXT_BODY)
                ctk.CTkButton(
                    row, text="" + ("Stáhnout modely" if self.current_language == "cs" else "Download models"),
                    width=135, height=26,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    fg_color=ORANGE_PRIMARY, hover_color=ORANGE_HOVER,
                    text_color="#FFFFFF", command=self._settings_download_models_action
                ).pack(side="right", padx=12)

            # --- Row 2: Pracovní adresáře ---
            row, t_lbl, s_lbl = row_refs[2]
            row.configure(fg_color=BG_CARD_INNER)
            t_lbl.configure(text=self.tr("comp_dirs_ok"), text_color="#22C55E")
            s_lbl.configure(text=self.tr("comp_dirs_desc"), text_color=TEXT_BODY)

        self.after(80, finalize)

    def _settings_download_ffmpeg_action(self):
        if getattr(self, "_is_downloading_comp_ffmpeg", False):
            return
        self._is_downloading_comp_ffmpeg = True
        self._comp_ffmpeg_frac = 0.05
        self._comp_ffmpeg_last_msg = "Zahajuji stahování FFmpeg..." if self.current_language == "cs" else "Starting FFmpeg download..."
        self._render_components_static()

        def progress_cb(fraction: float, message: str):
            self.after(0, lambda: self._update_ffmpeg_download_progress(fraction, message))

        def worker():
            success, msg = download_ffmpeg_auto(progress_callback=progress_cb)
            self.after(0, lambda: self._on_comp_ffmpeg_download_finished(success, msg))

        threading.Thread(target=worker, daemon=True).start()

    def _update_ffmpeg_download_progress(self, fraction: float, message: str):
        self._comp_ffmpeg_frac = fraction
        self._comp_ffmpeg_last_msg = message
        clamped = min(max(fraction, 0.0), 1.0)
        pct_text = f"{int(clamped * 100)} %"

        if hasattr(self, "_comp_ffmpeg_pbar") and self._comp_ffmpeg_pbar.winfo_exists():
            self._comp_ffmpeg_pbar.set(clamped)
        if hasattr(self, "_comp_ffmpeg_pct_lbl") and self._comp_ffmpeg_pct_lbl.winfo_exists():
            self._comp_ffmpeg_pct_lbl.configure(text=pct_text)
        if hasattr(self, "_comp_ffmpeg_sub_lbl") and self._comp_ffmpeg_sub_lbl.winfo_exists():
            self._comp_ffmpeg_sub_lbl.configure(text=message)

        # Mirror progress to main view status bar
        if hasattr(self, "progress_bar") and self.progress_bar.winfo_exists():
            self.progress_bar.set(clamped)
        if hasattr(self, "lbl_status") and self.lbl_status.winfo_exists():
            self.lbl_status.configure(text=message)
        if hasattr(self, "lbl_progress_pct") and self.lbl_progress_pct.winfo_exists():
            self.lbl_progress_pct.configure(text=pct_text)

    def _on_comp_ffmpeg_download_finished(self, success: bool, msg: str):
        self._is_downloading_comp_ffmpeg = False
        self._check_ffmpeg_status()
        self._render_components_static()
        if success:
            if hasattr(self, "progress_bar") and self.progress_bar.winfo_exists():
                self.progress_bar.set(1.0)
            if hasattr(self, "lbl_progress_pct") and self.lbl_progress_pct.winfo_exists():
                self.lbl_progress_pct.configure(text="100 %")
            messagebox.showinfo("Hotovo" if self.current_language == "cs" else "Done", msg)
        else:
            messagebox.showerror(
                "Chyba instalace FFmpeg" if self.current_language == "cs" else "FFmpeg Install Error",
                f"{msg}\n\nTip: Nainstalujte FFmpeg ručně (winget install Gyan.FFmpeg na Windows)."
            )

    def _settings_download_models_action(self):
        if getattr(self, "_is_downloading_comp_models", False):
            return
        self._is_downloading_comp_models = True
        self._comp_models_frac = 0.0
        self._comp_models_last_msg = "Zahajuji stahování AI modelů..." if self.current_language == "cs" else "Starting AI models download..."
        self._render_components_static()

        def progress_cb(fraction: float, message: str):
            self.after(0, lambda: self._update_models_download_progress(fraction, message))

        def worker():
            success = ensure_ai_models_present(progress_callback=progress_cb)
            self.after(0, lambda: self._on_comp_models_download_finished(success))

        threading.Thread(target=worker, daemon=True).start()

    def _update_models_download_progress(self, fraction: float, message: str):
        self._comp_models_frac = fraction
        self._comp_models_last_msg = message
        clamped = min(max(fraction, 0.0), 1.0)
        pct_text = f"{int(clamped * 100)} %"

        if hasattr(self, "_comp_models_pbar") and self._comp_models_pbar.winfo_exists():
            self._comp_models_pbar.set(clamped)
        if hasattr(self, "_comp_models_pct_lbl") and self._comp_models_pct_lbl.winfo_exists():
            self._comp_models_pct_lbl.configure(text=pct_text)
        if hasattr(self, "_comp_models_sub_lbl") and self._comp_models_sub_lbl.winfo_exists():
            self._comp_models_sub_lbl.configure(text=message)

        # Mirror progress to main view status bar
        if hasattr(self, "progress_bar") and self.progress_bar.winfo_exists():
            self.progress_bar.set(clamped)
        if hasattr(self, "lbl_status") and self.lbl_status.winfo_exists():
            self.lbl_status.configure(text=message)
        if hasattr(self, "lbl_progress_pct") and self.lbl_progress_pct.winfo_exists():
            self.lbl_progress_pct.configure(text=pct_text)

    def _on_comp_models_download_finished(self, success: bool):
        self._is_downloading_comp_models = False
        self._render_components_static()
        if success:
            if hasattr(self, "progress_bar") and self.progress_bar.winfo_exists():
                self.progress_bar.set(1.0)
            if hasattr(self, "lbl_progress_pct") and self.lbl_progress_pct.winfo_exists():
                self.lbl_progress_pct.configure(text="100 %")
            msg = "Všechny Facecam AI modely byly úspěšně staženy (100 %) a jsou připraveny k použití." if self.current_language == "cs" else "All Facecam AI models were successfully downloaded (100%) and ready to use."
            messagebox.showinfo("Hotovo" if self.current_language == "cs" else "Done", msg)
        else:
            msg = "Stahování některých AI modelů selhalo. Zkontrolujte připojení k internetu." if self.current_language == "cs" else "Failed to download some AI models. Check your internet connection."
            messagebox.showerror("Chyba" if self.current_language == "cs" else "Error", msg)

    def _check_for_updates(self):
        self.btn_update.configure(state="disabled")
        if hasattr(self, "btn_install_update"):
            self.btn_install_update.configure(state="disabled")
        self.lbl_update_status.configure(
            text="Ověřuji dostupnost nejnovější verze...",
            text_color=TEXT_BODY
        )
        result_holder = {}

        def worker():
            import time
            import urllib.request
            import json
            time.sleep(0.3)

            new_version_found = None
            release_data = None
            repos = ["Pecislav/PecislavStudio", "Pecislav/SnapCut", "Pecislav/PeciCut"]
            for repo in repos:
                try:
                    # Query releases list (handles both final releases and prereleases/betas)
                    req = urllib.request.Request(
                        f"https://api.github.com/repos/{repo}/releases",
                        headers={"User-Agent": "PecislavStudio-App"}
                    )
                    with urllib.request.urlopen(req, timeout=4.0) as resp:
                        releases = json.loads(resp.read().decode("utf-8"))
                        if releases and isinstance(releases, list):
                            latest_rel = releases[0]
                            tag = latest_rel.get("tag_name", "").lstrip("v")
                            # If tag is strictly higher or different beta
                            if tag and tag != APP_VERSION.lstrip("v") and tag > APP_VERSION.lstrip("v"):
                                new_version_found = tag
                                release_data = latest_rel
                                break
                            elif tag and not new_version_found:
                                release_data = latest_rel
                except Exception:
                    continue

            self._latest_release_info = release_data
            if new_version_found:
                msg = f"K dispozici je nová verze: Pecislav Studio v{new_version_found}!" if self.current_language == "cs" else f"New version available: Pecislav Studio v{new_version_found}!"
                color = ORANGE_ACCENT_TEXT
                has_update = True
            else:
                msg = f"Používáte verzi Pecislav Studio v{APP_VERSION} (aktuální kód na GitHubu)." if self.current_language == "cs" else f"You are running Pecislav Studio v{APP_VERSION} (latest code on GitHub)."
                color = "#22C55E"
                has_update = False

            result_holder["done"] = (msg, color, has_update)

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        def poll():
            if not self.winfo_exists():
                return
            if "done" in result_holder:
                msg, color, has_update = result_holder["done"]
                self.btn_update.configure(state="normal")
                if hasattr(self, "btn_install_update"):
                    self.btn_install_update.configure(state="normal")
                self.lbl_update_status.configure(text=msg, text_color=color)
            else:
                self.after(100, poll)

        self.after(100, poll)

    def _perform_auto_update(self):
        """Downloads updated code or binary from GitHub and updates the application safely."""
        title = "Aktualizace aplikace" if self.current_language == "cs" else "Application Update"
        msg = ("Opravdu si přejete stáhnout a nainstalovat nejnovější verzi z GitHubu?\n\n"
               "Vaše nastavení (config.json) i historie projektů zůstanou plně zachovány.") if self.current_language == "cs" else (
               "Do you want to download and install the latest update from GitHub?\n\n"
               "Your settings (config.json) and project history will be fully preserved.")
        if not messagebox.askyesno(title, msg, parent=self):
            return

        self.btn_update.configure(state="disabled")
        if hasattr(self, "btn_install_update"):
            self.btn_install_update.configure(state="disabled")

        self.lbl_update_status.configure(
            text="Stahuji aktualizaci z GitHubu...",
            text_color=ORANGE_PRIMARY
        )

        result_holder = {}

        def update_worker():
            import zipfile
            import urllib.request

            # 1. If running as compiled standalone .exe (PyInstaller frozen)
            if getattr(sys, "frozen", False):
                try:
                    exe_path = Path(sys.executable).resolve()
                    exe_dir = exe_path.parent

                    download_url = None
                    rel_info = getattr(self, "_latest_release_info", None)
                    if rel_info and "assets" in rel_info:
                        for asset in rel_info["assets"]:
                            name = asset.get("name", "").lower()
                            if name.endswith(".exe"):
                                download_url = asset.get("browser_download_url")
                                break

                    if not download_url:
                        download_url = "https://github.com/Pecislav/PecislavStudio/releases/download/v1.0.0-beta/PecislavStudio.exe"

                    req = urllib.request.Request(
                        download_url,
                        headers={"User-Agent": "PecislavStudio-Updater"}
                    )

                    new_exe = exe_dir / f"{exe_path.stem}_new.exe"
                    with urllib.request.urlopen(req, timeout=180) as resp, open(new_exe, "wb") as f_out:
                        shutil.copyfileobj(resp, f_out)

                    bat_path = exe_dir / "update_and_restart.bat"
                    bat_content = f"""@echo off
timeout /t 1 /nobreak > nul
move /y "{new_exe.name}" "{exe_path.name}"
start "" "{exe_path.name}"
del "%~f0"
"""
                    bat_path.write_text(bat_content, encoding="utf-8")

                    result_holder["done"] = (True, "Aplikace byla úspěšně aktualizována na novou verzi.")
                    self._restart_bat_script = str(bat_path)
                    return
                except Exception as e:
                    result_holder["done"] = (False, f"Aktualizace .exe selhala: {e}")
                    return

            # 2. If running from source (Python)
            app_dir = Path(__file__).parent.resolve()

            # Try Git pull if in a git repository
            if (app_dir / ".git").is_dir() and shutil.which("git"):
                try:
                    cflags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
                    sinfo = None
                    if sys.platform.startswith("win"):
                        sinfo = subprocess.STARTUPINFO()
                        sinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        sinfo.wShowWindow = 0
                    res = subprocess.run(
                        ["git", "pull", "--ff-only"],
                        cwd=str(app_dir),
                        capture_output=True,
                        text=True,
                        startupinfo=sinfo,
                        creationflags=cflags,
                        timeout=25
                    )
                    if res.returncode == 0:
                        result_holder["done"] = (True, "Aplikace byla úspěšně aktualizována přes Git repository.")
                        return
                except Exception:
                    pass

            # Direct ZIP download from GitHub repository
            try:
                zip_url = "https://github.com/Pecislav/PecislavStudio/archive/refs/heads/main.zip"
                req = urllib.request.Request(
                    zip_url,
                    headers={"User-Agent": "PecislavStudio-Updater"}
                )

                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_path = Path(tmp_dir)
                    zip_file = tmp_path / "update.zip"

                    with urllib.request.urlopen(req, timeout=40) as resp, open(zip_file, "wb") as f_out:
                        shutil.copyfileobj(resp, f_out)

                    with zipfile.ZipFile(zip_file, "r") as zf:
                        zf.extractall(tmp_path)

                    extracted = [d for d in tmp_path.iterdir() if d.is_dir() and d != zip_file]
                    if not extracted:
                        result_holder["done"] = (False, "Chyba při rozbalení archivu aktualizace.")
                        return

                    source_dir = extracted[0]

                    # Safe copy: copy files into app_dir, preserving configs & caches
                    protected = {"config.json", ".git", ".project_cache", "output", "videos", "__pycache__"}

                    for item in source_dir.iterdir():
                        if item.name in protected:
                            continue
                        dest = app_dir / item.name
                        if item.is_dir():
                            shutil.copytree(item, dest, dirs_exist_ok=True)
                        else:
                            shutil.copy2(item, dest)

                result_holder["done"] = (True, "Soubory aplikace byly úspěšně aktualizovány na nejnovější verzi.")
            except Exception as e:
                result_holder["done"] = (False, f"Stažení selhalo: {e}")

        t = threading.Thread(target=update_worker, daemon=True)
        t.start()

        def poll_update():
            if not self.winfo_exists():
                return
            if "done" in result_holder:
                success, note = result_holder["done"]
                self.btn_update.configure(state="normal")
                if hasattr(self, "btn_install_update"):
                    self.btn_install_update.configure(state="normal")

                if success:
                    self.lbl_update_status.configure(
                        text="Aktualizace byla úspěšně nainstalována!",
                        text_color="#22C55E"
                    )
                    t_succ = "Aktualizace dokončena" if self.current_language == "cs" else "Update Completed"
                    m_succ = ("Pecislav Studio bylo úspěšně aktualizováno na nejnovější verzi.\n\n"
                              "Přejete si aplikaci restartovat nyní pro načtení změn?") if self.current_language == "cs" else (
                              "Pecislav Studio was successfully updated to the latest version.\n\n"
                              "Do you want to restart the application now?")
                    if messagebox.askyesno(t_succ, m_succ, parent=self):
                        self._restart_app()
                else:
                    self.lbl_update_status.configure(
                        text=f"Aktualizace selhala ({note})",
                        text_color="#EF4444"
                    )
                    messagebox.showerror(
                        "Chyba aktualizace" if self.current_language == "cs" else "Update Error",
                        f"Nepodařilo se dokončit automatickou aktualizaci:\n{note}"
                    )
            else:
                self.after(200, poll_update)

        self.after(200, poll_update)

    def _restart_app(self):
        """Cleanly restarts the application."""
        bat_script = getattr(self, "_restart_bat_script", None)
        if bat_script and Path(bat_script).is_file():
            try:
                cflags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
                subprocess.Popen(["cmd.exe", "/c", str(bat_script)], cwd=str(Path(bat_script).parent), creationflags=cflags)
                self.destroy()
                sys.exit(0)
            except Exception:
                pass
        try:
            self.destroy()
            python = sys.executable
            os.execl(python, python, *sys.argv)
        except Exception:
            try:
                cflags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
                subprocess.Popen([sys.executable] + sys.argv, creationflags=cflags)
                sys.exit(0)
            except Exception:
                pass

    def _build_file_section(self, parent):
        """1. File picker and metadata display."""
        box = ctk.CTkFrame(parent, corner_radius=12, fg_color=BG_CARD, border_width=1, border_color=BORDER_CARD)
        box.pack(fill="x", pady=8)

        # Header row with step badge, title, ? button, and Project History button
        hdr = ctk.CTkFrame(box, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(14, 6))

        step_badge = self._create_step_badge(hdr, "1")
        step_badge.pack(side="left", padx=(0, 8))

        raw_title = self.tr("sec_file_title")
        t_clean = raw_title.split(". ", 1)[-1] if ". " in raw_title else raw_title
        self.lbl_sec_file = ctk.CTkLabel(
            hdr,
            text=t_clean,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_sec_file.pack(side="left")

        q_btn = self._create_help_btn(
            hdr,
            text=(
                "Vyberte video soubor z vašeho streamu nebo nahrávání (.mp4, .mkv nebo .mov).\n\n"
                "SnapCut podporuje i velmi dlouhé soubory (2 až 6+ hodin). Video se načítá bezztrátově "
                "a analyzuje přímo v paměti bez vytváření obřích souborů na disku."
            ),
            recommendation="Nahrajte MP4 nebo MKV soubor z OBS Studia o délce 2 až 6 hodin."
        )
        q_btn.pack(side="left", padx=(8, 0))

        t_hist = "Historie projektů" if self.current_language == "cs" else "Project History"
        self.btn_open_history = ModernButton(
            hdr,
            text=t_hist,
            command=self._open_history_dialog,
            height=28,
            width=140,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=BG_CARD_INNER,
            hover_color=("#E5E7EB", "#252834"),
            text_color=ORANGE_PRIMARY,
            border_width=1,
            border_color=BORDER_CARD,
            corner_radius=8
        )
        self.btn_open_history.pack(side="right")

        # Interactive Drag & Drop Box (Logi Options+ style)
        self.drop_zone = ctk.CTkFrame(
            box,
            fg_color=BG_CARD_INNER,
            corner_radius=12,
            border_width=0
        )
        self.drop_zone.pack(fill="x", padx=16, pady=(4, 12))

        drop_inner = ctk.CTkFrame(self.drop_zone, fg_color="transparent")
        drop_inner.pack(fill="x", padx=16, pady=12)

        has_video = bool(self.current_video_path)
        btn_txt = self.tr('btn_change_file') if has_video else self.tr('btn_select_file')
        self.btn_select_file = ModernButton(
            drop_inner,
            text=btn_txt,
            image=self.icon_folder_white,
            compound="left",
            command=self._on_select_file,
            width=175,
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ORANGE_PRIMARY,
            hover_color=ORANGE_HOVER,
            border_width=0,
            text_color="#FFFFFF",
            corner_radius=10
        )
        self.btn_select_file.pack(side="left")

        path_box = ctk.CTkFrame(drop_inner, fg_color="transparent")
        path_box.pack(side="left", fill="x", expand=True, padx=(14, 10))

        self.lbl_file_path = ctk.CTkLabel(
            path_box,
            text=self.tr("no_file_selected"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_BODY,
            anchor="w"
        )
        self.lbl_file_path.pack(anchor="w")

        self.lbl_dnd_hint = ctk.CTkLabel(
            path_box,
            text=self.tr("dnd_drop_hint"),
            font=ctk.CTkFont(size=10),
            text_color=TEXT_MUTED,
            anchor="w"
        )
        self.lbl_dnd_hint.pack(anchor="w", pady=(2, 0))

        # Register Drag & Drop targets across the main window and drop zone
        if getattr(self, "_dnd_ready", False) and DND_FILES is not None:
            # Register only self and drop_zone to prevent false leave events between nested child widgets
            for target in [self, self.drop_zone]:
                try:
                    target.drop_target_register(DND_FILES)
                    target.dnd_bind('<<Drop>>', self._on_file_drop)
                    target.dnd_bind('<<DropEnter>>', self._on_drop_enter)
                    target.dnd_bind('<<DropPosition>>', self._on_drop_position)
                    target.dnd_bind('<<DropLeave>>', self._on_drop_leave)
                except Exception:
                    pass

        # Video metadata summary card
        self.meta_card = ctk.CTkFrame(box, fg_color=BG_CARD_INNER, corner_radius=12, border_width=0)
        self.meta_card.pack(fill="x", padx=16, pady=(0, 14))

        self.lbl_meta_info = ctk.CTkLabel(
            self.meta_card,
            text=self.tr("meta_info_placeholder"),
            font=ctk.CTkFont(size=12),
            text_color=TEXT_BODY,
            anchor="w"
        )
        self.lbl_meta_info.pack(padx=12, pady=8, anchor="w")

    def _is_cursor_over_drop_zone(self, event=None) -> bool:
        if not hasattr(self, "drop_zone") or not self.drop_zone.winfo_exists():
            return False
        try:
            rx = self.drop_zone.winfo_rootx()
            ry = self.drop_zone.winfo_rooty()
            rw = self.drop_zone.winfo_width()
            rh = self.drop_zone.winfo_height()
            x = getattr(event, "x_root", None) if event is not None else None
            y = getattr(event, "y_root", None) if event is not None else None
            if x is None or y is None:
                try:
                    x, y = self.winfo_pointerxy()
                except Exception:
                    return False
            return (rx <= x <= rx + rw) and (ry <= y <= ry + rh)
        except Exception:
            return False

    def _set_drop_zone_highlight(self, active: bool):
        if getattr(self, "_dnd_hover_active", None) == active:
            return
        self._dnd_hover_active = active
        if not hasattr(self, "drop_zone") or not self.drop_zone.winfo_exists():
            return
        if active:
            self.drop_zone.configure(
                border_color=ORANGE_PRIMARY,
                border_width=2,
                fg_color=("#FFEDD5", "#26170E")
            )
            if hasattr(self, "lbl_file_path"):
                t = "Pusťte video soubor zde pro načtení!" if self.current_language == "cs" else "Release video file here to load!"
                self.lbl_file_path.configure(text=t, text_color=ORANGE_PRIMARY)
            if hasattr(self, "lbl_dnd_hint"):
                t_sub = "Aplikace video okamžitě načte a připraví" if self.current_language == "cs" else "App will immediately load and prepare video"
                self.lbl_dnd_hint.configure(text=t_sub, text_color=TEXT_TITLE)
        else:
            self.drop_zone.configure(
                border_color=BORDER_CARD,
                border_width=1,
                fg_color=BG_CARD_INNER
            )
            self._update_drop_zone_labels()

    def _on_drop_enter(self, event=None):
        over = self._is_cursor_over_drop_zone(event)
        self._set_drop_zone_highlight(over)
        return getattr(event, "action", "copy") if event else "copy"

    def _on_drop_position(self, event=None):
        if event is not None:
            over = self._is_cursor_over_drop_zone(event)
            self._set_drop_zone_highlight(over)
        return getattr(event, "action", "copy") if event else "copy"

    def _on_drop_leave(self, event=None):
        self._set_drop_zone_highlight(False)
        return getattr(event, "action", "copy") if event else "copy"

    def _update_drop_zone_labels(self):
        if self.current_video_path and self.current_video_path.is_file():
            v_name = self.current_video_path.name
            disp_name = v_name if len(v_name) <= 34 else (v_name[:20] + "..." + v_name[-10:])
            if hasattr(self, "lbl_file_path"):
                self.lbl_file_path.configure(text=disp_name, text_color=TEXT_TITLE)
            if hasattr(self, "lbl_dnd_hint"):
                try:
                    size_mb = self.current_video_path.stat().st_size / (1024 * 1024)
                    self.lbl_dnd_hint.configure(
                        text=self.tr("dnd_ready_hint", size=f"{size_mb:.1f}"),
                        text_color=TEXT_MUTED
                    )
                except Exception:
                    pass
            if hasattr(self, "btn_select_file"):
                self.btn_select_file.configure(
                    text=self.tr("btn_change_file"),
                    image=self.icon_folder_white,
                    fg_color=ORANGE_PRIMARY,
                    hover_color=ORANGE_HOVER,
                    border_width=0,
                    text_color="#FFFFFF"
                )
        else:
            if hasattr(self, "lbl_file_path"):
                self.lbl_file_path.configure(text=self.tr("no_file_selected"), text_color=TEXT_BODY)
            if hasattr(self, "lbl_dnd_hint"):
                self.lbl_dnd_hint.configure(text=self.tr("dnd_drop_hint"), text_color=TEXT_MUTED)
            if hasattr(self, "btn_select_file"):
                self.btn_select_file.configure(
                    text=self.tr("btn_select_file"),
                    image=self.icon_folder_white,
                    fg_color=ORANGE_PRIMARY,
                    hover_color=ORANGE_HOVER,
                    border_width=0,
                    text_color="#FFFFFF"
                )

    def _on_file_drop(self, event):
        self._on_drop_leave()
        data = getattr(event, "data", "")
        if not data:
            return getattr(event, "action", "copy") if event else "copy"

        try:
            candidates = self.tk.splitlist(data)
        except Exception:
            candidates = [data.strip()]

        if not candidates:
            return getattr(event, "action", "copy") if event else "copy"

        candidate = str(candidates[0]).strip().strip("{}'\"")
        p = Path(candidate)
        if not p.is_file():
            messagebox.showwarning(
                "Neplatný soubor" if self.current_language == "cs" else "Invalid File",
                f"Přetažený soubor nebyl nalezen:\n{candidate}"
            )
            return getattr(event, "action", "copy") if event else "copy"

        ext = p.suffix.lower()
        valid_exts = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".ts", ".m4v"}
        if ext not in valid_exts:
            messagebox.showwarning(
                "Nepodporovaný formát" if self.current_language == "cs" else "Unsupported Format",
                f"Soubor '{p.name}' není podporované video.\nPodporované formáty: MP4, MKV, MOV, WebM, AVI."
            )
            return getattr(event, "action", "copy") if event else "copy"

        # Success animation flash (green border)
        if hasattr(self, "drop_zone"):
            self.drop_zone.configure(border_color="#22C55E", border_width=2)
            self.after(600, lambda: self.drop_zone.configure(border_color=BORDER_CARD, border_width=1) if hasattr(self, "drop_zone") else None)

        self._load_video_file(str(p))
        return getattr(event, "action", "copy") if event else "copy"

    def _show_dim_overlay(self, title: Optional[str] = None, subtitle: Optional[str] = None):
        """Zobrazí elegantní poloprůhledný závoj přes hlavní okno s kartou informující o otevřeném editoru či dialogu."""
        self._hide_dim_overlay()
        try:
            self.update_idletasks()
            # Ve světlém režimu jemný světlý závoj (#F0F2F5), v tmavém hluboká černá (#0F1013)
            self._dim_overlay = ctk.CTkFrame(
                self,
                fg_color=BG_WINDOW,
                corner_radius=0
            )
            self._dim_overlay.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
            self._dim_overlay.lift()

            card = ctk.CTkFrame(
                self._dim_overlay,
                fg_color=BG_CARD,
                corner_radius=14,
                border_width=1,
                border_color=BORDER_CARD
            )
            card.place(relx=0.5, rely=0.5, anchor="center")

            title_txt = title or ("Editor momentů je otevřen" if self.current_language == "cs" else "Segment Editor is Open")
            sub_txt = subtitle or ("Upravte nebo potvrďte výběr v okně editoru.\nPo dokončení nebo zavření editoru se aplikace odemkne."
                                   if self.current_language == "cs"
                                   else "Review clips in the editor window.\nThe main window will unlock once closed.")

            ctk.CTkLabel(
                card,
                text="",
                image=self.icon_info,
                width=32,
                height=32
            ).pack(padx=40, pady=(22, 2))

            ctk.CTkLabel(
                card,
                text=title_txt,
                font=ctk.CTkFont(size=17, weight="bold"),
                text_color=TEXT_TITLE
            ).pack(padx=40, pady=(0, 6))

            ctk.CTkLabel(
                card,
                text=sub_txt,
                font=ctk.CTkFont(size=12),
                text_color=TEXT_BODY,
                justify="center"
            ).pack(padx=40, pady=(0, 24))
        except Exception:
            pass

    def _hide_dim_overlay(self):
        """Skryje ztmavovací vrstvu."""
        if hasattr(self, "_dim_overlay") and self._dim_overlay:
            try:
                self._dim_overlay.destroy()
            except Exception:
                pass
            self._dim_overlay = None

    def _open_history_dialog(self):
        """Otevře samostatné okno s historií projektů pro výběr videa."""
        t_hist_title = "Historie projektů je otevřena" if self.current_language == "cs" else "Project History is Open"
        t_hist_sub = ("Vyberte video pro úpravu v editoru nebo zavřete okno historie pro návrat."
                      if self.current_language == "cs"
                      else "Select a video to edit in the editor or close the history window to return.")
        self._show_dim_overlay(title=t_hist_title, subtitle=t_hist_sub)

        ProjectHistoryDialog(
            parent=self,
            config=self.config,
            on_open_project=self._open_project_from_history,
            on_clear_history=self._clear_history,
            on_close=self._hide_dim_overlay,
            current_lang=self.current_language
        )

    def _open_project_from_history(self, item: Dict):
        """Načte zpracovaný projekt z historie a okamžitě otevře Segment Editor."""
        video_str = item.get("video", "")
        if not video_str:
            self._hide_dim_overlay()
            return
        video_path = Path(video_str)
        if not video_path.is_file():
            self._hide_dim_overlay()
            messagebox.showwarning(
                "Soubor nenalezen" if self.current_language == "cs" else "File Not Found",
                f"Video soubor nebyl nalezen na původní cestě:\n{video_str}"
            )
            return

        cache_file_str = item.get("cache_file", "")
        data = None
        if cache_file_str and Path(cache_file_str).is_file():
            try:
                with open(cache_file_str, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = None

        if not data:
            cache_dir = Path(__file__).parent / ".project_cache"
            v_hash = hashlib.md5(str(video_path.resolve()).encode("utf-8")).hexdigest()[:12]
            cand = cache_dir / f"{video_path.stem}_{v_hash}.json"
            if cand.is_file():
                try:
                    with open(cand, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = None

        if not data or not data.get("all_segments"):
            self._hide_dim_overlay()
            self._load_video_file(str(video_path))
            messagebox.showinfo(
                "Informace" if self.current_language == "cs" else "Info",
                "Video bylo načteno. Pro tento starší záznam nejsou uloženy náhledové segmenty v cache, spusťte prosím zpracování."
                if self.current_language == "cs"
                else "Video was loaded. Cached moments not found for this older item, please start processing."
            )
            return

        self.current_video_path = video_path
        disp_name = video_path.name if len(video_path.name) <= 34 else (video_path.name[:20] + "..." + video_path.name[-10:])
        self.lbl_file_path.configure(text=disp_name, text_color=TEXT_TITLE)
        if not self.video_metadata:
            self.video_metadata = get_video_metadata(video_path)

        all_segs = [tuple(s) for s in data.get("all_segments", [])]
        rec_segs = [tuple(s) for s in data.get("recommended_segments", all_segs)]
        target_dur = data.get("target_dur_sec")

        self._show_dim_overlay()

        def on_confirmed_from_editor(chosen_segments):
            self._hide_dim_overlay()
            self._start_export_for_segments(video_path, chosen_segments)

        def on_cancelled_from_editor():
            self._hide_dim_overlay()

        dlg = SegmentReviewDialog(
            parent=self,
            video_path=video_path,
            all_segments=all_segs,
            recommended_segments=rec_segs,
            target_duration_sec=target_dur,
            current_lang=self.current_language,
            on_confirm=on_confirmed_from_editor,
            on_cancel=on_cancelled_from_editor
        )
        dlg.lift()
        dlg.focus_force()

    def _start_export_for_segments(self, video_path: Path, segments: List[Tuple]):
        """Spustí export (EDL/MP4) přímo z editoru bez nutnosti re-analyzovat audio."""
        if not segments:
            return

        selected_format_label = self.format_var.get().lower()
        export_edl = "edl" in selected_format_label
        export_mp4 = "mp4" in selected_format_label
        selected_mode_label = self.mode_var.get().lower()
        mode = "highlights" if "highlight" in selected_mode_label else "remove_silence"
        output_dir = self.output_directory or video_path.parent

        self.is_processing = True
        self._proc_start_time = time.time()
        self._last_eta_calc_time = 0.0
        self._cached_eta_str = ""
        self._eta_smoothed = 25.0
        self.cancel_event.clear()
        self.btn_process.configure(state="disabled")
        self.btn_select_file.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.result_card.pack_forget()
        self.lbl_status.pack(anchor="w", padx=16, pady=(0, 10))
        self.progress_bar.set(0.0)

        def export_worker():
            try:
                meta = self.video_metadata or get_video_metadata(video_path)
                total_duration = meta.get("duration", 0.0)
                fps = meta.get("fps", 30.0)
                threads = self._get_configured_threads()

                stats = calculate_cut_statistics(total_duration, segments)
                base_name = video_path.stem
                suffix_mode = "highlights" if mode == "highlights" else "nosilence"
                generated_files = []

                if export_edl:
                    self._update_progress(0.20, "Generování CMX 3600 EDL souboru...")
                    edl_path = output_dir / f"{base_name}_SnapCut_{suffix_mode}.edl"
                    generate_cmx3600_edl(
                        segments=segments,
                        video_source_path=video_path,
                        output_edl_path=edl_path,
                        fps=fps,
                        title=f"SNAPCUT_{suffix_mode.upper()}"
                    )
                    generated_files.append(edl_path)
                    self.last_output_path = edl_path

                if export_mp4:
                    self._update_progress(0.40, "Příprava bezztrátového střihu videa (SnapCut FFmpeg concat)...")
                    def cut_cb(fraction: float, message: str):
                        p = 0.40 + (fraction * 0.58)
                        self._update_progress(p, message)

                    ext = video_path.suffix if video_path.suffix.lower() in [".mp4", ".mkv", ".mov"] else ".mp4"
                    out_video_path = output_dir / f"{base_name}_SnapCut_{suffix_mode}_cut{ext}"
                    cut_res = cut_video_lossless(
                        input_video_path=video_path,
                        segments=segments,
                        output_video_path=out_video_path,
                        threads=threads,
                        progress_callback=cut_cb,
                        cancel_event=self.cancel_event
                    )
                    if self.cancel_event.is_set():
                        self._on_finished_ui(cancelled=True)
                        return
                    if cut_res:
                        generated_files.append(cut_res)
                        self.last_output_path = cut_res

                self._update_progress(1.0, "Export úspěšně dokončen!")
                self._save_project_cache(
                    video_path=video_path,
                    all_segments=segments,
                    recommended_segments=segments,
                    target_dur_sec=None,
                    stats=stats,
                    output_files=generated_files
                )
                self._on_finished_ui(stats=stats, generated_files=generated_files)
            except Exception as e:
                self._on_finished_ui(error_msg=f"Chyba při exportu videa:\n{e}")

        threading.Thread(target=export_worker, daemon=True).start()

    def _save_project_cache(
        self,
        video_path: Path,
        all_segments: List[Tuple],
        recommended_segments: List[Tuple],
        target_dur_sec: Optional[float],
        stats: Optional[Dict] = None,
        output_files: Optional[List[Path]] = None
    ) -> Path:
        """Uloží segmenty a metadata projektu na disk pro okamžitý návrat z historie."""
        cache_dir = Path(__file__).parent / ".project_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        v_str = str(video_path.resolve())
        v_hash = hashlib.md5(v_str.encode("utf-8")).hexdigest()[:12]
        cache_file = cache_dir / f"{video_path.stem}_{v_hash}.json"

        def clean_segs(segs):
            return [[float(x) for x in s] for s in segs]

        date_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        data = {
            "video": v_str,
            "date": date_str,
            "target_dur_sec": target_dur_sec,
            "stats": stats or {},
            "output_files": [str(p) for p in (output_files or [])],
            "all_segments": clean_segs(all_segments),
            "recommended_segments": clean_segs(recommended_segments),
        }

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

        history = self.config.get("history", [])
        history = [h for h in history if h.get("video") != v_str]
        history.append({
            "video": v_str,
            "cache_file": str(cache_file),
            "date": date_str,
            "stats": {
                "original_duration_min": round((stats.get("original_duration_sec", 0) if stats else 0) / 60, 1),
                "output_duration_min": round((stats.get("output_duration_sec", 0) if stats else 0) / 60, 1),
                "total_segments": len(all_segments),
            },
            "output": str(output_files[0]) if output_files else "",
        })
        self.config["history"] = history[-15:]
        save_app_config(self.config)
        return cache_file

    def _open_folder(self, path: Path):
        """Otevře složku ve Finderu / Průzkumníku."""
        open_folder_in_file_manager(path)

    def _clear_history(self):
        self.config["history"] = []
        save_app_config(self.config)

    def _build_audio_track_section(self, parent):
        """2. Audio track dropdown menu."""
        box = ctk.CTkFrame(parent, corner_radius=12, fg_color=BG_CARD, border_width=1, border_color=BORDER_CARD)
        box.pack(fill="x", pady=8)

        hdr = ctk.CTkFrame(box, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(12, 4))

        step_badge = self._create_step_badge(hdr, "2")
        step_badge.pack(side="left", padx=(0, 8))

        raw_title = self.tr("sec_audio_title")
        t_clean = raw_title.split(". ", 1)[-1] if ". " in raw_title else raw_title
        self.lbl_sec_audio = ctk.CTkLabel(
            hdr,
            text=t_clean,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_sec_audio.pack(side="left")

        q_btn = self._create_help_btn(
            hdr,
            text=(
                "Klíčové nastavení pro záznamy z OBS Studia!\n\n"
                "OBS typicky nahrává zvuk hry na Stopu 1 a váš mikrofon na Stopu 2 (nebo naopak).\n\n"
                "Vyberte stopu obsahující POUZE váš mikrofon. SnapCut tak bude analyzovat váš hlas, smích a křik, "
                "aniž by byl maten hlasitou střelbou nebo hudbou ze hry."
            ),
            recommendation="Vyberte samostatnou stopu mikrofonu z OBS (často Stopa 2), nikoliv smíchaný zvuk."
        )
        q_btn.pack(side="left", padx=(8, 0))

        self.lbl_sec_audio_sub = ctk.CTkLabel(
            box,
            text=self.tr("sec_audio_sub"),
            font=ctk.CTkFont(size=12),
            text_color=TEXT_BODY
        )
        self.lbl_sec_audio_sub.pack(anchor="w", padx=16, pady=(0, 8))

        self.audio_track_var = ctk.StringVar(value="Stopa 1 (výchozí)")
        self.audio_dropdown = ModernOptionMenu(
            box,
            values=["Stopa 1 (výchozí)"],
            variable=self.audio_track_var,
            height=38
        )
        self.audio_dropdown.pack(fill="x", padx=16, pady=(0, 14))

    def _build_parameters_section(self, parent):
        """3. Mode Selection, Sliders, and Target Video Duration."""
        box = ctk.CTkFrame(parent, corner_radius=12, fg_color=BG_CARD, border_width=1, border_color=BORDER_CARD)
        box.pack(fill="x", pady=8)

        # 3.1 Mode Header
        hdr = ctk.CTkFrame(box, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(12, 4))

        step_badge = self._create_step_badge(hdr, "3")
        step_badge.pack(side="left", padx=(0, 8))

        raw_title = self.tr("sec_params_title")
        t_clean = raw_title.split(". ", 1)[-1] if ". " in raw_title else raw_title
        self.lbl_sec_params = ctk.CTkLabel(
            hdr,
            text=t_clean,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_sec_params.pack(side="left")

        q_btn = self._create_help_btn(
            hdr,
            text=(
                "• Akční highlighty: Vybere pouze nejhlasitější a nejenergičtější momenty (křik, leknutí, smích, hype). "
                "Ideální pro tvorbu zábavného sestřihu z dlouhého streamu.\n\n"
                "• Vyřezat pouze ticho: Zachová celé video v původní chronologii, ale vyřízne mrtvé pasáže, "
                "kdy nikdo nemluví. Vhodné pro zrychlení celých gameplay záznamů."
            ),
            recommendation="Pro YouTube video zvolte 'Akční highlighty'."
        )
        q_btn.pack(side="left", padx=(8, 0))

        # Mode dropdown
        saved_mode = self.config.get("detection_mode", "highlights")
        if saved_mode == "silence":
            init_mode = "Vyřezat pouze ticho (plná délka bez dlouhých pauz)"
        else:
            init_mode = "Pouze akční highlighty (sestřih křiku a reakcí)"

        self.mode_var = ctk.StringVar(value=init_mode)
        self.mode_dropdown = ModernOptionMenu(
            box,
            values=[
                "Pouze akční highlighty (sestřih křiku a reakcí)",
                "Vyřezat pouze ticho (plná délka bez dlouhých pauz)"
            ],
            variable=self.mode_var,
            command=self._on_mode_dropdown_change,
            height=38
        )
        self.mode_dropdown.pack(fill="x", padx=16, pady=(0, 10))

        # 3.2 Target Video Duration
        dur_hdr = ctk.CTkFrame(box, fg_color="transparent")
        dur_hdr.pack(fill="x", padx=16, pady=(6, 2))

        self.lbl_dur_heading = ctk.CTkLabel(
            dur_hdr,
            text=self.tr("lbl_target_dur_title"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_dur_heading.pack(side="left")

        q_dur = self._create_help_btn(
            dur_hdr,
            text=(
                "Chcete mít výsledné video o konkrétní délce (např. přesně 10 nebo 15 minut na YouTube)?\n\n"
                "Pokud nastavíte limit délky, SnapCut automaticky seřadí všechny zachycené momenty podle intenzity (hlasitosti) "
                "a vybere jen ty nejlepší hype reakce, které se vejdou do zadaného času!\n\n"
                "Možnost 'Bez limitu' zachová úplně všechny detekované momenty."
            ),
            recommendation="'10 minut' je ideální stopáž pro YouTube. Pro kompletní archiv zvolte 'Bez limitu'."
        )
        q_dur.pack(side="left", padx=(8, 0))

        dur_labels = [
            "Bez limitu (všechny zachycené momenty)",
            "5 minut (rychlý sestřih / TikTok / Shorts kompilace)",
            "10 minut (optimální pro YouTube video)",
            "15 minut (delší YouTube video)",
            "20 minut (rozsáhlý highlight)",
            "30 minut (dlouhá stream kompilace)"
        ]
        saved_dur = self.config.get("target_duration", "none")
        dur_key_map = {
            "none": dur_labels[0],
            "5min": dur_labels[1],
            "10min": dur_labels[2],
            "15min": dur_labels[3],
            "20min": dur_labels[4],
            "30min": dur_labels[5],
        }
        init_dur = dur_key_map.get(saved_dur, dur_labels[0])
        self.target_dur_var = ctk.StringVar(value=init_dur)
        self.target_dur_dropdown = ModernOptionMenu(
            box,
            values=dur_labels,
            variable=self.target_dur_var,
            command=lambda _: self._queue_save_settings(),
            height=38
        )
        self.target_dur_dropdown.pack(fill="x", padx=16, pady=(2, 10))

        # 3.3 Slider 1: Loudness Threshold dBFS
        s1_frame = ctk.CTkFrame(box, fg_color="transparent")
        s1_frame.pack(fill="x", padx=16, pady=4)

        saved_thresh = float(self.config.get("sound_threshold", -14.0))
        self.lbl_threshold_val = ctk.CTkLabel(
            s1_frame,
            text=f"{saved_thresh:.1f} dBFS",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=ORANGE_ACCENT_TEXT,
            fg_color=CHIP_BG,
            corner_radius=6,
            height=24,
            padx=8
        )
        self.lbl_threshold_val.pack(side="right")

        self.lbl_thresh_heading = ctk.CTkLabel(
            s1_frame,
            text=self.tr("lbl_threshold"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_thresh_heading.pack(side="left")

        self.q_thresh = self._create_help_btn(
            s1_frame,
            text=(
                "Určuje, jak hlasitý zvuk z mikrofonu musí být, aby se spustilo nahrávání klipu:\n\n"
                "• -10 dBFS: Pouze extrémní řev, panika a výkřiky leknutí.\n"
                "• -14 dBFS (výchozí): Standardní hlasitý křik, záchvat smíchu a hype reakce.\n"
                "• -18 dBFS: Zachytí i běžné mluvení a mírně zvýšený hlas.\n"
                "• -28 až -35 dBFS: Vhodné pro režim vyřezání ticha."
            ),
            recommendation="-14.0 dBFS je ideální střed. Pokud máš tichý mikrofon, zkus -16 dBFS."
        )
        self.q_thresh.pack(side="left", padx=(8, 0))

        self.slider_threshold = ModernSlider(
            box,
            from_=-35,
            to=-5,
            number_of_steps=60,
            command=self._on_threshold_slider_change,
            fg_color=TRACK_COLOR,
            progress_color=ORANGE_PRIMARY,
            button_color=ORANGE_PRIMARY,
            button_hover_color=ORANGE_HOVER
        )
        self.slider_threshold.set(saved_thresh)
        self.slider_threshold.pack(fill="x", padx=16, pady=(0, 8))
        self._disable_slider_mousewheel(self.slider_threshold)

        # 3.4 Padding frame (Before & After sliders side by side)
        pad_container = ctk.CTkFrame(box, fg_color="transparent")
        pad_container.pack(fill="x", padx=16, pady=2)

        # Context Before
        pad_left = ctk.CTkFrame(pad_container, fg_color="transparent")
        pad_left.pack(side="left", fill="x", expand=True, padx=(0, 10))

        p_before_hdr = ctk.CTkFrame(pad_left, fg_color="transparent")
        p_before_hdr.pack(fill="x")

        saved_pad_b = float(self.config.get("pad_before", 4.0))
        self.lbl_pad_before = ctk.CTkLabel(
            p_before_hdr,
            text=f"{saved_pad_b:.1f} s",
            text_color=ORANGE_ACCENT_TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=CHIP_BG,
            corner_radius=6,
            height=24,
            padx=8
        )
        self.lbl_pad_before.pack(side="right")

        self.lbl_pad_before_heading = ctk.CTkLabel(p_before_hdr, text=self.tr("lbl_pad_before"), font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_TITLE)
        self.lbl_pad_before_heading.pack(side="left")
        q_p_bef = self._create_help_btn(
            p_before_hdr,
            text=(
                "Kolik sekund videa před začátkem výkřiku má klip obsahovat.\n\n"
                "Například 4 sekundy zajistí, že divák uvidí herní situaci nebo jump scare, který výkřik způsobil."
            ),
            recommendation="4.0 s (ukáže herní akci před výkřikem)"
        )
        q_p_bef.pack(side="left", padx=(6, 0))

        self.slider_pad_before = ModernSlider(
            pad_left,
            from_=0,
            to=10,
            number_of_steps=40,
            command=self._on_pad_before_change,
            fg_color=TRACK_COLOR,
            progress_color=ORANGE_PRIMARY,
            button_color=ORANGE_PRIMARY,
            button_hover_color=ORANGE_HOVER
        )
        self.slider_pad_before.set(saved_pad_b)
        self.slider_pad_before.pack(fill="x", pady=(2, 6))
        self._disable_slider_mousewheel(self.slider_pad_before)

        # Context After
        pad_right = ctk.CTkFrame(pad_container, fg_color="transparent")
        pad_right.pack(side="right", fill="x", expand=True, padx=(10, 0))

        p_after_hdr = ctk.CTkFrame(pad_right, fg_color="transparent")
        p_after_hdr.pack(fill="x")

        saved_pad_a = float(self.config.get("pad_after", 2.0))
        self.lbl_pad_after = ctk.CTkLabel(
            p_after_hdr,
            text=f"{saved_pad_a:.1f} s",
            text_color=ORANGE_ACCENT_TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=CHIP_BG,
            corner_radius=6,
            height=24,
            padx=8
        )
        self.lbl_pad_after.pack(side="right")

        self.lbl_pad_after_heading = ctk.CTkLabel(p_after_hdr, text=self.tr("lbl_pad_after"), font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_TITLE)
        self.lbl_pad_after_heading.pack(side="left")
        q_p_aft = self._create_help_btn(
            p_after_hdr,
            text=(
                "Kolik sekund videa po skončení výkřiku má klip pokračovat.\n\n"
                "Například 2 sekundy zajistí, že video neusekne doznění smíchu nebo komentář těsně po reakci."
            ),
            recommendation="2.0 s (doznění smíchu a komentáře)"
        )
        q_p_aft.pack(side="left", padx=(6, 0))

        self.slider_pad_after = ModernSlider(
            pad_right,
            from_=0,
            to=10,
            number_of_steps=40,
            command=self._on_pad_after_change,
            fg_color=TRACK_COLOR,
            progress_color=ORANGE_PRIMARY,
            button_color=ORANGE_PRIMARY,
            button_hover_color=ORANGE_HOVER
        )
        self.slider_pad_after.set(saved_pad_a)
        self.slider_pad_after.pack(fill="x", pady=(2, 6))
        self._disable_slider_mousewheel(self.slider_pad_after)

        # 3.5 Smart merge gap slider
        gap_frame = ctk.CTkFrame(box, fg_color="transparent")
        gap_frame.pack(fill="x", padx=16, pady=(10, 2))

        gap_hdr = ctk.CTkFrame(gap_frame, fg_color="transparent")
        gap_hdr.pack(fill="x")

        saved_gap = float(self.config.get("min_gap", 2.0))
        self.lbl_gap_val = ctk.CTkLabel(
            gap_hdr,
            text=f"{saved_gap:.1f} s",
            text_color=ORANGE_ACCENT_TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=CHIP_BG,
            corner_radius=6,
            height=24,
            padx=8
        )
        self.lbl_gap_val.pack(side="right")

        self.lbl_gap_heading = ctk.CTkLabel(
            gap_hdr,
            text=self.tr("lbl_gap"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_gap_heading.pack(side="left")

        q_gap = self._create_help_btn(
            gap_hdr,
            text=(
                "Pokud se dvě hlasité reakce odehrají těsně za sebou (např. se zasmějete, na 1 sekundu se nadechnete "
                "a znovu zařvete), SnapCut tyto momenty automaticky spojí do jednoho plynulého klipu.\n\n"
                "Díky tomu se video neseká po půlsekundách a střih působí profesionálně a přirozeně."
            ),
            recommendation="2.0 s zajistí plynulý sestřih bez trhání."
        )
        q_gap.pack(side="left", padx=(6, 0))

        self.slider_gap = ModernSlider(
            box,
            from_=0,
            to=6,
            number_of_steps=60,
            command=self._on_gap_change,
            fg_color=TRACK_COLOR,
            progress_color=ORANGE_PRIMARY,
            button_color=ORANGE_PRIMARY,
            button_hover_color=ORANGE_HOVER
        )
        self.slider_gap.set(saved_gap)
        self.slider_gap.pack(fill="x", padx=16, pady=(0, 10))
        self._disable_slider_mousewheel(self.slider_gap)

        # 3.6 Facecam AI Feature Card
        facecam_box = ctk.CTkFrame(box, fg_color=BG_CARD_INNER, corner_radius=10, border_width=0)
        facecam_box.pack(fill="x", padx=16, pady=(4, 12))

        f_hdr = ctk.CTkFrame(facecam_box, fg_color="transparent")
        f_hdr.pack(fill="x", padx=12, pady=(10, 4))

        saved_fc = bool(self.config.get("facecam_enabled", True))
        self.facecam_ai_var = ctk.BooleanVar(value=saved_fc)
        self.chk_facecam_ai = ModernCheckBox(
            f_hdr,
            text=self.tr("chk_facecam"),
            variable=self.facecam_ai_var,
            command=self._queue_save_settings,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.chk_facecam_ai.pack(side="left")

        q_ai = self._create_help_btn(
            f_hdr,
            text=(
                "Jak funguje Facecam AI:\n\n"
                "1. Analýza výrazu obličeje: Hledá v záběru obličej a měří otevření úst (křik, leknutí, údiv) "
                "a široký úsměv (záchvat smíchu).\n\n"
                "2. Detekce pohybu těla a hlavy: Měří kinetickou energii (když streamer nadskočí leknutím, hází hlavou či gestikuluje).\n\n"
                "3. Inteligentní hybridní skóre: Zkombinuje hlasitost audia s reakcí ve webkameře. Momenty s velkou reakcí v obličeji "
                "dostanou nejvyšší prioritu pro finální sestřih, zatímco náhodné zvuky ze hry bez reakce v obličeji jsou odfiltrovány.\n\n"
                " Běží bleskově dvoufázově — skenuje pouze kandidátské momenty (cca 5-10 sekund na 4h video)."
            ),
            recommendation="Ponechte zapnuté pro záznamy s webkamerou. Aplikace automaticky detekuje obličej."
        )
        q_ai.pack(side="left", padx=(8, 0))

        self.sub_facecam = ctk.CTkLabel(
            facecam_box,
            text=self.tr("sub_facecam"),
            font=ctk.CTkFont(size=11),
            text_color=TEXT_BODY
        )
        self.sub_facecam.pack(anchor="w", padx=12, pady=(0, 10))

    def _build_export_section(self, parent):
        """4. Single-choice output format (Dropdown) and destination directory."""
        box = ctk.CTkFrame(parent, corner_radius=12, fg_color=BG_CARD, border_width=1, border_color=BORDER_CARD)
        box.pack(fill="x", pady=8)

        hdr = ctk.CTkFrame(box, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(12, 4))

        step_badge = self._create_step_badge(hdr, "4")
        step_badge.pack(side="left", padx=(0, 8))

        raw_title = self.tr("sec_export_title")
        t_clean = raw_title.split(". ", 1)[-1] if ". " in raw_title else raw_title
        self.lbl_sec_export = ctk.CTkLabel(
            hdr,
            text=t_clean,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.lbl_sec_export.pack(side="left")

        q_fmt = self._create_help_btn(
            hdr,
            text=(
                "• Hotové MP4 video: Okamžitý bezztrátový střih přes FFmpeg concat demuxer (-c copy). "
                "Zachovává 100% původní kvality obrazu i všechny zvukové stopy, hotovo za 1-2 minuty.\n\n"
                "• EDL Timeline: Vygeneruje soubor CMX 3600 EDL pro DaVinci Resolve a Adobe Premiere Pro. "
                "Umožní vám otevřít hotové střihy přímo v editoru a doladit hudbu, efekty či titulky."
            ),
            recommendation="'Hotové MP4 video' pro okamžité shlédnutí bez práce, 'EDL' pro úpravy v DaVinci/Premiere."
        )
        q_fmt.pack(side="left", padx=(8, 0))

        # Format selector (Modern Dropdown menu)
        saved_fmt = self.config.get("export_format", "mp4")
        init_fmt = "EDL Timeline (.edl pro DaVinci Resolve a Premiere Pro)" if saved_fmt == "edl" else "Hotové MP4 video (rychlý bezztrátový FFmpeg střih)"
        self.format_var = ctk.StringVar(value=init_fmt)
        self.format_dropdown = ModernOptionMenu(
            box,
            values=[
                "Hotové MP4 video (rychlý bezztrátový FFmpeg střih)",
                "EDL Timeline (.edl pro DaVinci Resolve a Premiere Pro)"
            ],
            variable=self.format_var,
            command=lambda _: self._queue_save_settings(),
            height=38
        )
        self.format_dropdown.pack(fill="x", padx=16, pady=(0, 12))

        # Output folder interactive card (Logi Options+ style)
        out_card = ctk.CTkFrame(
            box,
            corner_radius=12,
            fg_color=BG_CARD_INNER,
            border_width=1,
            border_color=BORDER_CARD
        )
        out_card.pack(fill="x", padx=16, pady=(0, 14))

        out_inner = ctk.CTkFrame(out_card, fg_color="transparent")
        out_inner.pack(fill="x", padx=12, pady=8)

        icon_lbl = ctk.CTkLabel(
            out_inner,
            text="",
            image=self.icon_folder,
            width=26,
            height=32,
            cursor="hand2"
        )
        icon_lbl.pack(side="left", padx=(0, 8))
        icon_lbl.bind("<Button-1>", lambda _: self._on_open_result_folder())

        init_out_text = (
            f"{self.tr('out_dir_custom')}{self.default_export_dir}"
            if self.default_export_dir and Path(self.default_export_dir).is_dir()
            else self.tr("out_dir_default")
        )
        self.lbl_output_dir = ctk.CTkLabel(
            out_inner,
            text=init_out_text,
            font=ctk.CTkFont(size=12),
            text_color=TEXT_TITLE if (self.default_export_dir and Path(self.default_export_dir).is_dir()) else TEXT_BODY,
            anchor="w",
            height=32,
            cursor="hand2"
        )
        self.lbl_output_dir.pack(side="left", fill="x", expand=True)
        self.lbl_output_dir.bind("<Button-1>", lambda _: self._on_open_result_folder())

        self.btn_reveal_out = ModernButton(
            out_inner,
            text=self.tr("btn_reveal_out"),
            command=self._on_open_result_folder,
            width=120,
            height=36,
            corner_radius=8,
            fg_color=BG_CARD,
            hover_color=("#E5E7EB", "#252834"),
            border_width=1,
            border_color=BORDER_CARD,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.btn_reveal_out.pack(side="right", padx=(6, 0))

        self.btn_change_out = ModernButton(
            out_inner,
            text=self.tr("btn_change_out"),
            command=self._on_select_output_dir,
            width=180,
            height=36,
            corner_radius=8,
            fg_color=BG_CARD,
            hover_color=("#E5E7EB", "#252834"),
            border_width=1,
            border_color=BORDER_CARD,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.btn_change_out.pack(side="right", padx=(8, 0))

        # Option A: Interactive review editor & preview checkbox (Styled identically to Facecam AI)
        rev_box = ctk.CTkFrame(box, fg_color=BG_CARD_INNER, corner_radius=10, border_width=0)
        rev_box.pack(fill="x", padx=16, pady=(0, 14))

        rev_hdr = ctk.CTkFrame(rev_box, fg_color="transparent")
        rev_hdr.pack(fill="x", padx=12, pady=(10, 4))

        saved_rev = bool(self.config.get("review_segments", True))
        self.review_segments_var = ctk.BooleanVar(value=saved_rev)
        self.chk_review_segments = ModernCheckBox(
            rev_hdr,
            text=self.tr("chk_review_segments"),
            variable=self.review_segments_var,
            command=self._queue_save_settings,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_TITLE
        )
        self.chk_review_segments.pack(side="left")

        q_rev = self._create_help_btn(
            rev_hdr,
            text=(
                "Před samotným střihem a uložením videa otevře interaktivní vizuální studio:\n\n"
                "• Zobrazí nalezené momenty a jejich délky\n"
                "• Umožní přehrát a zkontrolovat jednotlivé reakce\n"
                "• Můžete ručně vyřadit nebo přidat jednotlivé klipy"
            ),
            recommendation="Doporučeno nechat zapnuté, abyste měli plnou kontrolu nad finálním sestřihem."
        )
        q_rev.pack(side="left", padx=(8, 0))

        self.sub_review_segments = ctk.CTkLabel(
            rev_box,
            text=self.tr("sub_review_segments"),
            font=ctk.CTkFont(size=11),
            text_color=TEXT_BODY,
            wraplength=700,
            justify="left"
        )
        self.sub_review_segments.pack(anchor="w", padx=42, pady=(0, 10))

    def _build_progress_section(self, parent):
        """Action button, progress bar, textual feedback, and results card."""
        box = ctk.CTkFrame(parent, corner_radius=12, fg_color=BG_CARD, border_width=1, border_color=BORDER_CARD)
        box.pack(fill="x", pady=8)

        # Buttons row
        btn_row = ctk.CTkFrame(box, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(14, 10))

        self.btn_process = ModernButton(
            btn_row,
            text=self.tr("btn_process"),
            command=self._on_start_processing,
            height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=ORANGE_PRIMARY,
            hover_color=ORANGE_HOVER,
            text_color="#FFFFFF",
            corner_radius=8
        )
        self.btn_process.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.btn_cancel = ModernButton(
            btn_row,
            text=self.tr("btn_cancel"),
            command=self._on_cancel_processing,
            height=46,
            width=110,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#FEE2E2", "#301616"),
            hover_color=("#FECACA", "#451E1E"),
            text_color=("#DC2626", "#FF6B6B"),
            border_width=1,
            border_color=("#FCA5A5", "#5E2222"),
            corner_radius=8,
            state="disabled"
        )
        self.btn_cancel.pack(side="right")

        # Progress bar
        self.progress_bar = ModernProgressBar(box, height=14, fg_color=TRACK_COLOR, progress_color=ORANGE_PRIMARY)
        self.progress_bar.pack(fill="x", padx=16, pady=(4, 6))
        self.progress_bar.set(0.0)

        # Status row: text message on left, percentage label on right
        self.status_row = ctk.CTkFrame(box, fg_color="transparent")
        self.status_row.pack(fill="x", padx=16, pady=(0, 10))

        self.lbl_status = ctk.CTkLabel(
            self.status_row,
            text=self.tr("status_ready"),
            font=ctk.CTkFont(size=13),
            text_color=TEXT_TITLE
        )
        self.lbl_status.pack(side="left")

        self.lbl_progress_pct = ctk.CTkLabel(
            self.status_row,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=ORANGE_PRIMARY
        )
        self.lbl_progress_pct.pack(side="right")

        # Result row (Hidden initially - minimal checkmark + folder link)
        self.result_card = ctk.CTkFrame(box, fg_color="transparent")

        self.btn_open_folder = ModernButton(
            self.result_card,
            text=self.tr("btn_open_folder"),
            command=self._on_open_result_folder,
            height=32,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ORANGE_PRIMARY,
            hover_color=ORANGE_HOVER,
            text_color="#FFFFFF",
            corner_radius=8
        )
        self.btn_open_folder.pack(side="left", padx=(0, 14))

        self.lbl_result_check = ctk.CTkLabel(
            self.result_card,
            text=self.tr("lbl_done"),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#22C55E"
        )
        self.lbl_result_check.pack(side="left")

    def _build_footer(self, parent):
        """Bottom status bar."""
        footer_frame = ctk.CTkFrame(parent, height=30, corner_radius=0, fg_color=BG_HEADER)
        footer_frame.pack(fill="x", side="bottom")

        self.lbl_footer = ctk.CTkLabel(
            footer_frame,
            text=f"Pecislav Studio v{APP_VERSION} • Creator Suite by Pecislav • Lossless FFmpeg Engine",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED
        )
        self.lbl_footer.pack(side="left", padx=16, pady=4)

    # -------------------------------------------------------------------------
    # Settings & FFmpeg Management
    # -------------------------------------------------------------------------

    def _open_settings_dialog(self):
        """Switches to the integrated Settings view in Pecislav Studio."""
        self._switch_view("settings")

    def _check_ffmpeg_status(self):
        """Verifies FFmpeg presence and updates the sidebar indicator badge."""
        ffmpeg_path, ffprobe_path = get_ffmpeg_paths()
        if hasattr(self, "sidebar_ffmpeg_pill"):
            if ffmpeg_path and ffprobe_path:
                self.sidebar_ffmpeg_pill.configure(
                    text="FFmpeg připraven",
                    text_color="#22C55E",
                    border_width=1,
                    border_color="#22C55E"
                )
            else:
                self.sidebar_ffmpeg_pill.configure(
                    text="FFmpeg chybí",
                    text_color="#EF4444",
                    border_width=1,
                    border_color="#EF4444"
                )
        if hasattr(self, "comp_rows_frame") and self.comp_rows_frame.winfo_exists():
            self._render_components_static()

    def _on_ffmpeg_status_clicked(self):
        """Opens settings when status clicked."""
        self._open_settings_dialog()

    def _prompt_ffmpeg_download(self):
        """Prompts the user to auto-download FFmpeg if missing."""
        if self.is_downloading_ffmpeg:
            return

        confirm = messagebox.askyesno(
            "Pecislav Studio • Automatické stažení FFmpeg",
            "FFmpeg a FFprobe nebyly v systému nalezeny.\n\n"
            "Chcete, aby Pecislav Studio automaticky stáhl a nastavil FFmpeg do složky aplikace?\n\n"
            "(Vše proběhne na pozadí z oficiálních zdrojů a FFmpeg bude ihned připraven k použití.)"
        )
        if not confirm:
            return

        self._start_ffmpeg_download()

    def _start_ffmpeg_download(self):
        """Launches the automatic download in a background thread."""
        self.is_downloading_ffmpeg = True
        if hasattr(self, "sidebar_ffmpeg_pill"):
            self.sidebar_ffmpeg_pill.configure(
                text=" Stahuji...",
                image=self.icon_hourglass,
                compound="left",
                border_color=ORANGE_PRIMARY,
                text_color=ORANGE_PRIMARY
            )
        self.lbl_status.configure(text="Zahajuji automatické stahování FFmpeg...")
        self.progress_bar.set(0.05)

        self.download_thread = threading.Thread(
            target=self._download_worker,
            daemon=True
        )
        self.download_thread.start()

    def _download_worker(self):
        def progress_cb(fraction: float, message: str):
            self.after(0, lambda: self._update_download_progress(fraction, message))

        success, msg = download_ffmpeg_auto(progress_callback=progress_cb)
        self.after(0, lambda: self._on_download_finished(success, msg))

    def _update_download_progress(self, fraction: float, message: str):
        clamped = min(max(fraction, 0.0), 1.0)
        pct_text = f"{int(clamped * 100)} %"
        self.progress_bar.set(clamped)
        self.lbl_status.configure(text=message)
        if hasattr(self, "lbl_progress_pct") and self.lbl_progress_pct.winfo_exists():
            self.lbl_progress_pct.configure(text=pct_text)

    def _on_download_finished(self, success: bool, msg: str):
        self.is_downloading_ffmpeg = False
        self._check_ffmpeg_status()

        if success:
            self.progress_bar.set(1.0)
            if hasattr(self, "lbl_progress_pct") and self.lbl_progress_pct.winfo_exists():
                self.lbl_progress_pct.configure(text="100 %")
            self.lbl_status.configure(text="FFmpeg úspěšně nainstalován a připraven!")
            messagebox.showinfo("Hotovo", msg)
        else:
            self.progress_bar.set(0.0)
            if hasattr(self, "lbl_progress_pct") and self.lbl_progress_pct.winfo_exists():
                self.lbl_progress_pct.configure(text="")
            self.lbl_status.configure(text="Stažení FFmpeg selhalo.")
            messagebox.showerror("Chyba instalace FFmpeg", f"{msg}\n\nTip: Nainstalujte FFmpeg ručně (brew install ffmpeg na macOS, winget install Gyan.FFmpeg na Windows).")

    # -------------------------------------------------------------------------
    # Helper & Event Handlers & Persistent Settings
    # -------------------------------------------------------------------------

    def _queue_save_settings(self):
        """Debounced settings save to avoid excessive disk I/O while moving sliders."""
        timer = getattr(self, "_save_settings_timer", None)
        if timer:
            try:
                self.after_cancel(timer)
            except Exception:
                pass
        self._save_settings_timer = self.after(350, self._save_all_settings_to_config)

    def _save_all_settings_to_config(self):
        """Persists all current parameters and user selections to AppData config.json."""
        try:
            if hasattr(self, "mode_var"):
                self.config["detection_mode"] = "highlights" if "highlighty" in self.mode_var.get().lower() else "silence"
            if hasattr(self, "target_dur_var"):
                cur_dur = self.target_dur_var.get()
                dur_key = "none"
                for k, v in [("5min", "5 minut"), ("10min", "10 minut"), ("15min", "15 minut"), ("20min", "20 minut"), ("30min", "30 minut")]:
                    if v in cur_dur:
                        dur_key = k
                        break
                self.config["target_duration"] = dur_key
            if hasattr(self, "slider_threshold"):
                self.config["sound_threshold"] = round(float(self.slider_threshold.get()), 1)
            if hasattr(self, "slider_pad_before"):
                self.config["pad_before"] = round(float(self.slider_pad_before.get()), 1)
            if hasattr(self, "slider_pad_after"):
                self.config["pad_after"] = round(float(self.slider_pad_after.get()), 1)
            if hasattr(self, "slider_gap"):
                self.config["min_gap"] = round(float(self.slider_gap.get()), 1)
            if hasattr(self, "facecam_ai_var"):
                self.config["facecam_enabled"] = bool(self.facecam_ai_var.get())
            if hasattr(self, "format_var"):
                self.config["export_format"] = "edl" if "edl" in self.format_var.get().lower() else "mp4"
            if hasattr(self, "review_segments_var"):
                self.config["review_segments"] = bool(self.review_segments_var.get())
            if hasattr(self, "auto_open_folder"):
                self.config["auto_open_folder"] = bool(self.auto_open_folder)
            if hasattr(self, "default_export_dir"):
                self.config["default_export_dir"] = str(self.default_export_dir)
            if hasattr(self, "current_language"):
                self.config["language"] = self.current_language

            save_app_config(self.config)
        except Exception as e:
            print(f"[Config] Error saving settings: {e}")

    def _on_app_exit(self):
        """Handles clean application exit, confirming if busy and saving all configuration."""
        if self.is_processing:
            title = "Ukončit aplikaci" if self.current_language == "cs" else "Exit Application"
            msg = ("Právě probíhá střih videa. Opravdu si přejete aplikaci ukončit?\n\nRozpracovaný proces bude zrušen."
                   if self.current_language == "cs"
                   else "Video cutting is currently in progress. Do you really want to exit?\n\nThe process will be cancelled.")
            if not messagebox.askyesno(title, msg, parent=self):
                return
            self.cancel_event.set()

        self._save_all_settings_to_config()
        self.destroy()

    def _on_threshold_slider_change(self, value: float):
        self.lbl_threshold_val.configure(text=f"{value:.1f} dBFS")
        self._queue_save_settings()

    def _on_pad_before_change(self, v: float):
        if hasattr(self, "lbl_pad_before"):
            self.lbl_pad_before.configure(text=f"{v:.1f} s")
        self._queue_save_settings()

    def _on_pad_after_change(self, v: float):
        if hasattr(self, "lbl_pad_after"):
            self.lbl_pad_after.configure(text=f"{v:.1f} s")
        self._queue_save_settings()

    def _on_gap_change(self, v: float):
        if hasattr(self, "lbl_gap_val"):
            self.lbl_gap_val.configure(text=f"{v:.1f} s")
        self._queue_save_settings()

    def _on_mode_dropdown_change(self, choice: str):
        if "highlighty" in choice.lower():
            self.slider_threshold.set(-14.0)
            self.lbl_threshold_val.configure(text="-14.0 dBFS")
            if hasattr(self, "q_thresh"):
                tt = getattr(self.q_thresh, "_tooltip", None)
                if tt is not None:
                    tt.set_recommendation("-14.0 dBFS je ideální střed. Pokud máš tichý mikrofon, zkus -16 dBFS.")
        else:
            self.slider_threshold.set(-28.0)
            self.lbl_threshold_val.configure(text="-28.0 dBFS")
            if hasattr(self, "q_thresh"):
                tt = getattr(self.q_thresh, "_tooltip", None)
                if tt is not None:
                    tt.set_recommendation("-28.0 dBFS pro ticho (odstraní mrtvé pauzy bez hlasu).")
        self._queue_save_settings()

    def _on_select_file(self):
        """Opens file dialog for video selection and parses metadata."""
        filetypes = [
            ("Video soubory (*.mp4, *.mkv, *.mov, *.webm)", "*.mp4 *.mkv *.mov *.webm *.avi *.MP4 *.MKV *.MOV *.WEBM"),
            ("Všechny soubory", "*.*")
        ]
        initial = None
        if self.current_video_path and self.current_video_path.parent.is_dir():
            initial = self.current_video_path.parent
        elif self.default_export_dir and Path(self.default_export_dir).is_dir():
            initial = Path(self.default_export_dir)

        chosen = safe_ask_open_file(
            parent=self,
            title="Vyberte video záznam",
            filetypes=filetypes,
            initialdir=initial
        )
        if chosen:
            self._load_video_file(chosen)

    def _load_video_file(self, path: str):
        """Načte vybraný nebo přetažený video soubor a spustí extrakci metadat."""
        video_path = Path(path)
        if not video_path.is_file():
            return

        self.current_video_path = video_path
        disp_name = video_path.name if len(video_path.name) <= 34 else (video_path.name[:20] + "..." + video_path.name[-10:])
        self.lbl_file_path.configure(text=disp_name, text_color=TEXT_TITLE)

        if hasattr(self, "btn_select_file"):
            self.btn_select_file.configure(
                text=self.tr("btn_change_file"),
                image=self.icon_folder_white,
                fg_color=ORANGE_PRIMARY,
                hover_color=ORANGE_HOVER,
                border_width=0,
                text_color="#FFFFFF"
            )

        if hasattr(self, "lbl_dnd_hint"):
            try:
                size_mb = video_path.stat().st_size / (1024 * 1024)
                self.lbl_dnd_hint.configure(
                    text=self.tr("dnd_ready_hint", size=f"{size_mb:.1f}"),
                    text_color=TEXT_MUTED
                )
            except Exception:
                pass

        # Apply default export directory if set in config, otherwise default beside video
        if self.default_export_dir and Path(self.default_export_dir).is_dir():
            self.output_directory = Path(self.default_export_dir)
            self.lbl_output_dir.configure(
                text=f"{self.tr('out_dir_custom')}{self.default_export_dir}",
                text_color=TEXT_TITLE
            )
        else:
            self.output_directory = None
            self.lbl_output_dir.configure(
                text=self.tr("out_dir_default"),
                text_color=TEXT_BODY
            )

        # Reset results
        self.result_card.pack_forget()
        self.lbl_status.pack(anchor="w", padx=16, pady=(0, 10))
        self.lbl_status.configure(text=f"Načítám metadata souboru {video_path.name}...")

        # Load metadata in background thread
        threading.Thread(target=self._load_metadata_worker, args=(video_path,), daemon=True).start()

    def _load_metadata_worker(self, video_path: Path):
        try:
            meta = get_video_metadata(video_path)
            self.video_metadata = meta
            self.after(0, self._update_metadata_ui, meta)
        except Exception as e:
            self.after(0, lambda: self._show_error(f"Chyba při čtení metadat videa:\n{e}"))

    def _update_metadata_ui(self, meta: Dict):
        duration_sec = meta.get("duration", 0.0)
        h = int(duration_sec // 3600)
        m = int((duration_sec % 3600) // 60)
        s = int(duration_sec % 60)
        dur_str = f"{h}h {m:02d}m {s:02d}s"

        fps = meta.get("fps", 30.0)
        w = meta.get("width", 1920)
        h_res = meta.get("height", 1080)
        codec = meta.get("video_codec", "unknown")
        tracks = meta.get("audio_tracks", [])

        info_text = (
            f"Délka: {dur_str}  |  FPS: {fps:.2f}  |  Rozlišení: {w}x{h_res}  |  "
            f"Video Codec: {codec}  |  Audio stop: {len(tracks)}"
        )
        self.lbl_meta_info.configure(text=info_text, text_color=TEXT_TITLE)

        # Update audio track dropdown
        if tracks:
            track_labels = [t["label"] for t in tracks]
            self.audio_dropdown.configure(values=track_labels)
            self.audio_track_var.set(track_labels[0])
        else:
            self.audio_dropdown.configure(values=["Žádné audio stopy nenalezeny"])
            self.audio_track_var.set("Žádné audio stopy")

        self.lbl_status.configure(text=self.tr("status_ready"))

    def _on_select_output_dir(self):
        """Allows user to select custom destination folder."""
        initial = None
        if self.output_directory and self.output_directory.is_dir():
            initial = self.output_directory
        elif self.current_video_path and self.current_video_path.parent.is_dir():
            initial = self.current_video_path.parent
        elif self.default_export_dir and Path(self.default_export_dir).is_dir():
            initial = Path(self.default_export_dir)

        folder = safe_ask_directory(parent=self, title=self.tr("sec_export_title"), initialdir=initial)
        if folder:
            self.output_directory = Path(folder)
            self.lbl_output_dir.configure(
                text=f"{self.tr('out_dir_custom')}{self.output_directory}",
                text_color=TEXT_TITLE
            )

    def _on_cancel_processing(self):
        """Requests cancellation of ongoing analysis/cutting."""
        if self.is_processing:
            self.cancel_event.set()
            self.lbl_status.configure(text="Rušení operace, čekejte prosím...")
            self.btn_cancel.configure(state="disabled")

    def _on_open_result_folder(self):
        """Reveals output files in the OS file explorer."""
        target = self.last_output_path
        if not target and self.output_directory:
            target = self.output_directory
        elif not target and self.current_video_path:
            target = self.current_video_path.parent
        elif not target and self.default_export_dir and Path(self.default_export_dir).is_dir():
            target = Path(self.default_export_dir)
        elif not target:
            vids = Path.home() / "Videos"
            target = vids if vids.is_dir() else Path.home()

        if target:
            open_folder_in_file_manager(target)

    def _show_error(self, message: str):
        messagebox.showerror("Chyba", message)
        self.lbl_status.configure(text=f"Chyba: {message.splitlines()[0]}")

    # -------------------------------------------------------------------------
    # Core Processing Pipeline
    # -------------------------------------------------------------------------

    def _on_start_processing(self):
        """Validates inputs and spawns the background pipeline thread."""
        is_ok, msg = verify_binaries()
        if not is_ok:
            self._prompt_ffmpeg_download()
            return

        if not self.current_video_path or not self.current_video_path.exists():
            messagebox.showwarning("Upozornění", "Nejprve vyberte existující video soubor.")
            return

        selected_format_label = self.format_var.get().lower()
        export_edl = "edl" in selected_format_label
        export_mp4 = "mp4" in selected_format_label

        selected_mode_label = self.mode_var.get().lower()
        mode = "highlights" if "highlight" in selected_mode_label else "remove_silence"

        # Parse target duration
        target_str = self.target_dur_var.get()
        target_duration_sec: Optional[float] = None
        import re
        dur_match = re.search(r"(\d+)\s*min", target_str, re.IGNORECASE)
        if dur_match:
            target_duration_sec = float(dur_match.group(1)) * 60.0

        # Prepare UI for processing state
        self.is_processing = True
        self._proc_start_time = time.time()
        self._last_eta_calc_time = 0.0
        self._cached_eta_str = ""
        dur_sec = self.video_metadata.get("duration", 7200.0) if self.video_metadata else 7200.0
        self._eta_smoothed = max(35.0, (dur_sec / 150.0) + (25.0 if export_mp4 else 5.0))
        self.cancel_event.clear()
        self.btn_process.configure(state="disabled")
        self.btn_select_file.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.result_card.pack_forget()
        self.status_row.pack(fill="x", padx=16, pady=(0, 10))
        self.progress_bar.set(0.0)
        self.lbl_progress_pct.configure(text="0 %")

        # Collect parameters
        track_str = self.audio_track_var.get()
        track_idx = 0
        if self.video_metadata and "audio_tracks" in self.video_metadata:
            for t in self.video_metadata["audio_tracks"]:
                if t["label"] == track_str:
                    track_idx = t["track_index"]
                    break

        params = {
            "video_path": self.current_video_path,
            "track_index": track_idx,
            "threshold_db": float(self.slider_threshold.get()),
            "mode": mode,
            "target_duration_sec": target_duration_sec,
            "padding_before": float(self.slider_pad_before.get()),
            "padding_after": float(self.slider_pad_after.get()),
            "min_gap": float(self.slider_gap.get()),
            "use_facecam_ai": self.facecam_ai_var.get(),
            "open_editor": bool(self.review_segments_var.get()) if hasattr(self, "review_segments_var") else True,
            "export_edl": export_edl,
            "export_mp4": export_mp4,
            "output_dir": self.output_directory or self.current_video_path.parent,
        }

        # Spawn worker thread
        self.processing_thread = threading.Thread(
            target=self._processing_worker,
            args=(params,),
            daemon=True
        )
        self.processing_thread.start()

    def _processing_worker(self, params: Dict):
        """Background thread executing analysis, merging, EDL, and video cutting."""
        video_path: Path = params["video_path"]
        output_dir: Path = params["output_dir"]
        track_idx: int = params["track_index"]
        threshold_db: float = params["threshold_db"]
        mode: str = params["mode"]
        target_dur_sec: Optional[float] = params["target_duration_sec"]
        pad_before: float = params["padding_before"]
        pad_after: float = params["padding_after"]
        min_gap: float = params["min_gap"]
        use_facecam_ai: bool = params.get("use_facecam_ai", False)
        open_editor: bool = params.get("open_editor", True)
        export_edl: bool = params["export_edl"]
        export_mp4: bool = params["export_mp4"]

        try:
            # 1. Inspect metadata if not already available
            if not self.video_metadata:
                self._update_progress(0.05, "Načítání metadat videa...")
                meta = get_video_metadata(video_path)
            else:
                meta = self.video_metadata

            total_duration = meta.get("duration", 0.0)
            fps = meta.get("fps", 30.0)
            threads = self._get_configured_threads()

            # 2. Audio Analysis (FFmpeg streaming + NumPy RMS)
            self._update_progress(0.08, "Zahajuji analýzu hlasitosti audia...")

            def analysis_cb(fraction: float, message: str):
                p = 0.10 + (fraction * 0.52)
                self._update_progress(p, message)

            # Pro cílovou délku (např. 10, 15, 20, 30 min) nasbíráme dostatečně
            # široký pool kandidátních momentů (včetně živého mluvení, smíchu a reakcí),
            # ze kterých následně AI vybere ty nejlepší a nejhlasitější pro naplnění stopáže.
            effective_thresh = threshold_db
            if mode == "highlights" and target_dur_sec and target_dur_sec > 0:
                effective_thresh = min(threshold_db, -17.5)

            raw_segments = analyze_audio_stream(
                video_path=video_path,
                track_index=track_idx,
                total_duration=total_duration,
                threshold_db=effective_thresh,
                mode=mode,
                padding_before=pad_before,
                padding_after=pad_after,
                threads=threads,
                progress_callback=analysis_cb,
                cancel_event=self.cancel_event
            )

            if self.cancel_event.is_set():
                self._on_finished_ui(cancelled=True)
                return

            if not raw_segments:
                self._on_finished_ui(error_msg="Nebyly detekovány žádné momenty odpovídající zadanému prahu hlasitosti.")
                return

            # 3. Intelligent segment merging
            self._update_progress(0.64, f"Inteligentní slučování segmentů (detekováno {len(raw_segments)} kandidátů)...")
            merged_segments = merge_overlapping_segments(
                raw_segments,
                min_gap=min_gap,
                min_duration=0.5
            )

            facecam_active = False
            # 3.5 Facecam AI Vision Pass (if enabled and in highlights mode)
            if use_facecam_ai and mode == "highlights" and merged_segments:
                self._update_progress(0.66, "Příprava Facecam AI (kontrola modelů YuNet a detektoru reakcí)...")
                models_ok = ensure_ai_models_present(
                    progress_callback=lambda msg: self._update_progress(0.66, msg)
                )
                if models_ok:
                    facecam_active = True
                    def ai_progress(pct: float, msg: str):
                        p = 0.67 + (pct / 100.0) * 0.08
                        self._update_progress(p, f"{msg}")

                    merged_segments = analyze_candidate_facecam_segments(
                        video_path=video_path,
                        candidate_segments=merged_segments,
                        sample_fps=2.0,
                        threads=threads,
                        progress_callback=ai_progress,
                        cancel_event=self.cancel_event
                    )

                    if self.cancel_event.is_set():
                        self._on_finished_ui(cancelled=True)
                        return

            all_candidate_segments = list(merged_segments)

            # 4. Limit to target duration if requested (prioritizes highest hype/loudness peaks)
            if target_dur_sec and target_dur_sec > 0:
                self._update_progress(0.70, f"Výběr doporučených momentů pro cílovou délku {int(target_dur_sec//60)} min...")
                recommended_segments = limit_segments_to_target_duration(
                    all_candidate_segments,
                    max_duration_sec=target_dur_sec
                )
            else:
                recommended_segments = list(all_candidate_segments)

            # Uložit do cache a historie po úspěšné audio analýze (proces je hotový)
            self._save_project_cache(
                video_path=video_path,
                all_segments=all_candidate_segments,
                recommended_segments=recommended_segments,
                target_dur_sec=target_dur_sec,
                stats={"original_duration_sec": total_duration, "total_segments": len(all_candidate_segments)},
                output_files=None
            )

            # 4.5 Interactive Segment Review & Video Preview Editor (Option A)
            if open_editor and all_candidate_segments:
                self._update_progress(0.70, self.tr("status_waiting_editor"))
                editor_event = threading.Event()
                editor_result = {"confirmed": False, "segments": []}

                def show_editor():
                    self._show_dim_overlay()
                    dlg = SegmentReviewDialog(
                        parent=self,
                        video_path=video_path,
                        all_segments=all_candidate_segments,
                        recommended_segments=recommended_segments,
                        target_duration_sec=target_dur_sec,
                        current_lang=self.current_language,
                        on_confirm=lambda chosen: on_editor_done(True, chosen),
                        on_cancel=lambda: on_editor_done(False, [])
                    )
                    dlg.lift()
                    dlg.focus_force()

                def on_editor_done(confirmed: bool, chosen: List[Tuple]):
                    self._hide_dim_overlay()
                    editor_result["confirmed"] = confirmed
                    editor_result["segments"] = chosen
                    editor_event.set()

                self.after(0, show_editor)
                editor_event.wait()

                if self.cancel_event.is_set() or not editor_result["confirmed"]:
                    self._on_finished_ui(cancelled=True)
                    return

                merged_segments = editor_result["segments"]
            else:
                merged_segments = recommended_segments

            if not merged_segments:
                self._on_finished_ui(error_msg="Po výběru nezůstal žádný segment k sestříhání.")
                return

            stats = calculate_cut_statistics(total_duration, merged_segments)
            stats["facecam_active"] = facecam_active
            base_name = video_path.stem
            suffix_mode = "highlights" if mode == "highlights" else "nosilence"

            generated_files = []

            # 5. EDL Export
            if export_edl:
                self._update_progress(0.70, "Generování CMX 3600 EDL souboru...")
                edl_filename = f"{base_name}_SnapCut_{suffix_mode}.edl"
                edl_path = output_dir / edl_filename
                generate_cmx3600_edl(
                    segments=merged_segments,
                    video_source_path=video_path,
                    output_edl_path=edl_path,
                    fps=fps,
                    title=f"SNAPCUT_{suffix_mode.upper()}"
                )
                generated_files.append(edl_path)
                self.last_output_path = edl_path

            # 6. MP4 Lossless Video Cut
            if export_mp4:
                self._update_progress(0.75, "Příprava bezztrátového střihu videa (SnapCut FFmpeg concat)...")

                def cut_cb(fraction: float, message: str):
                    p = 0.75 + (fraction * 0.23)
                    self._update_progress(p, message)

                ext = video_path.suffix if video_path.suffix.lower() in [".mp4", ".mkv", ".mov"] else ".mp4"
                out_video_name = f"{base_name}_SnapCut_{suffix_mode}_cut{ext}"
                out_video_path = output_dir / out_video_name

                cut_res = cut_video_lossless(
                    input_video_path=video_path,
                    segments=merged_segments,
                    output_video_path=out_video_path,
                    threads=threads,
                    progress_callback=cut_cb,
                    cancel_event=self.cancel_event
                )

                if self.cancel_event.is_set():
                    self._on_finished_ui(cancelled=True)
                    return

                if cut_res:
                    generated_files.append(cut_res)
                    self.last_output_path = cut_res

            # 7. Completed successfully
            self._update_progress(1.0, "Zpracování úspěšně dokončeno!")
            self._save_project_cache(
                video_path=video_path,
                all_segments=all_candidate_segments,
                recommended_segments=merged_segments,
                target_dur_sec=target_dur_sec,
                stats=stats,
                output_files=generated_files
            )
            self._on_finished_ui(stats=stats, generated_files=generated_files)

        except Exception as e:
            self._on_finished_ui(error_msg=f"Neočekávaná chyba při zpracování:\n{e}")

    def _update_progress(self, fraction: float, message: str):
        """Thread-safe UI update for progress bar and status label with percentage and conservative ETA."""
        def update():
            clamped = min(max(fraction, 0.0), 1.0)
            self.progress_bar.set(clamped)
            pct = int(round(clamped * 100))

            eta_str = ""
            start_t = getattr(self, "_proc_start_time", None)
            now = time.time()

            if start_t and 0.02 <= clamped < 0.99:
                last_calc = getattr(self, "_last_eta_calc_time", 0.0)
                cached = getattr(self, "_cached_eta_str", "")
                if (now - last_calc) >= 1.2 or not cached:
                    self._last_eta_calc_time = now
                    elapsed = max(0.5, now - start_t)

                    rate = clamped / elapsed
                    raw_remaining = (1.0 - clamped) / max(0.00005, rate)

                    curr_eta = getattr(self, "_eta_smoothed", raw_remaining)
                    # Plynulý odhad bez okamžitého propadu na 1s
                    self._eta_smoothed = 0.85 * curr_eta + 0.15 * raw_remaining

                    rem = int(round(self._eta_smoothed))
                    if rem >= 3600:
                        h, r = divmod(rem, 3600)
                        m = r // 60
                        eta_val = f"~{h}h {m:02d}m"
                    elif rem >= 60:
                        m, s = divmod(rem, 60)
                        eta_val = f"~{m}m {s:02d}s"
                    else:
                        eta_val = f"~{max(2, rem)}s"

                    if self.current_language == "cs":
                        self._cached_eta_str = f" (Zbývá {eta_val})"
                    else:
                        self._cached_eta_str = f" ({eta_val} left)"

                eta_str = getattr(self, "_cached_eta_str", "")

            full_text = f"{pct}%{eta_str} • {message}"
            self.lbl_status.configure(text=full_text)
            if hasattr(self, "lbl_progress_pct") and self.lbl_progress_pct.winfo_exists():
                self.lbl_progress_pct.configure(text=f"{pct} %")
        self.after(0, update)

    def _on_finished_ui(
        self,
        stats: Optional[Dict] = None,
        generated_files: Optional[List[Path]] = None,
        error_msg: Optional[str] = None,
        cancelled: bool = False
    ):
        """Thread-safe UI restoration after job completion, cancellation, or error."""
        def restore():
            self.is_processing = False
            self.btn_process.configure(state="normal")
            self.btn_select_file.configure(state="normal")
            self.btn_cancel.configure(state="disabled")

            if cancelled:
                self.progress_bar.set(0.0)
                if hasattr(self, "lbl_progress_pct") and self.lbl_progress_pct.winfo_exists():
                    self.lbl_progress_pct.configure(text="")
                self.result_card.pack_forget()
                if hasattr(self, "status_row") and self.status_row.winfo_exists():
                    self.status_row.pack(fill="x", padx=16, pady=(0, 10))
                self.lbl_status.configure(text="Zpracování bylo zrušeno uživatelem.")
                messagebox.showinfo("Zrušeno", "Operace byla zrušena.")
            elif error_msg:
                self.result_card.pack_forget()
                if hasattr(self, "lbl_progress_pct") and self.lbl_progress_pct.winfo_exists():
                    self.lbl_progress_pct.configure(text="")
                if hasattr(self, "status_row") and self.status_row.winfo_exists():
                    self.status_row.pack(fill="x", padx=16, pady=(0, 10))
                self.lbl_status.configure(text="Zpracování selhalo.")
                messagebox.showerror("Chyba zpracování", error_msg)
            else:
                self.progress_bar.set(1.0)
                if hasattr(self, "lbl_progress_pct") and self.lbl_progress_pct.winfo_exists():
                    self.lbl_progress_pct.configure(text="100 %")
                if hasattr(self, "status_row") and self.status_row.winfo_exists():
                    self.status_row.pack_forget()
                self.result_card.pack(anchor="w", padx=16, pady=(2, 12))
                if getattr(self, "auto_open_folder", True):
                    self.after(600, self._on_open_result_folder)
                self._refresh_cache_display()

        self.after(0, restore)


def main():
    app = AutoClipApp()
    app.mainloop()


if __name__ == "__main__":
    main()
