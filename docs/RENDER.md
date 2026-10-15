# Évaluation de Render — 15 octobre 2026

## Décision retenue

Maintien sur Vercel et sur les offres gratuites uniquement. Aucune migration Render et aucune souscription payante ne sont prévues. L’évaluation ci-dessous est conservée comme référence technique, sans action de déploiement.

## Évaluation technique initiale

Render est un candidat pertinent pour ce backend FastAPI avec moteur en RAM et WebSocket, sous réserve d’une adaptation et d’un test de charge sur l’instance cible. Commencer par une instance de préproduction ; ne pas déplacer directement le trafic public.

Starter : 7 USD/mois pour 512 Mo de RAM et une fraction de CPU au tarif consulté. Le coût total inclut éventuellement Turso, Redis, trafic sortant et taxes. Ce montant n’est pas un devis et ne garantit pas une capacité de 40 joueurs.

Free : adapté aux essais ponctuels. Veille après 15 minutes sans trafic entrant, redémarrage d’environ une minute, 750 heures gratuites partagées par workspace et par mois. Le trafic WebSocket entrant maintient désormais le service actif. Le disque est éphémère : conserver les sauvegardes distantes.

## Constats dans le dépôt

- Entrée ASGI : app:app ; dépendances déclarées dans pyproject.toml.
- Simulation SQLite en RAM, sauvegardes Turso et coordination Redis : conserver ces services dans une première migration.
- Les instances secondaires relaient les commandes via Redis ; une instance unique peut éviter ces relais interinstances, sans supprimer les autres usages Redis.
- Les WebSocket sont renouvelés par le code après 280 secondes. Render ne fixe pas cette limite : elle persisterait sans adaptation.
- Dans realtime.py, _socket_origin_allowed choisit HTTPS seulement avec VERCEL. Une installation Render HTTPS sans adaptation rejetterait l’origine WebSocket.
- L’authentification initiale du WebSocket et plusieurs comportements de sécurité sont conditionnés à VERCEL. Rechercher tous ces branchements avant migration ; ne pas définir artificiellement VERCEL=1 pour contourner le problème.
- Le client utilise des routes de même origine. Séparer frontend Vercel et backend Render nécessite d’adapter le routage HTTP et WebSocket, la validation des origines et la CSP. Servir initialement le frontend depuis la même application Render simplifie ce point.
- /health indique que le processus répond, sans garantir l’accès à Turso et Redis.

## Préparation technique

1. Introduire une configuration de production indépendante de Vercel et conserver les contrôles d’hôte, d’origine et d’authentification.
2. Vérifier HTTPS derrière le proxy Render ; renseigner l’origine publique exacte.
3. Installer avec python -m pip install . ; démarrer avec python -m uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1.
4. Renseigner les secrets Turso, Redis et RPG_ADMIN_TOKEN dans Render, jamais dans le dépôt. Reprendre les paramètres de production existants après vérification.
5. Tester inscription, connexion, refus d’une origine étrangère, WebSocket, deux joueurs, chat, sauvegarde et reprise après redéploiement.
6. Mesurer CPU, RAM et latence sur Starter avant de choisir la taille définitive. Le hachage scrypt utilise N=131072, r=8, p=1 et deux créneaux d’authentification : surveiller particulièrement les pics mémoire sur 512 Mo.
7. Arrêter les anciens moteurs avant la bascule et vérifier les derniers checkpoints Turso pour éviter deux déploiements concurrents.

Aucun service Render n’a été créé ; aucune facturation ni bascule n’a été lancée.

## Mentions légales

Le jeu contient un panneau accessible sans connexion avec l’identité et le contact de Baptiste Da Silva, les coordonnées officielles de Vercel et la politique de conservation demandée. Le contrôle du code précise les limites du chat : 50 messages globaux en mémoire par connexion, journal local sans purge chronologique définie, 200 messages de groupe au maximum, table chat exclue des checkpoints Turso. Une analyse HTML confirme des identifiants uniques et la présence des liens de contact.

Points non vérifiables dans le dépôt : identité du fournisseur Redis derrière les secrets, régions effectives, acceptation du DPA Turso et purge des copies des prestataires. La conservation des comptes inactifs doit encore être encadrée ; aucune suppression automatique n’a été ajoutée sans décision de l’éditeur. Aucune certification de conformité, fusion ou publication n’est annoncée.

## Sources

- https://render.com/pricing
- https://render.com/docs/free
- https://render.com/docs/websocket
- https://render.com/docs/web-services
- https://render.com/changelog/free-web-services-now-remain-active-while-receiving-websocket-messages
- https://www.economie.gouv.fr/entreprises/developper-son-entreprise/innover-et-numeriser-son-entreprise/mentions-sur-votre-site-internet-les-obligations-respecter
