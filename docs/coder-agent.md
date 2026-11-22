# Agent `coder` : coder sur les dépôts GitHub du propriétaire depuis TrueNAS

**Statut : actif**, déployé sur TrueNAS le 10/11
(`deploy/truenas/devbox/contract.json` en `active`, `just devbox-plan`).
L'image `0.2.0` (Node pour les sites, `nabla-yubikey`) est codée le 20/11, pas
encore déployée. Cycle du contrat : `prepared_not_deployed` →
`ready_to_deploy` (images épinglées par digest) → `active`. Ce document est le
runbook de déploiement, d'exploitation et de rollback.

## Objectif

Piloter depuis un groupe Telegram (puis Discord) un agent OpenClaw qui clone
l'un des dépôts de son contrat (`repositories` de `contract.json` :
[`fastapi-sample`](https://github.com/AlbanAndrieu/fastapi-sample),
[`nabla-compose`](https://github.com/AlbanAndrieu/nabla-compose), les deux
sites Next.js et `nabla-yubikey`)
(par GitHub, jamais le checkout de déploiement `/mnt/cpool/compose/nabla-compose`
et ses `.env`), modifie le code, lance les vérifications du dépôt et ouvre des PR **Draft**, sans
jamais exécuter de code dans le conteneur du Gateway.

```text
Telegram (groupe forum, 1 sujet = 1 session)
  └─> Gateway OpenClaw (App openclaw-gateway, agent `coder`, modèle litellm-coder/gpt-4.1)
        │   clé LiteLLM : SecretRef `file` (credentials/litellm/coder.key), 11 USD / 7 jours
        └─ sandbox `ssh` (exec, read, write, edit, apply_patch ; ask_user et goals côté Gateway)
             └─> openclaw-devbox:2222 (réseau Docker interne `openclaw-devbox`)
                   └─ HTTPS CONNECT ─> openclaw-devbox-egress (squid) ─> GitHub, PyPI, npm, FastAPI Cloud
```

Ni le Gateway ni LiteLLM ne redémarrent : le réseau est rattaché à chaud
(`docker network connect`), la clé est lue par une SecretRef `file`
(`openclaw secrets reload`) et LiteLLM n'a pas besoin de la variable.

## Choix OpenClaw (2026.10.7)

| Fonctionnalité | Choix | Raison |
| --- | --- | --- |
| Agent dédié `coder` (`agents.entries.coder`) | **Retenu** | Espace de travail, modèle, outils, sandbox et sessions propres ; `main` et `cron` inchangés |
| Profil d'outils `coding` + sandbox `ssh` (`mode: all`, `scope: session`) | **Retenu** | Commandes et outils fichiers exécutés sur la devbox ; une session (sujet) = un espace de travail isolé |
| Sandbox Docker/Podman | Écarté | Exige le socket Docker dans le Gateway (équivalent root sur TrueNAS) |
| OpenTerminal (Open WebUI) | Écarté pour `coder` | Voir ci-dessous |
| Node host / hébergement de sessions | Écarté pour l'instant | Appairage et TLS à mettre en place ; c'est la brique de la phase « ops » |
| ACP (Claude Code, Codex) et skill `coding-agent` | Écarté | ACP tourne côté Gateway ; une session en sandbox ne peut pas le lancer |
| Tool Search | Inchangé | Pas désactivable par agent en 2026.10.7 ; la skill donne des commandes exactes |
| Telegram : `groups.<id>.topics."*".agentId = coder` | **Retenu** | Routage par sujet de forum, appliqué par CLI hors Git (identifiants personnels) |
| Discord `#fastapi-sample-dev` | Reporté | Discord reste désactivé sur TrueNAS tant que le `doctor` avec le vrai token n'est pas attesté (`docs/roadmap.md`) |

### Pourquoi pas OpenTerminal ?

[Open Terminal](https://github.com/open-webui/open-terminal) expose un terminal
par une API REST protégée par une clé statique, pensé d'abord pour Open WebUI.
Pour `coder`, le backend `ssh` natif reste préférable :

- **intégration** : OpenClaw ne connaît pas OpenTerminal comme backend de
  sandbox. Il faudrait passer par un outil MCP ou HTTP, refuser tous les outils
  natifs (`read`, `write`, `edit`, `apply_patch`, `exec`, `process`) et perdre le
  confinement `workspaceOnly`, l'espace par session, `sandbox explain` et les
  politiques d'outils ;
- **surface** : l'image embarque Docker CLI, Compose et Buildx, et installe des
  paquets à chaque démarrage (`OPEN_TERMINAL_PACKAGES`) : moins reproductible et
  plus large que la devbox ;
- **authentification** : une clé API statique sur HTTP, contre une clé SSH
  dédiée avec clé d'hôte épinglée et `restrict,pty`.

OpenTerminal garde un intérêt pour Open WebUI (navigateur de fichiers,
terminal dans le chat), sur un réseau isolé et sans socket Docker.

## Sécurité

| Menace (STRIDE) | Contrôle |
| --- | --- |
| Lecture des secrets du Gateway par `exec` (I) | `sandbox.mode: all` : aucun outil de code ne tourne dans le Gateway ; `elevated` désactivé pour `coder` |
| Sortie de l'espace de travail (E) | `tools.fs.workspaceOnly` ; `read /etc/passwd` refusé (test E2E) ; utilisateur `1001`, `cap_drop: ALL`, rootfs en lecture seule |
| Mouvement latéral vers le LAN, TrueNAS ou Docker (E) | Réseau `openclaw-devbox` interne ; aucun socket Docker, aucun accès hôte ; squid refuse les destinations privées et les IP littérales |
| Exfiltration, téléchargement arbitraire (I) | `egress/allowed-domains.txt` (`.github.com`, `.githubusercontent.com`, `pypi.org`, `files.pythonhosted.org`, `registry.npmjs.org`, `fastapi-sample.fastapicloud.dev` : santé publique en lecture, l'instance TrueNAS reste refusée), `dstdomain -n` (pas de DNS inverse), CONNECT 443 uniquement |
| Usurpation de la devbox ou du Gateway (S) | Clé d'hôte épinglée (`known_hosts`, `strictHostKeyChecking`, `updateHostKeys: false`) ; clé client dédiée, `restrict,pty` |
| Modification non revue de `master` (T) | Token fine-grained limité au dépôt (Contents, Pull requests ; ni Workflows ni Administration) ; protection de `master` ; PR Draft, jamais de merge |
| Prompt injection par le dépôt, les issues ou le web (T) | `workspaces/coder/AGENTS.md` : contenu = donnée ; outils web, messages, cron, gateway, nodes et sessions refusés |
| Dérive de coût (D) | Clé LiteLLM `openclaw-coder` : 11 USD par 7 jours (10 € par semaine tant que EUR/USD ≥ 1,10) ; `maxConcurrent: 2` pour ne pas bloquer `main` et `cron` |
| Traçabilité (R) | Traces Langfuse par clé LiteLLM ; commits sous l'identité `openclaw-coder` ; journal squid horodaté (`docker logs openclaw-devbox-egress`) |

Risques résiduels :

- le token GitHub et la clé d'hôte de la devbox sont lisibles par l'agent (même
  UID) : le token est limité aux dépôts publics du contrat, et la clé ne sert
  qu'au réseau interne ;
- `npm ci` (sites) exécute du code de dépendances dans la devbox, là où le
  token est lisible : seules les versions du `package-lock.json` s'installent,
  et `strict-allow-scripts` (npm 12) bloque les scripts d'installation non
  autorisés par le dépôt. Node et npm eux-mêmes sont vérifiés par SHA-256 au
  build (règle `build_downloads_verified`) ;
- l'allowlist GitHub autorise la lecture de n'importe quel dépôt public
  (prompt injection par contenu tiers) ;
- le LiteLLM TrueNAS relaie `gpt-4.1` vers celui de la Workstation (clé IDE) :
  si elle est éteinte, `coder` (comme `main` et `cron`) n'a plus de modèle, et
  sa consommation compte aussi sur cette clé amont.

## Capacités « ops » : volontairement absentes

La devbox ne peut **pas** exécuter de scripts sur l'hôte TrueNAS, lire les logs
Docker ou Loki, redémarrer des Apps ni créer de datasets : chacune de ces
capacités donne un accès équivalent à root (socket Docker, middleware TrueNAS)
ou expose des secrets (`docker inspect` affiche l'environnement de toutes les
Apps). Les ajouter à un agent qui lit du code et des issues tiers ferait d'une
prompt injection une compromission du NAS.

Si ces capacités sont voulues, elles relèvent d'un agent distinct (phase 2) :

| Besoin | Mécanisme proposé | Garde-fou |
| --- | --- | --- |
| Diagnostic des Apps | Node host OpenClaw sur TrueNAS, `exec` limité à `scripts/truenas/app-ops.sh status\|diagnose <app>` (`nabla-compose`) | Allowlist de commandes exactes côté node |
| Redémarrage d'une App | `app-ops.sh restart <app> --apply` | Approbation humaine à chaque appel (exec approvals dans Telegram) + `NABLA_RUNTIME_CHANGE_APPROVED` |
| Logs | Requêtes Loki en lecture seule (`http://172.17.0.24:3100`), pas de socket Docker | Label et durée bornés ; secrets éventuels dans les logs à filtrer |
| Datasets | `bootstrap-repository-storage.sh --apply <app>` via `app-ops.sh storage` | Même approbation ; jamais de `zfs destroy` |

Aucun de ces éléments n'est inclus dans ce dépôt pour l'instant.

## Identité GitHub de la devbox : App dédiée (décision O2, 21/11/2026)

Le propriétaire a retenu une **App GitHub dédiée**, pas un compte machine :
permissions fine-grained par dépôt, révocable, jeton d'installation de 1 h.
La clé privée vit dans Vaultwarden et dans le chemin runtime protégé
`/mnt/cpool/secrets/runtime/openclaw-devbox/` (`1001:1001`, `0400`), jamais
dans ce dépôt. Statut : **CODED** (manifeste), App **non créée**, helpers
`git-credential-devbox` et `gh-wrapper.sh` encore sur le token fine-grained.

Manifeste : [`deploy/truenas/devbox/github-app-manifest.json`](../deploy/truenas/devbox/github-app-manifest.json),
`public: false`, aucun webhook ni événement. Permissions, dérivées de ce que
fait la devbox (clone, push de `openclaw/*`, `gh pr create --draft`,
`gh pr list`, `gh run list`) :

| Permission | Niveau | Usage |
| --- | --- | --- |
| `contents` | write | clone et push des branches `openclaw/*` |
| `pull_requests` | write | `gh pr create --draft`, `gh pr list` |
| `actions` | read | `gh run list --branch master` (skill `nabla-roadmap-pass`) |
| `metadata` | read | obligatoire |

Refusées : `workflows` (la règle 4 interdit de toucher `.github/workflows/`),
`administration`, `checks`/`statuses` (aucune skill ne les lit), `issues`,
`secrets`, `environments`. L'App ne figure **pas** dans la liste de
contournement des rulesets : la PR de l'App exige l'approbation du
propriétaire, qui n'est plus l'auteur.

**Création (opérateur, une fois)** :

1. Ouvrir la page *Settings → Developer settings → GitHub Apps → New GitHub
   App* du compte `AlbanAndrieu` par le flux « manifest » : formulaire `POST`
   du contenu du manifeste (champ `manifest`) vers
   `https://github.com/settings/apps/new`. Après confirmation, GitHub
   redirige vers `redirect_url` avec `?code=…` (le port local n'a pas besoin
   d'écouter : lire le code dans la barre d'adresse, valable 1 h).
2. Échanger le code sans l'écrire dans un historique partagé :
   `gh api -X POST /app-manifests/<code>/conversions` renvoie l'`id`, le `slug`
   et le `pem` (clé privée). Ne rien afficher d'autre que l'`id`.
3. Ranger le `pem` dans Vaultwarden (entrée `nabla/prod/openclaw-devbox-github-app`,
   champ caché) et en `/mnt/cpool/secrets/runtime/openclaw-devbox/github_app.pem`
   (`1001:1001`, `0400`), puis supprimer toute copie locale.
4. *Install App* sur le compte, en **Only select repositories** : les cinq
   dépôts du contrat (`fastapi-sample`, `nabla-compose`, `nabla-site-alban`,
   `nabla-site-bababou`, `nabla-yubikey`), jamais `nabla-memo`. Noter
   l'`installation_id`.
5. Reste à coder (autre PR) : les deux helpers frappent un jeton
   d'installation (JWT RS256 signé par le `pem`, puis
   `POST /app/installations/<id>/access_tokens`) au lieu de lire
   `github_token`, avec le contrat, le test et le préflight adaptés ; puis
   révoquer l'ancien token fine-grained et activer 1 approbation requise sur
   les rulesets (entrée 7 du runbook opérateur).

## Prérequis opérateur

1. **Clé LiteLLM coder**, dans `nabla-compose` :
   `just openclaw-coder-key-plan`, puis
   `NABLA_RUNTIME_CHANGE_APPROVED=yes just openclaw-coder-key-apply`. La
   recette génère la valeur une seule fois dans
   `/mnt/cpool/secrets/runtime/litellm/.env.secrets`, écrit le fichier du
   Gateway `/mnt/cpool/openclaw/state/credentials/litellm/coder.key`
   (`1000:1000`, `0600`) et enregistre la clé (11 USD / 7 jours), sans aucun
   redémarrage. Importer ensuite la valeur dans Vaultwarden avec la commande
   affichée (`import_dotenv_to_bitwarden.py --app litellm`).
2. **Token GitHub** fine-grained, limité aux dépôts du contrat
   (`repositories`), *Contents* et *Pull requests* en lecture/écriture, expiration ≤ 90
   jours, dans `/mnt/cpool/secrets/runtime/openclaw-devbox/github_token`
   (`1001:1001`, `0400`). Protection de branche active sur `master` de
   **chaque** dépôt avant de l'ajouter au token.
3. **Groupe Telegram** de type forum (sujets activés), avec le bot et le
   propriétaire seulement ; noter son identifiant `-100…`.

Le dataset `cpool/openclaw-devbox` (en `noSnapshot` dans `nabla-compose`), les
clés SSH, les images et l'App sont créés par le déploiement.

## Déploiement

```bash
# 0. Workstation : épingler les images, passer le contrat en ready_to_deploy, fusionner
just test && just devbox-pin
#    résolveurs dans l'ordre (chaque échec est affiché) : API registry v2 (HEAD,
#    jeton anonyme, sans Docker), docker buildx, crane, docker pull ; sinon
#    `just devbox-pin --via truenas` (même résolution sur TrueNAS, puis sudo docker pull)
#    ou DEVBOX_PIN_PYTHON_IMAGE=sha256:... DEVBOX_PIN_DEBIAN_IMAGE=sha256:... just devbox-pin
#    contract.json : "status": "ready_to_deploy" ; just devbox-plan ; PR, merge,
#    puis mettre à jour le submodule apps/openclaw sur TrueNAS

# 1. Préflight en lecture seule (contrat, checkout TrueNAS, token, clé, dataset, App)
just truenas-deploy-coder

# 2. Production, en une commande (aucun redémarrage du Gateway ni de LiteLLM)
NABLA_RUNTIME_CHANGE_APPROVED=yes CODER_TELEGRAM_GROUP_ID=-100XXXXXXXXXX just truenas-deploy-coder --apply
```

`--apply` enchaîne : dataset (middleware TrueNAS) → clés SSH
(`truenas-bootstrap-coder`) → `docker compose build --pull` → création ou
redéploiement de l'App `openclaw-devbox` (`app.create` avec un `include`) →
attente `healthy` → preuve d'egress (`devbox-egress-check`) → agent, espace de
travail, SecretRef, `secrets reload` et groupe Telegram (`truenas-apply-coder`).
Chaque étape est idempotente : relancer la commande reprend où elle s'est
arrêtée.

## Vérifications

```bash
just devbox-egress-check     # route directe bloquée ; GitHub et PyPI tunnelés ; autres domaines, LAN, IP et HTTP refusés (403 squid)
ssh truenas sudo docker exec openclaw-gateway node openclaw.mjs sandbox explain --agent coder
```

Test de fumée, dans un nouveau sujet Telegram :

> Clone fastapi-sample, lance `just test-local-first`, ne commite rien et donne
> le compte rendu.

Résultat attendu : clone dans l'espace de la session, `uv sync --frozen` via le
proxy, puis `test-local-first` en `PASS`, sans commit ni push.

## Exploitation

- **Nouvelle tâche** : nouveau sujet du groupe (nouvelle session, nouvel espace
  de travail). Les espaces inactifs sont purgés après 7 jours
  (`sandbox.prune`) : pousser la branche avant.
- **Mise à jour de la skill ou de `AGENTS.md`** : modifier `workspaces/coder/`,
  puis `just truenas-apply-coder`. Les sessions existantes gardent l'ancienne
  copie ; ouvrir un nouveau sujet.
- **Refus du proxy** : `ssh truenas sudo docker logs --tail 50 openclaw-devbox-egress | grep TCP_DENIED`.
  Tout nouveau domaine passe par une PR qui modifie
  `egress/allowed-domains.txt` **et** `contract.json` (`just devbox-plan` le
  vérifie), puis `just truenas-deploy-coder --apply`.
- **Coût** : `just openclaw-truenas-virtual-keys-quota` (`nabla-compose`) ; le
  budget se réinitialise tous les 7 jours.
- **Revue quotidienne** (codée, non déclarée sur le Gateway au 19/11) : le job `fastapi-sample-daily-improvement` (06:17
  Europe/Paris, session isolée, 30 min max) lance les gates de
  `fastapi-sample` et propose au plus une PR Draft `openclaw/daily-*` ; il ne
  fait rien tant qu'une précédente est ouverte. Message :
  `policies/cron/fastapi-sample-daily-improvement.message.md`. Installation ou
  mise à jour (idempotente) :
  `just truenas-apply-coder-cron` (groupe Telegram du coder lu dans la
  configuration du Gateway, ou `CODER_TELEGRAM_GROUP_ID=-100...`). Arrêt :
  `openclaw cron disable <id>` dans le Gateway, avant tout rollback de l'agent.
- **Passes de roadmap** : un job `<repo>-roadmap-pass` par dépôt de l'agent,
  chaque nuit (Europe/Paris, session isolée, 60 min max), sur des créneaux
  d'une heure qui ne se chevauchent pas. Le budget LiteLLM de la clé `coder`
  n'a pas été revu pour cinq passes par nuit (décision du 22/11 : à regarder
  plus tard) :

  | Heure | Job |
  |---|---|
  | 01:00 | `nabla-yubikey-roadmap-pass` |
  | 02:00 | `nabla-compose-roadmap-pass` |
  | 03:00 | `fastapi-sample-roadmap-pass` |
  | 04:00 | `nabla-site-alban-roadmap-pass` |
  | 05:00 | `nabla-site-bababou-roadmap-pass` |

  Tous suivent la skill `nabla-roadmap-pass` (sources de roadmap et porte hors
  ligne par dépôt) : porte de code (santé des services `NOT_RUN` depuis la
  devbox), au plus 3 items faisables hors ligne, trois boucles de
  consolidation, une PR Draft `openclaw/roadmap-pass-*` reprise d'une passe à
  l'autre, questions à la fin. Message commun :
  `policies/cron/roadmap-pass.message.md` (`<repo>` remplacé à
  l'installation). Installation ou mise à jour d'un job :
  `just truenas-apply-coder-cron <repo>-roadmap-pass`, ou de tous les jobs du
  coder : `just truenas-apply-coder-cron all`.
- **Alertes d'échec** : chaque job annonce sur le groupe Telegram du coder, donc
  OpenClaw y envoie déjà une alerte après 2 échecs consécutifs (puis au plus
  une par heure), par exemple quand le budget de la clé est épuisé
  (`docs/cli/cron.md` d'OpenClaw 2026.10.7). Rien à configurer ;
  `failureAlert: false` sur un job la couperait.
- **Garde-fous de session** (22/11) : détection de boucles
  (`agents.entries.coder.tools.loopDetection.enabled`, imposée par
  `check-devbox-contract.py`), `ask_user` (boutons Telegram) et goals
  (`get_goal`, `create_goal`, `update_goal`, `/goal`, plafond `token_budget`).
  Après `just truenas-apply-coder`, la ligne `coder_sandbox=... tools=` doit
  les lister ; sinon `/tools` dans un sujet du coder.
- **Passe de roadmap enrichie** (22/11) : état des services TrueNAS par
  l'instantané `status/homelab-health.json`, que le collecteur du heartbeat
  (`scripts/heartbeat/homelab-health.mjs`) écrit dans `workspace-coder` toutes
  les 30 min et que chaque session reçoit à l'amorçage de sa sandbox (aucun
  accès LAN ni jeton dans la devbox) ; santé FastAPI Cloud par le proxy ; tri
  des PR ouvertes, avec au plus 2 corrections par passe sur des branches
  `openclaw/fix-pr-<n>-*` en PR Draft vers la branche de la PR ; actions
  réservées à la Workstation (`apply`, secrets, déploiements) parquées sans
  question.

## Rollback

```bash
CODER_TELEGRAM_GROUP_ID=-100XXXXXXXXXX just truenas-rollback-coder
```

Supprime l'agent `coder` (avec ses sessions et son espace local), son
fournisseur, sa SecretRef, son droit au modèle et le groupe Telegram, puis
arrête la devbox. Arrêter ensuite l'App `openclaw-devbox` dans l'UI. Les
datasets, les clés et les branches poussées sont conservés ; `main`, `cron`, le
heartbeat et les canaux ne changent pas.

## Preuves de cette préparation (10 novembre 2026)

- `openclaw config validate` (2026.10.7) : seed valide ;
  `sandbox explain --agent coder` : `all/ssh/session`, `elevated=false`.
- E2E local avec OpenClaw 2026.10.7, un sshd configuré comme la devbox et un
  modèle simulé : `exec` exécuté en UID 1001 avec le proxy, `write` puis
  relecture par SSH, `read /etc/passwd` refusé ; la clé LiteLLM est bien lue
  par la SecretRef `file` (aucune variable d'environnement). Le modèle ne
  reçoit en direct que `exec`, `process`, `read`, `ls`, `write`, `edit` et
  `apply_patch`, plus les contrôles Tool Search ; `sessions_send` et
  `view_image` restent introuvables même par `tool_call`.
- Squid 6 non-root avec `allowed-domains.txt` : GitHub et PyPI tunnelés ;
  `example.com`, `github.com.evil.example`, `140.82.112.3`, `[::1]`,
  `192.168.1.1`, `localhost`, HTTP en clair et port 8443 refusés.
- sshd non-root : PTY (devpts `gid=5` comme Docker), redirection de port
  refusée, mauvaise clé refusée.
- `truenas-deploy-coder` (plan, refus sans approbation, `--apply` complet puis
  relance), `truenas-bootstrap-coder`, `truenas-apply-coder` (idempotent) et
  `truenas-rollback-coder` exécutés contre un faux TrueNAS (CLI OpenClaw réel,
  squid réel).
- Non vérifié ici : build des images (registres inaccessibles depuis
  l'environnement de préparation), `secrets reload` sur un Gateway vivant,
  exécution réelle sur TrueNAS et appel réel à `gpt-4.1`.
