#!/usr/bin/env python3
"""Import Michael Marte's corrected upright Sans Glyphs package.

The incoming package is the visual source of truth for outlines, glyph order,
and instance filters. Project naming and attribution stay in the repository's
existing fontinfo.plist. The five temporarily incompatible variable-font
glyphs remain parked only on the variable instance and are exported by every
static instance.

This updates the Glyphs design/static source only. The production upright VF
is rebuilt separately from sources/NamcheShadowSans-Upright; changes imported
here require an explicit migration of that quadratic source and its deltas.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil


PARKED_VF_GLYPHS = ("Yusbig-cy", "yusbig-cy", "mu", "baht", "peso")
REMOVE_GLYPHS_PARAMETER = """{
name = "Remove Glyphs";
value = (
"Yusbig-cy",
"yusbig-cy",
mu,
baht,
peso
);
},
"""
ROUND_CORNER_PARAMETER = re.compile(
    r'\{\nname = Filter;\nvalue = "RoundCorner;[^"\n]+";\n\},?\n'
)
ROUND_CORNER_VALUE = re.compile(
    r'(value = "RoundCorner;-?\d+;)(?:compatible;)?'
)


def balanced_assignment(text: str, marker: str) -> tuple[int, int, str]:
    start = text.index(marker)
    opening = text.index("(", start + len(marker) - 1)
    depth = 0
    quoted = False
    escaped = False

    for index in range(opening, len(text)):
        character = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                end = index + 1
                if text[end : end + 1] == ";":
                    end += 1
                if text[end : end + 1] == "\n":
                    end += 1
                return start, end, text[start:end]
    raise ValueError(f"unbalanced assignment: {marker}")


def top_level_blocks(assignment: str) -> list[str]:
    opening = assignment.index("(")
    closing = assignment.rindex(")")
    body = assignment[opening + 1 : closing]
    blocks: list[str] = []
    depth = 0
    start: int | None = None
    quoted = False
    escaped = False

    for index, character in enumerate(body):
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
        elif character == "{":
            if depth == 0:
                start = index
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0 and start is not None:
                end = index + 1
                if body[end : end + 1] == ",":
                    end += 1
                if body[end : end + 1] == "\n":
                    end += 1
                blocks.append(body[start:end])
                start = None
    if depth or start is not None:
        raise ValueError("unbalanced instance blocks")
    return blocks


def normalized_instances(incoming_fontinfo: str) -> str:
    _, _, assignment = balanced_assignment(incoming_fontinfo, "instances = (")
    blocks = top_level_blocks(assignment)
    if len(blocks) != 10:
        raise ValueError(f"expected one variable and nine static instances, found {len(blocks)}")

    normalized: list[str] = []
    variable_count = 0
    for block in blocks:
        if block.count(REMOVE_GLYPHS_PARAMETER) != 1:
            raise ValueError("each incoming instance must park the expected five glyphs")
        if not re.search(
            r'value = "RoundCorner;-10;(?:compatible;)?include:'
            r'Yusbig-cy, yusbig-cy, mu, baht, peso";',
            block,
        ):
            raise ValueError("incoming instance is missing the five-glyph RoundCorner -10 tier")

        roundcorner_count = len(ROUND_CORNER_PARAMETER.findall(block))
        if roundcorner_count != 7:
            raise ValueError(f"expected seven RoundCorner parameters, found {roundcorner_count}")

        if "type = variable;" in block:
            variable_count += 1
            block = block.replace('value = "Namche-Shadow[wght]";', 'value = "NamcheShadowSans[wght]";')
            block, removed = ROUND_CORNER_PARAMETER.subn("", block)
            if removed != 7:
                raise ValueError(f"expected seven variable RoundCorner parameters, found {removed}")
        else:
            block = block.replace(REMOVE_GLYPHS_PARAMETER, "")
            # A designer drop may come from the pre-VF recipe. Normalize every
            # static tier so the next native OTF export remains a valid rounded
            # source for build_sans_variable.py.
            block = ROUND_CORNER_VALUE.sub(r"\1compatible;", block)
            if block.count(";compatible;") != 7:
                raise ValueError("failed to make all static RoundCorner filters compatible")
        normalized.append(block)

    if variable_count != 1:
        raise ValueError(f"expected one variable instance, found {variable_count}")
    return "instances = (\n" + "".join(normalized) + ");\n"


def import_package(incoming: Path, target: Path) -> None:
    incoming_glyphs = incoming / "glyphs"
    target_glyphs = target / "glyphs"
    incoming_names = {path.name for path in incoming_glyphs.glob("*.glyph")}
    target_names = {path.name for path in target_glyphs.glob("*.glyph")}
    if incoming_names != target_names:
        missing = sorted(target_names - incoming_names)
        extra = sorted(incoming_names - target_names)
        raise ValueError(f"glyph sets differ; missing={missing}, extra={extra}")

    # Validate and normalize the complete incoming package before the first
    # maintained source file is replaced. A rejected drop must leave no hybrid
    # package behind.
    incoming_fontinfo = (incoming / "fontinfo.plist").read_text()
    instances = normalized_instances(incoming_fontinfo)
    incoming_yus = incoming_glyphs / "Y_usbig-cy.glyph"
    yus_text = incoming_yus.read_text()
    if yus_text.count("export = 0;\n") != 1:
        raise ValueError("expected incoming Yusbig-cy to contain exactly one disabled export flag")
    normalized_yus = yus_text.replace("export = 0;\n", "")
    order_text = (incoming / "order.plist").read_text()

    target_fontinfo_path = target / "fontinfo.plist"
    target_fontinfo = target_fontinfo_path.read_text()
    start, end, _ = balanced_assignment(target_fontinfo, "instances = (")
    normalized_fontinfo = target_fontinfo[:start] + instances + target_fontinfo[end:]

    for name in sorted(incoming_names):
        shutil.copyfile(incoming_glyphs / name, target_glyphs / name)
    (target_glyphs / "Y_usbig-cy.glyph").write_text(normalized_yus)
    (target / "order.plist").write_text(order_text)
    target_fontinfo_path.write_text(normalized_fontinfo)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("incoming", type=Path)
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("sources/NamcheShadowSans.glyphspackage"),
    )
    args = parser.parse_args()
    import_package(args.incoming, args.target)


if __name__ == "__main__":
    main()
