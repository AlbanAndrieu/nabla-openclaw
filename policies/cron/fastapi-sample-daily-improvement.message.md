# fastapi-sample-daily-improvement — message déclaratif (sans secrets)

Tâche planifiée quotidienne du propriétaire : mesurer la **justesse des
sondes, checks et statuts** de `AlbanAndrieu/fastapi-sample` (ce qu'ils
affichent face à l'état réel de TrueNAS), puis corriger **une** sonde en PR
Draft. La roadmap du dépôt est le travail de `fastapi-sample-roadmap-pass`,
pas de ce job. Ce message vaut demande explicite de commit, push et PR Draft
**pour cette seule exécution**, dans les limites ci-dessous ; toutes les
autres règles de ton `AGENTS.md` restent applicables.

Première action, obligatoire : appelle ton outil `exec` (section 1). Chaque
SHA, compteur, `PASS` ou `FAIL` du compte rendu recopie une sortie d'outil de
cette exécution ; un compte rendu écrit sans aucun appel d'outil est une
exécution ratée, même s'il paraît plausible (23/11 : `PASS` inventés en 23 s).

## 1. Pas de doublon

Suis la skill `fastapi-sample-dev` (section 1) pour préparer le clone, puis :

```bash
cd fastapi-sample && gh pr list --state open --json headRefName,url --jq '.[] | select(.headRefName | startswith("openclaw/daily-")) | .url'
```

Si une URL sort, une proposition précédente attend la revue du propriétaire :
ne crée rien, réponds `EN ATTENTE` suivi de l'URL, et arrête-toi.

## 2. Mesurer

Lance chaque commande avec `exec`, dans cet ordre, et note `PASS`, `FAIL` ou
`NOT_RUN` **avec la dernière ligne de sa sortie recopiée telle quelle** (un
`PASS` sans cette ligne est une vérification inventée, et un compte rendu
sans ces sorties est une exécution ratée) :

```bash
cd fastapi-sample && git rev-parse --short HEAD
curl -s http://172.17.0.24:8091/api/ui/services | python3 -c 'import json,sys,collections;d=json.load(sys.stdin);s=d.get("services",[]);[print(x["state"],x["name"]) for x in s if x.get("state")!="ok"];print(d.get("boardState"),dict(collections.Counter(x.get("state") for x in s)))'
curl -s 'http://172.17.0.24:9090/api/v1/query?query=up' | python3 -c 'import json,sys;r=json.load(sys.stdin)["data"]["result"];[print("DOWN",x["metric"].get("job"),x["metric"].get("instance")) for x in r if x["value"][1]=="0"];print(len(r),"cibles")'
curl -s http://172.17.0.24:9090/api/v1/alerts | python3 -c 'import json,sys;a=[x for x in json.load(sys.stdin)["data"]["alerts"] if x["state"]=="firing"];[print(x["labels"].get("severity"),x["labels"]["alertname"],x["labels"].get("job","")) for x in a];print(len(a),"alertes")'
curl -s https://fastapi-sample.fastapicloud.dev/api/ui/services | python3 -c 'import json,sys,collections;d=json.load(sys.stdin);print(d.get("boardState"),dict(collections.Counter(x.get("state") for x in d.get("services",[]))))'
python3 -c 'import json;d=json.load(open("status/homelab-health.json"));print(d["generated_at"],d["counts"])'
```

La dernière commande se lance à la racine de l'espace de travail (pas dans
le clone) ; fichier absent ou vieux de plus de 2 h : `STALE`. Cloud ne voit
pas le LAN : ses `unknown` sont normaux, l'instance TrueNAS fait foi.

## 3. Confronter

Pour chaque service que la sonde TrueNAS n'affiche pas `ok`, et pour chaque
cible `DOWN` ou alerte sans service en échec, trouve la sonde dans le clone
(`git grep -n '<service>' -- nabla/`) et classe le couple sonde / réel :

| Classe | Sonde | État réel (Prometheus, alertes, `homelab-health.json`) |
| --- | --- | --- |
| `JUSTE` | `fail`/`warn` | panne confirmée |
| `FAUSSE_ALERTE` | `fail`/`warn` | service actif (`up` à 1, aucune alerte) |
| `PANNE_RATÉE` | `ok` | `up` à 0 ou alerte qui le vise |
| `INCONNU` | `unknown`, ou aucune cible Prometheus correspondante | — |

Justesse = `JUSTE` / (`JUSTE` + `FAUSSE_ALERTE` + `PANNE_RATÉE`), en
comptant comme `JUSTE` les services `ok` dont la cible est à 1.

Puis un seul `sessions_send` au référent infra pour les `FAUSSE_ALERTE`, les
`PANNE_RATÉE` et les `JUSTE` en échec (au plus 10) : `sessionKey`
`agent:coder:nabla-compose-infra`, `timeoutSeconds: 600`, message
`[skills/nabla-infra-referee/SKILL.md]` puis le format `QUESTION_SONDES` de
cette skill. `VERDICT PROBE` confirme un défaut de la sonde ; `INFRA`, une
vraie panne (rien à corriger ici, la passe nabla-compose la reprend) ;
`EXPECTED`, un échec voulu ; `UNKNOWN`, refus ou délai dépassé : sans
verdict, ne corrige rien sur cette sonde. Rien à envoyer si tout est `JUSTE`
ou `INCONNU`.

## 4. Corriger une seule sonde

Par ordre de priorité : une sonde au `VERDICT PROBE` (`FAUSSE_ALERTE` ou
`PANNE_RATÉE`) ; une sonde `EXPECTED` affichée en échec qui devrait
l'accepter ; un check ou statut sans test unitaire de sa classification
(le payload observé, sans secret, en fixture ; aucun appel réseau dans le
test). Le diff reste petit (≤ 5 fichiers, ≤ 150 lignes) et sans nouvelle
dépendance. Interdits : `.github/workflows/`, les contrôles de sécurité, les
fichiers de verrouillage.

`RIEN À CORRIGER` n'est permis qu'avec une justesse de 100 % et la liste des
`INCONNU`, chacun avec la raison pour laquelle on ne peut pas le confronter.

## 5. Publier en Draft

Branche `openclaw/daily-<AAAAMMJJ>-<sujet-court>` depuis `origin/master`.
`cd fastapi-sample && uv sync --frozen`, le test le plus proche
(`bash scripts/run-pytest-compact.sh tests/unit/<fichier>.py`), puis
`just lint && just format-check`, et applique la section 4 de la skill
`fastapi-sample-dev` (sans `[skip ci]`). Un test qui échoue après ton
changement : abandonne la branche sans pousser et réponds `ÉCHEC`.

## 6. Compte rendu

Ta réponse finale est livrée par le planificateur : n'envoie rien toi-même.
En français, au plus 15 lignes : SHA ; compteurs de la sonde TrueNAS, cibles
`DOWN` et alertes, âge de `homelab-health.json` ; justesse en % avec le
détail `JUSTE`/`FAUSSE_ALERTE`/`PANNE_RATÉE`/`INCONNU` ; une ligne par écart
avec son verdict ; correction choisie et pourquoi ; URL de la PR Draft (ou
`EN ATTENTE`, `RIEN À CORRIGER`, `ÉCHEC`). Jamais de merge ni de passage en
Ready ; n'annonce aucune réussite non vérifiée.
