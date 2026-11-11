# Contrôle Vercel FinOps par OpenClaw — lecture seule

**Périmètre :** quota partagé de l'équipe Vercel `albanandrieus-projects` (Site Alban, Bababou, Checklist, Apache). Le contrôle utilise le même analyseur que Site Alban et Bababou, avec validation facultative de la **fraîcheur 48 h**.

## Principe

- Lancement uniquement **manuel**, depuis une workstation déjà authentifiée avec la CLI `vercel`, ou lecture d'un export JSON local.
- Aucun jeton Vercel dans le Gateway TrueNAS, aucune lecture des documents ou demandes privées Bababou et aucune modification de la configuration Vercel. **Un timer Workstation facultatif, désactivé par défaut, permet un relevé quotidien** ; le heartbeat TrueNAS ne consulte jamais Vercel directement.
- Limite du processus : **20 s**, **2 MB**, données brutes et erreurs CLI jamais écrites dans les journaux. Le programme ne conserve qu'un résumé JSON.
- Budget indicatif : 4 CPU-h/30 jours (Hobby), seuils `WATCH` 50 %, `INVESTIGATE` 75 %, `CRITICAL` 90 %. `NOT_MEASURED`, `WINDOW_UNVERIFIED`, `STALE_USAGE` et `NOT_RUN` sont des **preuves insuffisantes**, pas des `OK`.
- Les périodes doivent faire ~30 jours, avec une date de fin récente (moins de 48 h). Le parseur ne déduit jamais le CPU d'un coût en dollars, d'un `wall time` ou d'un nombre de requêtes.

## Commandes

```bash
cd ~/w/nabla-openclaw
just test
just vercel-finops             # opt-in : appelle seulement vercel usage
just vercel-finops-file /chemin/prive/usage.json # aucune requête externe
```

Le JSON de sortie contient uniquement `status`, `reason`, `team`, `observedAt`, `cpuHours`, `percentOfQuota`, `remainingHours`, `quotaHours` et les indicateurs de preuve. Le code de sortie est **0** si `OK`, **1** à partir de `WATCH` avec `--strict`, **2** sur preuve absente/invalide. Un export non reconnu reste `NOT_MEASURED`.

**Difficulté vérifiée :** les API Vercel Observability et Billing de ce compte Hobby ont renvoyé `404`. Preuve L3 du 11 novembre (CLI `vercel` 65.14.0, authentifiée) : `vercel usage` répond « Billing cost data is unavailable » (`reason: billing-data-unavailable-on-plan`), et `vercel metrics vercel.function_invocation.function_cpu_time_ms` répond `payment_required` (Observability Plus, indisponible en Hobby), même sur un projet et une heure. **Le CPU actif n'est pas mesurable par la CLI ni par l'API sur ce plan.** La seule source est le tableau de bord Usage : exporter son JSON à la main, puis `just vercel-finops-file <export>`.

## Instantané pour le briefing du matin (opt-in)

Sur décision opérateur seulement, `--output` écrit ce même résumé expurgé (jamais l'export brut) en `0600`, dans un répertoire créé en `0700` :

```bash
node scripts/finops/check-vercel-team.mjs --live --output "$HOME/.local/state/nabla/vercel-finops/latest.json"
```

`scripts/heartbeat/morning-briefing.mjs` ne lit cet instantané que si `VERCEL_FINOPS_REPORT` désigne un fichier lisible par le Gateway ; sans variable, le briefing est inchangé. Il n'affiche une ligne CPU que pour l'équipe exacte, une quantité CPU mesurée, une période et une fraîcheur vérifiées et un instantané de moins de 36 h ; sinon `NOT_MEASURED` ou `STALE`, jamais de faux vert, et aucun autre champ n'est transmis au modèle. Le Gateway TrueNAS n'a pas la CLI Vercel : l'opérateur y copie le seul résumé, sans token ni identité CLI.

## Heartbeat horaire — suivi du quota (11 novembre 2026)

Le collecteur homelab existant (`scripts/heartbeat/homelab-health.mjs`) lit maintenant l'instantané privé
`/home/node/.openclaw/nabla-heartbeat/vercel-finops.json` (chemin dérivé du fichier d'état du heartbeat,
ou `VERCEL_FINOPS_REPORT` si défini). Aucune invocation de `vercel` et aucune requête
HTTP supplémentaire ne sont exécutées par le Gateway. Le module de lecture
`scripts/heartbeat/vercel-finops.mjs` est distribué avec le collecteur par
`scripts/heartbeat/apply-truenas.sh`.

- **50 % — WATCH** : avertissement à partir de 2 h de CPU sur 4 h incluses.
- **75 % — INVESTIGATE** : investigation à partir de 3 h.
- **90 % — CRITICAL** : alerte critique à partir de 3,6 h.
- **Données absentes, non vérifiées ou âgées de plus de 36 h** : statut
  `NOT_MEASURED` / `STALE` sans pourcentage CPU inventé. Une anomalie CPU
  précédemment détectée n'est pas considérée comme résolue sans nouveau relevé fiable.

Les notifications sont dédupliquées avec le système `diff()` existant :
un seuil non modifié ne déclenche pas une nouvelle alerte horaire. Seuls un nouveau
seuil, une aggravation, une résolution attestée ou la perte de la preuve produisent
un changement d'état. Le fichier n'est accepté que s'il est régulier, non
symbolique, de taille inférieure à 8 Kio et non accessible au groupe ou aux autres.

## Collecte et transport de la seule synthèse expurgée

La CLI `vercel usage` est authentifiée **sur la Workstation uniquement**.
Le script calcule localement une sortie contenant exclusivement l'équipe, les
heures CPU, la période, l'instant de mesure et le seuil. Le transport
`ssh truenas` dépose **ce seul JSON** dans le volume OpenClaw TrueNAS,
avec un mode `0600`, par écriture atomique. Le transfert ne copie ni token,
ni facture, ni document Bababou et ne redémarre pas le Gateway.

```bash
cd ~/w/nabla-openclaw
just test

# Après fusion de la PR : publication du collecteur et du module sur TrueNAS.
just truenas-apply-heartbeat

# Workstation : lecture Vercel réelle et transfert du résumé si vérifiable.
just vercel-finops-refresh
```

Pour une automatisation **opt-in** sur la Workstation, une unité systemd
`deploy/workstation/systemd/nabla-openclaw-vercel-finops.{service,timer}`
est fournie mais **non installée, non activée** par cette PR :

```bash
mkdir -p ~/.config/systemd/user
install -m 0644 deploy/workstation/systemd/nabla-openclaw-vercel-finops.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user start nabla-openclaw-vercel-finops.service
# Activer uniquement après réussite de la collecte et vérification des droits :
systemctl --user enable --now nabla-openclaw-vercel-finops.timer
systemctl --user list-timers 'nabla-openclaw-vercel-finops*'
```

Le timer, s'il est activé, prélève **une fois par jour vers 08:20 Europe/Paris**.
La CLI doit être installée et connectée à l'équipe Vercel sur le poste et
`ssh truenas` doit autoriser le déploiement du seul instantané. En cas de
`costs_not_found`, d'export composé uniquement de coûts ou d'échec SSH,
la commande échoue sans publier de faux relevé : le heartbeat finira par
afficher une preuve manquante ou périmée.

**État opérationnel :** code et timer préparés dans Git. Ni commande de
publication, ni connexion Vercel authentifiée, ni service systemd ne sont
exécutés dans cette session. Ne pas prétendre que le contrôle tourne sur TrueNAS
avant exécution explicite des étapes de déploiement et de collecte.

Ne jamais joindre les charges détaillées à Telegram/Discord ni publier de
données de facturation sur Bababou.

Voir également [Site Alban](https://github.com/AlbanAndrieu/nabla-site-alban/blob/master/docs/vercel-finops-runbook.md) et [Bababou](https://github.com/AlbanAndrieu/nabla-site-bababou/blob/master/docs/vercel-finops.md).
