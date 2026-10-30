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

## Submodule futur

Ne pas créer de submodule tant que le dépôt n'a pas de tag de référence
testé et un manifeste composable sans secrets. Le superprojet
`nabla-compose` contient déjà `apps/openclaw/compose.yml` (un
sandbox), donc **ne pas** faire `git submodule add` sur
`apps/openclaw`. Proposition après validation :

```bash
# À NE PAS EXÉCUTER AVANT APPROBATION DU CUTOVER
git submodule add \
  git@github.com:AlbanAndrieu/nabla-openclaw.git \
  apps/openclaw/nabla-openclaw
```

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
