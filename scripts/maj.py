#!/usr/bin/env python3
"""Mise à jour d'Isoloir, lancée toutes les 12 heures par GitHub Actions.

1. Actus : articles des médias listés dans data/flux.json qui citent chaque candidat.
2. Portraits : photo sous licence libre trouvée via Wikidata et Wikimedia Commons.
3. Programmes : détection des changements sur les sites officiels des candidats
   (data/candidats.json, champ "sources_programme"). Un changement est inscrit au journal comme « à vérifier » :
   aucune position n'est modifiée automatiquement.
   Si la variable ANTHROPIC_API_KEY existe, un résumé neutre du changement est ajouté
   au journal, marqué « à valider ».

Aucune dépendance : bibliothèque standard Python 3.10+ uniquement.
"""
import difflib, email.utils, hashlib, html, json, os, re, sys, time
import urllib.parse, urllib.request, urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DATA = RACINE / "data"
INSTANTANES = DATA / "instantanes"
UA = "IsoloirBot/1.0 (comparateur citoyen ; contact : remplacer@exemple.fr)"
MAINTENANT = datetime.now(timezone.utc)
ACTUS_PAR_CANDIDAT, ACTUS_JOURS_MAX = 5, 30
LICENCES_OK = re.compile(r"^(CC0|CC BY|CC-BY|Public domain|PD|Domaine public)", re.I)


def lire(nom):
    return json.loads((DATA / nom).read_text(encoding="utf-8"))


def ecrire(nom, obj):
    (DATA / nom).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def telecharger(url, binaire=False, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return data if binaire else data.decode("utf-8", "replace")


def json_url(url, **params):
    return json.loads(telecharger(url + "?" + urllib.parse.urlencode(params)))


_robots = {}
def autorise(url):
    """Respecte le fichier robots.txt de chaque site suivi."""
    p = urllib.parse.urlparse(url)
    base = "%s://%s" % (p.scheme, p.netloc)
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser(base + "/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = None
        _robots[base] = rp
    rp = _robots[base]
    return True if rp is None else rp.can_fetch(UA, url)


def journal_ajout(journal, texte, **extra):
    journal["entrees"].append(dict(date=MAINTENANT.isoformat(timespec="minutes"), texte=texte, **extra))


# 1. Actus -------------------------------------------------------------------
def lire_flux(url):
    """Renvoie les articles d'un flux RSS ou Atom : (titre, lien, date)."""
    racine = ET.fromstring(telecharger(url))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for it in racine.iter("item"):
        try:
            d = email.utils.parsedate_to_datetime(it.findtext("pubDate"))
        except Exception:
            continue
        yield (it.findtext("title") or "").strip(), (it.findtext("link") or "").strip(), d
    for it in racine.iter("{http://www.w3.org/2005/Atom}entry"):
        lien = it.find("a:link", ns)
        try:
            d = datetime.fromisoformat((it.findtext("a:updated", namespaces=ns) or "").replace("Z", "+00:00"))
        except Exception:
            continue
        yield (it.findtext("a:title", namespaces=ns) or "").strip(), (lien.get("href") if lien is not None else ""), d


def maj_actus(candidats, actus):
    """Lit les flux des médias listés dans data/flux.json et garde, pour chaque candidat,
    les articles dont le titre cite son nom complet."""
    medias = lire("flux.json")["flux"]
    articles = []
    for m in medias:
        if not autorise(m["url"]):
            print("  flux %s : robots.txt refuse la lecture" % m["nom"])
            continue
        try:
            for titre, lien, d in lire_flux(m["url"]):
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
                if MAINTENANT - d <= timedelta(days=ACTUS_JOURS_MAX):
                    articles.append({"titre": titre, "source": m["nom"], "date": d.isoformat(), "lien": lien})
        except Exception as e:
            print("  flux %s : échec (%s)" % (m["nom"], e))
        time.sleep(1)
    flux = {}
    for c in candidats:
        nom = ("%s %s" % (c["prenom"], c["nom"])).lower()
        trouves = [a for a in articles if nom in a["titre"].lower()]
        trouves.sort(key=lambda a: a["date"], reverse=True)
        if trouves:
            flux[c["id"]] = trouves[:ACTUS_PAR_CANDIDAT]
    actus["flux"] = flux
    actus["maj"] = MAINTENANT.isoformat(timespec="minutes")


# 2. Portraits ---------------------------------------------------------------
def trouver_qid(c):
    res = json_url("https://www.wikidata.org/w/api.php", action="wbsearchentities", format="json",
                   language="fr", uselang="fr", type="item", limit=5,
                   search="%s %s" % (c["prenom"], c["nom"]))
    for r in res.get("search", []):
        desc = (r.get("description") or "").lower()
        if any(m in desc for m in ("polit", "candidat", "député", "maire", "ministre", "militant", "syndical")):
            return r["id"]
    return None


def maj_portrait(c, journal):
    if not c.get("wikidata"):
        qid = trouver_qid(c)
        if not qid:
            return
        c["wikidata"] = qid
        journal_ajout(journal, "Fiche Wikidata %s associée automatiquement, à vérifier." % qid, type="portrait", candidat=c["id"])
    ent = json_url("https://www.wikidata.org/w/api.php", action="wbgetentities", format="json",
                   ids=c["wikidata"], props="claims")["entities"][c["wikidata"]]
    p18 = ent.get("claims", {}).get("P18")
    if not p18:
        return
    fichier = p18[0]["mainsnak"]["datavalue"]["value"]
    if c.get("photo") and c["photo"].get("commons") == fichier:
        return  # déjà à jour
    q = json_url("https://commons.wikimedia.org/w/api.php", action="query", format="json",
                 titles="File:" + fichier, prop="imageinfo", iiprop="url|extmetadata", iiurlwidth=480)
    info = next(iter(q["query"]["pages"].values()))["imageinfo"][0]
    meta = info.get("extmetadata", {})
    licence = meta.get("LicenseShortName", {}).get("value", "")
    if not LICENCES_OK.match(licence):
        print("  portrait %s : licence non retenue (%s)" % (c["id"], licence))
        return
    auteur = html.unescape(re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", ""))).strip()
    nom_local = "photos/%s.jpg" % c["id"]
    (DATA / nom_local).write_bytes(telecharger(info.get("thumburl") or info["url"], binaire=True))
    c["photo"] = {"fichier": nom_local, "commons": fichier, "auteur": auteur or "Auteur inconnu",
                  "licence": licence, "page": info.get("descriptionurl")}
    journal_ajout(journal, "Nouveau portrait (%s)." % licence, type="portrait", candidat=c["id"])


# 3. Programmes --------------------------------------------------------------
def texte_page(url):
    brut = telecharger(url)
    brut = re.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav)\b.*?</\1>", " ", brut)
    brut = re.sub(r"(?s)<[^>]+>", "\n", brut)
    lignes = [re.sub(r"\s+", " ", html.unescape(l)).strip() for l in brut.split("\n")]
    return "\n".join(l for l in lignes if len(l) > 2)


def resume_claude(nom, avant, apres):
    cle = os.environ.get("ANTHROPIC_API_KEY")
    if not cle:
        return None
    diff = "\n".join(difflib.unified_diff(avant.splitlines(), apres.splitlines(), lineterm="", n=1))[:8000]
    corps = {"model": "claude-sonnet-5-5", "max_tokens": 400, "messages": [{"role": "user", "content":
        "Voici les différences entre deux versions d'une page présentant le programme de %s, candidat à "
        "l'élection présidentielle française. En deux phrases neutres et factuelles, en français, dis ce qui "
        "a changé dans les propositions. Ne juge pas. Si rien de substantiel n'a changé, réponds seulement "
        "« Pas de changement de fond ».\n\n%s" % (nom, diff)}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(corps).encode(),
        headers={"x-api-key": cle, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            rep = json.loads(r.read())
        return "".join(b.get("text", "") for b in rep.get("content", [])).strip()
    except Exception as e:
        print("  résumé : échec (%s)" % e)
        return None


def maj_programmes(candidats, journal):
    INSTANTANES.mkdir(exist_ok=True)
    empreintes = journal.setdefault("empreintes", {})
    for c in candidats:
        for url in c.get("sources_programme", []):
            if not autorise(url):
                print("  programme %s : robots.txt refuse %s" % (c["id"], url))
                continue
            try:
                texte = texte_page(url)
            except Exception as e:
                print("  programme %s : échec (%s)" % (c["id"], e))
                continue
            h = hashlib.sha256(texte.encode()).hexdigest()
            fichier = INSTANTANES / (hashlib.md5(url.encode()).hexdigest() + ".txt")
            ancien = empreintes.get(url)
            if ancien and ancien != h:
                avant = fichier.read_text(encoding="utf-8") if fichier.exists() else ""
                resume = resume_claude("%s %s" % (c["prenom"], c["nom"]), avant, texte)
                if resume and resume.lower().startswith("pas de changement de fond"):
                    pass
                else:
                    journal_ajout(journal, "Changement détecté sur une page de programme suivie.",
                                  type="programme", candidat=c["id"], url=url, resume=resume)
            empreintes[url] = h
            fichier.write_text(texte, encoding="utf-8")
            time.sleep(2)


def main():
    cand_data, actus, journal = lire("candidats.json"), lire("actus.json"), lire("journal.json")
    candidats = cand_data["candidats"]
    etapes = sys.argv[1:] or ["actus", "portraits", "programmes"]
    if "actus" in etapes:
        print("Actus…"); maj_actus(candidats, actus)
    if "portraits" in etapes:
        print("Portraits…")
        for c in candidats:
            try:
                maj_portrait(c, journal)
            except Exception as e:
                print("  portrait %s : échec (%s)" % (c["id"], e))
            time.sleep(1)
    if "programmes" in etapes:
        print("Programmes…"); maj_programmes(candidats, journal)
    journal["entrees"] = journal["entrees"][-300:]
    ecrire("candidats.json", cand_data); ecrire("actus.json", actus); ecrire("journal.json", journal)
    print("Terminé.")


if __name__ == "__main__":
    main()
