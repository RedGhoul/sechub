"""Namespace-agnostic XML helpers.

EDGAR XML documents use a variety of namespaces (and some omit them), so we
match elements by *local name* rather than fully-qualified tags. This keeps the
parsers resilient across filer software and schema versions.
"""

from __future__ import annotations

from lxml import etree


def local_name(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def find(el: etree._Element, name: str) -> etree._Element | None:
    """First descendant whose local name == ``name`` (case-insensitive)."""
    target = name.lower()
    for child in el.iter():
        if local_name(child.tag).lower() == target:
            return child
    return None


def child(el: etree._Element, name: str) -> etree._Element | None:
    """First *direct* child with the given local name (case-insensitive)."""
    target = name.lower()
    for c in el:
        if local_name(c.tag).lower() == target:
            return c
    return None


def text(el: etree._Element | None, name: str | None = None) -> str | None:
    """Text of ``el`` (or of its first descendant named ``name``)."""
    node = el if name is None else (find(el, name) if el is not None else None)
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


def iter_named(root: etree._Element, name: str):
    """Yield every element with the given local name."""
    target = name.lower()
    for el in root.iter():
        if local_name(el.tag).lower() == target:
            yield el
