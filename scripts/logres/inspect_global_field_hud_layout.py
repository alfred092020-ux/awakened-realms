#!/usr/bin/env python3
"""Extract bounded field-HUD layout facts from recovered Global Logres HUD Lua.

The tool reads the owner's recovered HUD.mbn from an archive, extracts only the
requested generated Lua entries, and emits metadata/coordinates. It never writes
or republishes proprietary source bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hydrate_private_assets import parse_mbn

HUD_MEMBER = "files/cache/patch/gui/HUD.mbn"
MAIN_HUD_ENTRY = "MainHUD.lua"
FIELD_FOOTER_ENTRY = "field_hud_footer.lua"

KNOWN_GLOBAL = {
    "package_sha256": "d4fe09e50c8f8fa6cb560ea4ef5348c9092a41fff03f17e316a982f10cc6316a",
    "entries": {
        MAIN_HUD_ENTRY: "b1252039f5f64653578345990d977ddcfa62dd38fe9c8166befedcd78d0d3dc4",
        FIELD_FOOTER_ENTRY: "e15f4433dfbc2be6118a6f6564ecd72c6b1527fa0117a4f473eba1057ade3b2f",
    },
}

_NUMBER = r"-?(?:\d+(?:\.\d*)?|\.\d+)"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _structural(line: str) -> str:
    out: list[str] = []
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(line):
        char = line[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            out.append(" ")
            index += 1
            continue

        if char in {'"', "'"}:
            quote = char
            out.append(" ")
            index += 1
            continue

        if char == "-" and index + 1 < len(line) and line[index + 1] == "-":
            break

        out.append(char)
        index += 1

    return "".join(out)


def _balanced_table_from(text: str, start: int) -> str:
    if start < 0 or start >= len(text) or text[start] != "{":
        raise ValueError("table start is not an opening brace")

    depth = 0
    quote: str | None = None
    escaped = False
    line_comment = False
    index = start

    while index < len(text):
        char = text[index]

        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue

        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue

        if char in {'"', "'"}:
            quote = char
            index += 1
            continue

        if char == "-" and index + 1 < len(text) and text[index + 1] == "-":
            line_comment = True
            index += 2
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

        index += 1

    raise ValueError("unterminated Lua table")


def enclosing_table(text: str, marker: str) -> str:
    marker_index = text.find(marker)
    if marker_index < 0:
        raise ValueError(f"marker not found: {marker}")

    stack: list[int] = []
    quote: str | None = None
    escaped = False
    line_comment = False
    index = 0

    while index < marker_index:
        char = text[index]

        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue

        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue

        if char in {'"', "'"}:
            quote = char
            index += 1
            continue

        if char == "-" and index + 1 < marker_index and text[index + 1] == "-":
            line_comment = True
            index += 2
            continue

        if char == "{":
            stack.append(index)
        elif char == "}":
            if stack:
                stack.pop()

        index += 1

    if not stack:
        raise ValueError(f"marker has no enclosing table: {marker}")

    return _balanced_table_from(text, stack[-1])


def _direct_line(block: str, key: str) -> str | None:
    depth = 0
    for line in block.splitlines():
        structural = _structural(line)
        if depth == 1 and re.match(rf"^\s*{re.escape(key)}\s*=", structural):
            return line
        depth += structural.count("{") - structural.count("}")
    return None


def direct_string(block: str, key: str) -> str | None:
    line = _direct_line(block, key)
    if line is None:
        return None
    match = re.search(rf"{re.escape(key)}\s*=\s*\"([^\"]*)\"", line)
    return match.group(1) if match else None


def direct_number(block: str, key: str) -> float | None:
    line = _direct_line(block, key)
    if line is None:
        return None
    match = re.search(rf"{re.escape(key)}\s*=\s*({_NUMBER})", line)
    return float(match.group(1)) if match else None


def direct_pair(block: str, key: str) -> list[float] | None:
    line = _direct_line(block, key)
    if line is None:
        return None
    match = re.search(
        rf"{re.escape(key)}\s*=\s*\{{\s*({_NUMBER})\s*,\s*({_NUMBER})\s*\}}",
        line,
    )
    if not match:
        return None
    return [float(match.group(1)), float(match.group(2))]


def direct_identifier_list(block: str, key: str) -> list[str] | None:
    line = _direct_line(block, key)
    if line is None:
        return None
    match = re.search(rf"{re.escape(key)}\s*=\s*\{{([^}}]*)\}}", line)
    if not match:
        return None
    values = [part.strip() for part in match.group(1).split(",") if part.strip()]
    return values


def direct_nested_table(block: str, key: str) -> str | None:
    lines = block.splitlines(keepends=True)
    depth = 0
    offset = 0
    for line in lines:
        structural = _structural(line)
        if depth == 1 and re.match(rf"^\s*{re.escape(key)}\s*=", structural):
            opening = block.find("{", offset + line.find("="))
            if opening < 0:
                return None
            return _balanced_table_from(block, opening)
        depth += structural.count("{") - structural.count("}")
        offset += len(line)
    return None


def anchor_styles(block: str) -> dict[str, object] | None:
    styles = direct_nested_table(block, "anchorStyles")
    if styles is None:
        return None

    result: dict[str, object] = {}
    anchors = direct_identifier_list(styles, "anchor")
    if anchors is not None:
        result["anchors"] = anchors

    for key in ("top", "bottom", "left", "right"):
        value = direct_number(styles, key)
        if value is not None:
            result[key] = value

    return result


def node_facts(block: str) -> dict[str, object]:
    result: dict[str, object] = {}

    for key in ("name", "resource"):
        value = direct_string(block, key)
        if value is not None:
            result[key] = value

    for key in ("position", "contentSize", "sliceSize", "anchor", "scale"):
        value = direct_pair(block, key)
        if value is not None:
            result[key] = value

    order_z = direct_number(block, "orderZ")
    if order_z is not None:
        result["orderZ"] = order_z

    styles = anchor_styles(block)
    if styles:
        result["anchorStyles"] = styles

    return result


def extract_layout(archive: Path, *, require_known_global: bool) -> dict[str, object]:
    with ZipFile(archive) as source:
        package = source.read(HUD_MEMBER)

    entries = parse_mbn(package)
    try:
        main_hud = entries[MAIN_HUD_ENTRY]
        field_footer = entries[FIELD_FOOTER_ENTRY]
    except KeyError as exc:
        raise ValueError(f"HUD package missing required entry: {exc.args[0]}") from exc

    package_hash = sha256(package)
    entry_hashes = {
        MAIN_HUD_ENTRY: sha256(main_hud),
        FIELD_FOOTER_ENTRY: sha256(field_footer),
    }

    known_match = (
        package_hash == KNOWN_GLOBAL["package_sha256"]
        and all(
            entry_hashes[name] == expected
            for name, expected in KNOWN_GLOBAL["entries"].items()
        )
    )

    if require_known_global and not known_match:
        raise ValueError("archive does not match the verified Global HUD evidence hashes")

    main_text = main_hud.decode("utf-8", "strict")
    footer_text = field_footer.decode("utf-8", "strict")

    main_root = enclosing_table(main_text, 'name = "window"')
    footer_root = enclosing_table(footer_text, 'name = "window"')
    footer_bar = enclosing_table(footer_text, 'name = "footer_bar"')
    menu_button = enclosing_table(footer_text, 'name = "menu"')
    menu_normal = enclosing_table(
        menu_button,
        'resource = "gui/HUD/field_menu.png"',
    )

    return {
        "provenance": "RECOVERED_GLOBAL_2017_HUD_LUA",
        "evidence_classification": "CONFIRMED ORIGINAL SOURCE BYTES",
        "package": {
            "archive_member": HUD_MEMBER,
            "sha256": package_hash,
            "size": len(package),
            "known_global_match": known_match,
        },
        "entries": {
            MAIN_HUD_ENTRY: {
                "sha256": entry_hashes[MAIN_HUD_ENTRY],
                "size": len(main_hud),
                "root": node_facts(main_root),
            },
            FIELD_FOOTER_ENTRY: {
                "sha256": entry_hashes[FIELD_FOOTER_ENTRY],
                "size": len(field_footer),
                "root": node_facts(footer_root),
            },
        },
        "field_hud_footer": {
            "footer_bar": node_facts(footer_bar),
            "menu_button": node_facts(menu_button),
            "menu_normal_image": node_facts(menu_normal),
        },
        "interpretation": {
            "raw_lua_coordinates": "CONFIRMED ORIGINAL",
            "raw_anchor_constraints": "CONFIRMED ORIGINAL",
            "runtime_screen_transform": "UNRESOLVED",
            "historical_footer_variant_selection": "UNRESOLVED",
        },
    }


def self_test() -> None:
    sample = """
local rootComponent =
{
    guiType = lfs.gui.kGUI_Window,
    name = "window",
    contentSize = {720.000000, 1104.000000},
    children =
    {
        {
            guiType = lfs.gui.kGUI_Image9Slice,
            resource = "gui/HUD/field_underbar.png",
            sliceSize = {720.000000, 100.000000},
            name = "footer_bar",
            position = {360.000000, 76.000000},
            anchor = {0.500000, 0.500000},
            anchorStyles =
            {
                anchor = {lfs.gui.kBottom, lfs.gui.kHorizontalCenter},
                bottom = 45,
            },
        },
        {
            guiType = lfs.gui.kGUI_Button,
            normal =
            {
                guiType = lfs.gui.kGUI_Image,
                resource = "gui/HUD/field_menu.png",
                position = {0.000000, 0.000000},
                anchorStyles =
                {
                    bottom = 35,
                    left = 88,
                },
            },
            name = "menu",
            anchorStyles =
            {
                anchor = {lfs.gui.kVerticalCenter, lfs.gui.kRight},
                bottom = 0,
                right = 88,
            },
        },
    },
}
return rootComponent
"""

    root = enclosing_table(sample, 'name = "window"')
    footer = enclosing_table(sample, 'name = "footer_bar"')
    menu = enclosing_table(sample, 'name = "menu"')
    menu_image = enclosing_table(menu, 'resource = "gui/HUD/field_menu.png"')

    assert direct_pair(root, "contentSize") == [720.0, 1104.0]
    assert direct_pair(footer, "position") == [360.0, 76.0]
    assert direct_pair(footer, "sliceSize") == [720.0, 100.0]
    assert anchor_styles(footer) == {
        "anchors": ["lfs.gui.kBottom", "lfs.gui.kHorizontalCenter"],
        "bottom": 45.0,
    }
    assert anchor_styles(menu) == {
        "anchors": ["lfs.gui.kVerticalCenter", "lfs.gui.kRight"],
        "bottom": 0.0,
        "right": 88.0,
    }
    assert direct_pair(menu_image, "position") == [0.0, 0.0]
    assert anchor_styles(menu_image) == {
        "bottom": 35.0,
        "left": 88.0,
    }

    print("Logres Global field HUD layout inspector self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-known-global", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    if args.archive is None:
        parser.error("archive is required unless --self-test is used")

    result = extract_layout(
        args.archive,
        require_known_global=args.require_known_global,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
