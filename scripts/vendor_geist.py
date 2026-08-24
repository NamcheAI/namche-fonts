#!/usr/bin/env python3
"""Vendor the upstream Geist variable webfonts from the pinned npm package.

Namche applications use Geist as their body font, so the release ships the
upstream Geist Sans variable faces alongside the Namche Shadow families and
serves them from the same CDN release. Unlike the Namche Shadow families,
fonts/Geist is a byte-faithful copy of Vercel's published binaries: never
rename its metadata or regenerate it by hand. Update it by bumping
sources/geist-upstream.json and rerunning this script; verify it with
--check, which re-downloads the pinned tarball and byte-compares.

Geist Mono and Geist Pixel are deliberately not vendored: Namche Shadow
Mono and Pixel are outline-identical renamed derivatives of the same
binaries and already ship in this release.

Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import sys
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
LOCK_FILE = ROOT / "sources" / "geist-upstream.json"
FAMILY_ROOT = ROOT / "fonts" / "Geist"

# Tarball member -> path below fonts/Geist. Upstream file names are kept:
# build-webfont-css.mjs already parses the Variable and Italic[wght]
# suffixes as variable faces.
VENDORED_FILES = {
    "package/dist/fonts/geist-sans/Geist-Variable.woff2": "webfonts/Geist-Variable.woff2",
    "package/dist/fonts/geist-sans/Geist-Italic[wght].woff2": "webfonts/Geist-Italic[wght].woff2",
    "package/LICENSE.txt": "LICENSE.txt",
}


class VendorError(RuntimeError):
    """The upstream package or the vendored copy violates the pin."""


def read_lock() -> dict[str, str]:
    lock = json.loads(LOCK_FILE.read_text())
    for key in ("name", "version", "tarball", "integrity"):
        if not isinstance(lock.get(key), str) or not lock[key]:
            raise VendorError(f"{LOCK_FILE} is missing {key!r}")
    if lock["name"] != "geist":
        raise VendorError(f"unexpected upstream package {lock['name']!r}")
    expected_tarball = f"https://registry.npmjs.org/geist/-/geist-{lock['version']}.tgz"
    if lock["tarball"] != expected_tarball:
        raise VendorError(f"tarball URL must be {expected_tarball}")
    return lock


def download_tarball(lock: dict[str, str]) -> bytes:
    with urllib.request.urlopen(lock["tarball"]) as response:
        data = response.read()

    algorithm, _, expected = lock["integrity"].partition("-")
    if algorithm != "sha512":
        raise VendorError(f"unsupported integrity algorithm {algorithm!r}")
    actual = base64.b64encode(hashlib.sha512(data).digest()).decode()
    if actual != expected:
        raise VendorError(
            f"tarball integrity mismatch: expected sha512-{expected}, got sha512-{actual}"
        )
    return data


def extract_vendored(tarball: bytes) -> dict[str, bytes]:
    contents: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise VendorError(f"unsafe tar path: {member.name}")
            if member.isfile() and member.name in VENDORED_FILES:
                contents[VENDORED_FILES[member.name]] = archive.extractfile(member).read()
    missing = sorted(set(VENDORED_FILES.values()) - set(contents))
    if missing:
        raise VendorError(f"upstream package is missing {', '.join(missing)}")
    return contents


def committed_files() -> set[str]:
    return {
        str(path.relative_to(FAMILY_ROOT).as_posix())
        for path in FAMILY_ROOT.rglob("*")
        if path.is_file()
    }


def check(contents: dict[str, bytes]) -> list[str]:
    errors = []
    for relative, expected in sorted(contents.items()):
        path = FAMILY_ROOT / relative
        if not path.is_file():
            errors.append(f"fonts/Geist/{relative} is missing; run scripts/vendor_geist.py")
        elif path.read_bytes() != expected:
            errors.append(
                f"fonts/Geist/{relative} differs from the pinned upstream package"
            )
    for unexpected in sorted(committed_files() - set(contents)):
        errors.append(f"fonts/Geist/{unexpected} is not part of the upstream pin")
    return errors


def vendor(contents: dict[str, bytes]) -> None:
    for relative, data in sorted(contents.items()):
        path = FAMILY_ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"Vendored fonts/Geist/{relative} ({len(data):,} bytes)")
    for stale in sorted(committed_files() - set(contents)):
        (FAMILY_ROOT / stale).unlink()
        print(f"Removed stale fonts/Geist/{stale}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed copy against the pinned tarball without writing",
    )
    args = parser.parse_args()

    lock = read_lock()
    contents = extract_vendored(download_tarball(lock))

    if args.check:
        errors = check(contents)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print(f"Validated {len(contents)} vendored Geist files against geist@{lock['version']}")
        return 0

    vendor(contents)
    print(f"fonts/Geist now mirrors geist@{lock['version']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VendorError as error:
        print(f"vendor_geist: {error}", file=sys.stderr)
        raise SystemExit(1)
