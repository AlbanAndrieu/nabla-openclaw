# Nabla OpenClaw

**Statut : migration préparatoire — aucune instance déployée.**

Ce dépôt deviendra la source de vérité du **service OpenClaw cible TrueNAS**
(réseau, image, configuration déclarative non secrète, politiques
d'automations, heartbeat, tests et runbooks).

- **Actuel** : Gateway OpenClaw sur la Workstation, fonctionnement conservé.
- **Cible** : application Docker/TrueNAS SCALE, déployée par
  `nabla-compose` via un futur **submodule** au chemin
  `apps/openclaw` une fois l'ancien sandbox déplacé dans
  `apps/openclaw-sandbox` et les politiques migrées.
- `ansible-workstation` gère l'OS de développement et l'audit local, et
  **ne déploie pas le Gateway cible**.
- `nabla-compose` garde les dépendances réseau, volumes, NFS,
  LiteLLM TrueNAS, politiques d'exposition et le catalogue des services.

Le `apps/openclaw/compose.yml` historique de Compose représente
actuellement un **sandbox** avec des volumes Workstation ; ce n'est
**pas** un Gateway TrueNAS prêt au déploiement. Ne pas le remplacer,
le lancer en production ni le pointer vers des répertoires de
`/home/albandrieu` sur TrueNAS sans migration de données approuvée.

L'état du Gateway (sessions SQLite, identities, tokens, conversations,
credentials, backups) reste privé hors Git. Aucun déploiement automatique,
aucune mutation des agents, ni appel LLM pendant la préparation.

## Stratégie

1. Importer par lots des fichiers **publics et expurgés** depuis la
   PR Compose #295, en conservant les tests et les chemins de provenance.
2. Définir un contrat `compose.yml` TrueNAS cible sans secrets ni
   chemins Workstation ; vérifier volumes, UID/GID, résolveur, sorties
   réseau et rollback.
3. Valider les modèles LiteLLM sur TrueNAS (actuellement `gpt-4.1`
   et `gpt-4.1-mini` absents), les clés virtuelles et les budgets
   **avant** d'activer un agent ou heartbeat.
4. Ajouter un submodule Git piné dans Compose seulement après une
   version testée. Migration de `~/.openclaw` par sauvegarde chiffrée
   opérateur, avec restauration testée et **cutover manuel**.
5. Maintenir la Workstation comme repli jusqu'au smoke end-to-end.

**Compatibilité :** les wrappers `just openclaw-*` dans Compose ne
seront retirés qu'après parité des contrôles et document de rollback.

Voir [plan de migration](docs/migration.md).
