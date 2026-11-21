# Boucle roadmap du 21 novembre 2026 — état

Mode sprint homelab (décision du propriétaire du 21/11), skill
`nabla-roadmap-loop` de nabla-compose. Une seule PR : #26
(`feat/coder-more-repos-20261120`, Draft). Mode `workstation`, sans action
sur TrueNAS : un autre agent détient le runtime OpenClaw et Coder.

## Compteur

| Passe | Base `origin/master` | Résultat |
| --- | --- | --- |
| 1 | `a195898` | Docs réconciliées, rien de codable hors ligne |
| 2 | `a195898` | Contrat x-nabla corrigé (**TESTED**), affirmations « non déployé » retirées, B1 clos |

## Passe 1

Faits sur `master` ou ailleurs, donc sautés :

- #22 et #23 (passe du 16/11) fusionnées le 16/11 ;
- B2 du 16/11 : nabla-compose #427 pine `apps/openclaw` sur `a195898` (20/11) ;
- runbook opérateur 7.5 : nabla-compose #417 fermée le 20/11.

Fait dans la PR (**CODED**, docs seules) : statut du README (le Gateway tourne
sur TrueNAS depuis le 3/11, plus sur la Workstation), P1 « diagnostics
cron/LiteLLM et migration » clos, token de la devbox à réduire aux cinq dépôts
du contrat (7.2), B2 et 7.5 rayés.

## Passe 2

Hors ligne, sans toucher au runtime (Gateway et devbox) :

- **x-nabla `status: planned` sur des services en production** (**TESTED**) :
  le Gateway (`deploy/truenas/compose.yml`) et les deux services de la devbox
  le déclaraient encore, alors que les deux contrats sont `active`. Passés en
  `active` ; `check-target-contract.py` et `check-devbox-contract.py` (règle
  `catalog_status_matches_contract`) lient désormais ce statut à celui du
  contrat, avec un test chacun. Le catalogue nabla-compose ne lit pas le
  sous-module : aucun effet runtime.
- **Affirmations périmées** (**CODED**, docs) : `coder-agent.md` (« préparé,
  non déployé », deux dépôts), `migration.md` (contrôle « non déployé »,
  runbooks #295 « jusqu'à la bascule »), roadmap (Gateway Workstation
  « actuel », étape 5 « non déployée »).
- **B1 clos** : collecteur `0f52f1ea…` = `master` sur TrueNAS, scratch
  révision 8, relevé par la session nabla-compose le 21/11 (journal de sa
  boucle, PR nabla-compose #430). **DEPLOYED**, non réobservé par cette passe.
- **Étape 10** (dans nabla-compose, hors de cette PR) : sur son `origin/master`
  du 21/11, 41 scripts OpenClaw sur 55 restent sous `scripts/workstation/`
  et 13 fichiers sous `ops/openclaw-workstation/` ; rien n'a bougé depuis le
  11/11. Les recettes `openclaw-upgrade-local-*` et `openclaw-429-*` visent le
  Gateway Workstation, désactivé depuis le 3/11 : à retirer dans la PR
  nabla-compose.

Contrôles : `just test` (103 tests Python dont 1 sauté, 31 + 11 tests Node),
`just plan` (`active_truenas`), `just devbox-plan` (`active`),
`docker compose config --quiet --no-interpolate --no-env-resolution` sur les
deux Compose, `git diff --check`.

## Bloqués

1. ~~**B1, heartbeat TrueNAS en retard**~~ : réappliqué le 21/11 (passe 2).

2. **Devbox `coder` 0.2.0 et job quotidien** (runtime, après fusion de #26 et
   avancée du pin `apps/openclaw` dans nabla-compose) :

   ```bash
   NABLA_RUNTIME_CHANGE_APPROVED=yes just truenas-deploy-coder --apply
   just devbox-egress-check
   just truenas-apply-coder-cron   # fastapi-sample-daily-improvement, non déclaré le 19/11
   ```

   Puis, depuis Telegram : « Clone nabla-site-alban, lance `npm ci` et
   `npm run test:unit`, ne commite rien et donne le compte rendu. »

3. **H20 (question O1), Slack existant pour le control plane** (propriétaire, puis
   fastapi-sample). Côté OpenClaw, H20 n'est que le canal Slack de l'app
   existante, en Socket Mode. Deux préalables manquent : les jetons (`xapp-`
   à régénérer, car exposé le 11/11 ; `xoxb-` à réobtenir par *Reinstall*),
   et l'inventaire des approbations OWNER, encore en PR ouverte
   (fastapi-sample #453 ; #449, citée par le runbook de convergence, a livré
   le SSO Cloudflare Access). Question : *le canal Slack d'OpenClaw doit-il
   porter les notifications du control plane FastAPI, en sortie seule et
   sans approbation depuis Slack, ou FastAPI garde-t-il sa propre intégration ?*

4. **Identité GitHub de la devbox (question O2)** (décision du propriétaire, runbook
   opérateur 7.1 et 7.2). Le token agit au nom du propriétaire et peut
   fusionner sa propre PR. Question : *App GitHub dédiée ou compte machine ?*
   Exiger une approbation bloque aussi les PR du propriétaire, sauf s'il
   figure dans la liste de contournement. En attendant, réduire le token
   fine-grained aux cinq dépôts du contrat.

5. **Vercel FinOps P0 7-9 et P1 mémoire/invocations (question O3)** (propriétaire) :
   inchangé depuis le 16/11 (B4). Export JSON du tableau de bord *Usage*,
   puis `just vercel-finops-file <chemin privé>`.

6. **Discord**, **Homarr `401`**, **AutoKuma**, **`APP_DOMAIN`**, **imports
   Vaultwarden** : inchangés, [runbook opérateur](../operator-pending.md),
   entrée 7.

7. **V1, Vaultwarden verrouillé** (21/11) : tout ce qui lit ou range un
   secret attend son déverrouillage, dont les jetons Slack (3) et
   l'import de `LITELLM_PROMETHEUS_METRICS_API_KEY`.
