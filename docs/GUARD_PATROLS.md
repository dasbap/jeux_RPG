# Patrouilles de gardes : combat et repli collectif

Les gardes du monde vivant sont des soldats autonomes dans les cartes physiques
des villages. Ils attaquent les monstres considérés hostiles par le moteur,
avec vérification de la distance et de la ligne de vue. Une créature neutre non
provoquée est ignorée. Les gardes conservent leur territoire : ils ne traversent
pas les passages pour poursuivre un ennemi dans un camp hostile.

## Comportement

- Une patrouille contient **trois gardes**, chacun avec **45 PV** et un sprite.
- Ils détectent les ennemis à **six cases** et les frappent au corps à corps.
  Les ennemis peuvent les prendre pour cible et leur infliger dégâts ou altérations.
- Dès qu'un membre atteint **30 % de ses PV ou moins**, toute la patrouille cesse
  l'offensive et rejoint son point de ralliement. Les gardes évitent de distancer
  le blessé et se regroupent sur le chemin du retour.
- Une fois regroupés, ils récupèrent **3 PV par seconde réelle** à vitesse normale,
  uniquement si aucun ennemi détecté n'est encore à proximité. Le service reprend
  quand **tous les membres atteignent au moins 80 % de leurs PV**.
- Si toute la patrouille est hors combat, un remplacement arrive au village après
  **180 secondes de jeu**, soit une minute réelle avec l'horloge habituelle.

Leurs barres de vie et leur activité (combat, repli, soins, hors combat) apparaissent
sur la carte et dans **Carte → Vie du monde**. Les soldats ne sont pas des unités
contrôlables par le joueur ; leurs PV ne sont pas ajoutés à ceux du personnage.

Les constantes initiales se trouvent dans `guard_patrols.py`. La patrouille utilise
les mêmes déplacements, couvertures, résistances et règles de dégâts que le moteur
tactique. Le déplacement des gardes reste à sa vitesse normale si l'on accélère
le calendrier stratégique avec `--world-speed`.

## Partage, sauvegarde et récompenses

Les PV, positions et décisions appartiennent au **royaume**, dans le calendrier
`world_life:<royaume>`. Les ouvrir dans une autre fenêtre ne crée pas trois nouveaux
soldats. Les royaumes sont séparés. Le contexte utilisé par une étape de combat
est retiré de l'aventure avant sa sauvegarde pour éviter les copies persistantes.

Les aventures et leurs monstres restent propres aux personnages/équipes. Une
patrouille intervient dans **une aventure à la fois** ; une prise en charge
temporaire empêche deux sessions de la faire attaquer deux fois au même instant.
Les autres joueurs du royaume voient ses mêmes PV et positions. Quand une carte
n'est plus observée, les coups ne sont pas rejoués hors ligne : le retour et la
récupération sont résolus de façon bornée après le délai prévu.

La progression de l'aventure et les modifications de la patrouille sont capturées
ensemble dans le mécanisme de sauvegarde existant avec fencing. L'intégration D1
est vérifiée par une base simulée ; les essais de cette fonctionnalité sont locaux.

Un ennemi éliminé uniquement par les gardes ne donne ni XP, ni butin, ni progression
de quête au joueur. Si le joueur ou ses invocations ont participé, la récompense
habituelle du groupe est conservée. Les dégâts reçus uniquement par les gardes ne
font pas échouer les conditions de combat sans dégâts du personnage.

## Périmètre

Le combat concerne les monstres tactiques présents sur la carte du village, y
compris ceux qui y poursuivent un joueur. Les sièges du calendrier gardent leur
résolution stratégique ; leurs marqueurs d'assaillants ne constituent pas encore
une armée tactique partagée. Cette version ne transforme pas les monstres des
aventures personnelles en un ensemble de monstres commun à tous les joueurs.

La charge de 40 joueurs simultanés reste à valider. La simulation des gardes reste
bornée par étape et ne rattrape pas une longue interruption en infligeant des
centaines de coups à la reprise.

## Vérifications locales

```powershell
.\.venv-reprise\Scripts\python.exe -m pytest test/test_guard_patrols.py -q
.\.venv-reprise\Scripts\python.exe scripts/verify_living_world_browser.py --guards
```

Le scénario navigateur utilise une base temporaire et bloque les connexions
externes. Il vérifie les attaques, les barres de vie, le repli collectif, les
soins puis la reprise de la patrouille.

Les tests couvrent l'attaque automatique, les cibles neutres et les obstacles,
la riposte des monstres, le déclenchement du repli après un coup, la cohésion,
les soins et leur seuil de reprise, les récompenses avec ou sans participation,
le partage entre sessions, l'isolation des royaumes, la sauvegarde commune avec
l'aventure et la récupération hors ligne sans doublon.
