# daily-tech-news-digest — message déclaratif (sans secrets)

Produis le digest tech quotidien du skill `tech-news-digest`, installé dans
`skills/tech-news-digest/`. Le skill n'est pas un outil : ne l'appelle pas
par son nom, et ne relis ni `SKILL.md` ni `references/digest-prompt.md` ;
les règles utiles du template sont reprises ci-dessous.

- MODE = daily
- TIME_WINDOW = past 1-2 days
- FRESHNESS = pd
- RSS_HOURS = 48
- ITEMS_PER_SECTION = 5
- ENRICH = true
- LANGUAGE = French
- SOURCES = flux des catégories FreshRSS (LLM, AI Agent, Crypto, Frontier Tech), GitHub, GitHub Trending, Reddit, Web (sans Twitter : l'API X répond 402)

## 1. Collecte : un seul appel `exec`

Appelle l'outil `exec` une seule fois, avec `yieldMs` = 240000 et
`timeout` = 240, et exactement cette commande :

```sh
cd /home/node/.openclaw/workspace && date +%F && { python3 scripts/freshrss-sources.py || true; } > /tmp/td-pipeline.log 2>&1 && python3 skills/tech-news-digest/scripts/run-pipeline.py --defaults skills/tech-news-digest/config/defaults --config skills/tech-news-digest/workspace/config --hours 48 --freshness pd --archive-dir archive/tech-news-digest --output /tmp/td-merged.json --force --enrich --skip twitter >> /tmp/td-pipeline.log 2>&1 && python3 skills/tech-news-digest/scripts/summarize-merged.py --input /tmp/td-merged.json --top 5 > /tmp/td-summary.txt && grep -F 'pts) [' /tmp/td-summary.txt | cut -d']' -f3- | sed 's/^ /- [/; s/$/]/' > archive/tech-news-digest/daily-$(date +%F).md && cat /tmp/td-summary.txt || { tail -n 20 /tmp/td-pipeline.log; exit 1; }
```

La commande reprend d'abord la liste des flux depuis FreshRSS (en cas
d'échec, la dernière liste reste valable), puis archive les titres retenus :
le pipeline du lendemain pénalise ceux qui ont déjà été publiés.

N'invente ni script ni option et n'écris pas de Python. Si la commande
échoue, réponds `AUTOMATION_FAILED` suivi des dernières lignes affichées,
sans autre tentative.

Une sortie valide de l'outil `exec` commence par la date du jour puis
`=== Merged Data Summary ===` et `Total articles: <n>`. Sans cette sortie
(outil non appelé, sortie vide ou autre), réponds seulement
`AUTOMATION_FAILED` : n'écris jamais de digest de mémoire.

## 2. Rédaction

Chaque article de la sortie a une ligne `Source:` et une ligne `Link:`.
Recopie chaque lien tel quel depuis la ligne `Link:` de son article, sans le
modifier ni le compléter ; omets un article sans ligne `Link:`. N'écris
aucune URL absente de la sortie.

À partir de cette seule sortie, rédige le digest en français :

- titre `🚀 Tech Digest - <date affichée en première ligne>` ;
- une section par topic, dans l'ordre de la sortie, titrée exactement
  `🧠 LLM / Large Models` (`llm`), `🤖 AI Agent` (`ai-agent`),
  `💰 Cryptocurrency` (`crypto`) ou `🔬 Frontier Tech` (`frontier-tech`),
  avec au plus 5 articles de score ≥ 3, chacun au format
  `• 🔥<score> | <résumé en une phrase> — [<source>](<lien>)` ; une section
  sans article retenu est omise ;
- pied : `📊 <total> articles fusionnés | tech-news-digest v3.16.0`, où
  `<total>` est le nombre de la ligne `Total articles:` de la sortie.

Sélection (27/11 : deux articles à 🔥0 de Grey Matter et Concetto Labs, MIT
Technology Review deux fois sur les mains bioniques, classées en LLM) :

- jamais d'article sous 🔥3, ni de contenu marketing : page d'un éditeur ou
  d'une agence qui vend son service ;
- un sujet n'apparaît qu'une fois : garde l'article d'origine, pas la revue
  de presse qui le relaie (« The Download » de MIT Technology Review) ;
- classe chaque article selon son sujet, pas selon son flux : robotique,
  biotech et matériel vont dans `🔬 Frontier Tech`.

Pas d'introduction, de tableau, de section supplémentaire ni de liste
d'articles hors des sections.

## 3. Livraison

Ta réponse finale est le digest lui-même : le planificateur le livre sur
Telegram. N'envoie rien toi-même et ne modifie ni les destinataires, ni les
clés, ni la livraison du job. N'invente pas de réussite : sans sortie valide
de l'étape 1, réponds `AUTOMATION_FAILED`. Respecte le budget, les cooldowns
et la politique de retry du job ; ne relance pas automatiquement en cas de 429.
