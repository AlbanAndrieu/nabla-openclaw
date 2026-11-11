# Runbook opérateur — actions en attente (10 novembre 2026)

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

## 2. `fastapi-sample` : ruleset de `master`

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
- **Slack** : régénérer les jetons du bot (`invalid_auth`), puis activer
  `channels.slack`.
- **Discord** : attester un `doctor` avec le vrai token avant de réactiver le
  canal, puis router `#fastapi-sample-dev` vers `coder`.

## 8. PR à fusionner

| PR | Effet à la fusion | Suite |
| --- | --- | --- |
| ~~nabla-compose #348~~ (fusionnée le 11/11) | aucun | ~~redéploiement de Prometheus~~ fait le 11/11, cible `up` |
| ~~nabla-compose #349~~ (fusionnée le 11/11) | aucun | aucune |
| ~~nabla-openclaw #16~~ (fusionnée le 11/11) | aucun | ~~`just truenas-apply-coder`~~ fait le 11/11 |
| ~~nabla-openclaw #17~~ (fusionnée le 11/11) | aucun | ~~`just truenas-apply-heartbeat`~~ fait le 11/11 ; reste le premier relevé Vercel (export manuel en Hobby) |
| nabla-compose #350 (épinglage `apps/openclaw` `dd13688` → `ff74bfa` ajouté) | aucun pour l'épinglage (simple trace) | redéploiements listés dans la PR (grafana, pyroscope, gatus) |