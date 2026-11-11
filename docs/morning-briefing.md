# Runbook — briefing du matin (11 novembre 2026)

Le briefing du mercredi 11/11 remontait quatre problèmes. Pour chacun : la cause
vérifiée, le correctif et ce qui reste à appliquer. Les commandes TrueNAS
d'écriture demandent l'accord du propriétaire.

## 1. Format

Le collecteur (`scripts/heartbeat/morning-briefing.mjs`) n'affiche plus que les
anomalies :

- Slack n'apparaît que si `channels.slack` est actif ; la section Canaux
  (Telegram, Discord) disparaît.
- Homelab : `✅ RAS` si rien ne va mal, sinon seulement les hôtes en anomalie.
  Le compteur ne garde que les sévérités présentes.
- Une ligne par nom d'alerte : les cibles d'un exporter injoignable tiennent
  sur une ligne, désignées par leur label `job` au lieu de `IP:port`.

Briefing produit le 11/11 vers 19 h 45 dans le Gateway (copie temporaire du
script, rien de déployé ; emails omis ici) :

```text
## INFRA
🟠 8 · ⚪ 2
TrueNAS et services :
🟠 Cible Prometheus fastapi_sample injoignable
🟠 Cible Prometheus keycloak injoignable
🟠 Cible Prometheus litellm_hermes injoignable
🟠 TrueNAS : RAM 94 %
🟠 Conteneur TrueNAS fastapi-sample : unhealthy
🟠 Conteneur TrueNAS pihole-dns-sync : redémarre en boucle
🟠 Alerte NablaExporterTargetDown : opensearch, haproxy, postgres_exporter, opensearch-security
🟠 6 sondes Gatus en échec : ai/OpenHands, development/FastAPI Sample, network/DDNS Updater, observability/Dozzle, operations/Dockhand, productivity/Draw.io
⚪ Source docker injoignable (fetch failed)
⚪ Vercel Fluid Active CPU : métriques absentes ou non vérifiées (NOT_MEASURED)
```

Les deux lignes `Conteneur TrueNAS` sont périmées (sections 3 et 4) : elles
disparaîtront quand la source docker répondra de nouveau (section 2).

## 2. « Source docker injoignable (fetch failed) »

**Cause** : le collecteur lisait `http://172.17.0.24:2375`, port publié par
l'ancienne app catalogue `docker-socket-proxy`. Le 10/11 à 23:47 UTC,
nabla-compose `e51726d3` l'a remplacée par l'app versionnée
`apps/docker-socket-proxy`. Celle-ci ne publie aucun port et ne sert que le
réseau interne `docker-proxy` (et `intranet`, à titre transitoire). Premier
heartbeat en échec : 11/11 06:33 UTC. Depuis, le collecteur conserve les
dernières anomalies docker connues, d'où les lignes périmées.

**Correctif (ce dépôt)** : le collecteur lit
`http://docker-socket-proxy:2375`, et le Gateway rejoint `docker-proxy`
(`deploy/truenas/compose.yml`).

**Compromis de sécurité** : le proxy autorise `GET /containers/*`, donc aussi
`inspect`, qui montre les variables d'environnement des conteneurs. Le Gateway
avait déjà cet accès par le port publié jusqu'au 10/11. Rejoindre le réseau
interne réserve cet accès au Gateway au lieu de l'ouvrir à tout le LAN. Pour
aller plus loin, il faudrait un proxy dédié limité à `GET /containers/json`.

**À appliquer après fusion** (accord requis) :

```bash
just truenas-apply-heartbeat
# immédiat, perdu au prochain redéploiement tant que nabla-compose n'a pas le sous-module à jour
ssh truenas sudo -n docker network connect docker-proxy openclaw-gateway
# durable : monter apps/openclaw dans nabla-compose, puis redéployer l'App openclaw-gateway
ssh truenas "sudo -n docker exec openclaw-gateway node -e \"fetch('http://docker-socket-proxy:2375/_ping').then(r=>r.text()).then(console.log)\""
```

Résultat attendu : `OK`, puis au heartbeat suivant `Résolu` pour la source
docker et les deux conteneurs.

## 3. `pihole-dns-sync` « redémarre en boucle »

**Cause** : du 9/11 vers 19:32 UTC au 10/11 23:51 UTC, il ne résolvait pas
`docker-socket-proxy` (`lookup docker-socket-proxy on 127.0.0.11:53: no such
host`, 117 fois dans les 80 dernières minutes de la boucle, `RestartCount`
5005) : l'app catalogue avait de nouveau quitté `intranet`.

**Corrigé à la source** par nabla-compose `e51726d3`, déployé le 10/11 :
conteneur recréé à 23:51 UTC sur `docker-proxy` et `intranet`, stable depuis
(aucun redémarrage le 11/11). La ligne du briefing était l'entrée périmée du
ledger (section 2).

**Reste, sans blocage** : à chaque création de conteneur, `pihole-dns-sync`
demande `GET /volumes/<id>`, que le proxy refuse (`403`, `VOLUMES` hors liste
blanche). La synchro continue (`Exists DNS`, `Updated routes`). À décider :
ajouter `VOLUMES: 1` (lecture seule) dans `apps/docker-socket-proxy` ou
accepter ce bruit.

## 4. `fastapi-sample` « unhealthy »

Deux incidents distincts.

1. **10/11, de 21:24 à environ 23:50 UTC** : le redéploiement de
   nabla-compose `fd98421b` (TLS vérifié vers PostgreSQL, alors que TLS y est
   désactivé) échoue (`sample did not become stable within 300s`). **Corrigé**
   par `b773cc56` (`sslmode=prefer`) ; la cible Prometheus repasse à `up` dès
   00:00 UTC. La ligne du briefing du 11/11 était cette entrée périmée.
2. **11/11, de 18:27 à 18:42 UTC** (conteneur recréé) : le healthcheck expire
   (10 s) et le worker gunicorn met plus de 10 min à démarrer : `Creating API`
   puis 38 s, 5 min 44 s et 1 min 53 s entre les lignes suivantes, à 0,1 % de
   CPU. Il attend les E/S. **Cause** : TrueNAS sature (PSI io 58 %, iowait
   39 %, 3,8 Gio disponibles sur 62, ARC réduit à 8 Gio sur 61, alerte
   `TrueNASHostOutOfMemory` active, 121 conteneurs). Les plus gros :
   OpenSearch 2,4 Gio, `openclaw-gateway` 2,3 Gio, Nexus 2,2 Gio,
   `opensearch-security` 2,0 Gio, `wazuh-indexer` 1,7 Gio. C'est la même cause
   que les démarrages lents du 3/11 ([roadmap](roadmap.md)).

Le worker a fini de démarrer vers 18:42 UTC, et l'app est de nouveau `healthy`.
Le problème reviendra à chaque redémarrage tant que TrueNAS sature.

**Bloqué** : il faut libérer de la mémoire, donc arrêter des Apps peu utiles,
ce que seul le propriétaire peut décider. Allonger le `start_period` masquerait
le symptôme sans le corriger. Contrôle :

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://172.17.0.24:8091/health
ssh truenas sudo -n docker inspect -f '{{.State.Health.Status}}' fastapi-sample
```

## 5. Gmail : « Lecture impossible : Command failed »

**Constat** : échec à 8 h les 10/11 et 11/11, succès du 5/11 au 9/11.

**Non reproduit** le 11/11 entre 19:27 et 19:45, en six essais, tous terminés
avec le code 0 :

- même binaire (`gog` v0.33.0) et même environnement minimal que le script
  (`env -i`) ;
- fenêtres de 1, 2 et 3 jours ;
- le script complet lancé dans le Gateway.

Le jeton se rafraîchit (trousseau réécrit à 19:27) et le compte `openclaw` est
valide (`gog auth list` : gmail, calendar). La transcription du run de 8 h
montre que le script sort en 37 s avec le code 0 : c'est `gog` qui échoue. Le
script ne gardait que la première ligne de l'erreur Node, la ligne de commande,
et perdait donc la cause écrite par `gog` sur stderr.

**Correctif (ce dépôt)** : le briefing affiche la dernière ligne de stderr de
`gog`, compte masqué, ou `délai dépassé`. Au prochain échec, la cause réelle
apparaîtra dans le briefing. Hypothèses à confirmer alors : réseau ou DNS à 8 h
pendant la saturation E/S de TrueNAS (section 4), ou erreur 5xx de Google.

Vérifier sans attendre 8 h (après `just truenas-apply-heartbeat`) :

```bash
ssh truenas "sudo -n docker exec openclaw-gateway node /home/node/.openclaw/workspace/scripts/morning-briefing.mjs" | sed -n '/^## EMAILS/,+1p'
```

Résultat attendu : `<<<DÉBUT DONNÉES NON FIABLES>>>` ou `Rien depuis 24 h.`
