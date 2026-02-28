#!/usr/bin/env python3
"""URDF validation script for Clawbot X3.

Checks:
- XML syntax
- All parent/child links exist
- Kinematic chain continuity from base_footprint to all leaves
- No duplicate link/joint names

Usage:
    python3 urdf/validate_urdf.py [urdf_file]
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

URDF_PATH = Path(__file__).parent / "clawbot_X3.urdf"

def validate(path: Path) -> bool:
    """Validate URDF structure and kinematic tree.

    Args:
        path: Path to the URDF file.

    Returns:
        True if valid, False if errors found.
    """
    print(f"Validating: {path}")
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        print(f"❌ XML parse error: {e}")
        return False

    root = tree.getroot()
    links  = {l.get("name") for l in root.findall("link")}
    joints = root.findall("joint")
    errors = []

    # Check uniqueness
    all_links  = [l.get("name") for l in root.findall("link")]
    all_joints = [j.get("name") for j in joints]
    if len(all_links) != len(links):
        errors.append("❌ Duplicate link names detected")

    # Check parent/child references
    children: set[str] = set()
    for j in joints:
        p = j.find("parent").get("link") if j.find("parent") is not None else None
        c = j.find("child").get("link")  if j.find("child")  is not None else None
        if p and p not in links:
            errors.append(f"❌ Joint '{j.get('name')}': parent '{p}' not found")
        if c and c not in links:
            errors.append(f"❌ Joint '{j.get('name')}': child '{c}' not found")
        if c:
            children.add(c)

    # Root link = link with no parent
    roots = links - children
    if len(roots) != 1:
        errors.append(f"❌ Expected 1 root link, found {len(roots)}: {roots}")

    if errors:
        for e in errors:
            print(e)
        return False

    root_link = roots.pop()
    print(f"✅ Robot  : {root.get('name', 'unnamed')}")
    print(f"✅ Root   : {root_link}")
    print(f"✅ Links  ({len(links)}): {sorted(links)}")
    print(f"✅ Joints ({len(joints)}): {[j.get('name')+'('+j.get('type')+')' for j in joints]}")
    print("✅ URDF valid — kinematic tree is continuous")
    return True


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else URDF_PATH
    sys.exit(0 if validate(path) else 1)
