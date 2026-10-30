# Roadmap prioritaire — OpenClaw vers TrueNAS (30 octobre 2026)

> **Autorité :** `nabla-openclaw` détient le Gateway cible, ses politiques non secrètes, son heartbeat et les automations. `nabla-compose` garde LiteLLM/TrueNAS, datasets, NFS, réseau, secrets runtime et l'intégration du futur submodule. `ansible-workstation` audite l'ancien Gateway Workstation sans le redéployer. La migration est **préparée, non appliquée**.

## État constaté sur GitHub

- [PR #1](https://github.com/AlbanAndrieu/nabla-openclaw/pull/1) **fusionnée** : dépôts, politiques heartbeat/cron/digest inactives, contrats TrueNAS et tests offline disponibles. **Aucun Compose Gateway de production ni image/digest validés.**
- [PR Compose #295](https://github.com/AlbanAndrieu/nabla-compose/pull/295) **fusionnée** : scripts diagnostiques Workstation/TrueNAS et 14 artefacts non secrets relocalisés temporairement dans `ops/openclaw-workstation/`. L'ancien `apps/openclaw/` contient encore **4 fichiers sandbox**, pas 18 (historique avant relocation).
- Gateway actuel Workstation conservé ; les vérifications d'un runtime Gateway TrueNAS, du heartbeat natif, des agents et des quotas ne sont **pas attestées**. Les modèles GPT-4.1/mini ne doivent pas être considérés disponibles sans interrogation de TrueNAS.

## P0 — gates avant tout transfert de runtime

| Ordre | Action | Gate de fermeture | Statut |
| --- | --- | --- | --- |
| 1 | Importer depuis Compose **par lots** les politiques, diagnostics génériques, scripts de cron/heartbeat et tests pertinents ; séparer strictement les sondes serveur | Parité des exit codes/UNKNOWN, redaction, CLI/versions, `just test` ; anciens wrappers conservés | **Partiel** : politiques initiales importées |
| 2 | Attribuer les 429 (budget, RPM/TPM, upstream) et vérifier les deux LiteLLM ; corriger la provenance des clés scoped | États et coûts par agent vérifiés, aucune master key client ni génération répétée | **Runtime non attesté** |
| 3 | Aligner la politique de heartbeat restauré avec l'interface native OpenClaw effective | `plan → backup privé → apply manuel → verify → rollback`, pas de duplication ni activation automatique des 14 tâches | **Candidat inactif** |
| 4 | Attester le proxy LiteLLM **local TrueNAS** : modèle, alias, quotas, DB PostgreSQL, deux clés main/cron séparées | Tests transport, /v1/models authentifié et budgets ; pas d'inférence avant autorisation | **Bloquant** |
| 5 | Définir le contrat Gateway TrueNAS : image/digest, user non-root, dataset ZFS, ACL, egress, secrets hors Git | Review de `deploy/truenas/target-contract.json`, restauration isolée, absence d'accès public | **Non déployé** |

## P1 — intégration et bascule progressive

| Ordre | Action | Gate de fermeture |
| --- | --- | --- |
| 6 | Déplacer dans Compose les 4 fichiers sandbox vers `apps/openclaw-sandbox/`, avec audit des consommateurs | Références et catalogue mis à jour ; aucun redéploiement implicite ; `git ls-files -- apps/openclaw` vide |
| 7 | Ajouter le submodule piné `nabla-openclaw` **directement** à `nabla-compose/apps/openclaw` | SHA déterministe testé ; `git submodule status` vérifié ; aucune dépendance runtime à `~/.openclaw` |
| 8 | Déployer un Gateway TrueNAS parallèle **sans automations/heartbeat/connecteurs actifs** | Readiness privé, persistance/permissions, audit réseau, aucune double exécution |
| 9 | Basculer manuellement **cron**, puis **main** et le heartbeat léger, un à un | Une instance exécute chaque cron ; coût/observabilité, smoke autorisé, rollback Workstation testé |
| 10 | Déprécier les anciens chemins et scripts Workstation dans Compose | Parité totale, documentation à jour, retrait après vérification des consommateurs |

## Commandes sans mutation

```bash
# Sur le dépôt nabla-openclaw
just test
just plan

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
