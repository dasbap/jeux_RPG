# Cloudflare D1 : dossier fournisseur — 6 novembre 2026

La production utilise Cloudflare D1 depuis le 6 novembre 2026 ; les preuves
sont dans [D1_PRODUCTION.md](D1_PRODUCTION.md). Le Worker privé, l’adaptateur
Python et les outils d’export/import sont intégrés. La branche de conception
a été archivée ; elle n’est pas une étape restante de déploiement.

Les références contractuelles et chiffres ci-dessous ont été consultés le
6 novembre 2026. Ils restent datés : vérifier les textes applicables et les
quotas effectifs dans le compte avant une nouvelle décision d’exploitation.

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
des textes applicables et la preuve d’acceptation du compte. La bascule
technique terminée ne remplace pas cette vérification documentaire.
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

## Validation technique et suivi

La recette D1 réelle, le transfert des données et la restauration ont été
effectués ; voir [la préproduction](D1_PREPRODUCTION.md) et
[la bascule de production](D1_PRODUCTION.md). La production est configurée en UE.
Ces contrôles ne prouvent ni l’acceptation contractuelle du compte, ni tous les
traitements des autres fournisseurs, ni la capacité à 40 joueurs.

Suivre la consommation et les quotas réels de Workers/D1, Redis et Vercel,
et conserver les preuves contractuelles applicables. Turso reste verrouillé ;
une récupération doit préserver les écritures D1 actuelles.
