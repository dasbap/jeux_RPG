# Cloudflare D1 : dossier fournisseur — 6 novembre 2026

La branche `migration/cloudflare-d1-design` confirme que Cloudflare D1 est la
destination préparée pour quitter Turso. Elle fournit un Worker privé, un client
Python et un export/import, désactivés par défaut. La production n'a pas été
basculée lors de cette reprise.

## Documents publics

- [Self-Serve Subscription Agreement](https://www.cloudflare.com/terms/),
  sections 2.6 et 6.1 : les conditions couvrent les services gratuits et incorporent
  le DPA par référence lorsque les contenus incluent les données personnelles visées.
- [Data Processing Addendum](https://www.cloudflare.com/cloudflare-customer-dpa/),
  version 6.4 applicable depuis le 3 avril 2026 : responsabilités, sous-traitance,
  sécurité, transferts et annexes. Le texte vise notamment les contrats Self-Serve.
- [Sous-traitants](https://www.cloudflare.com/gdpr/subprocessors/).
- [Localisation D1](https://developers.cloudflare.com/d1/configuration/data-location/) :
  configurer la juridiction UE lors de la création de la base.

Ces textes publics permettent de constituer le dossier sans acheter un contrat
Enterprise. Cette lecture des clauses ne prouve ni l'acceptation dans le compte
du propriétaire ni la conformité de l'ensemble du jeu. Conserver une copie datée
des textes applicables et la preuve d'acceptation du compte avant la bascule.
La juridiction de la base ne suffit pas à déterminer tous les traitements
effectués par Workers, Vercel et le fournisseur Redis.

## Gratuité et limites

La [tarification D1](https://developers.cloudflare.com/d1/platform/pricing/)
comprend 5 millions de lignes lues par jour, 100 000 lignes écrites par jour et
5 Go de stockage total sur Workers Free. La
[limite par base gratuite](https://developers.cloudflare.com/d1/platform/limits/)
est de 500 Mo. Les requêtes cessent de fonctionner si les quotas gratuits sont
épuisés ; ces chiffres ne garantissent pas que le jeu restera dans les quotas.
Les requêtes Worker ont également leurs propres limites.

## Validation restante

Créer une base de recette avec juridiction UE, appliquer le schéma et les triggers
de fence, importer une sauvegarde privée, comparer les données et tester le
Worker sur D1 réel. Vérifier les comptes, sessions, progression, sauvegardes,
reprise après panne et concurrence entre moteurs. La sauvegarde finale et le gel
des écritures précèdent toute bascule ; conserver Turso pour le retour arrière.

Les tests locaux utilisent SQLite et des transports simulés. Ils ne valident pas
les accès Cloudflare, les quotas effectifs ou la région du compte.
