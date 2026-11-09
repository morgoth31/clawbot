"""Hook MkDocs: liens wiki Obsidian -> liens Markdown, et bandeau OKF.

Les documents de la base de connaissances (/Robot_Knowledge_Base, publiée dans
docs/knowledge-base/) utilisent la syntaxe de liens bidirectionnels [[nom]].
MkDocs ne la comprend pas. Ce hook la convertit au moment du rendu, sans
modifier les fichiers source : la base reste valide telle quelle pour Obsidian
et pour le validateur scripts/validate_okf.py.

Résolution :
 1. correspondance exacte sur le nom de fichier sans extension ;
 2. à défaut, correspondance insensible à la casse et aux tirets ;
 3. choix du fichier le plus proche du document appelant (même dossier, puis
    parent, puis n'importe où), pour lever l'ambiguïté des noms courants
    comme « index ».
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path

LINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:\|([^\]]+?))?\]\]")
H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)

STATUS_COLORS = {
    "actif": "#2e7d32",
    "validé": "#1565c0",
    "ouvert": "#c62828",
    "obsolète": "#616161",
}


class WikiLinks:
    """Convertit les liens [[...]] et affiche les métadonnées OKF."""

    def __init__(self) -> None:
        self._by_name: dict[str, list[str]] = {}
        self._by_slug: dict[str, list[str]] = {}

    # ------------------------------------------------------------------ config
    def on_config(self, config):
        docs_dir = Path(config["docs_dir"])
        self._by_name.clear()
        self._by_slug.clear()
        for path in docs_dir.rglob("*.md"):
            rel = path.relative_to(docs_dir).as_posix()
            self._by_name.setdefault(path.stem, []).append(rel)
            self._by_slug.setdefault(self._slug(path.stem), []).append(rel)
        return config

    # ------------------------------------------------------------------- page
    def on_page_markdown(self, markdown: str, page, config, files):
        if "[[" not in markdown and not page.meta.get("status"):
            return markdown

        src = page.file.src_path

        def replace(match: re.Match) -> str:
            target = match.group(1).strip()
            label = (match.group(2) or "").strip()
            resolved = self._resolve(target, src)
            if resolved is None:
                return match.group(0)
            text = label or target
            rel = posixpath.relpath(resolved, posixpath.dirname(src) or ".")
            return f"[{text}]({rel})"

        markdown = LINK_RE.sub(replace, markdown)
        return self._inject_meta(markdown, page)

    # ---------------------------------------------------------------- interne
    @staticmethod
    def _slug(name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

    def _resolve(self, target: str, src: str) -> str | None:
        candidates = self._by_name.get(target) or self._by_slug.get(self._slug(target))
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        src_dir = posixpath.dirname(src)

        def distance(rel: str) -> tuple[int, int]:
            rel_dir = posixpath.dirname(rel)
            common = 0
            a, b = src_dir.split("/"), rel_dir.split("/")
            if src_dir == "":
                common = 0
            else:
                for left, right in zip(a, b):
                    if left != right:
                        break
                    common += 1
            return (-common, len(rel_dir))

        return sorted(candidates, key=distance)[0]

    def _inject_meta(self, markdown: str, page) -> str:
        meta = page.meta or {}
        status = meta.get("status")
        if not status or not page.file.src_path.startswith("knowledge-base/"):
            return markdown

        date = meta.get("date", "")
        tags = meta.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        color = STATUS_COLORS.get(str(status).strip().lower(), "#455a64")
        tag_html = " ".join(f"<code>{t}</code>" for t in tags)
        badge = (
            '<div class="okf-meta">'
            f'<span class="okf-badge" style="background:{color}">{status}</span>'
            + (f'<span class="okf-date">Mis à jour : {date}</span>' if date else "")
            + (f'<span class="okf-tags">{tag_html}</span>' if tag_html else "")
            + "</div>"
        )
        match = H1_RE.search(markdown)
        if not match:
            return badge + "\n\n" + markdown
        end = match.end()
        return markdown[:end] + "\n\n" + badge + markdown[end:]


def on_config(config):  # MkDocs accepte des fonctions de module comme hooks
    return WikiLinks().on_config(config)


_links = WikiLinks()


def on_pre_build(config):
    _links.on_config(config)


def on_page_markdown(markdown, page, config, files):
    return _links.on_page_markdown(markdown, page, config, files)
