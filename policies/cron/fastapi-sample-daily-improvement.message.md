# fastapi-sample-daily-improvement — message déclaratif (sans secrets)

Tâche planifiée quotidienne du propriétaire : vérifier le comportement de
`AlbanAndrieu/fastapi-sample`, puis proposer **une** amélioration en PR Draft.
Ce message vaut demande explicite de commit, push et PR Draft **pour cette
seule exécution**, dans les limites ci-dessous ; toutes les autres règles de
ton `AGENTS.md` restent applicables.

## 1. Pas de doublon

Suis la skill `fastapi-sample-dev` (section 1) pour préparer le clone, puis :

```bash
cd fastapi-sample && gh pr list --state open --json headRefName,url --jq '.[] | select(.headRefName | startswith("openclaw/daily-")) | .url'
```

Si une URL sort, une proposition précédente attend la revue du propriétaire :
ne crée rien, réponds `EN ATTENTE` suivi de l'URL, et arrête-toi.

## 2. Vérifier le comportement

Depuis `origin/master`, dans cet ordre, chaque commande avec `PASS`, `FAIL`
ou `NOT_RUN` :

```bash
cd fastapi-sample && uv sync --frozen
cd fastapi-sample && just test-local-first
cd fastapi-sample && just lint && just format-check
cd fastapi-sample && gh run list --branch master --limit 5 --json name,conclusion,headSha
```

## 3. Choisir une seule amélioration

Par ordre de priorité : un test ou une gate en échec sur `master` ; un
comportement d'API non couvert par un test ; un avertissement (dépréciation,
lint) ; une petite clarification de doc liée au code. Le diff reste petit
(≤ 5 fichiers, ≤ 150 lignes) et sans nouvelle dépendance. Interdits :
`.github/workflows/`, les contrôles de sécurité, les fichiers de verrouillage.
Si rien d'utile et sûr n'apparaît, ne crée rien et réponds `RIEN À PROPOSER`
avec le bilan de l'étape 2.

## 4. Publier en Draft

Branche `openclaw/daily-<AAAAMMJJ>-<sujet-court>` depuis `origin/master`.
Relance le test le plus proche du changement, puis applique la section 4 de la
skill `fastapi-sample-dev` (sans `[skip ci]`). Un test qui échoue après ton
changement : abandonne la branche sans pousser et réponds `ÉCHEC`.

## 5. Compte rendu

Ta réponse finale est livrée par le planificateur : n'envoie rien toi-même.
En français, au plus 10 lignes : état des vérifications, amélioration choisie
et pourquoi, URL de la PR Draft (ou `EN ATTENTE`, `RIEN À PROPOSER`,
`ÉCHEC`). Jamais de merge ni de passage en Ready ; n'annonce aucune réussite
non vérifiée.
