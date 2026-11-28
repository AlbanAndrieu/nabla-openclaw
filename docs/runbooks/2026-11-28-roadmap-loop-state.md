# État de la boucle de roadmap — 28/11/2026

Mode sprint (`nabla-roadmap-loop`), demandé par le propriétaire le 28/11 vers
01:05. Branche et PR de ce dépôt : `fix/coder-cron-execution-bias-20261127`,
PR Draft #37.

## Périmètre de cette session

| Dépôt | Écrivain | Raison |
|---|---|---|
| `nabla-openclaw` | cette session (PR #37) | seule PR ouverte du dépôt |
| `nabla-compose`, `nabla-site-alban` | sessions pfSense (bot support, ARTEX) et Nexus (PR #454), en cours | une seule personne écrit dans une même PR : pas de troisième écrivain |
| `fastapi-sample`, `nabla-site-*`, `nabla-yubikey` | passes horaires du coder (08:00-23:00) et leurs PR `openclaw/roadmap-pass-*` | rien ici |

## Passe 1 (28/11, 01:05-)

| Item | Statut | Preuve ou blocage |
|---|---|---|
| Comptes rendus Telegram du coder, porte attendue, jq, umask 022, sources de roadmap | `DEPLOYED` `125ff78` (28/11 00:20-00:40) | skill `7a2f5e5e3a76`, devbox `jq-1.7` et `Umask: 0022`, 7 jobs ; `ACCEPTED` `NOT_RUN` (passes de 08:00) |
| Lot du 28/11 : cibles `planned`, passes `NO_REPLY`, jamais de push sur `master`, section CODER du briefing, digest, Dreaming à 12:30 | `DEPLOYED` `0147143` (28/11, 01:25-02:55) | `TESTED` : 118 unittest, node 42 et 11. Collecteurs `d21b5ff813cb` (remplacé à 02:38 par `bf519781aae1` de `cfa2dc4`) et `4fa09a7d1563` identiques à la branche ; 7 jobs du coder redéclarés à 02:41 (rc=0) ; Dreaming `30 12 * * *` Europe/Paris, sans redémarrage ; message du digest `d1dc0e8dc76c` (avant : `9183c02a3d3b`, identique à `master`, sauvegardé hors Git), horaire et livraison conservés. `ACCEPTED` `NOT_RUN` : passes de 08:00, briefing de 08:00, digest de 09:00, Dreaming de 12:30 |
| Collecteur docker (« Source docker injoignable ») | `DEPLOYED` par la session pfSense (28/11, ~02:00) | `docker network connect docker-proxy openclaw-gateway`, rc=0 ; `GET /containers/json` répond depuis le Gateway (180 conteneurs). Le compose déclare déjà le réseau : il reste en place au prochain redéploiement |
| `coderruns` en `--limit 200` | `TESTED` | 200 est le maximum de `CronRunsParamsSchema` (2026.10.7). À 01:11, pendant le creux d'IO de la nuit, la requête a échoué au bout de 112 s : « Source coderruns injoignable » ces nuits-là, comme avant. Relevé de jour `NOT_RUN` |
| P0-7 relevé CPU Vercel, P0-8 timer, P0-9 recette | bloqué | plan Hobby sans données de facturation : export manuel du tableau de bord Usage (B4) |
| P1 jeton Slack `xapp-`/`xoxb-` | bloqué | jeton à régénérer par le propriétaire dans Slack, puis à ranger dans Vaultwarden |

## Questions parquées (posées après cinq passes complètes)

1. Export manuel du tableau de bord Usage de Vercel (`just vercel-finops-file`) : il débloque P0-7 à P0-9 et la vérification de Fluid Provisioned Memory.
2. Régénération des jetons Slack (`xapp-`, `xoxb-`) : elle débloque `channels.slack` et les notifications F18.

## Pendant la passe

- 01:30-02:40 : creux d'IO de TrueNAS. Le Gateway s'est figé environ 66 s, une transaction SQLite a ralenti et la boucle de lecture Telegram s'est bloquée. Le `config set` de Dreaming a attendu 25 min avant de s'appliquer.
- 01:55-02:50 : la session « Coder measured passes PR » a écrit seule dans la PR #37, pour corriger d'urgence la devbox : les exec parallèles se marchaient dessus sur `sandbox-skills`. `cfa2dc4` passe le coder en `parallel_tool_calls: false`, déployé et vérifié à 02:45.
