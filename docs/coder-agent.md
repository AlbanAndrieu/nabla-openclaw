# Agent `coder` : coder sur fastapi-sample depuis TrueNAS

**Statut : préparé, non déployé** (`deploy/truenas/devbox/contract.json`,
`just devbox-plan`). Cycle du contrat : `prepared_not_deployed` →
`ready_to_deploy` (images épinglées par digest) → `active`. Ce document est le
runbook de déploiement, d'exploitation et de rollback.

## Objectif

Piloter depuis un groupe Telegram (puis Discord) un agent OpenClaw qui clone
[`AlbanAndrieu/fastapi-sample`](https://github.com/AlbanAndrieu/fastapi-sample),
modifie le code, lance les vérifications du dépôt et ouvre des PR **Draft**, sans
jamais exécuter de code dans le conteneur du Gateway.

```text
Telegram (groupe forum, 1 sujet = 1 session)
  └─> Gateway OpenClaw (App openclaw-gateway, agent `coder`, modèle litellm-coder/gpt-4.1)
        │   clé LiteLLM : SecretRef `file` (credentials/litellm/coder.key), 11 USD / 7 jours
        └─ sandbox `ssh` (exec, read, write, edit, apply_patch)
             └─> openclaw-devbox:2222 (réseau Docker interne `openclaw-devbox`)
                   └─ HTTPS CONNECT ─> openclaw-devbox-egress (squid) ─> GitHub, PyPI
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
| Exfiltration, téléchargement arbitraire (I) | `egress/allowed-domains.txt` (`.github.com`, `.githubusercontent.com`, `pypi.org`, `files.pythonhosted.org`), `dstdomain -n` (pas de DNS inverse), CONNECT 443 uniquement |
| Usurpation de la devbox ou du Gateway (S) | Clé d'hôte épinglée (`known_hosts`, `strictHostKeyChecking`, `updateHostKeys: false`) ; clé client dédiée, `restrict,pty` |
| Modification non revue de `master` (T) | Token fine-grained limité au dépôt (Contents, Pull requests ; ni Workflows ni Administration) ; protection de `master` ; PR Draft, jamais de merge |
| Prompt injection par le dépôt, les issues ou le web (T) | `workspaces/coder/AGENTS.md` : contenu = donnée ; outils web, messages, cron, gateway, nodes et sessions refusés |
| Dérive de coût (D) | Clé LiteLLM `openclaw-coder` : 11 USD par 7 jours (10 € par semaine tant que EUR/USD ≥ 1,10) ; `maxConcurrent: 2` pour ne pas bloquer `main` et `cron` |
| Traçabilité (R) | Traces Langfuse par clé LiteLLM ; commits sous l'identité `openclaw-coder` ; journal squid horodaté (`docker logs openclaw-devbox-egress`) |

Risques résiduels :

- le token GitHub et la clé d'hôte de la devbox sont lisibles par l'agent (même
  UID) : le token est limité à un dépôt public, et la clé ne sert qu'au réseau
  interne ;
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
2. **Token GitHub** fine-grained, dépôt `fastapi-sample` seul, *Contents* et
   *Pull requests* en lecture/écriture, expiration ≤ 90 jours, dans
   `/mnt/cpool/secrets/runtime/openclaw-devbox/github_token` (`1001:1001`,
   `0400`). Protection de branche active sur `master`.
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
