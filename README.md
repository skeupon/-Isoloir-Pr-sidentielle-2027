# Isoloir · Présidentielle 2027

Comparateur des programmes : fiches des candidats, programmes par thème, test, duel, actus.
Le site se met à jour tout seul toutes les 12 heures.

## Mise en ligne (une seule fois, environ 10 minutes)

1. Crée un dépôt sur GitHub et envoie-y ce dossier.
2. Dans le dépôt : **Settings → Pages → Source : GitHub Actions**.
3. Facultatif : **Settings → Secrets and variables → Actions → New repository secret**,
   nom `ANTHROPIC_API_KEY`, pour obtenir un résumé automatique des changements de programme.
4. Onglet **Actions → Mise à jour toutes les 12 heures → Run workflow** pour un premier passage.

Le site est alors publié à l’adresse `https://<ton-compte>.github.io/<dépôt>/`.

## Ce qui se met à jour automatiquement

| Quoi | D’où | Ce qui se passe |
| --- | --- | --- |
| Actus | Flux RSS des médias listés dans `data/flux.json` | Les 5 articles les plus récents (30 jours max) dont le titre cite le candidat |
| Portraits | Wikidata puis Wikimedia Commons | Photo téléchargée seulement si sa licence est libre (CC, domaine public), avec auteur et licence affichés |
| Programmes | Sites officiels des candidats (`sources_programme`) | Un changement est inscrit au journal « à vérifier » ; aucune position n’est modifiée sans relecture |

Le script respecte le fichier robots.txt de chaque site suivi.

## Ce qui reste éditorial

Les positions (`data/programmes.json`) et les questions du test (`data/test.json`) sont rédigées et
vérifiées à la main. Règle de sourcing : une position vient soit du site officiel du candidat
(`"t": "site"`), soit d’une déclaration rapportée par un média identifié (`"t": "media"`), avec le lien.
Pas de comparateur tiers, pas de propos d’un proche. Une question n’entre dans le test que si au moins
trois candidats y ont une position vérifiée. Pour ajouter les positions d’un candidat, ajoute ses
entrées dans `programmes.json` et passe `"detaille": true` dans `candidats.json`.

À vérifier avant une mise en ligne publique :
- les associations Wikidata faites automatiquement (le journal les signale) ;
- les adresses des flux RSS dans `data/flux.json` (un flux qui ne répond pas est ignoré) ;
- les sites officiels à suivre dans `sources_programme` : renseignés pour Retailleau, Attal et Mélenchon,
  à ajouter pour les autres candidats dès qu’ils publient un programme ;
- l’adresse de contact dans la variable `UA` de `scripts/maj.py`.

## Lancer à la main

```
python scripts/maj.py                 # tout
python scripts/maj.py actus           # seulement les actus
python scripts/build.py               # site/index.html
python scripts/build.py --autonome    # un seul fichier HTML, photos intégrées
```
