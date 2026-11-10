# Runbook opérateur — actions en attente (10 novembre 2026)

Ce qui reste de la [roadmap](roadmap.md) et ne peut pas avancer sans le
propriétaire : une action dans une interface (Telegram, GitHub, Cloudflare),
un secret à saisir, ou une décision. Chaque entrée donne l'état vérifié, la
commande et le résultat attendu. Rayer l'entrée une fois faite.

## 1. Agent `coder` : test de fumée

**État** : déployé sur TrueNAS le 10/11, redéployé avec `dd13688`. Toutes les
vérifications sont vertes : `devbox_egress=ok`, sandbox `all/ssh/session`,
`elevated=false`, `UV_PYTHON` et `TMPDIR=/home/coder/.tmp` présents dans la
devbox. Le premier essai a révélé deux défauts, corrigés par nabla-openclaw #15 :
l'interpréteur `3.13.17` épinglé par `fastapi-sample` était absent de l'image,
et `/tmp` est en `noexec`. Après correction, `just test-local-first` donne
`46 passed` dans la devbox.

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

Décision :
- **A (simple)** : retirer `Docker CI / Build Docker` des checks exigés
  (*Settings → Rules → Protect main*), puis reporter le changement dans
  `main.json` (#415) ;
- **B (propre)** : un job de synthèse qui se termine toujours dans un workflow
  de `fastapi-sample`, à exiger à la place.

À vérifier sur la première PR ouverte par l'agent : l'effet de
`require_extra_approval_for_unattributed_changes: true`, repris de la
configuration en ligne.

## 3. Cloudflare : retirer `postgres.albandrieu.com`

**État** : nabla-compose #345 est fusionnée (route TCP et app Access supprimées
du code, CNAME dans `retired_hostnames`). **Rien n'est appliqué** : la route
reste en ligne, protégée par l'app Access tant que ces commandes n'ont pas tourné.

```bash
# depuis ~/w/nabla-compose à jour, CLOUDFLARE_API_TOKEN chargé depuis Vaultwarden
scripts/infra/terragrunt-safe.sh infrastructure/cloudflare plan    # adopt
scripts/infra/terragrunt-safe.sh infrastructure/cloudflare apply
TF_VAR_dns_retirement_phase=retire scripts/infra/terragrunt-safe.sh infrastructure/cloudflare plan
```

Attendu : `dig +short postgres.albandrieu.com @1.1.1.1` vide.

## 4. LiteLLM : `401` sur `/metrics` toutes les minutes

**État** : le job Prometheus `litellm_hermes` (`apps/prometheus/prometheus.yml`
dans nabla-compose) interroge `172.17.0.24:4000/metrics` **sans clé**, d'où
1 440 `401 Unauthorized` par jour et une cible toujours `down`.

Décision :
- **A** : une clé LiteLLM en lecture seule, montée en fichier pour Prometheus
  (`authorization.credentials_file`). Le secret passe alors par le manifeste
  Vaultwarden.
- **B** : `litellm_settings.require_auth_for_metrics_endpoint: false`. Plus
  simple, mais les métriques (alias de clés, coûts) deviennent lisibles sur le LAN.
- **C** : retirer le job jusqu'à l'acceptation de Hermes.

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

Décision : valider ce lot, ou tout le dossier. Ensuite, une PR nabla-compose
retire les scripts, leurs tests et leurs recettes, une fois la session qui
travaille dans `~/w/nabla-compose` arrêtée.

## 6. Secrets runtime : normaliser les guillemets

**État** : nabla-compose #342 est fusionnée (parseur conforme à Compose et
audit sans valeurs). Le 10/11, l'audit relevait 233 lignes dans 20 fichiers :
24 commentaires en fin de ligne, 208 guillemets inutiles et une ligne mal formée
(`fastapisample/.env` `APP_DOMAIN`).

```bash
# sur TrueNAS, /mnt/cpool/compose/nabla-compose à jour
just runtime-secret-quoting-check
NABLA_RUNTIME_CHANGE_APPROVED=yes just runtime-secret-quoting-apply
```

À faire **avant** tout `import_dotenv_to_bitwarden.py --apply`, qui tourne sur
TrueNAS (`sudo cat` local). L'import est confié à une autre session.

## 7. Restent de la roadmap, côté propriétaire

- **Vercel FinOps, preuve L3** : la CLI `vercel` n'est pas installée sur la
  Workstation. Sur une machine authentifiée, lancer `just vercel-finops`. Ne
  jamais afficher `OK` sans CPU mesuré.
- **Slack** : régénérer les jetons du bot (`invalid_auth`), puis activer
  `channels.slack`.
- **Discord** : attester un `doctor` avec le vrai token avant de réactiver le
  canal, puis router `#fastapi-sample-dev` vers `coder`.

## 8. PR à fusionner

| PR | Effet à la fusion | Suite |
| --- | --- | --- |
| nabla-compose #348 | aucun (healthcheck LiteLLM, plan de la clé `coder`) | redéploiement de LiteLLM au prochain changement |
| nabla-openclaw (cette PR) | aucun | `just truenas-apply-coder` pour `compat.supportsUsageInStreaming` |
| fastapi-sample #415 | aucun (`main.json`) | bloquée par l'entrée 2 |
