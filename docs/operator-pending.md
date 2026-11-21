# Runbook opérateur — actions en attente (21 novembre 2026)

Passes du 21/11 : B2 (pin nabla-compose) réglé par nabla-compose #427 ; B1
(réappliquer le heartbeat) fait le 21/11, collecteur `0f52f1ea…` relevé sur
TrueNAS par la session nabla-compose. O1 et O2 tranchées le 21/11 ; autres questions : [état de la
boucle du 21/11](runbooks/2026-11-21-roadmap-loop-state.md). Historique de B1 :
[runbook du 16/11](runbooks/2026-11-16-roadmap-pass-blockers.md).

Ce qui reste de la [roadmap](roadmap.md) et ne peut pas avancer sans le
propriétaire : une action dans une interface (Telegram, GitHub, Cloudflare),
un secret à saisir, ou une décision. Chaque entrée donne l'état vérifié, la
commande et le résultat attendu. Rayer l'entrée une fois faite.

## 1. ~~Agent `coder` : test de fumée~~ (passé le 10/11, contrat `active`)

**État** : déployé sur TrueNAS le 10/11, redéployé avec `dd13688`. Toutes les
vérifications sont vertes : `devbox_egress=ok`, sandbox `all/ssh/session`,
`elevated=false`, `UV_PYTHON` et `TMPDIR=/home/coder/.tmp` présents dans la
devbox. Le premier essai a révélé deux défauts, corrigés par nabla-openclaw #15 :
l'interpréteur `3.13.17` épinglé par `fastapi-sample` était absent de l'image,
et `/tmp` est en `noexec`. Après correction, `just test-local-first` donne
`46 passed` dans la devbox. Le 11/11, après la fusion de #16,
`just truenas-apply-coder` a appliqué `compat.supportsUsageInStreaming` sans
redémarrage : la valeur est lue en ligne, et le Gateway reste `healthy`.

1. Telegram : promouvoir `@AlbandrieuBot` **administrateur** du groupe
   `fastapi-sample` (`-1004370510554`), tous droits décochés. Le bot a
   `can_read_all_group_messages=false` (mode confidentialité) : sans ce
   réglage, il ne reçoit que les messages qui le mentionnent.
2. Ouvrir un **nouveau sujet** et envoyer :
   > Clone fastapi-sample, lance `just test-local-first`, ne commite rien et donne le compte rendu.
3. Attendu : clone, `uv sync --frozen` via le proxy, `test-local-first` en
   `PASS`, sans commit ni push.
4. Si le test passe : PR de suivi, avec `deploy/truenas/devbox/contract.json` en
   `"status": "active"`, la puce de la roadmap en « déployé le 10 novembre »,
   puis `just test` et `just devbox-plan` (`=active`).
5. Si le test échoue : `CODER_TELEGRAM_GROUP_ID=-1004370510554 just truenas-rollback-coder`.

Constaté au passage : à l'ajout du bot au groupe, la fonction intégrée
« Channel room join introduction » de l'agent `main` a été refusée par le
filtre de contenu Azure (`ContentPolicyViolationError`, sur `gpt-4.1` puis
`gpt-4.1-mini`). Son prompt enveloppe le contenu externe dans des marqueurs
`EXTERNAL_UNTRUSTED_CONTENT`. L'incident est ponctuel : il ne se reproduit qu'à
l'arrivée du bot dans un nouveau groupe.

## 2. ~~`fastapi-sample` : ruleset de `master`~~ (fait, vérifié le 16/11)

Vérifié par `gh api` le 16/11 : « Protect main » n'exige plus que
`Test dependencies and optionally build Python package`.

**État** : le ruleset « Protect main » est actif depuis le 10/11, avec l'App de
release en bypass ; le doublon désactivé « Protect main tmp » est supprimé.
**Défaut** : le check exigé `Docker CI / Build Docker` n'est jamais créé sur une
PR qui ne touche pas Docker, car le job appelant `Docker CI` est sauté. Ces PR
restent bloquées : #415 est en `BLOCKED` malgré des checks verts. Le check
Python sauté, lui, compte comme réussi.

Décision (option A, retenue le 11/11) : retirer `Docker CI / Build Docker` des
checks exigés dans *Settings → Rules → Protect main*, à faire à la main ;
`main.json` est déjà aligné dans #415.

À vérifier sur la première PR ouverte par l'agent : l'effet de
`require_extra_approval_for_unattributed_changes: true`, repris de la
configuration en ligne.

## 3. ~~Cloudflare : retirer `postgres.albandrieu.com`~~ (fait le 11/11)

Plan relu puis appliqué (1 import, 1 modification, 2 suppressions) : app Access,
route TCP 5432 et CNAME détruits. `dig +short postgres.albandrieu.com @1.1.1.1`
est vide, et les plans `retire` et par défaut sont à 0. Sauvegarde de l'état
dans `~/.local/state/nabla-compose/opentofu-state-backups/cloudflare/`.
Politique DNS nettoyée par nabla-compose #349 (fusionnée le 11/11). Le jeton vient de
`nabla/prod/cloudflaretokens` (champ `CLOUDFLARE_API_TOKEN_NABLA_OPENTOFU`).
Les clés Garage étaient déjà dans l'environnement, et non dans Vaultwarden :
l'entrée `nabla/prod/infrastructure-bootstrap` n'existe pas encore.

## 4. ~~LiteLLM : `401` sur `/metrics` toutes les minutes~~ (corrigé le 11/11)

Prometheus redéployé le 11/11 au soir (`app.redeploy prometheus`) : la cible
`litellm_hermes` est `up`, sans erreur. Reste seulement l'import de la variable
dans Vaultwarden (fin de l'entrée).

**État** : le job Prometheus `litellm_hermes` (`apps/prometheus/prometheus.yml`
dans nabla-compose) interroge `172.17.0.24:4000/metrics` **sans clé**, d'où
1 440 `401 Unauthorized` par jour et une cible toujours `down`.

LiteLLM 1.108 exige un admin du proxy ou une clé autorisée sur `/metrics` :
même une clé virtuelle valide reçoit `401`. Décision (11/11) : une clé limitée
à cette route (`allowed_routes: ["/metrics"]`), lue par Prometheus depuis un
fichier. Code dans nabla-compose #348. **Clé appliquée le 11/11** :
`metrics_http=200`, `403` sur `/v1/models` et `/key/list`, fichier
`/mnt/cpool/prometheus/secrets/litellm-metrics.key` en `root:apps 0640`.

Reste (#348 fusionnée le 11/11 et présente dans le checkout TrueNAS) :
redéployer Prometheus et vérifier la cible `litellm_hermes` en `up`. Le 11/11
au soir, elle était encore `down` (`401 Unauthorized`), faute de redéploiement.
La nouvelle variable `LITELLM_PROMETHEUS_METRICS_API_KEY` du runtime LiteLLM
est à importer dans Vaultwarden avec les autres.

## 5. Étape 10 : retirer les scripts Workstation de Compose

**État** : le Gateway Workstation est désactivé depuis le 3/11
(`openclaw-gateway.service` en `disabled`), et aucune crontab ni unité systemd
de la Workstation n'appelle `scripts/workstation/`. nabla-compose en contient
79 scripts, dont 59 OpenClaw : 40 sont encore référencés hors du dossier (surtout
des recettes du `justfile`), 19 ne le sont plus. Certains servent encore TrueNAS
(`preflight-truenas-litellm-openclaw.py`, `check-truenas-litellm-secret-provenance.py`).

Non référencés hors du dossier, candidats à un premier lot (à confirmer : un
script du dossier peut en appeler un autre, par exemple `openclaw-ops.sh`) :
`openclaw-error-aggregate.py`, `classify-openclaw-secret-findings.py`,
`diagnose-openclaw-memory-search.py`, `inspect-openclaw-memory-min-score.py`,
`openclaw-auth-presence.py`, `openclaw-dotenv-diagnostic.py`,
`openclaw-heartbeat-workspace-audit.py`, `openclaw-litellm-audit.py`,
`openclaw-memory-audit.py`, `openclaw-rate-limit-correlation.py`,
`openclaw-terminal-style.py`, `plan-openclaw-secret-migration.py`,
`preflight-openclaw-secrets-import.py`, `openclaw-application-log-summary.py`,
`openclaw-cron-runs-summary.py`, `diagnose-openclaw-errors.sh`,
`prepare-openclaw-systemd.sh`, `diagnose-openclaw.sh`, `backup-openclaw.sh`.

Premier lot fait le 11/11 (nabla-compose #348) : six scripts que seul leur
test appelait sont retirés, avec ce test (`classify-openclaw-secret-findings`,
`diagnose-openclaw-memory-search`, `inspect-openclaw-memory-min-score`,
`openclaw-rate-limit-correlation`, `plan-openclaw-secret-migration`,
`preflight-openclaw-secrets-import`).

Second lot fait le 11/11 (nabla-compose #349) : `openclaw-ops.sh`, `diagnose-openclaw.sh`,
`openclaw-migration-evidence.sh` et les neuf scripts qu'ils étaient seuls à
appeler, avec leurs tests et recettes. Restent `backup-openclaw.sh`,
`openclaw-terminal-style.py` et `openclaw-litellm-audit.py`, utilisés par la
mise à jour mise (`openclaw-upgrade-local-*`) et le triage 429
(`openclaw-429-*`) : ils partiront avec ces recettes.

Constat du 21/11 sur `origin/master` de nabla-compose : rien n'a bougé depuis
le 11/11 (41 scripts OpenClaw sur 55 sous `scripts/workstation/`, 13 fichiers
sous `ops/openclaw-workstation/`). Ces deux familles de recettes visent le
Gateway Workstation, désactivé depuis le 3/11 : le lot suivant se fait dans
la PR en cours de nabla-compose, pas ici.

Lot 3a fait le 21/11 (nabla-compose #430) : recettes `openclaw-429-attribution*`
et `diagnose-openclaw-auth-cooldowns.py`, sans autre consommateur. Le reste de la
famille Workstation s'appelle en chaîne et dépasse 20 fichiers ; plusieurs scripts
font plus de 300 lignes, ce qui déclenche le garde `QG_LARGE_DELETION` du gate.
Il partira donc en un seul lot, revu par le propriétaire (question P3 du runbook
d'état de la boucle roadmap dans nabla-compose).

## 6. ~~Secrets runtime : normaliser les guillemets~~ (appliqué le 11/11)

Appliqué le 11/11 au soir : 231 lignes normalisées, avec sauvegarde 0600 et
valeurs prouvées inchangées, sans redémarrage. Reste une ligne mal formée,
laissée à relire : `fastapisample/.env` `APP_DOMAIN`. Elle doit être corrigée à
la main, sans afficher sa valeur, avant l'import Vaultwarden.

**État** : nabla-compose #342 est fusionnée (parseur conforme à Compose et
audit sans valeurs). Le 10/11, l'audit relevait 233 lignes dans 20 fichiers :
24 commentaires en fin de ligne, 208 guillemets inutiles et une ligne mal formée
(`fastapisample/.env` `APP_DOMAIN`).

```bash
# sur TrueNAS, /mnt/cpool/compose/nabla-compose à jour
just runtime-secret-quoting-check
NABLA_RUNTIME_CHANGE_APPROVED=yes just runtime-secret-quoting-apply
```

Audit relancé le 11/11 au soir : `dotenv_quoting_pending=232`, rien n'est
encore normalisé. `just` n'est pas installé sur TrueNAS : lancer la commande
de la recette, `sudo -n python3 scripts/secrets/audit_dotenv_quoting.py`.

À faire **avant** tout `import_dotenv_to_bitwarden.py --apply`, qui tourne sur
TrueNAS (`sudo cat` local). L'import est confié à une autre session.

## 7. Restent de la roadmap, côté propriétaire

- **Vercel FinOps** : preuve L3 faite le 11/11. En Hobby, ni `vercel usage`
  ni `vercel metrics` ne donnent le CPU actif ([détail](vercel-finops.md)).
  Seule voie : exporter à la main le JSON du tableau de bord Usage, puis
  `just vercel-finops-file <export>`.
- **Slack** (Socket Mode retenu le 11/11, sans exposition publique du Gateway ;
  **décision O1 du 21/11** : ce canal porte les notifications du control plane
  FastAPI Sample, item F18 de la roadmap de fastapi-sample, **en sortie
  seule** : aucune approbation ni commande depuis Slack, identité Slack
  OpenClaw existante, canal fixe, pas de nouveau bot, pas de partage du jeton
  `xapp-`) :
  - jeton d'application `SLACK_OPENCLAW_NABLA_TOKEN` (`xapp-`) : valide
    (`apps.connections.open` ok), mais **exposé en clair dans une conversation le
    11/11 : à régénérer** (*Basic Information → App-Level Tokens*, portée
    `connections:write`), puis à révoquer et à mettre dans Vaultwarden ;
  - jeton du bot : `SLACK_BOT_USER_OAUTH_TOKEN` (`xoxb-`) est révoqué
    (`invalid_auth`). `SLACK_TOKEN` est valide, mais il appartient à un autre
    espace de travail Slack : ne pas l'utiliser. Réinstaller l'app OpenClaw dans
    l'espace de travail (*OAuth & Permissions → Reinstall*) pour obtenir un
    nouveau `xoxb-` ;
  - ensuite : écrire les deux jetons en 0600 dans
    `/home/node/.openclaw/credentials/slack/` (provider SecretRef `file`, comme
    la clé `coder`), puis `channels.slack` avec `botToken` et `appToken` en
    SecretRef, sans redémarrage.
- **Agent `coder` sur `nabla-compose`** (appliqué le 19/11 : skills
  `nabla-compose-dev` et `nabla-roadmap-pass`, job `nabla-compose-roadmap-pass`
  à 02:00) :
  0. **Décisions du propriétaire (21/11)**, voir [coder-agent.md](coder-agent.md) :
     **O2** App GitHub dédiée à la devbox (pas de compte machine) ; manifeste
     prêt, création et installation restent à faire par l'opérateur (étapes 1
     à 4 de la section « Identité GitHub »), puis helpers à adapter ;
     **O1** le Slack d'OpenClaw porte les notifications du control plane
     FastAPI Sample (F18), en sortie seule (voir l'entrée Slack ci-dessus) ;
  1. ~~Ruleset « Protect master »~~ (fait le 19/11, aligné sur les 52 dépôts
     publics et `dotfiles`) : suppression et force-push interdits, historique
     linéaire, PR en squash, `GitGuardian Security Checks` exigé, App de
     release `4676280` seule exception (installée sur tous les dépôts), plus un
     ruleset séparé « Code quality ». Repris en OpenTofu par
     nabla-compose#420 (plan : 51 imports sans écart). **Reste ouvert** :
     0 approbation requise, et le token de la devbox agit au nom du
     propriétaire : il peut techniquement fusionner sa propre PR. Seule la
     politique de l'agent l'en empêche ; la parade est une identité GitHub
     dédiée à la devbox (**App, décision O2 du 21/11**) avec 1 approbation exigée ;
  2. réduire le token de la devbox aux cinq dépôts de l'agent (`repositories`
     de `deploy/truenas/devbox/contract.json`) : il couvre 10 dépôts le 19/11,
     dont `nabla-memo` (privé, sans protection possible) ;
  3. identité Git : la passe du 19/11 a écrasé `git config --global`
     (« OpenClaw Devbox Agent », adresse inventée, commit `987c4676` de #417).
     Corrigé dans le code : l'identité `openclaw-coder` vient du `SetEnv` de
     `sshd_config` (l'environnement prime sur toute config écrite par
     l'agent) et l'agent n'a plus le droit de toucher `git config`. Effectif
     après reconstruction de l'image : `just truenas-deploy-coder --apply` ;
  4. job `fastapi-sample-daily-improvement` : codé, **non déclaré** sur le
     Gateway (`cron list --all` du 19/11). `just truenas-apply-coder-cron` ;
  5. ~~fermer nabla-compose#417~~ (fermée le 20/11) : issue de la passe
     d'avant les correctifs, la passe de 02:00 repart d'une branche neuve.
- **Agent `coder` sur `nabla-site-alban`, `nabla-site-bababou` et
  `nabla-yubikey`** (codé le 20/11, `NOT_RUN` en runtime) : rulesets en place
  et dépôts déjà couverts par le token fine-grained (10 dépôts le 19/11).
  1. après fusion, mettre à jour `apps/openclaw` dans nabla-compose, puis
     `just truenas-deploy-coder --apply` : reconstruit les images `0.2.0`
     (Node 24.22.3 et npm 12.2.2 vérifiés par SHA-256, allowlist squid avec
     `registry.npmjs.org`) et applique les skills `nabla-site-dev` et
     `nabla-yubikey-dev`, sans redémarrer le Gateway ;
  2. preuve : `just devbox-egress-check`, puis depuis Telegram « Clone
     nabla-site-alban, lance `npm ci` et `npm run test:unit`, ne commite
     rien et donne le compte rendu. »
- **Discord** : attester un `doctor` avec le vrai token avant de réactiver le
  canal, puis router `#fastapi-sample-dev` vers `coder`.
- **Homarr** : la clé créée le 11/11 (`nabla/prod/homarr`) est installée dans
  `/mnt/cpool/secrets/runtime/homarr/.env.secrets` (seule cette ligne
  remplacée, sauvegarde 0600) et lue par le conteneur après redéploiement,
  mais Homarr répond encore `401`. Vérifier dans Homarr (*Settings → API*)
  que la clé existe et qu'elle a été copiée en entier (`id.jeton`).
- **AutoKuma** : les secrets vont dans `/mnt/cpool/secrets/runtime/autokuma/`,
  comme pour les autres Apps : dès que ce fichier existe, l'ancien
  `/mnt/cpool/autokuma/.env.secrets` (vide) n'est plus lu. **Bloqué en amont** :
  Uptime Kuma n'est pas déployé (aucune App, `172.17.0.24:31050` ne répond pas),
  donc il n'y a pas de jeton à créer, et AutoKuma tourne dans le vide
  (timeouts). Le README d'AutoKuma demande de le laisser arrêté tant
  qu'Uptime Kuma n'existe pas. Il n'y a pas non plus d'entrée
  `nabla/prod/autokuma` dans Vaultwarden.
- **Fichiers `nabla/env/home/pass/*.env.sh`** : inventaire du 11/11, noms
  seulement : 1 175 affectations, dont 356 secrets distincts (308 absents de
  Vaultwarden), 149 noms liés au contexte *Job* à relire, 351 réglages non
  secrets (URL, identifiants, régions), et aucun doublon contradictoire.
  **Importé le 12/11** dans le dossier Vaultwarden `TrueNAS`, une entrée par
  service (`nabla/prod/<service>`) : 123 entrées créées et 15 entrées
  existantes complétées, soit 291 champs cachés. Aucun champ existant n'a été
  écrasé (40 noms étaient déjà dans le coffre). Exclus : le contexte *Job* et
  les environnements DEV, UAT et PROD, les réglages non secrets et les alias.
  Les entrées créées portent la note « Imported from nabla/env/home/pass ».
  Les fichiers sont passés en `0600`. Ils restent la source tant que les
  scripts qui les sourcent n'ont pas migré vers Vaultwarden.
- **`fastapisample/.env`** : corriger la ligne mal formée `APP_DOMAIN` (entrée 6).
- **Vaultwarden** : importer `LITELLM_PROMETHEUS_METRICS_API_KEY` et créer
  l'entrée `nabla/prod/infrastructure-bootstrap` (clés Garage).

## 8. PR à fusionner

| PR | Effet à la fusion | Suite |
| --- | --- | --- |
| ~~nabla-compose #348~~ (fusionnée le 11/11) | aucun | ~~redéploiement de Prometheus~~ fait le 11/11, cible `up` |
| ~~nabla-compose #349~~ (fusionnée le 11/11) | aucun | aucune |
| ~~nabla-openclaw #16~~ (fusionnée le 11/11) | aucun | ~~`just truenas-apply-coder`~~ fait le 11/11 |
| ~~nabla-openclaw #17~~ (fusionnée le 11/11) | aucun | ~~`just truenas-apply-heartbeat`~~ fait le 11/11 ; reste le premier relevé Vercel (export manuel en Hobby) |
| ~~nabla-compose #350~~ (fusionnée le 11/11, avec l'épinglage `apps/openclaw` → `ff74bfa`) | aucun | fait le 11/11 : grafana, homarr, pyroscope et gatus redéployés et sains, crowdsec non redémarré ; AutoKuma bloqué (entrée 7) |
| ~~nabla-compose #351~~ (fusionnée le 12/11) | au prochain redéploiement de `homarr` | `homarr-sync` attend 3 min au lieu de 60 s (l'App passait en `CRASHED` le 11/11) |