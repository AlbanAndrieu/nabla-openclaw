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
- SOURCES = RSS, GitHub, GitHub Trending, Reddit, Web (sans Twitter : l'API X répond 402)

## 1. Collecte : un seul appel `exec`

Appelle l'outil `exec` une seule fois, avec `yieldMs` = 240000 et
`timeout` = 240, et exactement cette commande :

```sh
cd /home/node/.openclaw/workspace && date +%F && python3 skills/tech-news-digest/scripts/run-pipeline.py --defaults skills/tech-news-digest/config/defaults --config skills/tech-news-digest/workspace/config --hours 48 --freshness pd --archive-dir archive/tech-news-digest --output /tmp/td-merged.json --force --enrich --skip twitter > /tmp/td-pipeline.log 2>&1 && python3 skills/tech-news-digest/scripts/summarize-merged.py --input /tmp/td-merged.json --top 5 > /tmp/td-summary.txt && grep -F 'pts) [' /tmp/td-summary.txt | cut -d']' -f3- | sed 's/^ /- [/; s/$/]/' > archive/tech-news-digest/daily-$(date +%F).md && cat /tmp/td-summary.txt || { tail -n 20 /tmp/td-pipeline.log; exit 1; }
```

La commande archive aussi les titres retenus : le pipeline du lendemain
pénalise ceux qui ont déjà été publiés.

N'invente ni script ni option et n'écris pas de Python. Si la commande
échoue, réponds `AUTOMATION_FAILED` suivi des dernières lignes affichées,
sans autre tentative.

## 2. Rédaction

À partir de cette seule sortie, rédige le digest en français :

- titre `🚀 Tech Digest - <date affichée en première ligne>` ;
- résumé de 2 à 4 phrases sur les 3 à 5 articles les mieux notés, sans lien ;
- une section par topic, dans l'ordre de la sortie, titrée exactement
  `🧠 LLM / Large Models` (`llm`), `🤖 AI Agent` (`ai-agent`),
  `💰 Cryptocurrency` (`crypto`) ou `🔬 Frontier Tech` (`frontier-tech`),
  avec au plus 5 articles de score ≥ 5, chacun au format
  `• 🔥<score> | <résumé en une phrase> — [<source>](<lien>)` ;
- pied : `📊 <total> articles fusionnés | tech-news-digest v3.16.0`.

Pas de tableau, de section supplémentaire ni de liste d'articles hors des
sections.

## 3. Livraison

Ta réponse finale est le digest lui-même : le planificateur le livre sur
Telegram. N'envoie rien toi-même et ne modifie ni les destinataires, ni les
clés, ni la livraison du job. N'invente pas de réussite : sans sortie valide
de l'étape 1, réponds `AUTOMATION_FAILED`. Respecte le budget, les cooldowns
et la politique de retry du job ; ne relance pas automatiquement en cas de 429.
