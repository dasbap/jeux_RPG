# Vérification Oracle Always Free dans Brave

Contrôle du 13 novembre 2026, effectué dans la session Oracle ouverte par le
propriétaire. Le formulaire reste un brouillon : **aucun bouton Create n'a été
invoqué et aucune VM n'a été créée par l'assistant**.

## Observations dans la console

| Élément | Valeur vérifiée |
| --- | --- |
| Région courante | France Central (Paris), `eu-paris-1` |
| Région principale | France Central (Paris), libellé explicite « Home region » |
| Forme initiale | AMD `VM.Standard.E2.1.Micro`, 1 Go, Always Free-eligible |
| Forme préparée | ARM `VM.Standard.A1.Flex`, 2 OCPU et 12 Go, Always Free-eligible |
| Image préparée | Canonical Ubuntu 24.04 Minimal aarch64, publiée par Oracle, prix « Free » |
| Build de l'image | 2026.11.05-0 |
| Disque conservé | Taille standard indiquée 46,6 Go, personnalisation désactivée |
| Performance standard inspectée | Balanced, 10 VPU |
| Volumes supplémentaires | Aucun dans le formulaire |
| Chiffrement avec clé utilisateur | Désactivé ; clé gérée par Oracle |
| Quota régional Free Tier Volume | 200 Go |
| Usage de ce quota | 0 Go |
| Disponible dans ce quota | 200 Go |
| Usage A1 consulté dans AD-1 | 0 CPU, 0 Go de mémoire ; limites marquées Dynamic |

L'estimateur a affiché 1,85 €/mois pour le disque standard. Pendant l'inspection
des réglages personnalisés, 50 Go / 10 VPU affichaient 1,98 €/mois. La
personnalisation a ensuite été désactivée pour conserver le disque minimal
standard. Aucun de ces montants n'a été accepté par une création de ressource.

## Lecture de l'éligibilité

La [documentation Always Free Oracle](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
inclut A1 dans la région principale, avec une franchise mensuelle de
1 500 OCPU-heures et 9 000 Go-heures pour les comptes Always Free, ainsi que
200 Go de stockage boot/block combiné. Le brouillon et l'usage observé sont
compatibles avec ces plafonds.

L'encart d'estimation précise qu'il ne reflète pas toute la tarification par
paliers. Oracle décrit également la franchise de stockage dans son
[estimateur de coûts](https://docs.oracle.com/en-us/iaas/Content/Billing/Tasks/signingup_topic-Estimating_Costs.htm).
La lecture attendue est donc une couverture du calcul et du disque par
Always Free tant que les plafonds restent respectés. Ce contrôle d'éligibilité
ne constitue pas une facture vérifiée ni une validation du coût de futurs
services ajoutés au compte.

## État laissé et travail restant

Le récapitulatif du brouillon est ouvert dans Brave, sans création. Un second
onglet contient les limites et usages ; la capture du quota de stockage reste
hors Git dans `.data/oracle-test/oracle-free-storage-quota.png`.

Le réseau est encore à finaliser : nouveau VCN `jeux-rpg-vcn`, sous-réseau
`jeux-rpg-public` en brouillon et **IP publique indiquée No** dans le
récapitulatif. Il faut régler cet accès, conserver une clé SSH utilisable et
préparer un cloud-init pointant sur un commit réellement publié avant de
créer une VM destinée au moteur. La capacité A1 disponible chez Oracle n'a
pas été testée par un lancement.
