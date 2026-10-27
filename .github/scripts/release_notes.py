"""Texto das Releases = a secao "## vX" do CHANGELOG.md.

Uso:
  python .github/scripts/release_notes.py v3.0            -> escreve release_notes.md com a secao da tag
  python .github/scripts/release_notes.py --edit-all      -> atualiza a descricao de todas as Releases v* (precisa do gh e do GH_TOKEN)
"""
import json
import os
import re
import subprocess
import sys

REPO = os.environ.get("GITHUB_REPOSITORY", "marioondc9426/Lume")
TEXT = open("CHANGELOG.md", encoding="utf-8").read()


def section(tag):
    m = re.search(r"^## v" + re.escape(tag.lstrip("v")) + r"(?:[ \t][^\n]*)?\n(.*?)(?=^## v|\Z)", TEXT, re.S | re.M)
    return m.group(1).strip() if m else ""


def body_for(tag):
    body = section(tag) or "Veja o CHANGELOG.md"
    return body + "\n\n---\nFull changelog: https://github.com/" + REPO + "/blob/main/CHANGELOG-EN.md (EN) · https://github.com/" + REPO + "/blob/main/CHANGELOG.md\n"


if __name__ == "__main__":
    if sys.argv[1:] == ["--edit-all"]:
        rels = json.loads(subprocess.check_output(["gh", "release", "list", "--limit", "50", "--json", "tagName"]))
        for r in rels:
            tag = r["tagName"]
            if not re.fullmatch(r"v\d+(\.\d+)*", tag):
                continue
            if not section(tag):
                print(tag, "sem secao no CHANGELOG")
                continue
            open("notes.md", "w", encoding="utf-8").write(body_for(tag))
            subprocess.check_call(["gh", "release", "edit", tag, "--notes-file", "notes.md"])
            print(tag, "descricao atualizada")
    else:
        tag = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_REF_NAME", "")).strip()
        open("release_notes.md", "w", encoding="utf-8").write(body_for(tag))
        print("release_notes.md para", tag, "(%d caracteres)" % len(body_for(tag)))
