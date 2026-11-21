# Boucle roadmap du 21 novembre 2026 — état

Mode sprint homelab (décision du propriétaire du 21/11), skill
`nabla-roadmap-loop` de nabla-compose. Une seule PR : #26
(`feat/coder-more-repos-20261120`, Draft). Mode `workstation`, sans action
sur TrueNAS : un autre agent détient le runtime OpenClaw et Coder.

## Compteur

| Passe | Base `origin/master` | Résultat |
| --- | --- | --- |
| 1 | `a195898` | Docs réconciliées, rien de codable hors ligne |

## Passe 1

Faits sur `master` ou ailleurs, donc sautés :

- #22 et #23 (passe du 16/11) fusionnées le 16/11 ;
- B2 du 16/11 : nabla-compose #427 pine `apps/openclaw` sur `a195898` (20/11) ;
- runbook opérateur 7.5 : nabla-compose #417 fermée le 20/11.

Fait dans la PR (**CODED**, docs seules) : statut du README (le Gateway tourne
sur TrueNAS depuis le 3/11, plus sur la Workstation), P1 « diagnostics
cron/LiteLLM et migration » clos, token de la devbox à réduire aux cinq dépôts
du contrat (7.2), B2 et 7.5 rayés.

## Bloqués

1. **B1, heartbeat TrueNAS en retard** (runtime). Le Gateway exécutait
   `homelab-health.mjs` `ec2e6901…` le 16/11, `master` porte `0f52f1ea…`
   (postgres, redis, Restic, disque monté une fois). Sans redémarrage :

   ```bash
   cd ~/w/nabla-openclaw && git switch master && git pull --ff-only && just test
   just truenas-apply-heartbeat
   ssh truenas 'sudo -n sha256sum /mnt/cpool/openclaw/state/workspace/scripts/homelab-health.mjs'  # attendu 0f52f1ea…
   ```

2. **Devbox `coder` 0.2.0 et job quotidien** (runtime, après fusion de #26 et
   avancée du pin `apps/openclaw` dans nabla-compose) :

   ```bash
   NABLA_RUNTIME_CHANGE_APPROVED=yes just truenas-deploy-coder --apply
   just devbox-egress-check
   just truenas-apply-coder-cron   # fastapi-sample-daily-improvement, non déclaré le 19/11
   ```

   Puis, depuis Telegram : « Clone nabla-site-alban, lance `npm ci` et
   `npm run test:unit`, ne commite rien et donne le compte rendu. »

3. **H20, Slack existant pour le control plane** (propriétaire, puis
   fastapi-sample). Côté OpenClaw, H20 n'est que le canal Slack de l'app
   existante, en Socket Mode. Deux préalables manquent : les jetons (`xapp-`
   à régénérer, car exposé le 11/11 ; `xoxb-` à réobtenir par *Reinstall*),
   et l'inventaire des approbations OWNER, encore en PR ouverte
   (fastapi-sample #453 ; #449, citée par le runbook de convergence, a livré
   le SSO Cloudflare Access). Question : *le canal Slack d'OpenClaw doit-il
   porter les notifications du control plane FastAPI, en sortie seule et
   sans approbation depuis Slack, ou FastAPI garde-t-il sa propre intégration ?*

4. **Identité GitHub de la devbox** (décision du propriétaire, runbook
   opérateur 7.1 et 7.2). Le token agit au nom du propriétaire et peut
   fusionner sa propre PR. Question : *App GitHub dédiée ou compte machine ?*
   Exiger une approbation bloque aussi les PR du propriétaire, sauf s'il
   figure dans la liste de contournement. En attendant, réduire le token
   fine-grained aux cinq dépôts du contrat.

5. **Vercel FinOps P0 7-9 et P1 mémoire/invocations** (propriétaire) :
   inchangé depuis le 16/11 (B4). Export JSON du tableau de bord *Usage*,
   puis `just vercel-finops-file <chemin privé>`.

6. **Discord**, **Homarr `401`**, **AutoKuma**, **`APP_DOMAIN`**, **imports
   Vaultwarden** : inchangés, [runbook opérateur](../operator-pending.md),
   entrée 7.
