# Générateur de documentation

Lancer depuis n'importe quel répertoire :

```powershell
python C:/save/perso/projet/jeuxRPG/__doc__/generate_docs.py
```

Le script utilise uniquement la bibliothèque standard Python 3.11+. Il produit un index, une arborescence et une page Markdown par fichier et dossier sélectionné. Les pages comportent des liens entre elles et vers les sources. Les symboles Python sont analysés sans importer ni exécuter le code. Les docstrings sont conservées dans leur langue d'origine.

## Liste blanche

Modifier `__doc__/docs.toml`, section `[documentation]`, pour ajouter ou retirer des motifs `include`. Tout fichier qui ne correspond à aucun motif reste hors de la documentation. Il n'y a pas de liste noire à entretenir lorsque de nouveaux outils, sauvegardes ou environnements sont ajoutés au dépôt.

- `scripts/*.py` autorise les fichiers Python directement dans `scripts`.
- `jeuxRPG/**/*.py` autorise les fichiers Python dans ce dossier et ses sous-dossiers.
- `desktop/package.json` autorise un fichier précis.
- Les parents des fichiers retenus apparaissent automatiquement dans l'arborescence.
- Les liens symboliques et la sortie du générateur ne sont pas sélectionnés. Les motifs absolus ou contenant `..` sont refusés.

Préférer des motifs limités aux dossiers de sources. Un motif très large comme `**/*` autorise volontairement tous les fichiers du projet, y compris les dépendances et données locales.

Les motifs sans correspondance sont signalés, sans empêcher la génération : une même configuration peut ainsi couvrir plusieurs variantes du projet.

## Options

```powershell
# Voir exactement ce qui sera documenté, sans écrire de fichier.
python __doc__/generate_docs.py --dry-run

# Remplacer la liste blanche pour cette exécution seulement.
python __doc__/generate_docs.py --include "jeuxRPG/**/*.py" --include "README.md"

# Changer la sortie, relative à la racine du projet.
python __doc__/generate_docs.py --output documentation-auto

# Documenter un autre projet avec ses propres règles.
python __doc__/generate_docs.py --root C:/autre-projet --config C:/autre-projet/documentation.toml
```

`--root` vaut par défaut la racine contenant ce script. Sans `--config`, le script cherche `<racine>/__doc__/docs.toml`. Si ce fichier n'existe pas, une liste blanche minimale documente les fichiers Python et Markdown à la racine, `pyproject.toml` et `requirements*.txt`. `--config` est relatif au répertoire courant ; les motifs et la sortie TOML sont relatifs à `--root`. `--output` et `--include` prennent priorité sur le TOML. Les motifs Windows utilisant `\` sont aussi acceptés.

Exemple de configuration pour un autre projet :

```toml
[documentation]
output = "documentation-auto"
include = ["src/**/*.py", "tests/**/*.py", "README.md", "pyproject.toml"]

[documentation.descriptions]
src = "Sources de l'application."
"src/config.py" = "Chargement et validation des paramètres."
```

Les descriptions peuvent cibler un nom ou un chemin relatif précis ; le chemin précis est prioritaire. Les descriptions standard servent de repli.

## Régénération

Le manifeste `.generated-pages.json` suit les pages produites. Quand la liste blanche change, les anciennes pages générées devenues inutiles sont retirées si leur contenu est inchangé. Une ancienne page modifiée manuellement est conservée et signalée. Les autres fichiers de la sortie restent en place. Les pages encore générées sont remplacées à chaque exécution : placer les guides manuels dans un fichier séparé, comme celui-ci.

La racine du projet et ses parents ne peuvent pas servir de dossier de sortie. Les chemins du manifeste qui sortiraient de la sortie sont refusés.
