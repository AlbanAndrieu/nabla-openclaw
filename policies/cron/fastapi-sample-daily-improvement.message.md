# fastapi-sample-daily-improvement — message déclaratif (sans secrets)

Tâche planifiée quotidienne du propriétaire : vérifier le comportement de
`AlbanAndrieu/fastapi-sample`, puis proposer **une** amélioration en PR Draft.
Ce message vaut demande explicite de commit, push et PR Draft **pour cette
seule exécution**, dans les limites ci-dessous ; toutes les autres règles de
ton `AGENTS.md` restent applicables.

## 1. Pas de doublon

Suis la skill `fastapi-sample-dev` (section 1) pour préparer le clone, puis :

```bash
cd fastapi-sample && gh pr list --state open --json headRefName,url --jq '.[] | select(.headRefName | startswith("openclaw/daily-")) | .url'
```

Si une URL sort, une proposition précédente attend la revue du propriétaire :
ne crée rien, réponds `EN ATTENTE` suivi de l'URL, et arrête-toi.

## 2. Vérifier le comportement

Depuis `origin/master`, dans cet ordre, chaque commande avec `PASS`, `FAIL`
ou `NOT_RUN` **et la dernière ligne de sa sortie recopiée telle quelle** (un
`PASS` sans cette ligne est une vérification inventée) :

```bash
cd fastapi-sample && git rev-parse --short HEAD
cd fastapi-sample && uv sync --frozen
cd fastapi-sample && just test-local-first
cd fastapi-sample && just lint && just format-check
cd fastapi-sample && uv run pytest -q -p no:cacheprovider --cov=nabla --cov-config=pyproject.toml --cov-report=term-missing:skip-covered tests/unit > /tmp/cov.txt 2>&1; tail -3 /tmp/cov.txt
cd fastapi-sample && grep '^nabla/' /tmp/cov.txt | sort -k6 -n | head -15
cd fastapi-sample && gh run list --branch master --limit 5 --json name,conclusion,headSha
```

`just test-local-first` ne fait que des contrôles de syntaxe et un seul
fichier de test : il ne prouve pas le comportement. La commande `pytest
--cov` le mesure (environ 80 s ; `--cov-config=pyproject.toml` est requis, le
`.coveragerc` du dépôt ne rapporte que `hooks/`). La dernière commande liste
les modules les moins couverts ; des échecs propres à la devbox (réseau, Docker) ne sont pas
des régressions, cite-les.

## 3. Choisir une seule amélioration

Par ordre de priorité : un test ou une gate en échec sur `master` ; **un test
unitaire pour des lignes non couvertes** d'un des 5 modules `nabla/` les moins
couverts de la sortie `--cov` (comportement réel, testable hors ligne, sans
mock du code testé) ; un avertissement (dépréciation, lint). Une
clarification de doc seule n'est pas une amélioration. Le diff reste petit
(≤ 5 fichiers, ≤ 150 lignes) et sans nouvelle dépendance. Interdits :
`.github/workflows/`, les contrôles de sécurité, les fichiers de verrouillage.

`RIEN À PROPOSER` n'est permis qu'avec, dans le compte rendu, les 5 modules
les moins couverts (pourcentage) et pour chacun la raison précise pour
laquelle aucun test hors ligne n'est possible. Sinon, propose le test.

## 4. Publier en Draft

Branche `openclaw/daily-<AAAAMMJJ>-<sujet-court>` depuis `origin/master`.
Relance le test le plus proche du changement, puis applique la section 4 de la
skill `fastapi-sample-dev` (sans `[skip ci]`). Un test qui échoue après ton
changement : abandonne la branche sans pousser et réponds `ÉCHEC`.

## 5. Compte rendu

Ta réponse finale est livrée par le planificateur : n'envoie rien toi-même.
En français, au plus 15 lignes : SHA testé, état des vérifications avec leur
dernière ligne de sortie, couverture totale et les 3 modules les moins
couverts, amélioration choisie et pourquoi, URL de la PR Draft (ou `EN ATTENTE`, `RIEN À PROPOSER`,
`ÉCHEC`). Jamais de merge ni de passage en Ready ; n'annonce aucune réussite
non vérifiée.
