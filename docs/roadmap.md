# Roadmap consolidée — nabla-openclaw (11 novembre 2026)

**État vérifié (11/11 au soir) :** [PR #17](https://github.com/AlbanAndrieu/nabla-openclaw/pull/17) fusionnée et **appliquée sur TrueNAS** ; aucun relevé CPU réel validé, car le plan Hobby n'expose pas le CPU actif à la CLI. Reste : **relevé (export manuel) → activation quotidienne si un relevé automatique devient possible**.

## P0 — Terminer et appliquer le contrôle Vercel dans le heartbeat

| Ordre | Statut | Action vérifiable |
| --- | --- | --- |
| 1 — Code et seuils 50/75/90 % | ✅ Implémenté dans #17 | Lecture locale privée, alertes dédupliquées ; aucun appel Vercel depuis TrueNAS |
| 2 — Confidentialité et résilience | ✅ Implémenté dans #17 | Snapshot 0600, contrôle de fraîcheur, refus du faux OK ; dépassement précédent non résolu sans preuve |
| 3 — Transport Workstation → TrueNAS | 🟡 Préparé | CLI Vercel Workstation ; transfert SSH du seul JSON expurgé, aucun token dans le Gateway |
| 4 — Gates sur SHA exact | ✅ Passées le 11/11 après rebase | `just test`, `just vercel-finops-test` (28 tests), `bash -n`, `git diff --check` et `systemd-analyze verify` verts ; transfert relu : JSON en liste blanche validé avant tout contact SSH, écriture atomique en 0600 dans un dossier 0700 du conteneur (UID 1000). Shellcheck ne signale que du style (SC2250), comme le reste du dépôt |
| 5 — Fusion de la PR #17 | ✅ Fusionnée le 11/11 (`390c6c0`) | Fusionner après revue et tests, sans masquer les résultats non exécutés |
| 6 — Appliquer sur TrueNAS | ✅ Appliqué le 11/11 | Collecteurs `homelab-health`, `morning-briefing` et `vercel-finops` installés en 0400 (UID 1000), un seul job par nom (`heartbeat-main`, `morning-briefing`, `daily-tech-news-digest`). Commande : `just truenas-apply-heartbeat` ; contrôler les trois modules, la politique chargée et la non-duplication des jobs |
| 7 — Premier relevé CPU réel | ⬜ Non mesuré | `just vercel-finops-refresh` sur Workstation authentifiée ; 30 jours et unité CPU vérifiés, sinon NOT_MEASURED. Essai CLI du 11/11 : en Hobby, `vercel usage` n'a aucune donnée de facturation et `vercel metrics` exige Observability Plus (`billing-data-unavailable-on-plan`) ; seul un export manuel du tableau de bord Usage est analysable (`just vercel-finops-file`) |
| 8 — Prélèvement quotidien | 🟡 Timer prêt, inactif | Installer/activer le timer systemd utilisateur **après** un relevé réussi ; 08:20 Europe/Paris |
| 9 — Recette end-to-end | 🟡 Partielle (11/11) | Contrôler 0600, transitions 50/75/90 %, perte de preuve et absence de notifications répétées. Hors ligne : tests verts ; `render` ne notifie que les clés nouvelles ou résolues, donc un `NOT_MEASURED` permanent (cas Hobby) sort une seule fois, puis seulement dans le briefing du matin. Sur le Gateway, collecteur lancé avec une copie de son état : `NOT_MEASURED` sort une fois en « Nouveau », sortie `exit=0`. Les transitions 50/75/90 % attendent un relevé réel |

**Condition DONE :** commit fusionné et testé, code réellement installé sur le Gateway TrueNAS, fichier de métrique valide et récent, alerte validée et timer actif **si souhaité**. Si Hobby ne fournit que des coûts monétaires (API Billing/Observability précédemment 404), conserver le statut **NOT_MEASURED**, jamais un faux OK.

### Commandes d’application sur la workstation (après revue/merge)

```bash
cd ~/w/nabla-openclaw
git pull --ff-only
just test
bash -n scripts/heartbeat/apply-truenas.sh \
  scripts/heartbeat/collect-publish-vercel-finops.sh \
  scripts/heartbeat/publish-vercel-finops.sh

# Attention : synchronise également briefing du matin et config heartbeat.
just truenas-apply-heartbeat
# Authentification CLI Vercel et SSH TrueNAS requises.
just vercel-finops-refresh

# Optionnel après une première collecte vérifiée.
mkdir -p ~/.config/systemd/user
install -m 0644 deploy/workstation/systemd/nabla-openclaw-vercel-finops.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now nabla-openclaw-vercel-finops.timer
systemctl --user list-timers 'nabla-openclaw-vercel-finops*'
```

### P1 — Après mise en service

- [ ] Vérifier aussi **Fluid Provisioned Memory**, Function Invocations et la ventilation entre les quatre projets Vercel ; le module actuel vérifie uniquement Fluid Active CPU.
- [ ] Reprendre les diagnostics cron/LiteLLM et la migration OpenClaw décrits plus bas, après contrôle de la réalité du Gateway ; les tableaux datés sont conservés comme historique.
- [ ] Maintenir les demandes et preuves privées Bababou **hors** des snapshots et du runtime FinOps.

Documentation de déploiement : [FinOps Vercel](vercel-finops.md).

---

> **Autorité :** `nabla-openclaw` détient le Gateway cible, ses politiques non secrètes, son heartbeat et les automations, ainsi que la configuration déclarative du Gateway **Workstation** actuel (`just workstation-*`). `nabla-compose` garde LiteLLM/TrueNAS, datasets, NFS, réseau, secrets runtime et l'intégration du futur submodule. `ansible-workstation` audite l'ancien Gateway Workstation sans le redéployer. La migration est **appliquée sans Discord depuis le 3 novembre** : le Gateway tourne sur TrueNAS.

## Historique — état constaté sur GitHub aux dates indiquées

- [PR #1](https://github.com/AlbanAndrieu/nabla-openclaw/pull/1) **fusionnée** : dépôts, politiques heartbeat/cron/digest inactives, contrats TrueNAS et tests offline disponibles. **Aucun Compose Gateway de production ni image/digest validés.**
- [PR Compose #295](https://github.com/AlbanAndrieu/nabla-compose/pull/295) **fusionnée** : scripts diagnostiques Workstation/TrueNAS et 14 artefacts non secrets relocalisés temporairement dans `ops/openclaw-workstation/`. L'ancien `apps/openclaw/` contient encore **4 fichiers sandbox**, pas 18 (historique avant relocation).
- Gateway actuel Workstation conservé ; les vérifications d'un runtime Gateway TrueNAS, du heartbeat natif, des agents et des quotas ne sont **pas attestées**. GPT-4.1/mini sont servis par TrueNAS depuis le 31/10 (relais vers la Workstation, voir P0.4).

## Historique de migration — gates avant transfert de runtime

| Ordre | Action | Gate de fermeture | Statut |
| --- | --- | --- | --- |
| 1 | Importer depuis Compose **par lots** les politiques, diagnostics génériques, scripts de cron/heartbeat et tests pertinents ; séparer strictement les sondes serveur | Parité des exit codes/UNKNOWN, redaction, CLI/versions, `just test` ; anciens wrappers conservés | **Partiel** : 18 fichiers historiques `apps/openclaw` et outillage GitOps Workstation importés, Gateway Workstation aligné sur ce dépôt (`just workstation-check` = 0 le 30/10 et le 01/11) ; outillage factorisé le 01/11 : `private_files.py` (fichiers privés), `openclaw_runtime.py` (pin, hôte, CLI) et l'orchestrateur `openclaw-workstation-gitops.py` derrière `just workstation-*`. Reste dans Compose : 41 scripts OpenClaw sous `scripts/workstation/` (18 retirés le 11/11, nabla-compose #348 et #349), les scripts de clés LiteLLM sous `scripts/truenas/` et 11 artefacts `ops/openclaw-workstation/`. **Import abandonné le 11/11** : ces diagnostics visent le Gateway Workstation, désactivé depuis le 3/11 ; ils sont retirés de Compose (étape 10) au lieu d'être importés |
| 2 | Attribuer les 429 (budget, RPM/TPM, upstream) et vérifier les deux LiteLLM ; corriger la provenance des clés scoped | États et coûts par agent vérifiés, aucune master key client ni génération répétée | **Partiel (31/10)** : LiteLLM Workstation sain sur 24 h (10 `chat/completions` en 200, aucun 429/budget/timeout) ; 2 `GET /v1/models` sans clé (02:00, 08:00, hôte Docker) d'origine inconnue ; export `langfuse_otel` vers TrueNAS **rétabli le 31/10** (base Langfuse vide réinitialisée par init headless, auth 200 ; nabla-compose #302/#303) ; LiteLLM TrueNAS lisible via `ssh truenas` + `sudo docker logs` (24 h : aucune complétion, 1440 × `GET /metrics` en 401 par minute). **Cause trouvée le 11/11** : LiteLLM 1.108 n'accepte sur `/metrics` qu'un admin du proxy ou une clé autorisée sur cette route ; nabla-compose #348 donne à Prometheus une clé limitée à `/metrics` (application : [runbook](operator-pending.md), entrée 4) |
| 3 | Aligner la politique de heartbeat restauré avec l'interface native OpenClaw effective | `plan → backup privé → apply manuel → verify → rollback`, pas de duplication ni activation automatique des 14 tâches | **Appliqué sur TrueNAS le 4 novembre** : seule la santé homelab est réactivée, par collecteur déterministe (voir ci-dessous) |
| 4 | Attester le proxy LiteLLM **local TrueNAS** : modèle, alias, quotas, DB PostgreSQL, deux clés main/cron séparées | Tests transport, /v1/models authentifié et budgets ; pas d'inférence avant autorisation | **Modèles attestés (31/10)** : `gpt-4.1` et `gpt-4.1-mini` servis par TrueNAS, relayés vers le LiteLLM Workstation avec la clé amont scopée ([nabla-compose #306](https://github.com/AlbanAndrieu/nabla-compose/pull/306) déployée) ; `models_allowlist=verified` ; portées des clés alignées par `--mode update-scope` (main : `workstation-qwen`, `qwen`, `gpt-4.1`, `gpt-4.1-mini` ; cron : `workstation-qwen`, `gpt-4.1-mini`), budget 2. Complétion réelle `gpt-4.1-mini` avec la clé cron via TrueNAS → Workstation : 200 (13 tokens), spend cron 6e-06 enregistré, générations visibles dans Langfuse TrueNAS (une par proxy). Le relais rend TrueNAS dépendant de la Workstation. Le faux `unhealthy` du healthcheck LiteLLM après chaque redéploiement (`start_period` 40 s pour un démarrage d'environ 100 s) est corrigé à 150 s par nabla-compose #348. Session `agent:cron:main` recréée le 31/10 (un tour minimal, `cron_main_reference=present`) |
| 5 | Définir le contrat Gateway TrueNAS : image/digest, user non-root, dataset ZFS, ACL, egress, secrets hors Git | Review de `deploy/truenas/target-contract.json`, restauration isolée, absence d'accès public | **Défini (01/11), non déployé** : image officielle `ghcr.io/openclaw/openclaw:2026.10.7` épinglée par digest (provenance SLSA GHCR), UID/GID 1000 (`node`), `cap_drop: ALL`, `no-new-privileges` ; dataset `cpool/openclaw` (état dans `state/`) ; **état neuf**, sans restauration Workstation (canaux réappairés à la bascule) ; port publié sur `127.0.0.1` uniquement (Control UI par `ssh -L`) ; LiteLLM par le réseau `ix-litellm_default` ; secrets du Gateway parallèle dans `/mnt/cpool/secrets/runtime/openclaw/gateway.env` (3 variables, sans token de canal ; le fichier complet existant à côté, avec les tokens Discord, Telegram et Slack, sert à la bascule) ; l'ancien état `.openclaw` du dataset (app TrueNAS de septembre, UID 568) est conservé intact ; `OPENCLAW_SKIP_CRON=1` et `heartbeat.every=0m` jusqu'à la bascule. Egress non restreint (documenté). Fichiers : `deploy/truenas/compose.yml`, `deploy/truenas/openclaw.json` (validé par `openclaw config validate`) |

## P1 — intégration et bascule progressive

| Ordre | Action | Gate de fermeture |
| --- | --- | --- |
| 6 | Retirer de l'index Compose les 4 fichiers sandbox, déjà importés à la racine de ce dépôt (chemins `apps/openclaw/*` conservés : plus de déplacement vers `apps/openclaw-sandbox/`) | Parité octet vérifiée (hors source de `catalog-info.yaml`) ; checkout TrueNAS avec `git submodule update --init apps/openclaw` ; aucun redéploiement implicite ; `git ls-files -- apps/openclaw` vide avant gitlink |
| 7 | Ajouter le submodule piné `nabla-openclaw` **directement** à `nabla-compose/apps/openclaw` | SHA déterministe testé ; `git submodule status` vérifié ; aucune dépendance runtime à `~/.openclaw` |
| 8 | Déployer un Gateway TrueNAS parallèle **sans automations/heartbeat/connecteurs actifs** | Readiness privé, persistance/permissions, audit réseau, aucune double exécution |
| 9 | Basculer manuellement **cron**, puis **main** et le heartbeat léger, un à un | Une instance exécute chaque cron ; coût/observabilité, smoke autorisé, rollback Workstation testé |
| 10 | Déprécier les anciens chemins et scripts Workstation dans Compose | Parité totale, documentation à jour, retrait après vérification des consommateurs |

**État au 1er novembre (soir)** :

- **6-7 faits** : `apps/openclaw` est le sous-module `nabla-openclaw` ([nabla-compose #314](https://github.com/AlbanAndrieu/nabla-compose/pull/314), pin `836ae53`). Le checkout TrueNAS l'initialise ; son ancien `.env` non suivi a été déplacé en `0600` dans `/mnt/cpool/openclaw/legacy-sandbox-20260704.env`. Le catalogue Compose ignore les descripteurs des sous-modules.
- **8 attesté puis arrêté** : l'App TrueNAS `openclaw-gateway` (état neuf) a atteint `/readyz` 200 en loopback, sans canal et avec le cron désactivé ; les clés main et cron ont lu `/v1/models` dans leur portée. Le démarrage est lent : environ 5 minutes, dont 97 s de boucle d'événements bloquée pendant les plugins. L'App est **STOPPED** depuis le rollback.
- **9 tenté puis annulé** : la Workstation a été arrêtée, puis l'App relancée avec le fichier de secrets complet des canaux. Le `doctor` du point d'entrée a activé les plugins brave, discord, searxng et tavily, puis il est resté bloqué en état `D` (`cv_timedwait_common`, attente ZFS) plus de 35 minutes, et de nouveau après un redémarrage. Le pool était sain et peu chargé. **Rollback appliqué** après environ 1 h d'interruption : Workstation réactivée (Discord, Telegram, WhatsApp et cron revenus), App TrueNAS arrêtée, contrat remis en `not_deployed`.
- **Reproduction du 3 novembre, hors bascule** : `openclaw doctor --fix --non-interactive` dans l'image épinglée, avec le marqueur d'activation absent, sur deux copies de `state/` dans `cpool/openclaw` et avec `.env.secrets`, mais de faux tokens Discord et Telegram. Sans réseau : code 0 en 8 min 30. Avec réseau et installation npm des 4 plugins (environ 1 min 40) : code 0 en 5 min 50. **Blocage non reproduit.** L'état `D` (`cv_timedwait_common`) signale des E/S lentes, pas un interblocage : sur 19 échantillons, 14 sont des `zfs_read` de la couche d'image (overlay sur `cpool/ix-apps/docker`, raidz2 de disques durs sans SLOG) et 3 des `fsync`. L'ARC est réduit à 2,4-3,8 Go (`arc_no_grow=1`) : 55 Go sur 61 sont pris par les VM et les Apps.
- **Écart avec le 1er novembre** : la capture `state/tmp/plugin-captures/8e853dfd…` contient 27 500 fichiers, dont 4 builds de plugins et 26 admissions natives du module `davey` de Discord (deux vagues, à 22:17 et 22:40), ainsi qu'un `owner.sqlite` vide avec son journal. Ce chemin ne se déclenche pas avec un faux token Discord. Le `tmpfs` sur `/tmp` efface aussi le marqueur d'activation : chaque redémarrage refait la capture complète. Les copies de test et cette capture ont été supprimées le 3 novembre.
- **9 fait le 3 novembre, sans Discord** : `openclaw-gateway.service` est arrêté et désactivé sur la Workstation. L'App TrueNAS est redéployée sur `c600e9d`, avec le sous-module TrueNAS détaché hors pin Compose. Dans la config d'état (sauvegarde `openclaw.json.pre-cutover-20261103`), les blocs Telegram et WhatsApp et `commands.ownerAllowFrom` sont repris de la Workstation, l'owner Telegram en `allowFrom`, et Discord est désactivé. La session WhatsApp est copiée dans `state/credentials/whatsapp`. Le premier démarrage a pris 23 min, dont 19 pour le `doctor` (installation du plugin WhatsApp) : `/readyz` 200, Telegram (polling) et WhatsApp connectés, heartbeat `main` toutes les 30 min, cron *dreaming* créé par `memory-core`, cron `daily-tech-news-digest` recréé depuis `policies/cron/` avec une livraison Telegram au lieu de Discord.
- **Chemin modèle rétabli le 4 novembre** : le `postgres` de `nabla-compose`, recréé le 3 novembre au soir, ne publie plus que `127.0.0.1:5432`, si bien que le LiteLLM Workstation, vers lequel relaie le LiteLLM TrueNAS, ne joignait plus sa base sur `172.17.0.57:5432` (503, puis arrêt en `P1001`). Son `DATABASE_URL` (`~/.litellm/.env`, sauvegarde `.bak-20261104`) vise désormais `postgres:5432` par le réseau `intranet`. Complétion `gpt-4.1-mini` depuis le Gateway : 200 en 2,5 s ; tour d'agent `main` : réponse `OK`.
- **Clôture le 4 novembre** : [nabla-compose #323](https://github.com/AlbanAndrieu/nabla-compose/pull/323) pine `afca101` (fusion de #9), et le checkout TrueNAS y est aligné sans redéploiement, puisque `deploy/` n'a pas changé depuis `c600e9d`. Run manuel du digest : **livré sur Telegram**, mais en erreur au bout de 35 s, car `gpt-4.1-mini` appelle le skill comme un outil. Python 3 et le skill sont pourtant présents dans le conteneur. Cette instabilité précède la migration : sur la Workstation, le digest était en erreur les 1er, 2 et 3 novembre (script introuvable, timeouts), et son dernier succès date du 31 octobre.
- **Digest fiabilisé le 4 novembre** : la cause est le message du cron, pas l'environnement. « Exécute le skill installé » laissait `gpt-4.1-mini` reconstruire le pipeline à partir de `SKILL.md` (536 lignes) et du template. Sur 10 runs Workstation (24/10-03/11), 2 succès seulement : le modèle appelle d'abord `tool_call` avec l'id du skill (Tool Search, actif par défaut), puis invente des chemins relatifs, des scripts (`format-discord.py`, `render-template.py`) ou des options (`summarize-merged.py --output`, `--top 3-5`). Sur TrueNAS, il abandonne dès l'erreur de `tool_call`. Twitter aggrave les timeouts : l'API X répond `402 Payment Required` pour les 48 comptes, soit 87 s pour 0 article. Le message de `policies/cron/` donne désormais la commande exacte, en un seul `exec` (`yieldMs` 240 s, collecte sans Twitter, puis `summarize-merged.py --top 5`), le format Telegram et la règle de livraison : la réponse finale est le digest, que le planificateur livre. Le job TrueNAS `27d71377…` est réglé à l'identique (`toolsAllow` `exec,process`, `lightContext`, `timeoutSeconds` 300 ; sauvegarde privée dans `state/backups/cron/`). Pipeline seul : 262 articles fusionnés, la source la plus lente hors Twitter (Web) prenant 29 s. Run manuel : **`ok` en 51 s, digest réel en français livré sur Telegram.**
- **Digest corrigé le 4 novembre au soir** : le run planifié de 9 h est `ok` en 86 s et livré, mais ses sections portaient l'id du topic avec un emoji deviné (`🪙 crypto`) et une liste « top 5 » les précédait en doublon. Le message fixe désormais les titres de section (emoji et libellé de `tech-news-digest-topics.json`) et interdit toute liste hors section. La même commande écrit les titres retenus dans `archive/tech-news-digest/daily-<date>.md`, au format `- [Titre]` que `merge-sources.py` relit sur 14 jours pour retirer 5 points aux articles déjà publiés. Sur un test, 19 titres sur 20 sont reconnus : `summarize-merged.py` tronque les titres à 100 caractères. Un second run le même jour pénalise aussi les articles du premier. Job TrueNAS mis à jour (sha `7d5c5ea0…`, sauvegarde privée) ; run manuel : **`ok` en 54 s, livré, sections conformes, archive écrite.**
- **Briefing du matin le 5 novembre** : aucun briefing ne tournait, ni sur TrueNAS ni sur la Workstation ; seul le modèle `MORNING_BRIEFING.md` existait, Gmail y étant en « réauth requise ». Le job `morning-briefing` (8 h, clé cron, `gpt-4.1-mini`) exécute `scripts/heartbeat/morning-briefing.mjs` : synthèse des emails Gmail de 24 h via `gog --readonly` (binaire et trousseau fichier dans le dataset), messages Slack si le canal est actif, anomalies en cours regroupées par hôte (les sondes Gatus en échec tiennent sur une ligne), état des canaux. Le heartbeat ne fait plus de récapitulatif quotidien. Le plugin `@openclaw/slack` est installé et configuré en mode socket, mais **désactivé** : le jeton du bot repris de la Workstation est révoqué (`invalid_auth`).
- **Reste hors bascule** : régénérer les jetons Slack puis activer `channels.slack` ; réactiver Discord après un `doctor` attesté avec le vrai token ; étape 10 (retirer les anciens scripts Workstation de Compose).
- **Agent `coder` déployé sur TrueNAS le 10 novembre** : agent dédié à `fastapi-sample`, sandbox `ssh` vers la devbox `openclaw-devbox` (réseau interne, egress squid GitHub/PyPI en IPv4 et IPv6), clé LiteLLM `openclaw-coder` sur `gpt-4.1` (11 USD / 7 jours ≈ 10 €/semaine, SecretRef `file`, sans redémarrage), groupe Telegram forum `fastapi-sample` routé par sujet ; `just test-local-first` passe dans la devbox (`UV_PYTHON` système, `TMPDIR` exécutable dans le home). Le test de fumée depuis Telegram passe : le contrat `deploy/truenas/devbox/contract.json` est en `active` ([runbook](coder-agent.md)). Discord viendra avec sa réactivation.
- **Actions en attente du propriétaire** (ruleset `fastapi-sample`, retrait DNS de `postgres`, `401` sur `/metrics` LiteLLM, étape 10, guillemets des secrets) : [runbook opérateur](operator-pending.md).

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
