#!/usr/bin/env python3
"""Generate version-aware stub shared libraries for headless Qt.

The sandbox lacks the native GL/EGL/xkb/pulse/NSS/xcb libraries that the
PyQt6-bundled Qt links against. In offscreen mode Qt never calls most of
them, so empty-but-complete stubs let the legacy UI import and run its test
suite. This is a test-environment tool only — nothing here ships.

Symbols referenced *with* a version tag (e.g. ``PK11_SetPasswordFunc@
NSS_3.2``) are defined once per version via ``.symver`` aliases, exactly
like glibc does for its own versioned symbols.

Usage: python3 make_qt_stubs.py <output-dir> [libname ...]
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

QT_ROOT = "/usr/local/lib/python3.11/dist-packages/PyQt6"
QT_SCAN = (
    f"{QT_ROOT}/Qt6/lib/*.so* {QT_ROOT}/*.so* "
    f"{QT_ROOT}/Qt6/plugins/*/*.so* {QT_ROOT}/Qt6/plugins/*/*/*.so* "
    f"{QT_ROOT}/Qt6/libexec/*"
)

# libname -> symbol prefixes it must provide
WANTED = {
    "libEGL.so.1": ["egl"],
    "libGL.so.1": ["gl"],
    "libxkbcommon.so.0": ["xkb"],
    "libpulse.so.0": ["pa_"],
    "libdbus-1.so.3": ["dbus_"],
    "libasound.so.2": ["snd_"],
    "libxcb-dri3.so.0": ["xcb_dri3"],
    "libxcb-cursor.so.0": ["xcb_cursor"],
    "libxcb-icccm.so.4": ["xcb_icccm"],
    "libxcb-keysyms.so.1": ["xcb_key"],
    "libnss3.so": ["NSS", "CERT_", "SEC", "PR_", "PL_", "PK11_", "SECMOD", "SSL_"],
    "libnssutil3.so": ["NSS_", "SEC", "_NSS", "PK11_", "SECMOD"],
    "libsmime3.so": ["NSS", "SEC", "CERT_"],
    "libssl3.so": ["SSL"],
    "libnspr4.so": ["PR_", "PL_"],
    "libplc4.so": ["PL_"],
    "libplds4.so": ["PL_"],
    "libdrm.so.2": ["drm"],
    "libgbm.so.1": ["gbm"],
    "libX11-xcb.so.1": ["XGetXCB", "Xxcb"],
    "libXcomposite.so.1": ["Xcomposite"],
    "libXdamage.so.1": ["Xdamage"],
    "libXfixes.so.3": ["Xfixes"],
    "libXrandr.so.2": ["XRR", "Xrandr"],
    "libXtst.so.6": ["XTest", "Xtst"],
    "libpcsclite.so.1": ["SCard"],
    "libwayland-client.so.0": ["wl_"],
    "libwayland-cursor.so.0": ["wl_cursor"],
    "libxcb-image.so.0": ["xcb_image"],
    "libxcb-randr.so.0": ["xcb_randr"],
    "libxcb-render-util.so.0": ["xcb_render_util"],
    "libxcb-render.so.0": ["xcb_render"],
    "libxcb-shape.so.0": ["xcb_shape"],
    "libxcb-shm.so.0": ["xcb_shm"],
    "libxcb-sync.so.1": ["xcb_sync"],
    "libxcb-util.so.1": ["xcb_util"],
    "libxcb-xfixes.so.0": ["xcb_xfixes"],
    "libxcb-xkb.so.1": ["xcb_xkb"],
    "libxkbcommon-x11.so.0": ["xkb_x11"],
    "libxkbfile.so.1": ["xkbfile"],
}

_NM_CACHE: str | None = None


def undefined_refs() -> list[tuple[str, str | None]]:
    """(symbol, version) pairs referenced by any Qt/PyQt6 binary."""
    global _NM_CACHE
    if _NM_CACHE is None:
        _NM_CACHE = subprocess.run(
            f"nm -D --undefined-only {QT_SCAN} 2>/dev/null",
            shell=True, capture_output=True, text=True,
        ).stdout
    refs: list[tuple[str, str | None]] = []
    for line in _NM_CACHE.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        full = parts[-1]
        if full.startswith("_Jv"):
            continue
        if "@" in full:
            symbol, version = full.split("@", 1)
            if version:
                refs.append((symbol, version))
        else:
            refs.append((full, None))
    return refs


def version_needs() -> dict[str, set[str]]:
    """dependency soname -> version nodes required from it (across Qt libs)."""
    out: dict[str, set[str]] = {}
    text = subprocess.run(
        f"readelf -V {QT_SCAN} 2>/dev/null",
        shell=True, capture_output=True, text=True,
    ).stdout
    file_re = re.compile(r"File: (\S+)\s+Cnt: \d+")
    name_re = re.compile(r"Name: (\S+)")
    current = None
    for line in text.splitlines():
        match = file_re.search(line)
        if match:
            current = match.group(1)
            continue
        name = name_re.search(line)
        if name and current:
            out.setdefault(current, set()).add(name.group(1))
    return out


def build(out_dir: Path, libname: str, prefixes: list[str], _family_versions: set[str] | None = None) -> None:
    lowered = [prefix.lower() for prefix in prefixes]
    family_versions = _family_versions or set()
    refs = [
        (symbol, version)
        for symbol, version in undefined_refs()
        if any(symbol.lower().startswith(prefix) for prefix in lowered)
        or (version and version in family_versions)
    ]
    # symbols we must define: each versioned ref exactly once, plus plain refs
    versioned: dict[str, set[str]] = {}
    plain: set[str] = set()
    for symbol, version in refs:
        if version:
            versioned.setdefault(version, set()).add(symbol)
        else:
            plain.add(symbol)
    # a symbol referenced both plain and versioned: define plain default too
    for version, symbols in versioned.items():
        for symbol in symbols:
            if any(s == symbol and v is None for s, v in refs):
                plain.add(symbol)

    # version nodes that must merely EXIST (readelf version-needs)
    for version in version_needs().get(libname, set()):
        if version not in versioned:
            versioned[version] = set()

    lines = ["void __jmdb_stub(void) {}"]
    script_nodes: list[str] = []
    index = 0
    for symbol in sorted(plain):
        lines.append(f"void {symbol}(void) {{}}")
    for version in sorted(versioned):
        node = [f"{version} {{", "  global:", "    __jmdb_stub;"]
        for symbol in sorted(versioned[version]):
            index += 1
            lines.append(f"void __stub_{index}(void) {{}}")
            lines.append(f'__asm__(".symver __stub_{index},{symbol}@{version}");')
            node.append(f"    {symbol};")
        node.append("};")
        script_nodes.append("\n".join(node))
    if plain:
        node = ["JMDB_STUB_DEFAULT {", "  global:"]
        node += [f"    {symbol};" for symbol in sorted(plain)]
        node += ["  local:", "    *;", "};"]
        script_nodes.append("\n".join(node))

    c_file = out_dir / "stub.c"
    c_file.write_text("\n".join(lines) + "\n")
    cmd = ["gcc", "-shared", "-fPIC", "-o", str(out_dir / libname), str(c_file)]
    if script_nodes:
        ld_file = out_dir / "stub.ld"
        ld_file.write_text("\n\n".join(script_nodes) + "\n")
        cmd += ["-Wl,--version-script", str(ld_file)]
    subprocess.run(cmd, check=True)
    total = len(plain) + sum(len(s) for s in versioned.values())
    print(f"{libname}: {total} symbol defs "
          f"(plain={len(plain)}, versions={sorted(versioned)})")


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out_dir.mkdir(parents=True, exist_ok=True)
    targets = sys.argv[2:] or list(WANTED)
    needs = version_needs()
    nss_family = {
        "libnss3.so", "libnssutil3.so", "libsmime3.so", "libssl3.so",
        "libnspr4.so", "libplc4.so", "libplds4.so",
    }
    nss_versions = set()
    for soname in nss_family:
        nss_versions.update(needs.get(soname, set()))
    # never claim versions owned by glibc/openssl — the stub must not shadow
    # the real system libraries
    nss_versions = {v for v in nss_versions if v.startswith(("NSS", "NSPR"))}
    for libname in targets:
        family = nss_versions if libname in nss_family else None
        build(out_dir, libname, WANTED[libname], family)
    return 0


if __name__ == "__main__":
    sys.exit(main())
