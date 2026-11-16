# Passe roadmap du 16 novembre 2026 — blocages

Passe complète de la [roadmap](../roadmap.md) et du [runbook opérateur](../operator-pending.md),
branche `feat/openclaw-roadmap-pass-20261116` (base `origin/master` `4921230`).
Mode `workstation`, sans accès TrueNAS : pas de ControlMaster ouvert
(`ssh -O check truenas` : socket absent), la clé SSH est sur la YubiKey.

## Fait pendant la passe

- **Cinq commits orphelins rapatriés** : faits du 6 au 10/11 sur
  `docs/truenas-cutover-closure-20261104` après la fusion de sa PR #10, ils
  n'étaient jamais arrivés sur `master` (`git cherry` : tous `+`). Rejoués par
  `cherry-pick -x`, conflits résolus en gardant les deux côtés :
  disque monté deux fois signalé une seule fois ; santé postgres et redis de la
  Workstation ; synthèse des emails du briefing même sans action ; flux RSS du
  digest pris dans les catégories FreshRSS ; sauvegarde Restic de la
  Workstation périmée au-delà de 26 h. Le sixième commit (`3136ae9`) ne touche
  que `.claude/settings.local.json`, local : non repris.
  `just test` : 91 tests Python (1 sauté), 31 + 11 tests Node, tous verts.
- **Ruleset `fastapi-sample`** (runbook opérateur, entrée 2) : vérifié par
  `gh api` le 16/11. « Protect main » est actif et n'exige plus que
  `Test dependencies and optionally build Python package` ;
  `Docker CI / Build Docker` n'est plus requis.
- **nabla-compose #351** (attente de l'API Homarr) : fusionnée le 12/11.
- **Bababou hors du FinOps** : garanti par construction.
  `publish-vercel-finops.sh` reconstruit le JSON champ par champ (liste
  blanche), et `--output` n'écrit que le résumé compact (testé).

## Blocages

### B1. Heartbeat et briefing TrueNAS probablement revenus en arrière (11/11)

`just truenas-apply-heartbeat`, lancé le 11/11 depuis `master`, installe
`homelab-health.mjs` et le message du briefing depuis le checkout. Or `master`
n'avait pas les correctifs du 6 au 10/11 (voir ci-dessus). Le Gateway tourne donc
probablement sans les contrôles postgres, redis et Restic, avec le disque monté
deux fois signalé en double, et avec l'ancienne consigne des emails.

Vérification, en lecture seule, après `ssht` :

```bash
ssh truenas 'sudo -n sha256sum /mnt/cpool/openclaw/state/workspace/scripts/homelab-health.mjs /mnt/cpool/openclaw/state/workspace/scripts/freshrss-sources.py'
```

| Fichier | `master` (`4921230`) | cette branche |
| --- | --- | --- |
| `homelab-health.mjs` | `ec2e6901bc5cb905…` | `0f52f1ea8abf6f9f…` |
| `freshrss-sources.py` | absent | `630c803632fbc7a1…` |

Correction, **après fusion** de cette branche et avec un OK explicite : sans
redémarrage, depuis le checkout à jour.

```bash
cd ~/w/nabla-openclaw && git switch master && git pull --ff-only && just test
just truenas-apply-heartbeat
```

Retour arrière : relancer la même recette depuis `4921230`
(`git switch --detach 4921230 && just truenas-apply-heartbeat`).

### B2. Pin `apps/openclaw` de nabla-compose revenu à `afca101` (15/11)

Le commit `e8dac27` (« fix(claude): claude local »), entré dans `master` avec
nabla-compose #395 (pfSense), a fait passer le gitlink `apps/openclaw` de
`ff74bfa` à `afca101` (4/11, avant l'agent `coder`, la devbox et le FinOps
Vercel). Probablement un sous-module local en retard, indexé avec la
configuration Claude.

Impact runtime nul pour l'instant : `scripts/cron.sh` fusionne sans
récursion des sous-modules (`submodule.recurse=false`). Mais un
`git submodule update` sur TrueNAS ou un clone neuf ramènerait `afca101`.

Correction dans nabla-compose, sur sa branche de PR en cours, une fois cette
branche fusionnée (`<sha>` = nouveau `master` de nabla-openclaw) :

```bash
git -C apps/openclaw fetch origin && git -C apps/openclaw switch --detach <sha>
git add apps/openclaw
git commit -m "fix(openclaw): restore the apps/openclaw pin rolled back by e8dac27"
```

Retour arrière : `git revert` de ce commit. La session « Améliorations
nabla-compose » travaille ce dépôt : à lui confier, ou à faire ici ?

### B3. Publication de cette branche

Publiée en PR Draft le 16/11, sur accord explicite de l'opérateur. Le passage
en Ready et la fusion restent à sa main ; B1 et B2 se traitent après la fusion.

### B4. Vercel FinOps : P0 7 à 9 et P1 mémoire/invocations

Inchangé : en Hobby, ni la CLI ni l'API ne donnent le CPU actif. Il faut
l'export JSON du tableau de bord *Usage*, à déposer dans un chemin privé, puis :

```bash
just vercel-finops-file /chemin/prive/usage.json
```

Le P1 (Fluid Provisioned Memory, invocations, ventilation par projet) attend
ce même export : sans échantillon réel, le format est inconnu, et le
parseur est partagé avec nabla-site-alban et Bababou.

### B5. Actions propriétaire non revérifiées le 16/11

Sans accès TrueNAS ni aux consoles : jetons Slack (`xapp-` à régénérer,
`xoxb-` à réobtenir), `doctor` Discord, Homarr `401`, AutoKuma (bloqué tant
qu'Uptime Kuma n'est pas déployé), ligne `APP_DOMAIN` de
`fastapisample/.env`, imports Vaultwarden. Détail dans le
[runbook opérateur](../operator-pending.md), entrées 6 et 7.
L'étape 10 reste dans nabla-compose : 41 scripts OpenClaw sous
`scripts/workstation/`, dont `backup-openclaw.sh`,
`openclaw-terminal-style.py` et `openclaw-litellm-audit.py`.
