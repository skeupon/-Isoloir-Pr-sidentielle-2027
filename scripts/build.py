#!/usr/bin/env python3
"""Assemble site/index.html à partir de site/modele.html et des fichiers data/*.json.

Usage :
  python scripts/build.py              -> site/index.html (photos servies depuis site/photos/)
  python scripts/build.py --autonome   -> site/isoloir-autonome.html (photos intégrées, un seul fichier)
"""
import base64, json, mimetypes, shutil, sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DATA, SITE = RACINE / "data", RACINE / "site"


def charger(nom):
    return json.loads((DATA / nom).read_text(encoding="utf-8"))


def main():
    autonome = "--autonome" in sys.argv
    donnees = {k: charger(k + ".json") for k in ("candidats", "programmes", "test", "actus", "journal")}
    donnees["journal"].pop("empreintes", None)  # inutile côté navigateur

    (SITE / "photos").mkdir(parents=True, exist_ok=True)
    for c in donnees["candidats"]["candidats"]:
        photo = c.get("photo")
        if not photo or not photo.get("fichier"):
            continue
        source = DATA / photo["fichier"]
        if not source.exists():
            c["photo"] = None
            continue
        if autonome:
            mime = mimetypes.guess_type(source.name)[0] or "image/jpeg"
            photo["src"] = "data:%s;base64,%s" % (mime, base64.b64encode(source.read_bytes()).decode())
        else:
            shutil.copy2(source, SITE / "photos" / source.name)
            photo["src"] = "photos/" + source.name

    js = json.dumps(donnees, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = (SITE / "modele.html").read_text(encoding="utf-8").replace("/*DONNEES*/null", js, 1)
    sortie = SITE / ("isoloir-autonome.html" if autonome else "index.html")
    sortie.write_text(page, encoding="utf-8")
    print("Écrit :", sortie, "(%d Ko)" % (sortie.stat().st_size // 1024))


if __name__ == "__main__":
    main()
