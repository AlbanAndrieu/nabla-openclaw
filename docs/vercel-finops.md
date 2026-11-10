# Contrôle Vercel FinOps par OpenClaw — lecture seule

**Périmètre :** quota partagé de l'équipe Vercel `albanandrieus-projects` (Site Alban, Bababou, Checklist, Apache). Le contrôle utilise le même analyseur que Site Alban et Bababou, avec validation facultative de la **fraîcheur 48 h**.

## Principe

- Lancement uniquement **manuel**, depuis une workstation déjà authentifiée avec la CLI `vercel`, ou lecture d'un export JSON local.
- Ni tâche automatique, ni clé API, ni cron, ni lecture des documents et requêtes privées Bababou ; **aucune modification du Gateway**, des secrets, de Compose ou des paramètres Vercel.
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

**Difficulté vérifiée :** les API Vercel Observability et Billing de ce compte Hobby ont renvoyé `404`. La CLI peut rencontrer la même restriction. La source de repli est le tableau de bord Usage ; **aucune valeur CPU réelle n'est actuellement obtenue**.

## Instantané pour le briefing du matin (opt-in)

Sur décision opérateur seulement, `--output` écrit ce même résumé expurgé (jamais l'export brut) en `0600`, dans un répertoire créé en `0700` :

```bash
node scripts/finops/check-vercel-team.mjs --live --output "$HOME/.local/state/nabla/vercel-finops/latest.json"
```

`scripts/heartbeat/morning-briefing.mjs` ne lit cet instantané que si `VERCEL_FINOPS_REPORT` désigne un fichier lisible par le Gateway ; sans variable, le briefing est inchangé. Il n'affiche une ligne CPU que pour l'équipe exacte, une quantité CPU mesurée, une période et une fraîcheur vérifiées et un instantané de moins de 36 h ; sinon `NOT_MEASURED` ou `STALE`, jamais de faux vert, et aucun autre champ n'est transmis au modèle. Le Gateway TrueNAS n'a pas la CLI Vercel : l'opérateur y copie le seul résumé, sans token ni identité CLI.

La collecte n'est **pas ajoutée au heartbeat OpenClaw**. Avant toute planification future, confirmer les droits CLI et la structure réelle d'un export, définir la fréquence (au plus quotidienne), un stockage 0600 hors dépôt, des conditions d'alerte/déduplication et une politique de suppression. Ne jamais joindre les charges détaillées à Telegram/Discord ni publier sur Bababou.

Voir également [Site Alban](https://github.com/AlbanAndrieu/nabla-site-alban/blob/master/docs/vercel-finops-runbook.md) et [Bababou](https://github.com/AlbanAndrieu/nabla-site-bababou/blob/master/docs/vercel-finops.md).
