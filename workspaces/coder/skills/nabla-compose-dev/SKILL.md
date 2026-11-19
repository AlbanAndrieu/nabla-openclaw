---
name: nabla-compose-dev
description: Cloner, modifier, tester et publier en PR Draft le dépôt AlbanAndrieu/nabla-compose depuis la devbox. À lire avant toute tâche de code sur nabla-compose.
---

# nabla-compose — boucle de développement sur la devbox

Le clone vient de GitHub, jamais du checkout de déploiement TrueNAS
(`/mnt/cpool/compose/nabla-compose`), qui n'est pas monté dans la devbox et
contient des secrets. Ce dépôt décrit l'infrastructure (TrueNAS, pfSense,
secrets, Cloudflare) : la devbox ne peut **que** modifier le code, jamais
l'appliquer.

## 1. Préparer le clone (une fois par session)

```bash
test -d nabla-compose/.git || git clone --filter=blob:none https://github.com/AlbanAndrieu/nabla-compose.git nabla-compose
cd nabla-compose && git fetch origin master && git status --short --branch
```

Sans `--recurse-submodules` : les sous-modules (`apps/fastapi-sample`,
`apps/openclaw`, `litellm`…) sont d'autres dépôts, hors périmètre ; n'en
initialiser un que si la tâche l'exige, en lecture seule.

Lire ensuite, dans le clone, `AGENTS.md`, puis la seule skill utile dans
`.agents/skills/` (`local-first-quality` décrit les gates). Le mode
d'exécution de la devbox est `AGENT_EXECUTION_MODE=offline` : pas de
TrueNAS, pfSense, Vaultwarden, Docker ni réseau privé.

## 2. Branche de travail

```bash
cd nabla-compose && git switch -c openclaw/<sujet-court> origin/master
```

## 3. Vérifications (du plus ciblé au plus large)

```bash
cd nabla-compose && export AGENT_EXECUTION_MODE=offline
cd nabla-compose && uv sync --frozen
cd nabla-compose && uv run pytest -q <tests/fichier_le_plus_proche>.py
cd nabla-compose && just offline                    # L1 syntaxique, sans dépendance
```

`mise`, Docker et les outils de scan ne sont pas dans la devbox : `just
quality`, `just pre-push` et toute recette `*-apply`, `truenas-*` ou
`*-tunnel*` donnent `NOT_RUN` avec leur raison, jamais un `PASS`. Ne lance
jamais une recette qui se connecte à un hôte, même en `check`.

## 4. Publier (uniquement sur demande explicite du propriétaire)

Même procédure que la skill `fastapi-sample-dev` (section 4), dans
`nabla-compose/`. Le corps de la PR liste les commandes de réception à
lancer sur la Workstation pour ce qui est resté `NOT_RUN`.

## Interdits propres à ce dépôt

- Lire, créer ou modifier un `.env`, `.env.secrets` ou fichier sous
  `/mnt/cpool/secrets/` ; un secret ne passe jamais dans un diff ou un message.
- Affaiblir une protection (authentification, exposition publique, pare-feu,
  ruleset, gate) ou supprimer une donnée persistante.
