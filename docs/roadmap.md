# Roadmap prioritaire — OpenClaw vers TrueNAS (1er novembre 2026)

> **Autorité :** `nabla-openclaw` détient le Gateway cible, ses politiques non secrètes, son heartbeat et les automations, ainsi que la configuration déclarative du Gateway **Workstation** actuel (`just workstation-*`). `nabla-compose` garde LiteLLM/TrueNAS, datasets, NFS, réseau, secrets runtime et l'intégration du futur submodule. `ansible-workstation` audite l'ancien Gateway Workstation sans le redéployer. La migration est **préparée, non appliquée**.

## État constaté sur GitHub

- [PR #1](https://github.com/AlbanAndrieu/nabla-openclaw/pull/1) **fusionnée** : dépôts, politiques heartbeat/cron/digest inactives, contrats TrueNAS et tests offline disponibles. **Aucun Compose Gateway de production ni image/digest validés.**
- [PR Compose #295](https://github.com/AlbanAndrieu/nabla-compose/pull/295) **fusionnée** : scripts diagnostiques Workstation/TrueNAS et 14 artefacts non secrets relocalisés temporairement dans `ops/openclaw-workstation/`. L'ancien `apps/openclaw/` contient encore **4 fichiers sandbox**, pas 18 (historique avant relocation).
- Gateway actuel Workstation conservé ; les vérifications d'un runtime Gateway TrueNAS, du heartbeat natif, des agents et des quotas ne sont **pas attestées**. GPT-4.1/mini sont servis par TrueNAS depuis le 31/10 (relais vers la Workstation, voir P0.4).

## P0 — gates avant tout transfert de runtime

| Ordre | Action | Gate de fermeture | Statut |
| --- | --- | --- | --- |
| 1 | Importer depuis Compose **par lots** les politiques, diagnostics génériques, scripts de cron/heartbeat et tests pertinents ; séparer strictement les sondes serveur | Parité des exit codes/UNKNOWN, redaction, CLI/versions, `just test` ; anciens wrappers conservés | **Partiel** : 18 fichiers historiques `apps/openclaw` et outillage GitOps Workstation importés, Gateway Workstation aligné sur ce dépôt (`just workstation-check` = 0 le 30/10 et le 01/11) ; outillage factorisé le 01/11 : `private_files.py` (fichiers privés), `openclaw_runtime.py` (pin, hôte, CLI) et l'orchestrateur `openclaw-workstation-gitops.py` derrière `just workstation-*`. Reste dans Compose : 70 scripts OpenClaw sous `scripts/workstation/`, 3 sous `scripts/truenas/` (clés LiteLLM, binding sandbox) et 11 artefacts `ops/openclaw-workstation/`. Prochain lot : diagnostics cron (`diagnose-openclaw-cron-parent.py`, `plan-openclaw-cron-recovery.py`, `openclaw-cron-runs-summary.py`) avec leurs tests |
| 2 | Attribuer les 429 (budget, RPM/TPM, upstream) et vérifier les deux LiteLLM ; corriger la provenance des clés scoped | États et coûts par agent vérifiés, aucune master key client ni génération répétée | **Partiel (31/10)** : LiteLLM Workstation sain sur 24 h (10 `chat/completions` en 200, aucun 429/budget/timeout) ; 2 `GET /v1/models` sans clé (02:00, 08:00, hôte Docker) d'origine inconnue ; export `langfuse_otel` vers TrueNAS **rétabli le 31/10** (base Langfuse vide réinitialisée par init headless, auth 200 ; nabla-compose #302/#303) ; LiteLLM TrueNAS lisible via `ssh truenas` + `sudo docker logs` (24 h : aucune complétion, 1440 × `GET /metrics` en 401 par minute) ; le script `diagnose-openclaw-litellm-dual-logs.py` reste en `ssh_auth_denied` |
| 3 | Aligner la politique de heartbeat restauré avec l'interface native OpenClaw effective | `plan → backup privé → apply manuel → verify → rollback`, pas de duplication ni activation automatique des 14 tâches | **Candidat inactif** |
| 4 | Attester le proxy LiteLLM **local TrueNAS** : modèle, alias, quotas, DB PostgreSQL, deux clés main/cron séparées | Tests transport, /v1/models authentifié et budgets ; pas d'inférence avant autorisation | **Modèles attestés (31/10)** : `gpt-4.1` et `gpt-4.1-mini` servis par TrueNAS, relayés vers le LiteLLM Workstation avec la clé amont scopée ([nabla-compose #306](https://github.com/AlbanAndrieu/nabla-compose/pull/306) déployée) ; `models_allowlist=verified` ; portées des clés alignées par `--mode update-scope` (main : `workstation-qwen`, `qwen`, `gpt-4.1`, `gpt-4.1-mini` ; cron : `workstation-qwen`, `gpt-4.1-mini`), budget 2. Complétion réelle `gpt-4.1-mini` avec la clé cron via TrueNAS → Workstation : 200 (13 tokens), spend cron 6e-06 enregistré, générations visibles dans Langfuse TrueNAS (une par proxy). Le relais rend TrueNAS dépendant de la Workstation. Le healthcheck LiteLLM TrueNAS (`start_period` 40 s pour un démarrage d'environ 100 s) signale un faux `unhealthy` après chaque redéploiement. Session `agent:cron:main` recréée le 31/10 (un tour minimal, `cron_main_reference=present`) |
| 5 | Définir le contrat Gateway TrueNAS : image/digest, user non-root, dataset ZFS, ACL, egress, secrets hors Git | Review de `deploy/truenas/target-contract.json`, restauration isolée, absence d'accès public | **Non déployé** |

## P1 — intégration et bascule progressive

| Ordre | Action | Gate de fermeture |
| --- | --- | --- |
| 6 | Retirer de l'index Compose les 4 fichiers sandbox, déjà importés à la racine de ce dépôt (chemins `apps/openclaw/*` conservés : plus de déplacement vers `apps/openclaw-sandbox/`) | Parité octet vérifiée (hors source de `catalog-info.yaml`) ; checkout TrueNAS avec `git submodule update --init apps/openclaw` ; aucun redéploiement implicite ; `git ls-files -- apps/openclaw` vide avant gitlink |
| 7 | Ajouter le submodule piné `nabla-openclaw` **directement** à `nabla-compose/apps/openclaw` | SHA déterministe testé ; `git submodule status` vérifié ; aucune dépendance runtime à `~/.openclaw` |
| 8 | Déployer un Gateway TrueNAS parallèle **sans automations/heartbeat/connecteurs actifs** | Readiness privé, persistance/permissions, audit réseau, aucune double exécution |
| 9 | Basculer manuellement **cron**, puis **main** et le heartbeat léger, un à un | Une instance exécute chaque cron ; coût/observabilité, smoke autorisé, rollback Workstation testé |
| 10 | Déprécier les anciens chemins et scripts Workstation dans Compose | Parité totale, documentation à jour, retrait après vérification des consommateurs |

## Commandes sans mutation

```bash
# Sur le dépôt nabla-openclaw
just test
just plan

# Sur la Workstation dans nabla-openclaw (config du Gateway actuel)
just workstation-plan

# Sur la Workstation dans nabla-compose actualisé
just openclaw-migration-evidence-tests
just openclaw-migration-evidence-check
just openclaw-litellm-dual-logs-check
just openclaw-truenas-model-keys-check
just openclaw-truenas-tunnel-check

# Sur TrueNAS avec le dépôt Compose synchronisé
just openclaw-truenas-virtual-keys-status
just openclaw-truenas-virtual-keys-quota
just litellm-workstation-upstream-auth-check
```

**Stop :** ne pas lancer l'ancien sandbox comme Gateway de production, appliquer de template Node25 Ansible, migrer SQLite ou des sessions sans snapshot/restauration privés, créer/régénérer des clés pour satisfaire un `401`, lever les budgets pour masquer un `429`, ni démarrer deux heartbeat/cron à la fois.

**DONE OpenClaw** : nouveau Gateway TrueNAS attesté avec LiteLLM TrueNAS, modèles et clé scoped par agent ; heartbeat natif maîtrisé ; stores/sessions/automations restaurés de façon sécurisée ; rollback Workstation éprouvé ; submodule piné ; absence de doubles owners dans Compose. Tests unitaires seuls = **code prêt**, jamais **migration terminée**.

Voir [runbook de migration](migration.md) et [contrat cible](../deploy/truenas/target-contract.json).
