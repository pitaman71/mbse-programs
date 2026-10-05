"""What the case studies share: `outline`, which shows a tree one syntax node per line.

Each line is a syntax node's kind and the attributes it has set, under the property of its parent that holds it, such
as `left: Name` under a `BinOp`. Case study 1 explains attributes and children.
"""

from mbse.Programs.Framework.Syntax import Attribute, children


def _value(value):
    return f"'{value}'" if isinstance(value, str) else str(value)


def outline(node, label="", depth=0):
    """The tree under `node`, one syntax node per line, indented by depth."""
    attributes = ", ".join(f"{p.name}={_value(getattr(node, p.name))}" for p in node.PROPERTIES
                           if isinstance(p, Attribute) and getattr(node, p.name) not in (None, False, ""))
    lines = ["  " * depth + label + type(node).__name__ + (f"({attributes})" if attributes else "")]
    for prop, index, child in children(node):
        lines.append(outline(child, f"{prop}{'' if index is None else f'[{index}]'}: ", depth + 1))
    return "\n".join(lines)
