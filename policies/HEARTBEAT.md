# Heartbeat — santé du homelab et budget Vercel (TrueNAS et Workstation)

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
Il vérifie également un instantané **privé et local** du budget Fluid Active
CPU Vercel de l'équipe (seuils 50/75/90 %), jamais directement l'API Vercel :
un fichier absent, invalide ou périmé est signalé comme preuve insuffisante.
Un dépassement précédent n'est pas automatiquement marqué résolu si la
preuve est indisponible. Aucune sortie brute, URL privée ou clé n'est lue
ou transmise au modèle. L'approvisionnement est fait côté Workstation une
fois par jour, sans aucun nouvel appel réseau depuis ce heartbeat.
Il ne signale que les anomalies nouvelles ou résolues ; celles en cours sont
listées chaque matin par le job morning-briefing (policies/cron/morning-briefing.message.md).
Aucune réparation, aucun autre outil, aucun secret ni log brut dans la réponse.
-->
