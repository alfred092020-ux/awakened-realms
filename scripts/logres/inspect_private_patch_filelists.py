#!/usr/bin/env python3
"""Profile recovered Logres patch file-list formats without exporting payload data."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit
from zipfile import ZipFile

TARGETS = (
    "files/cache/download_filelist.txt",
    "files/cache/download_binfilelist.txt",
    "files/cache/download_extra_filelist.txt",
    "files/cache/filelist.bin",
    "files/cache/extra_filelist.bin",
    "files/cache/filelistbin.hash",
    "files/cache/extra_filelistbin.hash",
    "files/cache/patch/binfilelist.bin",
)
PRINTABLE_RE = re.compile(rb"[ -~]{4,300}")
URL_RE = re.compile(rb"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{4,1024}", re.I)
HOST_RE = re.compile(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?::\d+)?$")
HEX_RE = re.compile(r"^[0-9a-fA-F]{16,128}$")
INT_RE = re.compile(r"^-?\d+$")
PATHISH_RE = re.compile(r"^[A-Za-z0-9_./@%+~-]+\.[A-Za-z0-9]{1,8}$")
MAX_SAMPLE_LINES = 2000
MAX_SAMPLES = 24


def sanitize_url(value: str) -> str | None:
    try:
        parsed = urlsplit(value.rstrip("\"'<>),]}"))
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.lower()
    try:
        port = parsed.port
    except ValueError:
        port = None
    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", "", ""))


def field_kind(value: str) -> str:
    v = value.strip()
    if not v:
        return "EMPTY"
    if v.lower().startswith(("http://", "https://")):
        return "URL"
    if INT_RE.fullmatch(v):
        return "INT"
    if HEX_RE.fullmatch(v):
        return f"HEX{len(v)}"
    if PATHISH_RE.fullmatch(v) or "/" in v or v.lower().endswith(".mbn"):
        return "PATH"
    return "TEXT"


def safe_field(value: str) -> object:
    v = value.strip()
    kind = field_kind(v)
    if kind == "URL":
        return sanitize_url(v) or "<invalid-url>"
    if kind == "INT":
        try:
            return int(v)
        except ValueError:
            return "<int>"
    if kind.startswith("HEX"):
        return {"kind": kind, "prefix": v[:12].lower(), "length": len(v)}
    if kind == "PATH":
        return v[:300]
    if kind == "EMPTY":
        return ""
    return "<text>"


def choose_delimiter(lines: list[str]) -> str | None:
    candidates = ["\t", "|", ",", ";"]
    scores = []
    for delimiter in candidates:
        counts = [line.count(delimiter) for line in lines if line]
        nonzero = [count for count in counts if count]
        score = (len(nonzero), Counter(nonzero).most_common(1)[0][1] if nonzero else 0)
        scores.append((score, delimiter))
    scores.sort(reverse=True)
    best = scores[0]
    if best[0][0] == 0:
        return None
    return best[1]


def text_profile(name: str, data: bytes) -> dict:
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    sample_lines = [line for line in lines[:MAX_SAMPLE_LINES] if line]
    delimiter = choose_delimiter(sample_lines)
    shapes = Counter()
    samples = []
    path_prefixes = Counter()
    extensions = Counter()
    url_hosts = Counter()

    for line in sample_lines:
        fields = line.split(delimiter) if delimiter else line.split()
        kinds = tuple(field_kind(field) for field in fields)
        shapes["|".join(kinds)] += 1
        for field in fields:
            kind = field_kind(field)
            raw = field.strip()
            if kind == "PATH":
                parts = raw.replace("\\", "/").split("/")
                prefix = "/".join(parts[:3]) if len(parts) >= 3 else "/".join(parts[:2])
                if prefix:
                    path_prefixes[prefix] += 1
                ext = Path(raw).suffix.lower()
                if ext:
                    extensions[ext] += 1
            elif kind == "URL":
                sanitized = sanitize_url(raw)
                if sanitized:
                    host = urlsplit(sanitized).hostname
                    if host:
                        url_hosts[host] += 1
        if len(samples) < MAX_SAMPLES:
            samples.append([safe_field(field) for field in fields[:8]])

    return {
        "member": name,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "line_count": len(lines),
        "dominant_delimiter": (
            "TAB" if delimiter == "\t" else delimiter
        ),
        "line_shapes": dict(shapes.most_common(16)),
        "path_prefixes": dict(path_prefixes.most_common(20)),
        "extensions": dict(extensions.most_common(20)),
        "url_hosts": dict(url_hosts.most_common(20)),
        "sample_records": samples,
    }


def binary_profile(name: str, data: bytes) -> dict:
    printable = [m.group(0).decode("ascii", errors="ignore") for m in PRINTABLE_RE.finditer(data)]
    pathish = []
    hostish = []
    urls = []
    seen_paths = set()
    seen_hosts = set()
    seen_urls = set()
    ext_counts = Counter()
    term_tokens = []

    for token in printable:
        low = token.lower()
        if low.startswith(("http://", "https://")):
            url = sanitize_url(token)
            if url and url not in seen_urls:
                seen_urls.add(url)
                urls.append(url)
        if HOST_RE.fullmatch(token) and token.lower() not in seen_hosts:
            seen_hosts.add(token.lower())
            hostish.append(token.lower())
        if (
            ("/" in token or "\\" in token or token.lower().endswith(".mbn"))
            and len(token) <= 300
            and token not in seen_paths
        ):
            seen_paths.add(token)
            pathish.append(token)
            ext = Path(token.replace("\\", "/")).suffix.lower()
            if ext:
                ext_counts[ext] += 1
        if any(term in low for term in ("cdn", "patch", "filelist", "download", "manifest", ".mbn")):
            if len(term_tokens) < 80:
                term_tokens.append(token[:300])

    printable_bytes = sum(len(token) for token in printable)
    return {
        "member": name,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "header_hex": data[:64].hex(),
        "printable_string_count": len(printable),
        "printable_byte_ratio": round(printable_bytes / max(1, len(data)), 6),
        "zero_byte_ratio": round(data.count(0) / max(1, len(data)), 6),
        "mbn_ascii_count": data.lower().count(b".mbn"),
        "extensions": dict(ext_counts.most_common(20)),
        "path_strings": pathish[:MAX_SAMPLES],
        "host_strings": hostish[:MAX_SAMPLES],
        "urls": urls[:MAX_SAMPLES],
        "term_tokens": term_tokens[:MAX_SAMPLES],
    }


def patch_inventory(source: ZipFile) -> set[str]:
    result = set()
    marker = "files/cache/patch/"
    for info in source.infolist():
        if info.is_dir():
            continue
        if info.filename.startswith(marker):
            result.add(info.filename[len(marker):])
    return result


def text_paths(profile: dict) -> list[str]:
    result = []
    for record in profile.get("sample_records", []):
        for field in record:
            if isinstance(field, str) and field not in {"", "<text>", "<invalid-url>"}:
                if "/" in field or field.lower().endswith(".mbn"):
                    result.append(field)
    return result


def inspect_archive(archive: Path) -> dict:
    with ZipFile(archive) as source:
        names = set(source.namelist())
        profiles = {}
        missing = []
        for name in TARGETS:
            if name not in names:
                missing.append(name)
                continue
            data = source.read(name)
            if name.endswith(".txt") or name.endswith(".hash"):
                profiles[name] = text_profile(name, data)
            else:
                profiles[name] = binary_profile(name, data)

        patch_names = patch_inventory(source)
        sample_match = {}
        for name, profile in profiles.items():
            if not name.endswith(".txt"):
                continue
            candidates = text_paths(profile)
            normalized = []
            for value in candidates:
                item = value.replace("\\", "/")
                for prefix in ("files/cache/patch/", "cache/patch/", "patch/"):
                    if item.startswith(prefix):
                        item = item[len(prefix):]
                        break
                normalized.append(item)
            matches = sum(1 for item in normalized if item in patch_names)
            sample_match[name] = {
                "sample_path_field_count": len(normalized),
                "sample_exact_patch_member_matches": matches,
            }

    return {
        "provenance": "PRIVATE_CACHE_PATCH_FILELIST_FORMAT_METADATA",
        "policy": (
            "Exports only file-list structure, safe path/hash prefixes, selected printable "
            "metadata and aggregate matching. No resource payloads, dialogue, images, geometry "
            "or textures are exported."
        ),
        "targets": profiles,
        "missing": missing,
        "sample_patch_member_match": sample_match,
    }


def self_test() -> None:
    with tempfile.TemporaryDirectory() as raw:
        archive = Path(raw) / "private.zip"
        text = (
            "patch/gui/title.mbn\t0123456789abcdef0123456789abcdef\t12345\n"
            "patch/map/001_000_00001.mbn\tabcdef0123456789abcdef0123456789\t67890\n"
        ).encode()
        binary = b"\x01\x00cdn.example.invalid\x00patch/gui/title.mbn\x00"
        with ZipFile(archive, "w") as target:
            target.writestr("files/cache/download_filelist.txt", text)
            target.writestr("files/cache/filelist.bin", binary)
            target.writestr("files/cache/patch/gui/title.mbn", b"x")
            target.writestr("files/cache/patch/map/001_000_00001.mbn", b"y")

        result = inspect_archive(archive)
        txt = result["targets"]["files/cache/download_filelist.txt"]
        if txt["dominant_delimiter"] != "TAB":
            raise AssertionError("tab file-list format was not detected")
        if not txt["line_shapes"]:
            raise AssertionError("record shapes missing")
        binp = result["targets"]["files/cache/filelist.bin"]
        if "cdn.example.invalid" not in binp["host_strings"]:
            raise AssertionError("host string missing")
        if "patch/gui/title.mbn" not in binp["path_strings"]:
            raise AssertionError("binary path string missing")

    print("Logres patch file-list format inspector self-test: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.archive is None:
        print("archive argument required unless --self-test", file=sys.stderr)
        return 2
    try:
        result = inspect_archive(args.archive)
    except (OSError, ValueError) as exc:
        print(f"Logres patch file-list inspection failed: {exc}", file=sys.stderr)
        return 1
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
