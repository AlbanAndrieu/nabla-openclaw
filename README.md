# Nabla OpenClaw

**Statut : source de vérité de la configuration déclarative non secrète
du Gateway Workstation ; cible TrueNAS toujours non déployée.**

Ce dépôt est la source de vérité du **service OpenClaw** : configuration
déclarative non secrète, politiques d'automations, heartbeat, contrat
runtime, sandbox Docker, tests et runbooks. Il deviendra aussi celle du
**Gateway cible TrueNAS** (réseau, image, dataset).

- **Actuel** : Gateway OpenClaw sur la Workstation, piloté par la
  configuration de ce dépôt via `just workstation-*` (plan/apply explicites).
- **Cible** : application Docker/TrueNAS SCALE, déployée par
  `nabla-compose` via un futur **submodule** au chemin
  `apps/openclaw` (sandbox et politiques déjà importés ici ; reste à
  libérer le chemin dans `nabla-compose`).
- `ansible-workstation` gère l'OS de développement et l'audit local, et
  **ne déploie pas le Gateway cible**.
- `nabla-compose` garde les dépendances réseau, volumes, NFS,
  LiteLLM TrueNAS, politiques d'exposition et le catalogue des services.

Le `compose.yml` (avec `Dockerfile`, `catalog-info.yaml`,
`test-docker.sh`) à la racine est le **sandbox** importé de
`nabla-compose/apps/openclaw/`, avec des volumes Workstation ; ce n'est
**pas** un Gateway TrueNAS prêt au déploiement. Ne pas le remplacer,
le lancer en production ni le pointer vers des répertoires de
`/home/albandrieu` sur TrueNAS sans migration de données approuvée.
Placé à la racine, il garde le chemin `apps/openclaw/compose.yml`
une fois ce dépôt monté en submodule `apps/openclaw`.

## Workstation : appliquer la configuration de ce dépôt

Le Gateway ne lit pas Git au démarrage : un opérateur projette la
configuration validée, **une fois par changement**, depuis un checkout
`~/w/nabla-openclaw` **committé** (pas de symlink ni de checkout dans
`~/.openclaw`, pas d'édition SQLite).

| Source (ce dépôt) | Cible runtime | Outil |
| --- | --- | --- |
| `policies/HEARTBEAT.md` | `~/.openclaw/workspace/HEARTBEAT.md` | `openclaw-heartbeat-gitops.py` |
| `policies/MORNING_BRIEFING.md` | `~/.openclaw/workspace/MORNING_BRIEFING.md` | `openclaw-heartbeat-gitops.py` |
| `policies/cron/daily-tech-news-digest.message.md` | `payload.message` du job existant | `reconcile-openclaw-digest-cron.py` |
| `deploy/workstation/runtime-contract.json` | pin Node/OpenClaw, unité, port | `check-openclaw-runtime-alignment.py` |
| `deploy/workstation/systemd/30-nabla-runtime-alignment.conf.example` | drop-in `ExecStartPre` du Gateway | installation manuelle |

```bash
cd ~/w/nabla-openclaw
git pull --ff-only
just test
just workstation-plan            # lecture seule : hashes et états
just workstation-apply-heartbeat # sauvegarde 0600 puis remplacement atomique
just workstation-apply-digest <runtime_message_sha256>  # seulement si drift
just workstation-check           # non nul tant qu'un écart subsiste
```

Les recettes refusent un hôte autre que la Workstation
(`openclaw-host-context.py`) et une configuration non committée.
Aucune ne redémarre le Gateway, n'appelle un modèle ni ne crée de job.
Voir [docs/migration.md](docs/migration.md#workstation--bascule-de-la-source-de-configuration).

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
