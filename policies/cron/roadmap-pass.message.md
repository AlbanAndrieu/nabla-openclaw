# <repo>-roadmap-pass — message déclaratif (sans secrets)

Tâche planifiée horaire du propriétaire (24 min au plus) : une passe sur la
roadmap de `AlbanAndrieu/<repo>`.

Première action, obligatoire : lis `skills/nabla-roadmap-pass/SKILL.md` avec
ton outil `read`. Deuxième action, obligatoire : appelle ton outil `exec` avec
`test -d <repo>/.git || git clone --filter=blob:none https://github.com/AlbanAndrieu/<repo>.git <repo>`.
Ton espace de travail est vide à chaque exécution : avant ce clone, `<repo>/`
et `docs/` n'existent pas, et un `FileNotFoundError` veut dire « pas encore
cloné », jamais « dépôt absent ». Exécute ensuite les étapes 0 à 7 de la skill
avec tes outils, pour le dépôt `<repo>`.

Tu es un agent autonome et ce tour est le seul : personne ne te relancera.

- Avant chaque appel d'outil, dis en une ligne ce que tu en attends ; après,
  relis sa sortie avant de choisir l'appel suivant.
- Chaque `PASS`, SHA, PR, chiffre ou état du compte rendu recopie une sortie
  d'outil de ce tour. Une étape que tu n'as pas exécutée est `NOT_RUN`, jamais
  `PASS` ; un compte rendu écrit sans appel d'outil est une exécution ratée
  (27/11 : clone « PASS » en 8 s sans un seul `exec`).
- Une commande longue se lance avec `exec` et `yieldMs: 120000`. Si `exec`
  rend quand même un identifiant de session, elle continue : attends-la avant
  de poursuivre (porte hors ligne : commande d'attente de l'étape 1 de la
  skill ; sinon l'outil `process`, `action: "poll"`, `timeout: 30000`, à
  répéter).
- Ne rends la main qu'une fois l'étape 7 atteinte : jamais sur « je
  poursuivrai » ou « en cours », car aucune suite ne viendra.

**Porte rouge = le travail de la passe.** Si la porte hors ligne finit sur un
`gate_exit` différent de 0, ou si la CI de `master` est rouge, la passe
consiste à la réparer avant tout item : lis la première erreur de
`../gate.log`, crée `openclaw/roadmap-pass-<AAAAMMJJ>`, fais le plus petit
changement qui la corrige, relance la porte jusqu'à `gate_exit=0`, puis
commit, push et PR Draft. Tant que la porte est rouge : jamais `✅`, jamais
`NO_REPLY`, jamais « aucun item traitable » (28/11 : nabla-site-bababou a
conclu trois fois « aucun commit » sur `TS2304: Cannot find name 'PageProps'`).
Sans correction au bout de 15 min : `⚠️`, l'erreur exacte et ce que tu as
tenté.

« Aucun item traitable » n'est pas une conclusion : quand tous les items sont
`RUNTIME` ou `DÉCISION`, la part code de l'un d'eux (test de contrat, script
de réception, validation hors ligne) devient le commit de la passe.

Réponds exactement `NO_REPLY`, sans autre texte, quand la passe n'apporte rien
de nouveau : aucun commit, aucune PR ouverte ni poussée, aucun nouveau
blocage, aucun échec (porte, CI, push), même déjà signalé. Le briefing du matin compte ces
passes silencieuses. Une passe sans un seul appel d'outil n'a rien établi :
`NO_REPLY` aussi, jamais un compte rendu inventé (le heartbeat la signale).
Si la skill est introuvable ou qu'une étape bloque tout, commence par
`AUTOMATION_FAILED` et dis ce qui a échoué et ce que tu as tenté.

Ce message vaut demande explicite de commit, push et PR Draft **pour cette
seule exécution**, sur une branche `openclaw/roadmap-pass-*` ou
`openclaw/fix-pr-*` (correction d'une PR ouverte, PR Draft dont la base est la
branche de cette PR) uniquement ; jamais de push sur une autre branche, et
**jamais sur `master`** : un refus `GH013` veut dire que tu es resté sur
`master`, crée ta branche et pousse-la. Toutes
les autres règles de ton `AGENTS.md` restent applicables. Jamais de merge, de
`--force` ni de passage en Ready.

Ta réponse finale est livrée par le planificateur : c'est le compte rendu de
l'étape 7, questions restantes à la fin.
