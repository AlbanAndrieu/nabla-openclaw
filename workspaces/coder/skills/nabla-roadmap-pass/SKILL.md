---
name: nabla-roadmap-pass
description: Passe horaire (24 min max) sur un dépôt de l'agent (nabla-compose, fastapi-sample, nabla-site-alban, nabla-site-bababou, nabla-yubikey) depuis la devbox. Vérifier l'état des services, réparer d'abord les PR ouvertes (retard sur master, conflits, CI rouge) et la CI de master, puis refactorer, améliorer la performance et stabiliser le code avec une mesure, puis réconcilier la roadmap avec master (une fois par jour) et implémenter un par un les items de roadmap faisables hors ligne ; consolider la roadmap en trois boucles seulement après un commit de code, et regrouper les blocages et les questions à la fin. Lancée par les jobs planifiés `<repo>-roadmap-pass`.
---

# Passe de roadmap d'un dépôt

Le message du job nomme le dépôt `<repo>`. Ce tableau donne sa skill de
préparation, ses sources de roadmap (par priorité) et sa porte hors ligne :

| Dépôt | Skill | Sources de roadmap | Porte hors ligne |
|---|---|---|---|
| `nabla-compose` | `nabla-compose-dev` | `docs/roadmap-portfolio.md`, `docs/roadmap.md` | `export AGENT_EXECUTION_MODE=offline && uv sync --frozen && just offline` |
| `fastapi-sample` | `fastapi-sample-dev` | `docs/engineering-roadmap.md`, `docs/homelab-security-roadmap.md` | `uv sync --frozen && just test-local-first` |
| `nabla-site-alban` | `nabla-site-dev` | `docs/quality-roadmap.md`, `docs/homelab-roadmap.md`, `docs/stripe-hardening-roadmap.md` | `npm ci --no-fund && npm run lint && npm run typecheck && npm run test:unit` |
| `nabla-site-bababou` | `nabla-site-dev` | `docs/roadmap.md`, `docs/engineering-roadmap.md` | `npm ci --no-fund && npm run lint && npm run typecheck && npm run test:unit` |
| `nabla-yubikey` | `nabla-yubikey-dev` | `docs/roadmap.md`, `docs/roadmap-workstation-yubikey.md`, `docs/roadmap-vault-pki.md`, `docs/workstation-yubikey-gpg-vault-roadmap.md` | `export AGENT_EXECUTION_MODE=offline && just test` |

Une source absente n'est pas une erreur : passe à la suivante. Le dernier
`docs/runbooks/*roadmap*.md` du dépôt, s'il existe, est l'état de la passe
précédente.

## Directive du propriétaire (texte d'origine)

> Une fois les services tous fonctionnel, reprendre la roadmap et implemente
> la et iter sur chaque item jusqu'à avoir fait l'ensemble. Si tu es bloqué
> pose tes questions une fois la roadmap entière faite. A la fin de la roadmap
> consolide la et recommandations la boucle trois fois puis pose moi les
> questions qu'il reste.

Ordre fixé par le propriétaire (23/11) : **corriger les PR** (retard sur
`master`, conflits) **et la CI**, **puis refactorer, améliorer la
performance et stabiliser** le comportement, **puis itérer sur la roadmap**
et en implémenter les items. Une passe qui ne fait que consolider la roadmap
est une passe ratée.

Sur la devbox, cela devient les étapes 1 à 7 ci-dessous. La devbox est hors
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

- Une PR sort : `git fetch origin <branche> master && git switch <branche>`,
  puis `git merge origin/master` (conflits résolus, porte hors ligne) et
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

**Pannes transmises par le référent infra** (`nabla-compose` seulement) :
un `sessions_send` à la session persistante `agent:coder:nabla-compose-infra`
(skill `nabla-infra-referee`, `timeoutSeconds: 300`) de
`[skills/nabla-infra-referee/SKILL.md] INFRA_EN_ATTENTE?` ; chaque ligne
`INFRA` est une anomalie de service confirmée par le job
`fastapi-sample-daily-improvement`, traitée comme ci-dessous. Aucun autre
envoi : le référent ne répond qu'à ces formats. Pour `fastapi-sample`, la
justesse des sondes est le travail de ce job quotidien, pas de la passe :
la passe s'en tient à sa roadmap.

**Code** :

```bash
cd <repo> && gh run list --branch master --limit 5 --json name,conclusion,headSha
cd <repo> && (<porte hors ligne du tableau>) > ../gate.log 2>&1; echo "gate_exit=$?" >> ../gate.log; tail -n 3 ../gate.log
```

Chaque porte hors ligne de cette skill se lance ainsi, avec `exec` et
`yieldMs: 120000`, son maximum. Elle dure souvent plus (`uv sync`, `npm ci`) :
si `exec` rend un identifiant de session, elle continue en arrière-plan.
Attends-la avec cette commande, elle aussi en `yieldMs: 120000`, relancée tant
que `gate_exit=` n'apparaît pas, 6 fois au plus (27/11 : fastapi-sample
rendait la main sur « je poursuivrai » pendant `uv sync`) :

```bash
cd <repo> && timeout 110 sh -c 'until grep -q "^gate_exit=" ../gate.log; do sleep 5; done'; tail -n 3 ../gate.log
```

`gate_exit=0` vaut `PASS` ; un autre code vaut `FAIL`, avec la ligne d'erreur
de `../gate.log` ; toujours rien après 6 attentes : `NOT_RUN` (délai).

Avant ton premier changement, `just offline` affiche `files=0` sur
nabla-compose : c'est `NOT_RUN`, pas `PASS`.

Une anomalie de service que le code de `<repo>` explique devient un item
`CODE` prioritaire ; les autres sont `RUNTIME`, parquées sans question.

**Objectif de chaque passe : au moins un commit de code** aux étapes 2 à 4
(script, test, correctif ; une modification de roadmap ou de runbook seule ne
compte pas).

## 2. Corriger les PR ouvertes, puis la CI de `master` (≤ 6 min)

```bash
cd <repo> && gh pr list --state open --limit 20 --json number,title,author,headRefName,isCrossRepository,mergeable,mergeStateStatus,statusCheckRollup
```

Pour chaque PR (hors fork : `isCrossRepository` faux), classe-la, dans cet
ordre de priorité :

| État | Action |
|---|---|
| `mergeable: CONFLICTING` | réparer les conflits (ci-dessous) |
| un check `FAILURE`/`ERROR` | lire `gh run view <run-id> --log-failed`, reproduire avec la porte hors ligne, corriger (ci-dessous) |
| `mergeStateStatus: BEHIND`, sans conflit ni échec | la mettre à jour avec `master` (ci-dessous), porte hors ligne verte |
| verte et à jour | rien |

Réparer, au plus **2 PR par passe**, sans jamais pousser sur la branche de la
PR elle-même (ta propre branche `openclaw/roadmap-pass-*` est déjà à jour
depuis l'étape 0) :

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

Puis la CI de `master` (étape 1) : rouge, ou porte hors ligne en échec,
répare ce qui casse par un commit sur ta branche de passe avant toute autre
chose.

## 3. Refactorer, accélérer, stabiliser (≤ 6 min)

Au plus un commit par axe, chacun **mesuré** avant et après dans cette passe
(sinon pas de commit) ; comportement inchangé, porte hors ligne verte :

| Axe | Cible | Mesure à citer |
|---|---|---|
| Refactor | duplication, fonction trop longue, code mort, dans le module que la roadmap ou les derniers commits touchent | lignes ou branches retirées, tests verts avant et après |
| Performance | test, script ou fonction lent du dépôt (`uv run pytest -q --durations=10`, `node --test` et ses durées) | durée avant et après (`/usr/bin/time -f %e`, `python3 -m timeit`) : gain d'au moins 10 % |
| Stabilité | test instable (3 exécutions), erreur non gérée, délai ou nouvelle tentative absents, `TODO`/`FIXME` de robustesse | test qui reproduit le défaut, en échec avant et vert après |

Sources de cibles, dans cet ordre : un test ou une gate en échec ; le module le
moins couvert (`uv run pytest -q --cov --cov-report=term-missing:skip-covered` ;
pour `fastapi-sample`, `--cov=nabla --cov-config=pyproject.toml`, son
`.coveragerc` ne rapporte que `hooks/` ; sites : `node --test
--experimental-test-coverage`) ; `git grep -nE 'TODO|FIXME' -- '*.py' '*.ts' '*.sh'` ;
un avertissement de lint ou de dépréciation. Un axe sans commit cite la
commande lancée et pourquoi elle n'a rien donné.

## 4. Itérer sur la roadmap

Sources : celles du tableau, dans leur ordre, lues **dans le clone** (27/11 :
nabla-yubikey annonçait « aucun fichier roadmap trouvé » alors que ses quatre
sources existent) :

```bash
cd <repo> && ls -1 docs/*roadmap*.md
```

Liste vide dans le clone : l'étape est en `FAIL`, jamais « aucun item ».

**Réconcilier d'abord**, une fois par jour : sautée seulement si l'en-tête de
réconciliation de la première source porte déjà la date du jour. La roadmap
doit refléter `master` avant que tu choisisses un item (27/11 : fastapi-sample
restait réconciliée au 22/11 après 5 jours de PR fusionnées) :

```bash
cd <repo> && grep -n -m3 -i 'réconcili' <première source du tableau>
cd <repo> && gh pr list --state merged --search "merged:>=<AAAA-MM-JJ de cet en-tête>" --limit 50 --json number,title,mergedAt --jq '.[] | "#\(.number) \(.mergedAt[:10]) \(.title)"'
cd <repo> && git grep -n -i 'réconciliation mise à jour' -- tests/
```

Chaque PR fusionnée qui livre un item ouvert le fait passer à `CODED` avec
`#<numéro>` (jamais `DEPLOYED` ni `ACCEPTED`) ; un item livré qui n'est plus
ouvert nulle part rejoint « Travaux terminés ». Mets à jour la date (même
format) et le SHA de `master` de l'en-tête, ou ajoute en tête de la première
source `> Réconciliation mise à jour le <date> (master <sha>)` s'il n'y en a
pas. Un test qui fige cet en-tête (troisième commande) change dans le même
commit ; lance-le. Commit `docs(roadmap): reconcile with master <sha court>`.
Ce commit justifie la PR, mais ne remplace pas le commit de code de la passe.

Puis **liste** les
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

Aucun item `CODE` dans la roadmap, ou tous bloqués : implémente la part code
d'un item `RUNTIME` (script de réception, test de contrat, validation hors
ligne de la commande que la Workstation lancera).

Bloqué : note le blocage, passe à l'item suivant, ne pose **aucune** question
en cours de passe. « Jusqu'à avoir fait l'ensemble » se fait sur plusieurs
passes (une par heure, 24 min max) : au plus 3 items `CODE` par exécution, ≤ 10 fichiers et ≤ 400 lignes
chacun ; après 15 minutes de passe, termine l'item en cours et passe à l'étape 5.

Interdits : `.github/workflows/`, les contrôles de sécurité, les fichiers de
verrouillage, toute valeur de secret, la suppression de données persistantes.

## 5. Consolider la roadmap — trois boucles

Seulement si les étapes 2 à 4 ont produit au moins un commit de code. Sinon
écris « consolidation : sans objet (aucun commit de code) », ne touche pas à
la roadmap et passe à l'étape 7. Chaque boucle relit les fichiers (pas ta
mémoire de la passe) et finit par un commit `docs(roadmap): ...` :

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

## 6. Publier

Une PR n'existe que pour un commit de code ou de réconciliation. Jamais de
fichier de notes (`docs/*notes*.md`, `NOTES.md`…) : la roadmap, son runbook
et le code sont les seuls fichiers d'une passe (27/11 : fastapi-sample#460
n'ajoutait qu'un titre dans `docs/roadmap_pass_notes.md`). Écris d'abord le
compte rendu détaillé dans `pr-body.md`, à la racine de ton espace de
travail : c'est le corps de la PR, en français, dans cet ordre :

1. **Services** : âge de `status/homelab-health.json` et compteurs
   (`crit`/`warn`/`unknown`, ou `STALE`), les 3 anomalies les plus graves ;
   FastAPI Cloud : `/livez`, version, compteurs de `/api/ui/services` ;
   budget du coder : `<dépense> / <plafond> USD`, remise à zéro, ou « non
   mesuré » ; `nabla-compose` : entrées `INFRA` reçues du référent, `AUCUNE`
   ou `NOT_RUN` (sans réponse).
2. **Code** : CI `master` (nom et conclusion des jobs), porte hors ligne
   (`PASS`, `FAIL` ou `NOT_RUN`).
3. **PR ouvertes** : `#numéro titre → état → action` pour chacune, URL des PR
   `openclaw/fix-pr-*` ouvertes.
4. **Refactor, performance, stabilité** : une ligne par axe, avec sa mesure
   avant et après et le SHA, ou la commande lancée et pourquoi rien. Puis
   **3 propositions d'amélioration**, même sans commit : `fichier:ligne`, la
   sortie d'outil de cette passe qui la justifie (couverture, durée, `TODO`,
   lint) et l'effort estimé. « Rien à proposer » est une passe ratée.
5. **Roadmap** : les items listés à l'étape 4 avec leur classe ; items
   traités : uniquement les commits de cette passe, tels que les liste
   `git log --oneline origin/master..HEAD`. Chaque `PASS`/`FAIL` cite une
   commande exécutée dans cette passe **et la dernière ligne de sa sortie** ;
   toute autre vérification est `NOT_RUN`.
6. **Consolidation** : une ligne par boucle, ou « sans objet ».
7. **Blocages** `RUNTIME`, avec la commande à lancer sur la Workstation
   (`NOT_RUN`), et `DÉCISION`, avec leur question.

**Jamais de push sur `master`**, ni direct ni `HEAD:master` : `master` ne
change que par une PR fusionnée par le propriétaire (27/11 : `GH013` a refusé
les pushes de nabla-site-bababou et de nabla-yubikey restés sur `master`). Le
push ne part que d'une branche `openclaw/*` ; sinon, crée
`openclaw/roadmap-pass-<AAAAMMJJ>` depuis ton `HEAD` et relance-le :

```bash
cd <repo> && b=$(git branch --show-current) && case "$b" in openclaw/*) git push -u origin "$b" ;; *) echo "push refusé : branche '$b'" ;; esac
cd <repo> && gh pr create --draft --base master --title "docs(roadmap): openclaw roadmap pass <AAAA-MM-JJ>" --body-file ../pr-body.md
```

La PR existe déjà : `gh pr comment <numéro> --body-file ../pr-body.md`.

`nabla-compose` : si la passe a traité une entrée `INFRA` du référent, envoie
`[skills/nabla-infra-referee/SKILL.md] BILAN_INFRA` avec les services touchés
et l'URL de la PR (`timeoutSeconds: 0`, sans attendre la réponse).

Push ou PR refusé (permission, 403) : ne cherche pas d'autre voie. Exporte
`git format-patch origin/master -o ~/outbox/<repo>-roadmap-pass-<AAAAMMJJ>/` et
réponds `BLOQUÉ: push` avec ce chemin.

## 7. Compte rendu Telegram (livré par le planificateur)

Le propriétaire le lit sur son téléphone, cinq dépôts par heure : au plus
15 lignes et 1 500 caractères, sans titre ni tableau, sans rien envoyer
toi-même. Le détail reste dans `pr-body.md` et la PR (27/11 : 58 comptes
rendus sur 81 dépassaient 2 000 caractères, l'URL de PR n'apparaissait que
dans 17). Gabarit, dans cet ordre :

```text
✅ <repo> : <ce que la passe a livré, en une phrase>
PR : <URL de la PR Draft | aucun commit, aucune PR | BLOQUÉ: push ~/outbox/...>
Porte : <PASS|FAIL|NOT_RUN> (<commande courte>) : <dernière ligne de sa sortie>
CI master : <verte | rouge : nom du job>
Commits : <sha court> <titre> ; … ou « aucun »
PR ouvertes : <#numéro → action> ; …
Roadmap : <n> items ouverts ; traités : <identifiants> ; réconciliation <faite | déjà du jour | NOT_RUN>
Propositions :
1. <fichier:ligne> : <amélioration> (<preuve de cette passe>, <effort>)
2. …
3. …
Blocages : <n> RUNTIME, <n> DÉCISION ; principal : <commande ou question courte>
Questions :
1. <arbitrage d'un item DÉCISION>
```

- Icône : `✅` pour au moins un commit de code et une porte `PASS`, `⚠️`
  sinon ; `AUTOMATION_FAILED` à sa place quand la passe n'a pas pu se
  dérouler.
- `Commits` recopie `git log --oneline origin/master..HEAD` ; chaque
  `PASS`/`FAIL` cite une commande de cette passe et la dernière ligne de sa
  sortie, le reste est `NOT_RUN`.
- Lignes `PR ouvertes`, `Blocages` et `Questions` sans objet : omises.
- Rien de nouveau (aucun commit, aucune PR ouverte ni poussée, aucun nouveau
  blocage, aucun échec) : la réponse est exactement `NO_REPLY`, sans gabarit.
- Pas de ligne `Services` : le heartbeat du Gateway les rapporte déjà (27/11 :
  la même section dans 68 comptes rendus sur 81). Seule exception, une ligne
  `Services :` quand une anomalie relève de ce dépôt (item `CODE`) ou que
  `status/homelab-health.json` est `STALE`.
- **À la fin**, les questions restantes, numérotées : uniquement des
  arbitrages du propriétaire sur un item `DÉCISION`, aucune sur le déroulé.

Jamais de merge ni de passage en Ready ; n'annonce aucune réussite non
vérifiée.
