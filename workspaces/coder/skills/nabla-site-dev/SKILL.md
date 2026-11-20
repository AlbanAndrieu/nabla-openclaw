---
name: nabla-site-dev
description: Cloner, modifier, tester et publier en PR Draft les sites Next.js AlbanAndrieu/nabla-site-alban et AlbanAndrieu/nabla-site-bababou depuis la devbox. À lire avant toute tâche de code sur l'un de ces deux sites.
---

# nabla-site-alban et nabla-site-bababou — boucle de développement sur la devbox

Deux sites Next.js publics, déployés par Vercel. La devbox a Node 24 et npm 12
(versions exigées par `engines`) ; le proxy n'autorise que GitHub, PyPI et
`registry.npmjs.org`. Remplacer `<site>` par `nabla-site-alban` ou
`nabla-site-bababou`.

## 1. Préparer le clone (une fois par session)

```bash
test -d <site>/.git || git clone --filter=blob:none https://github.com/AlbanAndrieu/<site>.git <site>
cd <site> && git fetch origin master && git status --short --branch
```

Lire ensuite, dans le clone, `AGENTS.md` (mode d'exécution, gates, règles de
publication propres au site) puis la seule skill utile dans `.agents/skills/`.
La devbox n'est ni la Workstation ni le LAN : sondes OWNER/LAN, Vercel, Sops
et navigateurs sont `NOT_RUN`.

## 2. Branche de travail

```bash
cd <site> && git switch -c openclaw/<sujet-court> origin/master
```

## 3. Dépendances et vérifications (du plus ciblé au plus large)

```bash
cd <site> && npm ci --no-fund
cd <site> && node --test <unit-tests/fichier_le_plus_proche>.test.mjs
cd <site> && npm run lint
cd <site> && npm run typecheck
cd <site> && npm run test:unit
```

- `npm ci` suit le `package-lock.json` et le `.npmrc` du dépôt
  (`strict-allow-scripts`) : ne pas ajouter `--force`, ni modifier `.npmrc`,
  `allowScripts` ou le lockfile pour faire passer une installation.
- `npm run build`, `npm test` (Playwright), Lighthouse, ZAP et `just quality`
  téléchargent des navigateurs ou appellent des services hors allowlist :
  `NOT_RUN` avec leur raison, jamais un `PASS`. La CI GitHub les exécute.

## 4. Publier (uniquement sur demande explicite du propriétaire)

Même procédure que la skill `fastapi-sample-dev` (section 4), dans `<site>/`,
en respectant les règles de commit et de PR de l'`AGENTS.md` du site (par
exemple : pas de `[skip ci]` sur `nabla-site-bababou`).

## Interdits propres à ces dépôts

- Lire, déchiffrer ou modifier `secrets.env.sops`, `.env*` ou `.sops.yaml`.
- Modifier `vercel.json`, les en-têtes de sécurité (CSP, HSTS) ou les règles
  d'accès sans demande explicite, et toujours en le signalant.
