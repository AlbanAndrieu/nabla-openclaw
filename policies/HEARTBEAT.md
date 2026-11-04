# Heartbeat — santé du homelab (TrueNAS et Workstation)

1. Appelle l'outil `exec` une seule fois, avec `timeout` = 60, et exactement cette commande :
   `node /home/node/.openclaw/workspace/scripts/homelab-health.mjs`
2. Si la sortie est exactement `NO_REPLY`, réponds `NO_REPLY`.
3. Sinon, réponds avec la sortie telle quelle : ne la reformule pas, ne la résume pas et n'ajoute aucun conseil.
4. Si la commande échoue, réponds `🩺 Collecteur homelab en échec :` suivi des 5 dernières lignes affichées, sans autre tentative.

<!--
Monitor scratch du heartbeat TrueNAS, appliqué par `just truenas-apply-heartbeat`.
Le collecteur (scripts/heartbeat/homelab-health.mjs) lit en lecture seule Prometheus
(alertes, cibles, CPU, RAM, disques, pools ZFS, services systemd), Gatus, Docker,
Scrutiny et la readiness LiteLLM (TrueNAS et Workstation, base PostgreSQL comprise).
Il ne signale que les anomalies nouvelles ou résolues, plus un récapitulatif par jour.
Aucune réparation, aucun autre outil, aucun secret ni log brut dans la réponse.
Le briefing du matin reste dans policies/MORNING_BRIEFING.md, hors heartbeat.
-->
