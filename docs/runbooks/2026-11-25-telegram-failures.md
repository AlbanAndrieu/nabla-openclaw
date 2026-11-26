# Échecs relayés sur Telegram, 24-25 novembre 2026

Revue demandée par le propriétaire le 25/11 au soir (« regarde les messages
Telegram et fix ce qui n'a pas fonctionné »). Source : historique
`cron runs --all` du Gateway TrueNAS (lecture seule) et messages Telegram
fournis par le propriétaire. Mode `workstation`, ControlMaster ouvert par le
propriétaire.

## Constat et causes

| Symptôme (Telegram ou run) | Cause | Correctif | Statut |
| --- | --- | --- | --- |
| Heartbeat `agent-runner-failure` du 24/11 17:37 au 25/11 ~20:30 ; digest du 25/11 : `422 Budget has been exceeded` | Clé LiteLLM `openclaw-main` plafonnée à **2 USD à vie** (`budget_duration` nul), atteint le 24/11 ; le digest est sur `gpt-4.1` depuis le 23/11 | nabla-compose : `main` et `cron` à **2 USD / 7 jours** (décision du 25/11), mode `--update-budget` (plafond et période seulement, nouvelle fenêtre à 0) | **DEPLOYED** 25/11 : dépense 0/2, remise le 30/11 puis chaque semaine |
| Passes et briefing en `model idle timeout` ou `timed out` (nuit du 24 au 25/11) ; `Connection error` depuis 21:00 le 25/11 | Le LiteLLM Workstation (relais `gpt-4.1`/`gpt-4.1-mini` de TrueNAS) ne résout plus le DNS dans Docker : `daemon.json` impose `9.9.9.9` et `172.17.0.24`, qui ne répondent plus depuis la workstation. Au démarrage, l'échec du téléchargement de la table de coûts fait planter l'image (`ImportError` dans `litellm.rust_bridge`), d'où l'arrêt du service à 20:45 | Override Compose `~/.litellm/compose.dns.yml` (DNS pfSense `172.17.0.1`, puis `1.1.1.1`) chargé par `/etc/systemd/system/litellm.service.d/10-dns.conf` ; service relancé | **DEPLOYED** : `readiness` healthy, TrueNAS le joint, heartbeat de 22:32 `ok` en 8 s |
| Passes du 24/11 : `npm: not found`, FastAPI Cloud et Prometheus refusés, `cd nabla-site-bababou` impossible, `docs/` introuvable | Devbox restée en **0.1.0** : le cron horaire avance nabla-compose sans les sous-modules (`submodule.recurse=false`) ; `apps/openclaw` était encore à `a195898` sur TrueNAS malgré le pin `fe43cc3` | Sous-module TrueNAS avancé à `c6b3a8b` (`master`, voir ci-dessous), `truenas-deploy-coder --apply`, `truenas-apply-coder-cron all` | **DEPLOYED** : images 0.2.0, Node 24.22.3 / npm 12.2.2, 17 sondes d'egress `ok`, 7 jobs coder redéclarés (11 jobs, sans doublon) |
| Compte rendu `fastapi-sample-daily-improvement` du 24/11 : SHA `af9a723` et PR #123 inventés | Un seul appel modèle, sans outil (65 s, 795 tokens, aucun `cache_read`) | Contrôle `coderruns` : un run « ok » sans lecture de cache est signalé | **DEPLOYED** (collecteur `ab596165…`) |
| Contrôle `coderruns` (#33) : `Source coderruns injoignable (node:internal/modules/cjs/loader…)` | L'outil `exec` d'OpenClaw pose `OPENCLAW_CLI=1` comme marqueur dans tout processus enfant : le collecteur lançait `node 1` | Chemin `/app/openclaw.mjs` en dur | **DEPLOYED** ; vérifié dans le Gateway avec `OPENCLAW_CLI=1` |
| `Automation … failed 2 times, Cause: timeout` en début de nuit | `isolated agent setup timed out before runner start` (60 s, constante non réglable, diagnostic de #33) ; la relance suivante passe | Aucun | Inchangé |

Pourquoi `c6b3a8b` plutôt que le pin `fe43cc3` : l'espace de travail du coder
avait été appliqué depuis la tête de la PR #31 (`3e04138`). Réappliquer
`fe43cc3` aurait retiré la skill `nabla-infra-referee`, dont le job tourne à
00:30. Le pin nabla-compose suit dans la PR #449. D'ici sa fusion,
`git submodule status` affiche `+c6b3a8b` sur TrueNAS.

Le digest du 24/11 est **ACCEPTED** : `ok` en 66 s, archive
`daily-2026-11-24.md` écrite (20 titres).

## Reste ouvert

- **DNS Docker de la workstation** (ansible-workstation, chantier DNS en
  cours dans une autre session) : remplacer `9.9.9.9`/`172.17.0.24` dans
  `/etc/docker/daemon.json`, puis retirer l'override et le drop-in LiteLLM.
  Pi-hole TrueNAS ne répond pas, même sur `127.0.0.1:53` (relancé le 25/11
  vers 20:30, conteneur `healthy`).
- Clé `openclaw-main` : elle sert aussi `qwen-cpu`, absent de
  `provision-openclaw-litellm-keys.py` (ajout hors script), d'où
  `model_scope=mismatch` dans `--quota-audit`. Intégrer ce modèle au script
  ou le retirer de la clé : à arbitrer.
- **Relevé du 26/11 au soir** (lecture seule, `cron list`) : briefing du
  26/11 `ok` et livré, digest `ok` en 75 s, livré, archive
  `daily-2026-11-26.md` de 20 titres : **ACCEPTED** avec le nouveau budget.
  Passes coder : 6 jobs sur 7 en échec, et la ligne « relance suivante
  passe » ci-dessus ne tient plus. Cinq dépassent le délai de setup chaque nuit
  depuis le 20/11, dans la saturation IO de TrueNAS (fenêtre de nuit de
  nabla-compose) ; la passe nabla-yubikey tourne sans cloner son dépôt.
  Correctifs dans la PR #36 (vagues avant minuit, clone imposé, contrôle
  `coderjobs`). Horaires **DEPLOYED** le 27/11 à 00:25 depuis la branche
  (`150369b`) : 7 jobs redéclarés sans doublon (11 jobs au total),
  prochains départs le 27/11 de 21:00 à 23:30. Rollback : réappliquer
  `apply-cron-truenas.sh all` depuis `master` (anciens horaires 00:30 à
  06:17). npm, FastAPI Cloud, sites et résolution des alertes `coderruns` :
  **ACCEPTED** `NOT_RUN` jusqu'au relevé du 28/11 au matin.
