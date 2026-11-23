---
name: nabla-roadmap-pass
description: Passe nocturne sur la roadmap d'un dépôt de l'agent (nabla-compose, fastapi-sample, nabla-site-alban, nabla-site-bababou, nabla-yubikey) depuis la devbox. Vérifier l'état des services et la CI, réparer les PR ouvertes (conflits, CI rouge), implémenter un par un les items faisables hors ligne, consolider la roadmap en trois boucles, puis regrouper les blocages et les questions à la fin. Lancée par les jobs planifiés `<repo>-roadmap-pass`.
---

# Passe de roadmap d'un dépôt

Le message du job nomme le dépôt `<repo>`. Ce tableau donne sa skill de
préparation, ses sources de roadmap (par priorité) et sa porte hors ligne :

| Dépôt | Skill | Sources de roadmap | Porte hors ligne |
|---|---|---|---|
| `nabla-compose` | `nabla-compose-dev` | `docs/roadmap-portfolio.md`, `docs/roadmap.md` | `export AGENT_EXECUTION_MODE=offline && uv sync --frozen && just offline` |
| `fastapi-sample` | `fastapi-sample-dev` | `docs/engineering-roadmap.md`, `docs/homelab-security-roadmap.md` | `uv sync --frozen && just test-local-first` |
| `nabla-site-alban` | `nabla-site-dev` | `docs/quality-roadmap.md`, `docs/homelab-roadmap.md`, `docs/stripe-hardening-roadmap.md` | `npm ci --no-fund && npm run lint && npm run typecheck && npm run test:unit` |
| `nabla-site-bababou` | `nabla-site-dev` | `docs/roadmap.md` | `npm ci --no-fund && npm run lint && npm run typecheck && npm run test:unit` |
| `nabla-yubikey` | `nabla-yubikey-dev` | `docs/roadmap.md`, `docs/roadmap-workstation-yubikey.md`, `docs/roadmap-vault-pki.md` | `export AGENT_EXECUTION_MODE=offline && just test` |

Une source absente n'est pas une erreur : passe à la suivante. Le dernier
`docs/runbooks/*roadmap*.md` du dépôt, s'il existe, est l'état de la passe
précédente.

## Directive du propriétaire (texte d'origine)

> Une fois les services tous fonctionnel, reprendre la roadmap et implemente
> la et iter sur chaque item jusqu'à avoir fait l'ensemble. Si tu es bloqué
> pose tes questions une fois la roadmap entière faite. A la fin de la roadmap
> consolide la et recommandations la boucle trois fois puis pose moi les
> questions qu'il reste.

Sur la devbox, cela devient les étapes 1 à 6 ci-dessous. La devbox est hors
ligne (`AGENT_EXECUTION_MODE=offline`, proxy limité à GitHub, PyPI, npm,
FastAPI Cloud, aux sites publics et, en lecture seule, à Prometheus et FastAPI
Sample sur TrueNAS) : elle ne voit ni le reste du LAN, ni pfSense, ni Talos,
ni Vaultwarden, ni Cloudflare. Toutes les règles de ton `AGENTS.md` et de la
skill du dépôt (tableau ci-dessus) restent applicables, y compris ses
interdits propres.

### Réservé à la Workstation : ne le demande jamais

`tofu`/`terragrunt` `apply`, Cloudflare, secrets et Vaultwarden, déploiement
ou redémarrage d'une App, `just *-apply`, `truenas-*`, SSH vers un hôte : seul
le propriétaire les lance, depuis sa Workstation. Un item qui en dépend est
`RUNTIME` : parque-le avec la commande exacte, **sans** question. Ne pose pas
non plus de question sur le déroulé de cette skill : elle y répond.

## 0. Reprendre là où la passe précédente s'est arrêtée

Prépare le clone avec la skill du dépôt (section 1), puis :

```bash
cd <repo> && gh pr list --state open --json number,headRefName,url --jq '.[] | select(.headRefName | startswith("openclaw/roadmap-pass")) | "\(.number) \(.headRefName) \(.url)"'
```

- Une PR sort : `git fetch origin <branche> && git switch <branche>`, puis
  continue dessus (nouveaux commits, jamais de `--force`).
- Sinon : `git switch -c openclaw/roadmap-pass-<AAAAMMJJ> origin/master`.

Lis le dernier `docs/runbooks/*roadmap*.md` : ses items parqués ne se
retentent pas sans fait nouveau.

## 1. Porte « services fonctionnels »

**Services TrueNAS** : le heartbeat du Gateway (toutes les 30 min) dépose
dans ton espace de travail `status/homelab-health.json` : sondes Gatus en
échec, alertes Prometheus, conteneurs en panne, LiteLLM, et le budget de ta
clé LiteLLM (`coder_budget` : dépense, plafond, remise à zéro). Lis-le à la
racine de l'espace de travail (pas dans le clone) :

```bash
python3 -c 'import json;d=json.load(open("status/homelab-health.json"));print(d["generated_at"],d["counts"],d.get("coder_budget"));[print(a["sev"],a["text"]) for a in d["anomalies"][:15]]'
```

Fichier absent, ou `generated_at` vieux de plus de 2 h : état `STALE`, jamais
`PASS`.

**En direct sur TrueNAS** (HTTP en `GET`, lecture seule ; Gatus, POST et tout
autre chemin ou port du LAN sont refusés par le proxy, c'est voulu) :

```bash
curl -s 'http://172.17.0.24:9090/api/v1/query?query=up==0' | python3 -c 'import json,sys;[print("DOWN",r["metric"].get("job"),r["metric"].get("instance")) for r in json.load(sys.stdin)["data"]["result"]]'
curl -s http://172.17.0.24:9090/api/v1/alerts | python3 -c 'import json,sys;[print(a["labels"].get("severity"),a["labels"]["alertname"],a["labels"].get("job","")) for a in json.load(sys.stdin)["data"]["alerts"] if a["state"]=="firing"]'
curl -s http://172.17.0.24:8091/v2/version
curl -s http://172.17.0.24:8091/api/ui/services | python3 -c 'import json,sys,collections;d=json.load(sys.stdin);print(d.get("boardState"),collections.Counter(s.get("state") for s in d.get("services",[])))'
```

Prometheus n'accepte que `query`, `query_range`, `series`, `labels`,
`label/<nom>/values`, `alerts`, `rules`, `targets` et `metadata` ; les routes
de diagnostic de FastAPI (`/readyz`, `/api/health-board`…) répondent `401`
sans clé, c'est normal.

**FastAPI Sample sur FastAPI Cloud** (seule instance joignable) :

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://fastapi-sample.fastapicloud.dev/livez
curl -s https://fastapi-sample.fastapicloud.dev/v2/version
curl -s https://fastapi-sample.fastapicloud.dev/api/ui/services | python3 -c 'import json,sys,collections;d=json.load(sys.stdin);print(d.get("boardState"),collections.Counter(s.get("state") for s in d.get("services",[])))'
```

`build_revision` à `null` sur Cloud est normal ; `boardState=stale` aussi
(lecture passive du cache). Cloud ne voit pas le LAN : la plupart des services
y sont `unknown`, la référence pour TrueNAS reste `status/homelab-health.json`.

**Sondes en échec → référent infra** (`fastapi-sample` et `nabla-compose`
seulement). Une panne n'est imputée ni à la sonde ni au service sans le
verdict du référent, la session persistante `agent:coder:nabla-compose-infra`
(skill `nabla-infra-referee`) :

- `fastapi-sample` : réunis les sondes en échec (services `fail` ou `warn` de
  `http://172.17.0.24:8091/api/ui/services`, cibles `up==0` et alertes qui
  les concernent) et leur source dans le clone (`git grep -n '<service>' --
  nabla/`). S'il y en a, un seul `sessions_send` : `sessionKey`
  `agent:coder:nabla-compose-infra`, `timeoutSeconds: 600`, message
  `[skills/nabla-infra-referee/SKILL.md]` puis le format `QUESTION_SONDES` de
  cette skill (au plus 10 sondes). Suite de chaque `VERDICT` : `PROBE` →
  item `CODE` prioritaire, corriger la sonde avec un test ; `INFRA` →
  `RUNTIME`, parqué avec la preuve du référent (la passe nabla-compose le
  reprend) ; `EXPECTED` → rien à changer, citer la preuve ; `UNKNOWN`, refus,
  erreur ou délai dépassé → `UNKNOWN`, parqué sans question.
- `nabla-compose` : un `sessions_send` (`timeoutSeconds: 300`) de
  `[skills/nabla-infra-referee/SKILL.md] INFRA_EN_ATTENTE?` ; chaque ligne
  `INFRA` est une anomalie de service, traitée comme ci-dessous.

Aucun autre envoi : le référent ne répond qu'à ces formats.

**Code** :

```bash
cd <repo> && gh run list --branch master --limit 5 --json name,conclusion,headSha
cd <repo> && <porte hors ligne du tableau>
```

Avant ton premier changement, `just offline` affiche `files=0` sur
nabla-compose : c'est `NOT_RUN`, pas `PASS`.

Si `master` est rouge, le premier item est de réparer ce qui casse (par le
code). Une anomalie de service que le code de `<repo>` explique devient un
item `CODE` prioritaire ; les autres sont `RUNTIME`, parquées sans question.

## 2. PR ouvertes du dépôt

```bash
cd <repo> && gh pr list --state open --limit 20 --json number,title,author,headRefName,isCrossRepository,mergeable,mergeStateStatus,statusCheckRollup
```

Pour chaque PR (hors fork : `isCrossRepository` faux), classe-la :

| État | Action |
|---|---|
| `mergeable: CONFLICTING` | réparer les conflits (ci-dessous) |
| un check `FAILURE`/`ERROR` | lire `gh run view <run-id> --log-failed`, reproduire avec la porte hors ligne, corriger (ci-dessous) |
| `mergeStateStatus: BEHIND`, sans conflit ni échec | signaler « rebase suggéré » au compte rendu, rien d'autre |
| verte et à jour | rien |

Réparer, au plus **2 PR par passe**, sans jamais pousser sur la branche de la
PR elle-même :

```bash
cd <repo> && git fetch origin <headRefName> master
cd <repo> && git switch -c openclaw/fix-pr-<numéro>-<AAAAMMJJ> origin/<headRefName>
cd <repo> && git merge origin/master   # conflits : résous-les, puis la porte hors ligne
```

Commit (« fix: ... » en anglais), `git push -u origin HEAD`, puis
`gh pr create --draft --base <headRefName> --title "fix(pr-<numéro>): ..."` :
le propriétaire fusionne la correction dans sa branche s'il l'accepte. Une
PR `openclaw/fix-pr-<numéro>-*` déjà ouverte : continue dessus. Un échec
de CI qui demande un secret, un workflow ou un service : note-le, ne le
contourne pas (jamais de test désactivé ni de `skip`).

## 3. Itérer sur la roadmap

**Objectif de chaque passe : au moins un commit de code** (script, test,
correctif ; une modification de roadmap ou de runbook seule ne compte pas).

Sources : celles du tableau, dans leur ordre. Commence par **lister** les
items ouverts (ni `DONE` ni `ACCEPTED`) : identifiant et titre des 10
premiers. « Aucun item traitable » sans cette liste est une passe ratée.
Pour chaque item, par priorité, classe-le :

| Classe | Critère | Action |
|---|---|---|
| `CODE` | faisable et testable hors ligne : script, test, doc, catalogue, Compose non déployé | l'implémenter |
| `RUNTIME` | exige un hôte, Docker, un secret, un `apply` ou un déploiement | parquer avec la commande de réception Workstation, sans question |
| `DÉCISION` | exige un arbitrage du propriétaire | parquer, avec la question |

Pour chaque item `CODE` : le plus petit changement complet, le test le plus
proche puis la porte hors ligne, un commit par item (message conventionnel en
anglais). Dans la roadmap, marque l'item `CODED` ou `TESTED` avec la commande
lancée ; jamais `DEPLOYED` ni `ACCEPTED`. Un générateur indisponible hors
ligne (tofu, Docker, mise) rend l'item `RUNTIME`. Un item `RUNTIME` peut
souvent avancer côté code (test, script de réception, doc de la commande) :
cette part est `CODE`.

Un item déjà livré sur `master` (PR fusionnée, code présent) n'est **pas** un
item traité par toi : ferme-le à la boucle 1 avec sa référence.

Aucun item `CODE` dans la roadmap, ou tous bloqués : prends le premier
chantier de cette liste qui donne un commit, dans cet ordre :

1. un test ou une gate en échec (porte hors ligne, CI `master`) ;
2. un test pour du code non couvert : `uv run pytest -q --cov --cov-report=term-missing:skip-covered`
   (Python ; pour `fastapi-sample`, `--cov=nabla --cov-config=pyproject.toml`, son
   `.coveragerc` ne rapporte que `hooks/`) ou `node --test --experimental-test-coverage`
   (sites), module le moins couvert que la roadmap cite ;
3. la part code d'un item `RUNTIME` : script de réception, test de contrat,
   validation hors ligne de la commande que la Workstation lancera ;
4. un `TODO`/`FIXME` du code (`git grep -nE 'TODO|FIXME' -- '*.py' '*.ts' '*.sh'`) ;
5. un avertissement de lint ou de dépréciation.

Une passe sans commit de code doit lister, pour chacun des 5 chantiers, la
commande lancée et pourquoi elle n'a rien donné.

Bloqué : note le blocage, passe à l'item suivant, ne pose **aucune** question
en cours de passe. « Jusqu'à avoir fait l'ensemble » se fait sur plusieurs
jours : au plus 3 items `CODE` par exécution, ≤ 10 fichiers et ≤ 400 lignes
chacun ; après 40 minutes, termine l'item en cours et passe à l'étape 4.

Interdits : `.github/workflows/`, les contrôles de sécurité, les fichiers de
verrouillage, toute valeur de secret, la suppression de données persistantes.

## 4. Consolider la roadmap — trois boucles

Seulement si l'étape 3 a produit un commit, ou si un item est livré sur
`master` mais encore ouvert. Sinon écris « consolidation : sans objet » et
passe à l'étape 6. Chaque boucle relit les fichiers (pas ta mémoire de la
passe) et finit par un commit `docs(roadmap): ...` :

1. **Statuts** : chaque item touché porte son statut, sa preuve (commande,
   SHA) et la preuve manquante ; un item déjà livré sur `master` mais encore
   ouvert est fermé avec sa référence.
2. **Doublons et obsolètes** : fusionne les doublons entre les sources,
   retire ce qui ne s'applique plus, garde les liens.
3. **Recommandations** : relis le diff complet de la passe et ajoute au plus
   3 recommandations priorisées (quoi, pourquoi) dans une section
   « Recommandations de la passe du <AAAA-MM-JJ> ».

Parque blocages et questions dans
`docs/runbooks/<AAAA-MM-JJ>-openclaw-roadmap-pass.md` : un tableau
`item | classe | blocage | question ou commande de réception`.

## 5. Publier

```bash
cd <repo> && git push -u origin HEAD
```

Puis `gh pr create --draft` (titre `docs(roadmap): openclaw roadmap pass
<AAAA-MM-JJ>`, base `master`), ou un commentaire de bilan si la PR existe déjà. Le corps
liste les commandes restées `NOT_RUN` à lancer sur la Workstation.

`nabla-compose` : si la passe a traité une entrée `INFRA` du référent, envoie
`[skills/nabla-infra-referee/SKILL.md] BILAN_INFRA` avec les services touchés
et l'URL de la PR (`timeoutSeconds: 0`, sans attendre la réponse).

Push ou PR refusé (permission, 403) : ne cherche pas d'autre voie. Exporte
`git format-patch origin/master -o ~/outbox/<repo>-roadmap-pass-<AAAAMMJJ>/` et
réponds `BLOQUÉ: push` avec ce chemin.

## 6. Compte rendu (livré par le planificateur)

En français, au plus 30 lignes, sans rien envoyer toi-même, dans cet ordre :

1. **Services** : âge de `status/homelab-health.json` et compteurs
   (`crit`/`warn`/`unknown`, ou `STALE`), les 3 anomalies les plus graves ;
   FastAPI Cloud : `/livez`, version, compteurs de `/api/ui/services` ;
   budget du coder : `<dépense> / <plafond> USD`, remise à zéro, ou « non
   mesuré » ; référent infra : compteurs `PROBE`/`INFRA`/`EXPECTED`/`UNKNOWN`
   des verdicts reçus, « aucune sonde en échec » ou `NOT_RUN` (sans réponse).
2. **Code** : CI `master` (nom et conclusion des jobs), porte hors ligne
   (`PASS`, `FAIL` ou `NOT_RUN`).
3. **PR ouvertes** : `#numéro titre → état → action` pour chacune, URL des PR
   `openclaw/fix-pr-*` ouvertes.
4. **Roadmap** : les items listés à l'étape 3 avec leur classe ; items
   traités : uniquement les commits de cette passe, tels que les liste
   `git log --oneline origin/master..HEAD`. Chaque `PASS`/`FAIL` cite une
   commande exécutée dans cette passe **et la dernière ligne de sa sortie** ;
   toute autre vérification est `NOT_RUN`.
5. **Consolidation** : une ligne par boucle, ou « sans objet ».
6. **Publication** : exactement une de ces formes : URL de la PR Draft ;
   « aucun commit, aucune PR » ; `BLOQUÉ: push` et le chemin `~/outbox/...`.
7. **Blocages** `RUNTIME` (commande Workstation) et `DÉCISION` : nombre et
   les 3 plus importants.
8. **À la fin**, les questions restantes, numérotées : uniquement des
   arbitrages du propriétaire sur un item `DÉCISION`, aucune sur le déroulé.

Jamais de merge ni de passage en Ready ; n'annonce aucune réussite non
vérifiée.
