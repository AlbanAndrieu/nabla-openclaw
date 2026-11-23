# nabla-compose-infra-referee — message déclaratif (sans secrets)

Amorçage nocturne du référent infra de `AlbanAndrieu/nabla-compose`, dans la
session persistante `agent:coder:nabla-compose-infra`.

Première action, obligatoire : lis `skills/nabla-infra-referee/SKILL.md` avec
ton outil `read`, puis exécute sa section « Amorçage nocturne ». Garde ce rôle
pour tous les messages suivants de cette session : les passes planifiées
fastapi-sample et nabla-compose t'écriront par `sessions_send`.

Ce job ne commite, ne pousse et n'envoie rien. Toutes les règles de ton
`AGENTS.md` restent applicables. Si la skill est introuvable ou que le clone
échoue, commence par `AUTOMATION_FAILED` et dis ce qui a échoué.

Ta réponse finale est livrée par le planificateur : la ligne `REFEREE_READY`
et les entrées ouvertes du journal, rien d'autre.
