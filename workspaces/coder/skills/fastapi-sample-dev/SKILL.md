---
name: fastapi-sample-dev
description: Cloner, modifier, tester et publier en PR Draft le dépôt AlbanAndrieu/fastapi-sample depuis la devbox. À lire avant toute tâche de code sur fastapi-sample.
---

# fastapi-sample — boucle de développement sur la devbox

Commandes exactes, à lancer avec `exec` depuis la racine de l'espace de travail
de la session. Ne pas inventer d'autres scripts ou options : en cas de doute,
lire le `justfile` ou le `AGENTS.md` du dépôt.

## 1. Préparer le clone (une fois par session)

```bash
test -d fastapi-sample/.git || git clone --filter=blob:none https://github.com/AlbanAndrieu/fastapi-sample.git fastapi-sample
cd fastapi-sample && git fetch origin master && git status --short --branch
```

Lire ensuite, dans le clone, `AGENTS.md`, puis la seule section utile à la
tâche (`just agent-context <ui|api|quality|...>` aide à la choisir). Les skills
du dépôt sont dans `.agents/skills/` ; `local-first-quality` décrit les gates.

## 2. Branche de travail

```bash
cd fastapi-sample && git switch -c openclaw/<sujet-court> origin/master
```

## 3. Dépendances et vérifications (du plus ciblé au plus large)

```bash
cd fastapi-sample && uv sync --frozen
cd fastapi-sample && just test-local-first          # L1 rapide, sans réseau
cd fastapi-sample && just lint && just format-check
cd fastapi-sample && bash scripts/run-pytest-compact.sh tests/unit/<fichier>.py
cd fastapi-sample && just ui-quick                  # seulement pour l'UI /api
cd fastapi-sample && just quality                   # L2, plus long
```

Lancer d'abord le test le plus proche du changement. `just quality` peut
dépasser plusieurs minutes : utiliser `yieldMs` puis `process` pour suivre la
sortie, sans relancer en boucle. Un outil absent de la devbox (`trivy`,
`betterleaks`…) donne `NOT_RUN` avec sa raison, jamais un `PASS`.

## 4. Publier (uniquement sur demande explicite du propriétaire)

```bash
cd fastapi-sample && git add -- <fichiers modifiés> && git diff --cached --stat
cd fastapi-sample && git commit -m "<type>(<scope>): <résumé en anglais> [skip ci]"
cd fastapi-sample && git push -u origin HEAD
cd fastapi-sample && gh pr create --draft --base master --title "<titre en français>" --body-file <fichier>
```

- Messages de commit au format Conventional Commits, comme l'historique du
  dépôt ; `[skip ci]` seulement en mode local-first demandé par le
  propriétaire, et la PR reste Draft.
- Corps de PR en français : contexte, changements, vérifications
  `PASS`/`FAIL`/`NOT_RUN`, risques. Terminer par
  `Généré par l'agent OpenClaw coder (devbox TrueNAS).`
- Après la PR, donner son URL et s'arrêter : pas de merge, pas de Ready.

## Échecs fréquents

| Symptôme | Cause | Action |
| --- | --- | --- |
| `403` ou `CONNECT tunnel failed` | domaine hors allowlist du proxy | le signaler, ne pas contourner |
| `remote: Permission denied` sur `.github/workflows` | le token n'a pas ce droit, c'est voulu | retirer ce changement |
| `QG_LOCKED` (code 75) | une autre gate tourne sur ce checkout | attendre, ne pas supprimer le verrou |
