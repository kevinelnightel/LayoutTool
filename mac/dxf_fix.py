"""dxf_fix.py - clean a PDMS Draft DXF export IN PLACE.

Deployed copy for LayoutTool (E:\\AVEVA\\Addin\\PMLLIB\\LayoutTool\\mac).
Source of truth: E:\\ZCode\\PDMSAgent\\tools\\dxf_clean.py

Called by dxf_fix.bat, which the DrawingExporter calls after a successful
LIEXEC export (see .FixDxf() in DrawingExporter.pmlobj).

What it fixes (all measured 2026-10-28 on a 9.2 MB PDMS export):
  * WIPEOUT entities behind every text -> white boxes that cover geometry once
    the drawing is exploded
  * 3D extrusion thickness (group 39) + polyline vertex widths (group 40/41)
    -> the sheet frame looks one size too thick
  * $EXTMIN/$EXTMAX = +/-1e20 and missing $VIEWRES/$FACETRES -> arcs look
    faceted until REGEN
  * $INSUNITS = 1 (inch) while geometry is millimetres
  * no layer lineweight -> set 0.25 mm and switch $LWDISPLAY on

Byte level only: geometry and text are never decoded, so Chinese MTEXT keeps
its ANSI (GBK) code page.

Usage:  python dxf_fix.py <file.dxf> [lineweight_0.01mm]
Exit:   0 ok/skipped, 2 bad args, 3 IO error, 4 transform produced nothing
"""
import os
import sys

VIEWRES = 20000
FACETRES = 10.0
DEFAULT_LINEWEIGHT = 25  # 0.01 mm


def read_pairs(path):
    with open(path, "rb") as f:
        raw = f.read()
    eol = b"\r\n" if b"\r\n" in raw else b"\n"
    lines = raw.split(eol)
    if lines and lines[-1] == b"":
        lines.pop()
    return [(lines[i].strip(), lines[i + 1]) for i in range(0, len(lines) - 1, 2)], eol


def looks_like_pdms_export(pairs):
    has_wipeout = any(c == b"0" and v.strip() == b"WIPEOUT" for c, v in pairs)
    has_thick = any(c == b"39" for c, v in pairs)
    return has_wipeout or has_thick


def compute_extents(pairs):
    xs, ys = [], []
    cur = None
    sec = None
    for i, (c, v) in enumerate(pairs):
        vs = v.strip()
        if c == b"0":
            cur = vs
            if vs == b"SECTION" and i + 1 < len(pairs):
                sec = pairs[i + 1][1].strip()
            continue
        if sec != b"ENTITIES":
            continue
        if cur == b"VERTEX":
            if c == b"10":
                xs.append(float(v))
            elif c == b"20":
                ys.append(float(v))
        elif cur in (b"MTEXT", b"INSERT"):
            if c == b"10":
                xs.append(float(v))
            elif c == b"20":
                ys.append(float(v))
    cur = None
    cx = cy = None
    for c, v in pairs:
        if c == b"0":
            cur = v.strip()
            continue
        if cur == b"ARC":
            if c == b"10":
                cx = float(v)
            elif c == b"20":
                cy = float(v)
            elif c == b"40" and cx is not None and cy is not None:
                r = float(v)
                xs += [cx - r, cx + r]
                ys += [cy - r, cy + r]
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def transform(pairs, lineweight):
    ext = compute_extents(pairs)
    out = []
    cur = None
    skip = False
    stats = {"wipeout": 0, "thick": 0, "width": 0, "lw": 0,
             "viewres": False, "facetres": False, "ext": ext}

    def fnum(code, value):
        out.append((code, b" %.6f" % value))

    i = 0
    while i < len(pairs):
        c, v = pairs[i]
        vs = v.strip()

        if c == b"0":
            cur = vs
            if vs == b"WIPEOUT":
                skip = True
                stats["wipeout"] += 1
            else:
                skip = False
                out.append((c, v))
            i += 1
            continue
        if skip:
            i += 1
            continue

        if c == b"9":
            if vs == b"$EXTMIN" and ext:
                out.append((b"9", b"$EXTMIN"))
                fnum(b"10", ext[0])
                fnum(b"20", ext[1])
                out.append((b"30", b" 0.0"))
                i += 4
                continue
            if vs == b"$EXTMAX" and ext:
                out.append((b"9", b"$EXTMAX"))
                fnum(b"10", ext[2])
                fnum(b"20", ext[3])
                out.append((b"30", b" 0.0"))
                if not stats["viewres"]:
                    out.append((b"9", b"$VIEWRES"))
                    out.append((b"70", b" " + str(VIEWRES).encode()))
                    stats["viewres"] = True
                if not stats["facetres"]:
                    out.append((b"9", b"$FACETRES"))
                    out.append((b"40", b" %.1f" % FACETRES))
                    stats["facetres"] = True
                i += 4
                continue
            if vs == b"$INSUNITS":
                out.append((c, v))
                out.append((pairs[i + 1][0], b"     4"))
                i += 2
                continue
            if vs == b"$LWDISPLAY":
                out.append((c, v))
                out.append((pairs[i + 1][0], b"     1"))
                i += 2
                continue
            if vs == b"$VIEWRES":
                out.append((c, v))
                out.append((b"70", b" " + str(VIEWRES).encode()))
                stats["viewres"] = True
                i += 2
                continue
            if vs == b"$FACETRES":
                out.append((c, v))
                out.append((b"40", b" %.1f" % FACETRES))
                stats["facetres"] = True
                i += 2
                continue

        if c == b"39":
            stats["thick"] += 1
            i += 1
            continue
        if cur == b"VERTEX" and c in (b"40", b"41"):
            stats["width"] += 1
            i += 1
            continue
        if cur == b"LAYER" and c == b"370":
            out.append((c, b"    " + str(lineweight).encode()))
            stats["lw"] += 1
            i += 1
            continue

        out.append((c, v))
        i += 1

    return out, stats


def _base_dir():
    """Exe 所在目录。PyInstaller onefile 下 __file__ 指向解包临时目录，
    必须用 sys.executable，否则会去临时目录找 dxf_fix_req.txt 而永远找不到。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _base_dir()


def read_request():
    """PML cannot substitute $! inside SYSCOM's |...| command line, so
    DrawingExporter.FixDxf() writes the target path to dxf_fix_req.txt and the
    bat runs without arguments; we pick it up here and remove it."""
    req = os.path.join(BASE_DIR, "dxf_fix_req.txt")
    if not os.path.isfile(req):
        return None, None
    with open(req, "r", encoding="utf-8-sig") as f:
        path = f.read().strip().splitlines()[0].strip()
    try:
        os.remove(req)
    except OSError:
        pass
    return path, req


def fix_one(path, lw):
    """Clean one DXF in place. Returns 0 ok/skip, 2/3/4 as before."""
    if not os.path.isfile(path):
        print("[dxf_fix] not a file: %s" % path)
        return 2

    pairs, eol = read_pairs(path)
    if not looks_like_pdms_export(pairs):
        print("[dxf_fix] skip (no WIPEOUT / thickness found): %s" % path)
        return 0

    out, st = transform(pairs, lw)
    if not out:
        print("[dxf_fix] ERROR empty result, original kept")
        return 4

    tmp = path + ".tmpfix"
    try:
        with open(tmp, "wb") as f:
            for c, v in out:
                f.write(c + eol + v + eol)
        os.replace(tmp, path)
    except OSError as e:
        print("[dxf_fix] ERROR %s" % e)
        try:
            os.remove(tmp)
        except OSError:
            pass
        return 3

    print("[dxf_fix] %s" % os.path.basename(path))
    print("          wipeout %d | thickness %d | vertex width %d | layer lw %d"
          % (st["wipeout"], st["thick"], st["width"], st["lw"]))
    if st["ext"]:
        print("          extents %.1f,%.1f .. %.1f,%.1f" % st["ext"])
    return 0


def main(argv):
    # batch: dxf_fix.exe a.dxf b.dxf ... -> 逐个处理，全部跑完再返回
    if len(argv) > 1:
        lw = DEFAULT_LINEWEIGHT
        paths = argv[1:]
        # 允许最后一个参数是线宽（纯数字且至少还有两个参数时按线宽解释）
        if len(paths) >= 2 and paths[-1].isdigit():
            lw = int(paths[-1])
            paths = paths[:-1]
        rc = 0
        for p in paths:
            r = fix_one(p, lw)
            if r != 0:
                rc = r
        return rc
    path, _ = read_request()
    if not path:
        print("[dxf_fix] no argument and no dxf_fix_req.txt - nothing to do")
        return 2
    return fix_one(path, DEFAULT_LINEWEIGHT)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
