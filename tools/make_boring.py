#!/usr/bin/env python3
"""Rebuild harihud-boring from harihud-3.0.

Copies this HUD into ../harihud-boring (next to this repo), then:
  * swaps the sakura colours for hypno red / blue in .res/.txt files
  * recolours every texture (VTF and PNG) that uses the sakura colours
  * removes the sakura branches from the class selection menu
and commits the result in harihud-boring.

Usage:
    python3 tools/make_boring.py              # rebuild + commit
    python3 tools/make_boring.py --no-commit  # rebuild only
    python3 tools/make_boring.py --force      # overwrite uncommitted edits in harihud-boring

Never edit harihud-boring by hand: the next run overwrites it.
Boring-only changes belong in this script.

Needs Python 3 with numpy and Pillow.
"""
import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
SAKURA_RED = (214, 180, 214)
SAKURA_BLUE = (178, 180, 225)
SAKURA_BLUE_WHEEL = (178, 180, 255)  # the taunt/disguise wheel PNGs use this one
HYPNO_RED = (238, 54, 54)
HYPNO_BLUE = (85, 163, 238)

# sakura colour -> hypno colour, used for textures
TEXTURE_MAP = [
    (SAKURA_RED, HYPNO_RED),
    (SAKURA_BLUE, HYPNO_BLUE),
    (SAKURA_BLUE_WHEEL, HYPNO_BLUE),
]
# colours that sakura pixels get blended with at their edges
# (TanLight outline, black, white, black_bright_hari)
BLEND_BASES = [(235, 226, 202), (0, 0, 0), (255, 255, 255), (27, 27, 27)]

# plain text replacements in .res / .txt files
TEXT_REPLACE = [
    ("sakura_red_hari", "red_hypno_hari"),
    ("sakura_blue_hari", "blue_hypno_hari"),
    ('"214 180 214', '"238 54 54'),
    ('"178 180 225', '"85 163 238'),
    ('"194 180 214', '"218 34 34'),  # Team menu red hover (darker sakura)
    ('"158 180 225', '"65 143 218'),  # Team menu blue hover (darker sakura)
]
# lines removed from clientscheme.res (the sakura colour definitions)
SCHEME_DROP = re.compile(r'^[ \t]*"sakura_(red|blue)_hari"[^\n]*\n', re.M)

# panels removed from .res files: file -> panel names
REMOVE_PANELS = {
    "resource/ui/classselection.res": ["SakuraBranchLeft", "SakuraBranchRight"],
}
# files deleted from the boring copy (glob patterns)
REMOVE_FILES = [
    "materials/vgui/replay/thumbnails/panels/sakura_branch_*",
]
# textures never recoloured (paths relative to the HUD root)
TEXTURE_SKIP = {
    "materials/vgui/replay/thumbnails/bunny_calm.vtf",
}
# folders whose textures are never recoloured (pictures, not UI shapes)
TEXTURE_SKIP_DIRS = (
    "materials/vgui/replay/thumbnails/menu/",
)
# not copied into harihud-boring
COPY_EXCLUDE = {".git", "tools"}

MIN_SAKURA_PIXELS = 8  # a texture needs this many pure sakura pixels to be recoloured
MIN_SAKURA_SHARE = 0.01  # ...and they must be at least this share of its visible pixels
MAX_DXT_SIZE = 512  # DXT textures get re-saved as uncompressed at this size at most

# --------------------------------------------------------------------------
# Colour maths
# --------------------------------------------------------------------------


def recolour_rgb(rgb):
    """rgb: (N,3) uint8. Returns recoloured copy.

    Each pixel is matched as   t * sakura + (1 - t) * base   and replaced by
    t * hypno + (1 - t) * base, so anti-aliased edges and shades keep their look.
    """
    c = rgb.astype(np.float32)
    best_err = np.full(len(c), np.inf, np.float32)
    out = c.copy()
    for S, H in TEXTURE_MAP:
        S = np.array(S, np.float32)
        H = np.array(H, np.float32)
        for K in BLEND_BASES:
            K = np.array(K, np.float32)
            v = S - K
            t = np.clip(((c - K) @ v) / (v @ v), 0, 1)
            fit = K + t[:, None] * v
            err = ((fit - c) ** 2).sum(1)
            new = K + t[:, None] * (H - K)
            take = (err < best_err) & (err < 14 * 14) & (t > 0.08)
            out[take] = new[take]
            best_err = np.minimum(best_err, np.where((err < 14 * 14) & (t > 0.08), err, np.inf))
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def has_sakura(rgba):
    """True when a texture clearly uses the sakura colours (not just a few stray
    pixels in a picture). rgba: (N,4) uint8"""
    vis = rgba[rgba[:, 3] >= 20][:, :3].astype(np.int32)
    n = 0
    for S, _ in TEXTURE_MAP:
        n += int((((vis - np.array(S)) ** 2).sum(1) < 20 * 20).sum())
    return n >= MIN_SAKURA_PIXELS and n >= MIN_SAKURA_SHARE * len(vis)


def recolour_rgba(rgba):
    out = rgba.copy()
    vis = out[:, 3] > 0
    out[vis, :3] = recolour_rgb(out[vis, :3])
    return out


# --------------------------------------------------------------------------
# VTF
# --------------------------------------------------------------------------
FMT_BGRA8888 = 12
FMT_DXT1 = 13
FMT_DXT5 = 15


def vtf_header(d):
    w, h = struct.unpack_from("<HH", d, 16)
    frames = struct.unpack_from("<H", d, 24)[0]
    fmt = struct.unpack_from("<i", d, 52)[0]
    mips = d[56]
    return w, h, frames, fmt, mips


def write_bgra_vtf(path, img):
    """Uncompressed BGRA8888 VTF 7.2 with a full mip chain."""
    w, h = img.size
    mips = [img]
    while mips[-1].width > 1 or mips[-1].height > 1:
        m = mips[-1]
        mips.append(m.resize((max(1, m.width // 2), max(1, m.height // 2)), Image.LANCZOS))
    flags = 0x2000 | 0x0004 | 0x0008  # eightbitalpha, clamps, clampt
    hdr = struct.pack(
        "<4sIIIHHIHH4x3f4xfiBiBBH",
        b"VTF\0", 7, 2, 80, w, h, flags, 1, 0,
        1.0, 1.0, 1.0, 1.0, FMT_BGRA8888, len(mips), -1, 0, 0, 1,
    ).ljust(80, b"\0")
    data = b"".join(m.tobytes("raw", "BGRA") for m in reversed(mips))
    Path(path).write_bytes(hdr + data)


def process_vtf(path):
    d = bytearray(Path(path).read_bytes())
    w, h, frames, fmt, mips = vtf_header(d)
    if fmt == FMT_BGRA8888:
        size = sum(max(1, w >> i) * max(1, h >> i) * 4 * frames for i in range(mips))
        start = len(d) - size
        top = np.frombuffer(bytes(d[-w * h * 4:]), np.uint8).reshape(-1, 4)[:, [2, 1, 0, 3]]
        if not has_sakura(top):
            return False
        px = np.frombuffer(bytes(d[start:]), np.uint8).reshape(-1, 4)
        rgba = px[:, [2, 1, 0, 3]]
        new = recolour_rgba(rgba)[:, [2, 1, 0, 3]]
        d[start:] = new.tobytes()
        Path(path).write_bytes(bytes(d))
        return True
    if fmt in (FMT_DXT1, FMT_DXT5) and frames == 1:
        bw, bh = max(4, w), max(4, h)
        top_size = (bw // 4) * (bh // 4) * (8 if fmt == FMT_DXT1 else 16)
        img = Image.frombytes("RGBA", (w, h), bytes(d[-top_size:]), "bcn", 1 if fmt == FMT_DXT1 else 3)
        rgba = np.asarray(img).reshape(-1, 4)
        if not has_sakura(rgba):
            return False
        img = Image.fromarray(recolour_rgba(rgba).reshape(h, w, 4), "RGBA")
        if max(w, h) > MAX_DXT_SIZE:
            s = MAX_DXT_SIZE / max(w, h)
            img = img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
        write_bgra_vtf(path, img)
        return True
    return False


def process_png(path):
    img = Image.open(path)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    mode = img.mode
    rgba = np.asarray(img.convert("RGBA")).reshape(-1, 4)
    if not has_sakura(rgba):
        return False
    new = Image.fromarray(recolour_rgba(rgba).reshape(img.height, img.width, 4), "RGBA")
    new.convert(mode).save(path)
    return True


# --------------------------------------------------------------------------
# Text
# --------------------------------------------------------------------------


def remove_panel(text, name):
    """Remove a top-level-in-file panel block  "name" { ... }  (nested braces ok)."""
    m = re.search(r'\n[ \t]*"%s"[ \t]*\r?\n[ \t]*\{' % re.escape(name), text)
    if not m:
        return text, False
    i = m.end()
    depth = 1
    while depth and i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    # also eat the rest of the closing line
    j = text.find("\n", i)
    j = len(text) if j == -1 else j
    return text[: m.start()] + text[j:], True


def process_text(path, rel):
    raw = Path(path).read_bytes()
    text = raw.decode("latin-1")  # byte-exact round trip, keeps CRLF
    if rel == "resource/clientscheme.res":
        text = SCHEME_DROP.sub("", text)
    for a, b in TEXT_REPLACE:
        text = text.replace(a, b)
    for name in REMOVE_PANELS.get(rel, []):
        text, ok = remove_panel(text, name)
        if not ok:
            print(f"  warning: panel {name} not found in {rel}")
    new = text.encode("latin-1")
    if new != raw:
        Path(path).write_bytes(new)
        return True
    return False


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], check=check, capture_output=True, text=True).stdout


def mirror(src, dst):
    """Make dst an exact copy of src (except COPY_EXCLUDE and dst/.git)."""
    for item in dst.iterdir():
        if item.name == ".git":
            continue
        shutil.rmtree(item) if item.is_dir() and not item.is_symlink() else item.unlink()
    for item in src.iterdir():
        if item.name in COPY_EXCLUDE:
            continue
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, symlinks=True)
        else:
            shutil.copy2(item, target)


def main():
    here = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=here, help="harihud folder (default: this repo)")
    ap.add_argument("--dst", type=Path, default=here.parent / "harihud-boring", help="boring folder")
    ap.add_argument("--no-commit", action="store_true", help="don't commit in harihud-boring")
    ap.add_argument("-v", "--verbose", action="store_true", help="list every recoloured texture")
    ap.add_argument("--force", action="store_true", help="overwrite uncommitted changes in harihud-boring")
    a = ap.parse_args()
    src, dst = a.src.resolve(), a.dst.resolve()

    if src == dst or dst in src.parents or src in dst.parents:
        sys.exit("src and dst must be separate folders")
    if not (src / "info.vdf").exists():
        sys.exit(f"{src} doesn't look like a HUD (no info.vdf)")
    if dst.exists() and any(dst.iterdir()) and not (dst / "info.vdf").exists():
        sys.exit(f"{dst} exists and isn't a HUD; refusing to overwrite it")
    dst.mkdir(parents=True, exist_ok=True)
    if not (dst / ".git").exists():
        git(dst, "init", "-q", "-b", "main")
    elif git(dst, "status", "--porcelain").strip() and not a.force:
        sys.exit(f"{dst} has uncommitted changes; commit them, or rerun with --force to overwrite them")

    print(f"copying {src.name} -> {dst}")
    mirror(src, dst)

    for pattern in REMOVE_FILES:
        for f in dst.glob(pattern):
            f.unlink()

    changed_text = changed_tex = 0
    for root, dirs, files in os.walk(dst):
        dirs[:] = [x for x in dirs if x != ".git"]
        for name in files:
            p = Path(root) / name
            rel = p.relative_to(dst).as_posix()
            low = name.lower()
            try:
                if low.endswith((".res", ".txt", ".vmt", ".vdf", ".bak")):
                    changed_text += process_text(p, rel)
                elif rel in TEXTURE_SKIP or rel.startswith(TEXTURE_SKIP_DIRS) or not rel.startswith("materials/"):
                    continue
                elif low.endswith((".vtf", ".png")):
                    if (process_vtf if low.endswith(".vtf") else process_png)(p):
                        changed_tex += 1
                        if a.verbose:
                            print("  recoloured", rel)
            except Exception as e:  # keep going, report the file
                print(f"  warning: skipped {rel}: {e}")
    print(f"recoloured {changed_tex} textures, edited {changed_text} text files")

    if a.no_commit:
        return
    git(dst, "add", "-A")
    if not git(dst, "status", "--porcelain").strip():
        print("harihud-boring is already up to date")
        return
    rev = git(src, "rev-parse", "--short", "HEAD", check=False).strip() or "unknown"
    dirty = " (with uncommitted changes)" if git(src, "status", "--porcelain", check=False).strip() else ""
    git(dst, "commit", "-q", "-m", f"sync with harihud-3.0 {rev}{dirty}")
    print(git(dst, "log", "--oneline", "-1").strip())


if __name__ == "__main__":
    main()
