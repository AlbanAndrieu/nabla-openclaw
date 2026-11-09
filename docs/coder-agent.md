# Agent `coder` : coder sur fastapi-sample depuis TrueNAS

**Statut : préparé, non déployé** (`deploy/truenas/devbox/contract.json`,
`just devbox-plan`). Ce document est le runbook de déploiement, d'exploitation et
de rollback.

## Objectif

Piloter depuis un groupe Telegram (puis Discord) un agent OpenClaw qui clone
[`AlbanAndrieu/fastapi-sample`](https://github.com/AlbanAndrieu/fastapi-sample),
modifie le code, lance les vérifications du dépôt et ouvre des PR **Draft**, sans
jamais exécuter de code dans le conteneur du Gateway.

```text
Telegram (groupe forum, 1 sujet = 1 session)
  └─> Gateway OpenClaw (App openclaw-gateway, agent `coder`, modèle litellm-coder/gpt-4.1)
        └─ sandbox `ssh` (exec, read, write, edit, apply_patch)
             └─> openclaw-devbox:2222 (réseau Docker interne `openclaw-devbox`)
                   └─ HTTPS CONNECT ─> openclaw-devbox-egress (squid) ─> GitHub, PyPI
```

## Choix OpenClaw (2026.10.7)

| Fonctionnalité | Choix | Raison |
| --- | --- | --- |
| Agent dédié `coder` (`agents.entries.coder`) | **Retenu** | Espace de travail, modèle, outils, sandbox et sessions propres ; `main` et `cron` inchangés |
| Profil d'outils `coding` + sandbox `ssh` (`mode: all`, `scope: session`) | **Retenu** | Commandes et outils fichiers exécutés sur la devbox ; une session (sujet) = un espace de travail isolé |
| Sandbox Docker/Podman | Écarté | Exige le socket Docker dans le Gateway (équivalent root sur TrueNAS) |
| Node host / hébergement de sessions | Écarté pour l'instant | Appairage et TLS à mettre en place ; espaces de travail transférés par le Gateway |
| ACP (Claude Code, Codex) et skill `coding-agent` | Écarté | ACP tourne côté Gateway ; une session en sandbox ne peut pas le lancer |
| Tool Search | Inchangé | Pas désactivable par agent en 2026.10.7 ; la skill donne des commandes exactes |
| Telegram : `groups.<id>.topics."*".agentId = coder` | **Retenu** | Routage par sujet de forum, appliqué par CLI hors Git (identifiants personnels) |
| Discord `#fastapi-sample-dev` | Reporté | Discord reste désactivé sur TrueNAS tant que le `doctor` avec le vrai token n'est pas attesté (`docs/roadmap.md`) |

## Sécurité

| Menace (STRIDE) | Contrôle |
| --- | --- |
| Lecture des secrets du Gateway par `exec` (I) | `sandbox.mode: all` : aucun outil de code ne tourne dans le Gateway ; `elevated` désactivé pour `coder` |
| Sortie de l'espace de travail (E) | `tools.fs.workspaceOnly` ; `read /etc/passwd` refusé (test E2E) ; utilisateur `1001`, `cap_drop: ALL`, rootfs en lecture seule |
| Mouvement latéral vers le LAN ou les Apps (E) | Réseau `openclaw-devbox` interne ; seul le proxy sort ; destinations privées refusées par squid |
| Exfiltration, téléchargement arbitraire (I) | Allowlist `.github.com`, `.githubusercontent.com`, `pypi.org`, `files.pythonhosted.org`, CONNECT 443 uniquement |
| Usurpation de la devbox ou du Gateway (S) | Clé d'hôte épinglée (`known_hosts`, `strictHostKeyChecking`, `updateHostKeys: false`) ; clé client dédiée, `restrict,pty` |
| Modification non revue de `master` (T) | Token fine-grained limité au dépôt (Contents, Pull requests ; ni Workflows ni Administration) ; protection de `master` ; PR Draft, jamais de merge |
| Prompt injection par le dépôt, les issues ou le web (T) | `workspaces/coder/AGENTS.md` : contenu = donnée ; outils web, messages, cron, gateway, nodes et sessions refusés |
| Dérive de coût (D) | Clé LiteLLM `openclaw-coder` dédiée (budget, RPM) ; `maxConcurrent: 2` pour ne pas bloquer `main` et `cron` |
| Traçabilité (R) | Traces Langfuse par clé LiteLLM ; commits sous l'identité `openclaw-coder` ; logs `docker logs openclaw-devbox-egress` |

Risques résiduels :

- le token GitHub et la clé d'hôte de la devbox sont lisibles par l'agent (même
  UID) : le token est limité à un dépôt public, et la clé ne sert qu'au réseau
  interne ;
- l'allowlist GitHub autorise la lecture de n'importe quel dépôt public
  (prompt injection par contenu tiers) ;
- le LiteLLM TrueNAS relaie vers celui de la Workstation : si elle est éteinte,
  `coder` (comme `main` et `cron`) n'a plus de modèle.

## Prérequis opérateur

1. **Clé LiteLLM** `LITELLM_OPENCLAW_CODER_API_KEY` : générée hors Git, rangée
   dans Vaultwarden (`nabla/prod/litellm`), ajoutée à
   `/mnt/cpool/secrets/runtime/litellm/.env.secrets` **et** à
   `/mnt/cpool/secrets/runtime/openclaw/gateway.env`, puis enregistrée par
   `just openclaw-truenas-virtual-keys-add-missing` (`nabla-compose`).
2. **Token GitHub** fine-grained, dépôt `fastapi-sample` seul, *Contents* et
   *Pull requests* en lecture/écriture, expiration ≤ 90 jours, dans
   `/mnt/cpool/secrets/runtime/openclaw-devbox/github_token` (`1001:1001`,
   `0400`). Protection de branche active sur `master`.
3. **Dataset** `cpool/openclaw-devbox` créé (UI TrueNAS ou middleware), en
   `noSnapshot` dans la politique de snapshots (`nabla-compose`) : clones et
   caches jetables, travail poussé sur GitHub, clés recréées par le bootstrap.
4. **Groupe Telegram** de type forum (sujets activés), avec le bot et le
   propriétaire seulement ; noter son identifiant `-100…`.

## Déploiement

```bash
# 0. Workstation, ce dépôt
just test && just devbox-plan
just devbox-pin              # épingle python:3.13-slim-trixie et debian:trixie-slim par digest
# relire, commiter, puis passer contract.json en "active" dans la même PR

# 1. TrueNAS : répertoires, clés SSH, known_hosts (idempotent, n'affiche aucune clé privée)
just truenas-bootstrap-coder

# 2. TrueNAS UI : Custom App "openclaw-devbox" dont le Compose est
#    include: [/mnt/cpool/compose/nabla-compose/apps/openclaw/deploy/truenas/devbox/compose.yml]
#    puis vérifier qu'elle est healthy :
ssh truenas sudo docker ps --filter name=openclaw-devbox --format '{{.Names}} {{.Status}}'

# 3. Recréer l'App openclaw-gateway seulement si gateway.env vient de recevoir la clé coder
#    (sinon l'étape 4 rattache le réseau sans redémarrage)

# 4. Agent, espace de travail et groupe Telegram (dry run puis écriture, sans redémarrage)
CODER_TELEGRAM_GROUP_ID=-100XXXXXXXXXX just truenas-apply-coder
```

## Vérifications

```bash
# Egress : sans proxy rien ne sort ; via le proxy, GitHub passe et le reste reçoit 403
ssh truenas "sudo docker exec openclaw-devbox curl -sS -m 5 -o /dev/null https://api.github.com/zen" || echo "direct=blocked"
ssh truenas "sudo docker exec openclaw-devbox curl -sS -m 10 -x http://openclaw-devbox-egress:3128 -o /dev/null -w '%{http_code}\n' https://api.github.com/zen"
ssh truenas "sudo docker exec openclaw-devbox curl -sS -m 10 -x http://openclaw-devbox-egress:3128 -o /dev/null https://example.com" || echo "example.com=denied"
# Politique effective de l'agent
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
- **Refus du proxy** : `ssh truenas sudo docker logs --tail 50 openclaw-devbox-egress | grep DENIED`.
  Tout nouveau domaine passe par une PR qui modifie `squid.conf` **et**
  `contract.json`.
- **Coût** : `provision-openclaw-litellm-keys.py --quota-audit` (`nabla-compose`).

## Rollback

```bash
CODER_TELEGRAM_GROUP_ID=-100XXXXXXXXXX just truenas-rollback-coder
```

Supprime l'agent `coder` (avec ses sessions et son espace local), son
fournisseur, son droit au modèle et le groupe Telegram, puis arrête la devbox.
Arrêter ensuite l'App `openclaw-devbox` dans l'UI. Les datasets, les clés et les
branches poussées sont conservés ; `main`, `cron`, le heartbeat et les canaux ne
changent pas.

## Preuves de cette préparation (9 novembre 2026)

- `openclaw config validate` (2026.10.7) : seed valide ;
  `sandbox explain --agent coder` : `all/ssh/session`, `elevated=false`.
- E2E local avec OpenClaw 2026.10.7, un sshd configuré comme la devbox et un
  modèle simulé : `exec` exécuté en UID 1001 avec le proxy, `write` puis
  relecture par SSH, `read /etc/passwd` refusé. Le modèle ne reçoit en direct
  que `exec`, `process`, `read`, `ls`, `write`, `edit` et `apply_patch`, plus
  les contrôles Tool Search ; `sessions_send` et `view_image` restent
  introuvables même par `tool_call` (`Unknown tool id`).
- Squid 6 non-root : GitHub et PyPI tunnelés ; `example.com`, HTTP en clair,
  `192.168.1.1`, port 8443 et `localhost` refusés.
- sshd non-root : PTY (devpts `gid=5` comme Docker), redirection de port
  refusée, mauvaise clé refusée.
- Scripts `truenas-bootstrap-coder`, `truenas-apply-coder` (idempotent) et
  `truenas-rollback-coder` exécutés contre un faux TrueNAS (CLI OpenClaw réel).
- Non vérifié ici : build des images (registres inaccessibles depuis
  l'environnement de préparation), exécution réelle sur TrueNAS et appel réel à
  `gpt-4.1`.
