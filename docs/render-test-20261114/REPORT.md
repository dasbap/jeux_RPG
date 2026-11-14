# Recette Render Free du 14 novembre 2026

Service : https://jeux-rpg-render-test.onrender.com, Free à Francfort,
0,1 CPU et 512 Mo, moteur mono-instance et D1 fictif distant sans Redis.
La production Vercel n'est pas modifiée. Les deux jetons du service sont dans
un **Secret File** JSON monté au runtime, hors image Docker et hors dépôt.

## Résultats

| Joueurs distincts | Durée demandée | Réponses d'état | Médiane | p95 | Erreurs |
| --- | --- | --- | --- | --- | --- |
| 1 | 10 s | 10 | 37 ms | 53 ms | 0 |
| 10 | 15 s | 141 | 1 000 ms | 1 389 ms | 0 |
| 40 | 10 s | 128 | 4 315 ms | 5 611 ms | 0 |

Les 40 connexions WebSocket étaient authentifiées simultanément avec des
comptes et personnages différents. Chaque client demandait son état au plus
une fois par seconde ; les requêtes lentes ont prolongé la fin du dernier essai
à 15,14 secondes. Aucun combat actif n'a été provoqué par la sonde.
Les trois essais terminent avec `/ready` à 200.

Le parcours Chromium réel a confirmé connexion au compte, sélection du
personnage, aventure affichée et WebSocket, sans erreur JavaScript ni réponse
API 5xx. Le compte et son personnage avaient été créés via l'interface publique.

Une lecture indépendante de D1 a confirmé les 40 comptes de charge, leurs
40 personnages et leurs 40 aventures sauvegardées. Après un redémarrage réel
depuis Render, la génération du moteur a augmenté ; les 41 comptes,
41 personnages et 41 aventures, avec le compte navigateur, étaient présents.
Une nouvelle connexion navigateur a repris l'aventure après ce redémarrage.
La reconnexion d'une même fenêtre conservée ouverte pendant l'arrêt n'est pas
couverte par cette vérification.

## Conclusion et limites

Render Free permet de jouer et de tester la persistance, mais les latences
mesurées à 40 joueurs sont incompatibles avec l'objectif de combats rapides,
même sous cette charge légère. Ce court essai ne valide ni une capacité de
production à 40 joueurs, ni des combats simultanés, ni une stabilité prolongée.

Les graphiques CPU/RAM sont réservés aux instances payantes dans l'interface
Render consultée ; aucune marge CPU ou mémoire n'est donc revendiquée.
Les octets des rapports sont des tailles applicatives reçues et ne mesurent pas
la consommation réseau facturée après compression. Les comptes restent fictifs
dans le D1 isolé ; leurs mots de passe et jetons restent dans les fichiers locaux
ignorés, absents de ces rapports.

Les validations de code et la construction Docker ont réussi dans GitHub Actions.
La [sauvegarde indépendante chiffrée](https://github.com/dasbap/jeux_RPG/actions/runs/43533709553)
a exporté les 41 comptes et aventures. Le contrôle a restauré SQLite et rouvert
le moteur sans modifier D1 ; l'artifact `age` téléchargé a une somme de contrôle
conforme. Les résultats sont dans `backup-verification.json`. Aucun export en
clair n'est publié en artifact. Le déclenchement quotidien attend la
présence du workflow sur la branche par défaut ; aucune fusion n'est effectuée.
