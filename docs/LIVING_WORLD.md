# Monde vivant : prototype local

Le moteur fait évoluer un état partagé par royaume : villes, réserves, gardes,
patrouilles, groupes de monstres et caravane. Le relief, les villages, les chemins
et les marchandises viennent du catalogue Builder chargé par le jeu.

Cette fonctionnalité est désactivée par défaut. Aucun déploiement ni changement
des services Vercel, Render ou Cloudflare n'est nécessaire pour l'essayer.

Elle est désormais **activée dans le moteur solo embarqué** : le build Windows
local inclut le monde vivant à vitesse normale et sa sauvegarde dans la partie
solo. Le mode multijoueur continue d'utiliser la configuration du serveur ; il
n'est pas activé par ce changement. Lancer `dist/client/Jeux-RPG.exe`, choisir
le mode solo puis consulter **Carte → Vie du monde**.

## Lancer une partie locale

Depuis la racine du dépôt, avec les dépendances Python déjà installées :

```powershell
.\.venv-reprise\Scripts\python.exe -m scripts.run_living_world --profile demo-v1 --world-speed 60
```

Ouvrir **http://127.0.0.1:8085**. Créer un compte local, choisir un personnage et
commencer une aventure. La rubrique **Carte → Vie du monde** affiche les villes,
leurs réserves, les nouvelles et la caravane. Les habitants et patrouilles proches
apparaissent aussi sur la carte physique, dans les cases découvertes.

Le profil utilise uniquement `.data/living-world/demo-v1/world.sqlite3` et ses
journaux. Le lanceur ne charge pas `.env`, retire la configuration héritée des
connecteurs distants et utilise une présence en mémoire. Il écoute exclusivement
sur la boucle locale. `Ctrl+C` arrête le serveur ; relancer le même profil reprend
le monde avec le temps écoulé depuis son arrêt.

`--world-speed 60` accélère seulement le monde vivant. Le déplacement et le combat
du personnage conservent leur vitesse habituelle. Pour jouer à vitesse normale,
utiliser un **autre profil**, par exemple `--profile normal-v1 --world-speed 1`.
La vitesse fait partie de l'identité de la sauvegarde : changer sa valeur sur un
profil existant demande une migration explicite. Le moteur refuse les catalogues
incompatibles au lieu d'effacer le monde. Une nouvelle démonstration peut utiliser
un autre nom de profil, sans supprimer les anciennes données.

## Ce qui évolue automatiquement

- Deux habitants par village alternent trajet, travail, retour et repos. Pendant
  un siège, ils se mettent à l'abri ; les gardes présents défendent la ville.
- Les patrouilles de gardes et groupes de monstres changent de carte par les
  connexions du monde. Leur déplacement détaillé suit un chemin praticable.
  Les gardes humains restent dans les villages ; les groupes de monstres restent
  hors des villages. Les patrouilles déjà sauvegardées dans un territoire
  incompatible sont replacées dans leur zone d'origine, sans réinitialiser les
  réserves, événements ou compteurs du monde.
- Les villes produisent des ressources et des biens, entretiennent leurs gardes
  et reconstruisent leurs bâtiments après une attaque, en consommant des réserves.
- Une attaque est annoncée, devient un siège puis est résolue selon la force des
  assaillants, les gardes, les défenses et l'aide des joueurs. Les dégâts, pertes
  et réserves restent sauvegardés ; une ville endommagée renchérit les offres.
- La caravane séjourne dans un village puis suit un trajet existant vers un autre.
  Elle attend la fin d'un siège avant d'entrer. Son stock est fini et commun aux
  joueurs du royaume ; ses réapprovisionnements consomment les biens d'une ville
  et l'or du marchand.

Les joueurs présents en ville peuvent **ravitailler**, **reconstruire** ou
**renforcer la défense** pour 10 or. L'achat à la caravane exige sa présence et,
sur une carte physique, une distance maximale de deux cases. Le serveur vérifie
le stock, l'or et le prix affiché. Une requête répétée avec le même identifiant
n'achète pas et ne débite pas une deuxième fois.

À vitesse normale, une seconde réelle correspond actuellement à trois secondes
de jeu. Les délais suivants sont exprimés en **secondes de jeu** :

| Événement | Délai | Équivalent réel à vitesse 1 |
|---|---:|---:|
| Production, reconstruction, déplacement entre cartes des patrouilles | 900 | 5 min |
| Tentative d'attaque, par village | 7 200 | 40 min |
| Avertissement avant siège | 300 | 100 s |
| Siège | 180 | 60 s |
| Séjour de la caravane | 28 800 | 2 h 40 |
| Cycle des habitants | 3 600 | 20 min |

La première attaque est systématique pour permettre une recette reproductible.
Les suivantes ont une probabilité déterministe de 60 %. Les réglages sont dans
`living_world_catalog.DEFAULT_RULES` ; leur équilibre reste à ajuster en jeu.

## Temps, coût et sauvegarde

La simulation stratégique utilise une file d'échéances. Une zone vide n'exécute
pas de boucle de déplacement des PNJ. Pour la carte consultée par un joueur, les
positions et activités sont calculées à partir du calendrier, à une résolution
d'une seconde réelle, sans écrire les positions à chaque rafraîchissement.
Le moteur tactique existant garde sa boucle rapide.

Après un arrêt, le moteur traite **les mêmes événements dans le même ordre** que
s'il était resté allumé : identifiants stables, tirages dérivés de la graine, du
royaume et de l'événement, sans dépendance à un générateur aléatoire global.
Chaque passage traite au maximum 128 événements par royaume. Un retard important
est repris sur plusieurs passages ; l'interface signale le rattrapage et les
transactions de commerce ou d'aide attendent sa fin. Le curseur ne saute jamais
des événements non traités. L'historique conservé est limité à 40 nouvelles.

L'état est stocké dans `meta`, sous `world_life:<royaume>`. Le calendrier et ses
conséquences sont enregistrés dans la même transaction SQLite. Les interactions
ajoutent dans cette transaction l'inventaire, l'or, la révision et le reçu
d'idempotence. Un échec provoque un retour arrière de l'ensemble.

Le calendrier rejoint le mécanisme existant de sauvegarde D1 avec fencing ; l'or
et le monde sont capturés ensemble, y compris pour une simple contribution à une
ville. Ce raccordement est vérifié avec un **D1 simulé en mémoire**, sans appeler
Cloudflare. Aucun schéma distant n'est modifié. Les garanties existantes contre
les moteurs concurrents restent nécessaires : la simulation n'ajoute pas un
deuxième moteur autoritaire. Une écriture encore uniquement en RAM peut être
perdue si le processus s'arrête avant sa sauvegarde distante.

L'activation ultérieure se fera explicitement avec `RPG_LIVING_WORLD=1`
(`RPG_WORLD_SPEED=1` par défaut et `RPG_WORLD_SEED` optionnelle pour le runtime
mono-instance). Cette activation en ligne ne fait pas partie de cette recette.

## Vérifications locales

```powershell
.\.venv-reprise\Scripts\python.exe -m pytest test/test_living_world.py test/test_living_world_service.py -q
node scripts/verify_living_world.cjs
.\.venv-reprise\Scripts\python.exe -m scripts.verify_living_world_browser
```

Les tests Python bloquent les connexions réseau. Ils couvrent le rattrapage
déterministe, 30 jours de calendrier, les reprises de sauvegarde, les budgets,
les attaques, la reconstruction, la caravane, les royaumes isolés, la portée des
achats, les stocks partagés, les reçus et l'atomicité des sauvegardes.

Le test navigateur utilise les installations locales de JSDOM
(`.ui-test/node_modules/jsdom`) et Playwright
(`.data/browser-tools/node_modules/playwright`, navigateurs dans
`.data/browser-binaries`). Il crée une base temporaire et un compte fictif,
effectue une vraie connexion, un achat et une aide à la défense, puis vérifie
l'alerte, le siège et sa résolution. Les requêtes hors de son serveur local sont
bloquées ; aucun secret du projet n'est utilisé. Capture locale :
`.data/living-world-local.png`. Les dépendances ne sont pas téléchargées par ces
scripts.

Recette effectuée le 14 novembre 2026 : **181 tests Python réussis**, un test
nécessitant un vrai Redis ignoré, **18 tests JavaScript réussis** (navigation et
monde vivant), et parcours navigateur complet réussi. Les connexions externes et
la résolution DNS externe étaient bloquées pendant la suite Python de
non-régression. Ruff et la vérification des espaces du diff passent également.
Ces résultats ne constituent pas un essai de charge à 40 joueurs.

## Limites de cette version

Les gardes disposent maintenant d'un [combat autonome et d'un repli collectif](GUARD_PATROLS.md)
contre les monstres tactiques proches. Les habitants, groupes de monstres ambiants
et assaillants stratégiques affichés restent des acteurs de décor. Les sièges sont
résolus au niveau stratégique, avec contribution des joueurs via la défense.
La vie des PNJ ne remplace pas les quêtes ni les combats existants. Les vitesses
et fréquences sont des valeurs initiales, et **40 joueurs simultanés ne sont pas
validés** par ces essais locaux. La mise en veille, le réveil de l'hébergement et
les sauvegardes indépendantes relèvent du chantier de déploiement séparé.
