# Diligences et passages de zone

Les sorties physiques du monde publié mènent directement à la carte voisine. La carte régionale reste consultable depuis le menu, mais ne s’ouvre pas lors des passages ou des voyages.

Trois relais permettent de monter : Rosée, Brume et la forêt des Éveillés. Les arrêts de la Lisière, des Prairies et de la Tour des Cimes servent uniquement à descendre. Chaque ligne possède son propre sens : une arrivée n’implique jamais un trajet retour.

Approchez-vous du relais, puis choisissez une destination. Tous les compagnons vivants doivent être présents. Une poursuite ennemie empêche le départ. Le voyage montre un cheval attelé et une diligence animés ; sa progression est sauvegardée et l’arrivée replace directement le groupe sur la carte du lieu. L’ancienne animation de marche reste disponible pour les trajets à pied des catalogues historiques.

Dans le Builder, « Relais et arrêts » règle la carte, les coordonnées et le droit d’embarquement. L’édition synchronise le lieu physique correspondant. « Lignes de diligence » définit départ, arrivée et durée réelle en secondes ; le validateur refuse un départ depuis un arrêt de dépose.

Vérifications : `python -m pytest test/test_coaches.py`, puis `python -m scripts.verify_coaches_browser`. Le second scénario utilise une base SQLite temporaire, embarque vers la Lisière, recharge pendant le voyage et vérifie l’arrivée, la sauvegarde, l’absence d’ouverture de l’atlas et la conservation du marcheur.

Le contrôle natif `node scripts/verify_desktop_coaches.cjs --packaged` accepte `RPG_DESKTOP_EXECUTABLE`. Il marche jusqu’au relais, voyage avec le moteur Pyodide hors ligne puis ferme et rouvre le client sur un profil temporaire.
