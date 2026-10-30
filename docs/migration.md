# Plan — de OpenClaw Workstation vers TrueNAS

La cible est désormais **TrueNAS**, pas ansible-workstation. Cette
distinction évite de confondre la source opérationnelle (`systemd
--user` Workstation) avec la destination (`Docker Custom App`
TrueNAS SCALE).

## Propriété

| Environnement | Référentiel |
| --- | --- |
| Gateway cible, conteneur, politiques publiques, heartbeat et automations | **nabla-openclaw** |
| OS Ubuntu, `mise`/Node, audits du Gateway source, outils de développement | ansible-workstation |
| Volumes ZFS, réseau, secrets runtime, LiteLLM local et catalogue TrueNAS | nabla-compose |
| Profil shell et configuration interactive Workstation | dotfiles |

Les copies des fichiers publics dans `policies/` proviennent de la
PR Compose #295. Elles ne sont pas activées. Les chemins
`apps/openclaw/workstation/*` ont été *relocalisés* dans ce
dépôt et leurs références internes actualisées.

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

**Bloquant actuel :** `nabla-compose` suit déjà 18 fichiers sous
`apps/openclaw/`, dont quatre fichiers de sandbox
(`compose.yml`, `Dockerfile`, `catalog-info.yaml`,
`test-docker.sh`) et les politiques Workstation. Git ne peut
pas remplacer ce répertoire non vide par un gitlink.

Séquence préparatoire — **ne pas exécuter avant la validation des
consommateurs du sandbox et des imports Workstation** :

1. Conserver le sandbox sous un nom distinct,
   `apps/openclaw-sandbox/`, avec un changement de chemins
   contrôlé. Vérifier les références du catalogue, les scripts
   TrueNAS, les volumes, la composition et le nom de l'application
   avant de déplacer les quatre fichiers. Le sandbox historique
   monte des chemins Workstation ; il ne constitue pas le Gateway
   TrueNAS cible.
2. Migrer les politiques et références
   `apps/openclaw/workstation/` dans `nabla-openclaw/policies/`
   en gardant les wrappers Compose tant qu'ils sont utilisés.
   Corriger les scripts et leurs tests avant suppression du
   répertoire Workstation historique.
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
