---
name: nabla-yubikey-dev
description: Cloner, modifier, tester et publier en PR Draft le dépôt AlbanAndrieu/nabla-yubikey (procédures et tests hors ligne YubiKey/FIDO2/SSH) depuis la devbox. À lire avant toute tâche de code sur nabla-yubikey.
---

# nabla-yubikey — boucle de développement sur la devbox

Le dépôt décrit des procédures YubiKey/FIDO2/PIV/OpenPGP/SSH-sk et leurs tests
hors ligne. La devbox n'a **aucune** clé matérielle, ni `ykman`, ni `gpg`, ni
accès SSH ou NFS : seuls le code, la documentation, les fixtures et les tests
hors ligne sont dans son périmètre.

## 1. Préparer le clone (une fois par session)

```bash
test -d nabla-yubikey/.git || git clone --filter=blob:none https://github.com/AlbanAndrieu/nabla-yubikey.git nabla-yubikey
cd nabla-yubikey && git fetch origin master && git status --short --branch
```

Lire ensuite `AGENTS.md` dans le clone. Mode d'exécution :
`AGENT_EXECUTION_MODE=offline`.

## 2. Branche de travail

```bash
cd nabla-yubikey && git switch -c openclaw/<sujet-court> origin/master
```

## 3. Vérifications

```bash
cd nabla-yubikey && export AGENT_EXECUTION_MODE=offline
cd nabla-yubikey && just test
```

`just check` et toute recette `*-readonly` interrogent du matériel ou l'hôte :
`NOT_RUN` avec leur raison, jamais un `PASS`. Ne jamais les lancer.

## 4. Publier (uniquement sur demande explicite du propriétaire)

Même procédure que la skill `fastapi-sample-dev` (section 4), dans
`nabla-yubikey/`. Le corps de la PR liste les commandes de réception à lancer
sur la Workstation pour ce qui est resté `NOT_RUN`.

## Interdits propres à ce dépôt

- Écrire une procédure ou un script qui modifie une clé (PIN, PUK, slots,
  applets, reset) sans demande explicite, et toujours en le signalant.
- Ajouter une clé privée, un numéro de série, une sauvegarde chiffrée ou un
  identifiant personnel dans un fichier, un test ou un message.
