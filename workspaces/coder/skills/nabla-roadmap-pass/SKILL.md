---
name: nabla-roadmap-pass
description: Passe quotidienne sur la roadmap de nabla-compose depuis la devbox. Vérifier la porte de santé, implémenter un par un les items faisables hors ligne, consolider la roadmap en trois boucles, puis regrouper les blocages et les questions à la fin. Lancée par le job planifié `nabla-compose-roadmap-pass`.
---

# Passe de roadmap nabla-compose

## Directive du propriétaire (texte d'origine)

> Une fois les services tous fonctionnel, reprendre la roadmap et implemente
> la et iter sur chaque item jusqu'à avoir fait l'ensemble. Si tu es bloqué
> pose tes questions une fois la roadmap entière faite. A la fin de la roadmap
> consolide la et recommandations la boucle trois fois puis pose moi les
> questions qu'il reste.

Sur la devbox, cela devient les étapes 1 à 5 ci-dessous. La devbox est hors
ligne (`AGENT_EXECUTION_MODE=offline`, proxy limité à GitHub et PyPI) : elle
ne voit ni TrueNAS, ni pfSense, ni Talos, ni Vaultwarden, ni Cloudflare.
Toutes les règles de ton `AGENTS.md` et de la skill `nabla-compose-dev`
restent applicables.

## 0. Reprendre là où la passe précédente s'est arrêtée

Prépare le clone avec la skill `nabla-compose-dev` (section 1), puis :

```bash
cd nabla-compose && gh pr list --state open --json number,headRefName,url --jq '.[] | select(.headRefName | startswith("openclaw/roadmap-pass")) | "\(.number) \(.headRefName) \(.url)"'
```

- Une PR sort : `git fetch origin <branche> && git switch <branche>`, puis
  continue dessus (nouveaux commits, jamais de `--force`).
- Sinon : `git switch -c openclaw/roadmap-pass-<AAAAMMJJ> origin/master`.

Lis le dernier `docs/runbooks/*roadmap-pass*.md` : ses items parqués ne se
retentent pas sans fait nouveau.

## 1. Porte « services fonctionnels »

La santé des services ne se voit pas depuis la devbox : note-la
`NOT_RUN (vantage devbox)`, jamais `PASS`. La porte vérifiable est celle du
code :

```bash
cd nabla-compose && gh run list --branch master --limit 5 --json name,conclusion,headSha
cd nabla-compose && export AGENT_EXECUTION_MODE=offline && uv sync --frozen && just offline
```

Si `master` est rouge, le premier item est de réparer ce qui casse (par le
code). Si ce n'est pas réparable, saute l'étape 2 et passe à l'étape 3.

## 2. Itérer sur la roadmap

Sources, dans cet ordre : `docs/roadmap-portfolio.md` (priorités), puis
`docs/roadmap.md`. Pour chaque item ouvert (ni `DONE` ni `ACCEPTED`), par
priorité, classe-le :

| Classe | Critère | Action |
|---|---|---|
| `CODE` | faisable et testable hors ligne : script, test, doc, catalogue, Compose non déployé | l'implémenter |
| `RUNTIME` | exige un hôte, Docker, un secret ou un déploiement | parquer, avec la commande de réception Workstation |
| `DÉCISION` | exige un arbitrage du propriétaire | parquer, avec la question |

Pour chaque item `CODE` : le plus petit changement complet, le test le plus
proche puis `just offline`, un commit par item (message conventionnel en
anglais). Dans la roadmap, marque l'item `CODED` ou `TESTED` avec la commande
lancée ; jamais `DEPLOYED` ni `ACCEPTED`. Un générateur indisponible hors
ligne (tofu, Docker, mise) rend l'item `RUNTIME`. `just offline` ne contrôle
que les fichiers modifiés : avant ton premier changement il affiche `files=0`,
ce qui ne prouve rien.

Un item déjà livré sur `master` (PR fusionnée, code présent) n'est **pas** un
item traité par toi : ferme-le à la boucle 1 avec sa référence.

Bloqué : note le blocage, passe à l'item suivant, ne pose **aucune** question
en cours de passe. « Jusqu'à avoir fait l'ensemble » se fait sur plusieurs
jours : au plus 3 items `CODE` par exécution, ≤ 10 fichiers et ≤ 400 lignes
chacun ; après 40 minutes, termine l'item en cours et passe à l'étape 3.

Interdits : `.github/workflows/`, les contrôles de sécurité, les fichiers de
verrouillage, toute valeur de secret, la suppression de données persistantes.

## 3. Consolider la roadmap — trois boucles

Chaque boucle relit les fichiers (pas ta mémoire de la passe) et finit par un
commit `docs(roadmap): ...` :

1. **Statuts** : chaque item touché porte son statut, sa preuve (commande,
   SHA) et la preuve manquante ; un item déjà livré sur `master` mais encore
   ouvert est fermé avec sa référence.
2. **Doublons et obsolètes** : fusionne les doublons entre les deux roadmaps,
   retire ce qui ne s'applique plus, garde les liens.
3. **Recommandations** : relis le diff complet de la passe et ajoute au plus
   3 recommandations priorisées (quoi, pourquoi) dans une section
   « Recommandations de la passe du <AAAA-MM-JJ> ».

Parque blocages et questions dans
`docs/runbooks/<AAAA-MM-JJ>-openclaw-roadmap-pass.md` : un tableau
`item | classe | blocage | question ou commande de réception`.

## 4. Publier

```bash
cd nabla-compose && git push -u origin HEAD
```

Puis `gh pr create --draft` (titre `docs(roadmap): openclaw roadmap pass
<AAAA-MM-JJ>`), ou un commentaire de bilan si la PR existe déjà. Le corps
liste les commandes restées `NOT_RUN` à lancer sur la Workstation.

Push ou PR refusé (permission, 403) : ne cherche pas d'autre voie. Exporte
`git format-patch origin/master -o ~/outbox/roadmap-pass-<AAAAMMJJ>/` et
réponds `BLOQUÉ: push` avec ce chemin.

## 5. Compte rendu (livré par le planificateur)

En français, au plus 25 lignes, sans rien envoyer toi-même :

- porte : CI `master`, `just offline`, santé des services `NOT_RUN` ;
- items traités : uniquement les commits de cette passe, tels que les liste
  `git log --oneline origin/master..HEAD` ; chaque `PASS`/`FAIL` cite une
  commande exécutée dans cette passe, toute autre vérification est `NOT_RUN` ;
- consolidation : une ligne par boucle ;
- URL de la PR Draft, ou `BLOQUÉ: push` et le chemin `~/outbox/...` ;
- blocages `RUNTIME` et `DÉCISION` : nombre et les 3 plus importants ;
- **à la fin**, les questions restantes, numérotées.

Jamais de merge ni de passage en Ready ; n'annonce aucune réussite non
vérifiée.
