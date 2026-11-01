# Plan — de OpenClaw Workstation vers TrueNAS

La cible est désormais **TrueNAS**, pas ansible-workstation. Cette
distinction évite de confondre la source opérationnelle (`systemd
--user` Workstation) avec la destination (`Docker Custom App`
TrueNAS SCALE).

## Propriété

| Environnement | Référentiel |
| --- | --- |
| Gateway cible, conteneur/sandbox, politiques publiques, heartbeat et automations | **nabla-openclaw** |
| Configuration déclarative du Gateway **Workstation** actuel (heartbeat, briefing, message digest, pin runtime, gate systemd) | **nabla-openclaw** |
| OS Ubuntu, `mise`/Node, audits du Gateway source, outils de développement | ansible-workstation |
| Diagnostics Workstation (`scripts/workstation/*` non importés), wrappers `just openclaw-*` | nabla-compose (transitoire) |
| Volumes ZFS, réseau, secrets runtime, LiteLLM local et catalogue TrueNAS | nabla-compose |
| Profil shell et configuration interactive Workstation | dotfiles |

Les fichiers publics de `policies/` proviennent de la PR Compose #295
puis de l'import complet du 30 octobre (voir *Provenance*). Les
candidats (`*.candidate.md`, `*.policy.json`) ne sont pas activés ;
`MORNING_BRIEFING.md` et le message digest sont identiques à ceux de
`nabla-compose@4aae658` ; `HEARTBEAT.md` n'en diffère que par le chemin
cité dans son commentaire (toujours comment-only).

## Workstation : bascule de la source de configuration

Depuis le 30 octobre, le Gateway Workstation est piloté par **ce dépôt**
(`~/w/nabla-openclaw`) et non plus par `nabla-compose/ops/openclaw-workstation/`.
Les scripts GitOps sont importés avec leur logique de sûreté inchangée
(hash attendu, sauvegarde privée `0600`, refus des symlinks, remplacement
atomique, job existant uniquement, aucune inférence) ; seuls leurs chemins
sources changent. Le pin runtime est lu uniquement dans
`deploy/workstation/runtime-contract.json` (pas de `mise.toml` dupliqué).

Les sauvegardes restent aux mêmes emplacements :
`~/.openclaw/backups/heartbeat-gitops/` et
`~/.local/state/nabla-compose/openclaw/digest-gitops/`.

Bascule, **sur la Workstation uniquement** :

1. `git clone git@github.com:AlbanAndrieu/nabla-openclaw.git ~/w/nabla-openclaw`
   (ou `git pull --ff-only`), puis `just test`.
2. `just workstation-plan`, puis comparer avec les contrôles équivalents
   de `nabla-compose` (`openclaw-heartbeat-gitops.py --check`,
   `--briefing-check`, `just openclaw-digest-gitops-plan`). Un écart
   présent des deux côtés est **antérieur** à la bascule : constaté le
   30 octobre, la Workstation exécutait encore les versions du
   26 octobre (`nabla-compose@b96a7c3`, `apps/openclaw/workstation/`).
3. Si le drop-in `30-nabla-runtime-alignment.conf` est installé
   (`systemctl --user cat openclaw-gateway.service`), le remplacer par
   `deploy/workstation/systemd/30-nabla-runtime-alignment.conf.example`
   (chemin `%h/w/nabla-openclaw`), puis `systemctl --user daemon-reload`.
   **Ne pas redémarrer** le Gateway ; lancer d'abord
   `python3 scripts/workstation/check-openclaw-runtime-alignment.py`
   et n'installer le drop-in que sur `"alignment": "PASS"`.
4. Ensuite, toute modification passe par une PR ici, puis
   `just workstation-apply-*` et `just workstation-check`. Ne plus
   modifier les copies de `nabla-compose/ops/openclaw-workstation/` :
   elles sont gelées jusqu'à leur retrait par une PR Compose.

**Appliqué le 30 octobre** : `just workstation-check` retourne 0
(alignement `PASS`, heartbeat et briefing `matching`, digest
`already_aligned`). Le drop-in `30-nabla-runtime-alignment.conf` n'était
pas installé et ne l'est toujours pas. Le commentaire interne de
`policies/HEARTBEAT.md` cite désormais `policies/MORNING_BRIEFING.md`
(commentaire HTML ignoré par OpenClaw) : réappliquer avec
`just workstation-apply-heartbeat` une fois committé.

Le shell Workstation utilise `umask 0002` : chaque réinstallation
d'OpenClaw rend son paquet inscriptible par le groupe et les gates
échouent (`unsafe_or_absent`, `runtime_job_unverified`). Corriger avec
`chmod -R go-w ~/.local/share/mise/installs/node/<pin>/lib/node_modules/openclaw`
avant `just workstation-plan`.

Rollback : les wrappers `just openclaw-*` de `nabla-compose` restent
utilisables tant que ses copies n'ont pas divergé ; restaurer un fichier
workspace depuis la sauvegarde `0600`, et le job digest via la Control UI.

## Provenance de l'import du 30 octobre

Source : `AlbanAndrieu/nabla-compose@4aae6582aee013437f9b67a8c70f2993171033bf`.

| Source `nabla-compose` | Ici | Modification |
| --- | --- | --- |
| `apps/openclaw/{Dockerfile,compose.yml,test-docker.sh}` | racine | aucune |
| `apps/openclaw/catalog-info.yaml` | racine | `source-location`, `project-slug` → nabla-openclaw |
| `ops/openclaw-workstation/{HEARTBEAT,MORNING_BRIEFING,HEARTBEAT-SCRATCH.template}.md` | `policies/` | aucune, sauf le chemin cité dans le commentaire de `HEARTBEAT.md` |
| `ops/openclaw-workstation/runtime-contract.json` | `deploy/workstation/` | aucune |
| `ops/openclaw-workstation/systemd/*` | `deploy/workstation/systemd/` | drop-in repointé vers `%h/w/nabla-openclaw` ; unités rate-limit inchangées (script resté dans nabla-compose) |
| `ops/openclaw-workstation/{BACKUP,NFS-BACKUP}.md` | `docs/workstation/` | note de provenance, chemins Git mis à jour |
| `scripts/workstation/{openclaw-heartbeat-gitops,reconcile-openclaw-digest-cron,diagnose-openclaw-digest-top,openclaw-host-context,check-openclaw-runtime-alignment}.py` | `scripts/workstation/` | refactorés le 1er novembre (voir ci-dessous) |
| `scripts/workstation/openclaw_runtime_paths.py` | remplacé par `openclaw_runtime.py` | pin lu dans le seul contrat runtime |

Les 18 fichiers historiques de `apps/openclaw/` sont donc tous présents ici.

### Refactoring du 1er novembre

Mêmes noms de scripts, options et clés de sortie ; aucune garde assouplie.

- `private_files.py` : primitives communes (lecture `O_NOFOLLOW` + `fstat`
  sans course vérification/lecture, FIFO refusée, fichiers `0600` exclusifs,
  répertoires privés, remplacement atomique avec `fsync` du répertoire).
- `openclaw_runtime.py` : contrat runtime unique, chemins CLI épinglés,
  détection d'hôte et lecture du job cron, remplaçant les chargements de
  modules par chemin (`run_path`, `importlib`) et les validations dupliquées.
- Diagnostics précis : état par fichier, version Node systemd, `hint`
  (alignement) ; `cron_job_read` et `runtime_install` (digest).
- `openclaw-workstation-gitops.py` : point d'entrée unique des recettes
  `just workstation-*` ; gardes hôte, configuration committée et **fusionnée
  dans `origin/master`**, désormais testées (auparavant en shell).
- `openclaw-heartbeat-gitops.py --check` retourne `2` sur écart (comme le
  digest) ; un `apply` déjà aligné ne crée plus de sauvegarde inutile ; les
  refus affichent leur code (`symlink_refused`…) au lieu du seul type.
- `check-target-contract.py` : règles nommées, évaluées une seule fois,
  violations listées sur stderr, contrat illisible = `invalid` (pas de trace).

Parité revérifiée le 30 octobre, fichier par fichier, contre
`nabla-compose@407590b` (#300) : `apps/openclaw/` (4 fichiers),
`ops/openclaw-workstation/` (14 fichiers) et les 6 scripts portés ne
diffèrent d'ici que par les écarts du tableau ci-dessus, plus les champs
`source`/`message_source` et `migration_target` des `*.policy.json`
issus de la PR #295.

## Gates de migration

1. **Inventaire** de l'instance Workstation : version CLI/Gateway,
   utilisateurs, sessions (métadonnées seulement), cron, heartbeat,
   modèles, budgets. Ne jamais committer `~/.openclaw`.
2. **Image** OpenClaw : sélectionner une image et son digest après
   vérification de la provenance, du user non-root, du protocole
   d'initialisation et du confinement réseau.
3. **Stockage** : approuver un dataset et sa sauvegarde chiffrée
   indépendante ; vérifier ACL, UID/GID, persistance DB, droits des
   fichiers et tests de restauration hors production.
4. **LiteLLM TrueNAS** : modèles effectivement autorisés, clés
   `main`/`cron` scoped, budget, RPM/TPM, embedding et repli. À ce
   jour, `gpt-4.1`/`gpt-4.1-mini` ne sont pas confirmés sur
   TrueNAS ; **aucun cutover** tant que l'équivalence modèle est
   bloquée.
5. **Réseau** : port privé, authentification, absence d'exposition
   publique non autorisée, tunnel, Egress allowlist pour connecteurs.
6. **Démarrage parallèle** avec automations, heartbeat et delivery
   **désactivés** : prouver readiness sans duplication de Gmail,
   Discord, WhatsApp, calendrier, webhooks ou cron.
7. **Bascule explicite** avec instantané privé, fenêtre courte,
   activation contrôlée des agents/cron, preuve d'un run synthétique,
   coûts et traçabilité.
8. **Rollback** : vérifier que le Gateway Workstation peut reprendre
   sans exécutions simultanées des mêmes crons.

## Submodule futur : chemin canonique `apps/openclaw`

**Décision du 30 octobre :** le sous-module de
`AlbanAndrieu/nabla-openclaw` sera directement `apps/openclaw`,
sans niveau `nabla-openclaw` intermédiaire.

**Bloquant actuel :** `nabla-compose` suit encore 4 fichiers sous
`apps/openclaw/` (`compose.yml`, `Dockerfile`, `catalog-info.yaml`,
`test-docker.sh`) ; les 14 fichiers Workstation sont déjà sous
`ops/openclaw-workstation/`. Git ne peut pas remplacer ce répertoire
non vide par un gitlink.

**Mise à jour du 30 octobre :** ces 4 fichiers sont importés **à la
racine** de ce dépôt. Une fois monté en `apps/openclaw`, les chemins
`apps/openclaw/compose.yml` (include TrueNAS, `build.sh`, catalogue)
restent identiques : le déplacement vers `apps/openclaw-sandbox/`
n'est plus nécessaire. En contrepartie, le checkout TrueNAS doit
initialiser le submodule (`git submodule update --init apps/openclaw`)
**avant** toute réévaluation de l'App, sinon l'include disparaît.

Séquence préparatoire — **ne pas exécuter avant la validation des
consommateurs du sandbox et des imports Workstation** :

1. Vérifier que `compose.yml`, `Dockerfile` et `test-docker.sh`
   de `nabla-compose/apps/openclaw/` sont identiques à la racine du
   pin choisi ici (`catalog-info.yaml` ne diffère que par la source).
   Le sandbox monte des chemins Workstation ; il ne constitue pas
   le Gateway TrueNAS cible.
2. Politiques Workstation : **migrées** (voir *Provenance*). Retirer
   `nabla-compose/ops/openclaw-workstation/` et ses wrappers dans une
   PR Compose dédiée, après parité des contrôles.
3. Exiger un `apps/openclaw` vide et absent de l'index Git
   avant l'ajout du submodule ; confirmer par
   `git ls-files -- apps/openclaw`.
4. Ajouter **après validation**, dans une PR Compose séparée,
   le submodule et le pin d'un commit testé de ce dépôt :

```bash
# FUTUR / MANUEL : seulement après libération du chemin et revue.
cd ~/w/nabla-compose
test -z "$(git ls-files -- apps/openclaw)" || {
  echo 'STOP: tracked files still occupy apps/openclaw'
  exit 2
}
git submodule add \
  git@github.com:AlbanAndrieu/nabla-openclaw.git \
  apps/openclaw
git add .gitmodules apps/openclaw
git diff --cached --submodule=log
# Commit après revue, jamais automatisé.
```

Le `compose.yml` Gateway TrueNAS doit provenir de ce dépôt,
pas du sandbox déplacé. Ne pas confondre ajout de gitlink et
déploiement effectif du Gateway.

Un gitlink **pinne un commit**. Un `git pull` de Compose ne
déploie pas le Gateway ; un wrapper TrueNAS doit vérifier le pin,
les secrets disponibles et l'état des services, puis faire un apply
séparé. N'utiliser ni symlink pour `~/.openclaw` ni checkout dans
un dataset de runtime.

## Déploiement du Gateway TrueNAS (état neuf)

Décisions du 1er novembre : dataset `cpool/openclaw`, état **neuf** (pas de
restauration Workstation, canaux réappairés à la bascule), port publié sur
`127.0.0.1` de TrueNAS seulement, bascule complète cron puis main.

Prérequis : `nabla-compose` monte ce dépôt en sous-module `apps/openclaw`,
et le checkout TrueNAS a lancé `git submodule update --init apps/openclaw`.

1. **Stockage** : le dataset `cpool/openclaw` existait déjà, avec l'état
   `.openclaw` d'une ancienne app TrueNAS (UID 568, septembre 2026,
   snapshots quotidiens) : il est conservé intact. Créer à côté `state/` et
   `state/workspace/` en `1000:1000`, mode `0700`, sans ACL (`setfacl -b`).
2. **Secrets** : `/mnt/cpool/secrets/runtime/openclaw/gateway.env` (`0600`,
   root), avec seulement `OPENCLAW_GATEWAY_TOKEN` (nouveau, aléatoire),
   `LITELLM_OPENCLAW_MAIN_API_KEY` et `LITELLM_OPENCLAW_CRON_API_KEY`
   (valeurs reprises de l'environnement du conteneur `litellm`, jamais
   affichées). Le fichier voisin, plus ancien, contient les tokens de canaux
   et des clés LiteLLM périmées : il ne doit pas alimenter le Gateway
   parallèle.
3. **Config de départ** : copier `deploy/truenas/openclaw.json` en
   `state/openclaw.json` (`0600`, `1000:1000`), une seule fois. Projeter
   `policies/HEARTBEAT.md` et `policies/MORNING_BRIEFING.md` dans
   `state/workspace/`.
4. **App** : Custom App `openclaw-gateway` avec le wrapper
   `include: [/mnt/cpool/compose/nabla-compose/apps/openclaw/deploy/truenas/compose.yml]`.
5. **Vérifier** : `/healthz` et `/readyz` depuis TrueNAS, puis
   `ssh -L 18789:127.0.0.1:18789 truenas` pour la Control UI.

Bascule, une étape à la fois, avec accord explicite :

1. **cron** : arrêter le job digest sur la Workstation, retirer
   `OPENCLAW_SKIP_CRON` côté TrueNAS (PR), recréer le job digest depuis
   `policies/cron/` sur TrueNAS, puis vérifier un run.
2. **main et canaux** : arrêter et désactiver `openclaw-gateway.service` sur la
   Workstation, puis appairer les canaux sur TrueNAS et activer le heartbeat.
3. **Rollback** : arrêter l'App TrueNAS, puis
   `systemctl --user enable --now openclaw-gateway.service` sur la Workstation.
   L'état Workstation reste intact, puisque rien n'est restauré.

## Tests disponibles

```bash
python3 -m unittest discover -s tests -p 'test_*py' -v
python3 scripts/check-target-contract.py
```

Ces tests sont offline. `check-target-contract.py` retourne
`0` si le contrat **reste en mode plan/non déployé** ; ce n'est
pas une preuve de disponibilité TrueNAS.

Les runbooks de la PR Compose #295 restent les instructions
opérationnelles jusqu'à la bascule du propriétaire.
