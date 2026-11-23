# <repo>-roadmap-pass — message déclaratif (sans secrets)

Tâche planifiée quotidienne du propriétaire : une passe sur la roadmap de
`AlbanAndrieu/<repo>`.

Première action, obligatoire : lis `skills/nabla-roadmap-pass/SKILL.md` avec
ton outil `read`, puis exécute ses étapes 0 à 7 avec tes outils, pour le dépôt `<repo>`.

`NO_REPLY` est interdit pour ce job : il y a toujours une roadmap à passer en
revue et un compte rendu à rendre, même si aucun item n'a pu être traité. Si la
skill est introuvable ou qu'une étape bloque tout, commence par
`AUTOMATION_FAILED` et dis ce qui a échoué et ce que tu as tenté.

Ce message vaut demande explicite de commit, push et PR Draft **pour cette
seule exécution**, sur une branche `openclaw/roadmap-pass-*` ou
`openclaw/fix-pr-*` (correction d'une PR ouverte, PR Draft dont la base est la
branche de cette PR) uniquement ; jamais de push sur une autre branche. Toutes
les autres règles de ton `AGENTS.md` restent applicables. Jamais de merge, de
`--force` ni de passage en Ready.

Ta réponse finale est livrée par le planificateur : c'est le compte rendu de
l'étape 7, questions restantes à la fin.
