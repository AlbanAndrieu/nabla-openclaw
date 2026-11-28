# Audit sécurité quotidien sur la devbox OpenClaw

Le job `security-audit-daily` tourne à 00:00 Europe/Paris, 25 minutes max,
avant le référent de 00:30 et hors fenêtre d'IO TrueNAS. Il alterne chaque jour
nabla-compose, fastapi-sample, nabla-site-alban et nabla-site-bababou (un dépôt
par jour, au plus six unités). Le skill Cloudflare déjà vendored est épinglé
à c1c8a8c1471069fb0e188eeaff69b8e8db6564a8 ; les huit fichiers nécessaires
sont contrôlés SHA-256 avant utilisation.

## Persistance et limite de sécurité

`/home/coder/security-audit-skill/<repo>/run-YYYY-MM-DD/` est directement dans
le bind mount existant `/mnt/cpool/openclaw-devbox/home` de TrueNAS, pas dans le
workspace éphémère d'une session. Les dossiers sont 0700, les fichiers 0600.
Le runner réserve un seul run par jour, enregistre SHA, scope et historique
compatible, refuse de remplacer un run, contrôle les fichiers et scelle un
résumé à partir des deux validateurs Node épinglés, avec manifeste SHA-256
privé pour détecter des corruptions avant réutilisation (pas une signature). Le code audité n'est
jamais exécuté. Un run interrompu reste incomplet et non scellé. Une revue
quick source-only **n'est pas** le full audit Cloudflare : les sous-agents
indépendants et l'isolation requise sont indisponibles (NOT_RUN).
Le stockage n'isole pas deux processus du même UID coder : c'est une limite
d'accès, pas une attestation d'intégrité face à un agent compromis.

L'archive reste locale, sans nouveaux droits, endpoint ou export réseau.
Le pool ZFS n'est pas à lui seul une sauvegarde : vérifier snapshots et
restauration autorisée de ce dataset, et définir une rétention (aucune
suppression automatique initiale). Un dépôt public ne doit jamais contenir
les runs, traces, hypothèses, fingerprints, logs ou preuves brutes, ni les
sources familiales. Git est adapté au code, politique et schémas ; au besoin
une synthèse agrégée validée manuellement pourra être publiée, pas un push
quotidien (historique immuable, coût CI et fuite potentielle).
summary.json est une projection à champs fixes, destinée aux métriques
privées (sans chemins, titres de findings ni extraits de code), non une
autorisation de publication. SARIF et DefectDojo : n'importer que des
findings indépendamment validés après revue ; ces runs n'en produisent pas.

## Application et recette (workstation autorisée)

Après revue du checkout exact et tests :
```bash
python3 -m unittest discover -s tests -p 'test_coder_cron.py'
python3 -m unittest discover -s tests -p 'test_security_audit_run.py'
bash -n scripts/coder/apply-cron-truenas.sh
just truenas-apply-coder-cron security-audit-daily
```
La commande déploie le runner en tant que coder et déclare le cron avec sa
clé stable, sans redémarrage. Contrôler via `openclaw cron list --all` depuis
le Gateway (un seul nom, prochain passage 00:00). Déclencher un seul
`openclaw cron run <id>` en fenêtre hors charge seulement après revue
du budget et de la config. Vérifier en lecture seule les permissions des
dossiers et summary.json sur le dataset, le SHA, les validateurs, puis la
réutilisation au passage suivant du même dépôt. Un échec ou run incomplet
n'est jamais un constat d'absence de vulnérabilité. Rollback : désactiver
la déclaration par son id exact via cron CLI, garder le dataset intact.
Ne pas effacer un run incomplet pour rejouer sans décision opérateur.

**État : CODED et TESTED offline ciblé, runtime NOT_RUN.** Prochaines étapes : recette TrueNAS,
vérification indépendante en environnement dédié sans egress ni secrets,
export des findings confirmés vers DefectDojo/SARIF et ingestion des
synthèses privées par FastAPI Sample, sans exposer les preuves.
