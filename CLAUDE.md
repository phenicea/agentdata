# CLAUDE.md — Phenicea : endpoint d'intelligence crypto/DeFi pour agents IA (x402)

> Document de contexte et de pilotage pour l'agent de développement (Claude Code).
> Nom du projet : **Phenicea** (ex nom de travail « AgentData »). Repo : `github.com/phenicea/agentdata`.
> Langue du doc : français + termes techniques en anglais. Le code, lui, peut être en anglais.
>
> **Ce fichier = stratégie & plan (stable).** L'**exécution réelle** (décisions datées, jalons, état live)
> vit dans [`decisions/DECISION_LOG.md`](decisions/DECISION_LOG.md) et les ADR ([`decisions/adr/`](decisions/adr/)).
> État résumé en §12 (avancement) et §16 (journal). MAJ : 2026-06-18.

---

## 0. À LIRE EN PREMIER (par l'agent dev)

Ce fichier décrit la **stratégie et le plan**, pas les signatures d'API exactes.
Les écosystèmes x402, MCP et BlockRun **évoluent vite**. Donc :

- **Ne déduis JAMAIS une signature d'API / un nom de package / un schéma de paiement de ce fichier.** Va chercher la doc live avant d'implémenter (URLs en §10).
- Vérifie les **conditions d'utilisation (ToS)** de chaque source de données avant de la wrapper.
- **Tout se développe et se teste sur testnet d'abord.** On ne touche au mainnet / vrai USDC qu'une fois le flux solide.
- En cas de doute, pose la question ou propose une vérification — ne devine pas sur ce qui touche à l'argent.

---

## 1. CONTEXTE & VISION

On construit un produit dans le **commerce agentique** : des agents IA qui achètent et paient des services digitaux de façon autonome, réglés en **stablecoins (USDC)** via le protocole **x402** (standard ouvert, HTTP 402, créé par Coinbase, sous la Linux Foundation, zéro frais de protocole). Le marché est jeune mais en croissance, et la plus grosse catégorie d'achat des agents est **l'accès aux données et aux APIs**.

**Thèse stratégique :** au lieu de construire une infrastructure lourde (un gateway, un protocole), on devient un **fournisseur de données** : un endpoint payable à l'appel qui sert de l'**intelligence crypto/DeFi calculée/normalisée** à des agents. On le **branche sur des canaux de distribution qui ont déjà du trafic** (voir §9), pour ne pas partir de zéro sur la découverte.

C'est un **pari de positionnement précoce** (voir §4) : c'est pas cher à construire, on apprend tout le pipeline, on bâtit un historique de fiabilité, et on est positionné pour quand le marché scale et/ou quand on empile plusieurs endpoints et qu'on remonte vers une position de **routeur/réputation** (voir §13).

---

## 2. CE QU'ON CONSTRUIT (LE PRODUIT)

**Un endpoint HTTP payable à l'appel qui sert de l'intelligence crypto/DeFi normalisée à des agents IA.**

Flux : un agent appelle l'endpoint → reçoit un `HTTP 402` (termes de paiement) → paie en USDC (Base ou Solana) → reçoit la donnée en JSON propre. **Le paiement EST l'authentification** : pas de compte, pas de clé API, pas d'abonnement.

**Règle de valeur ajoutée (cruciale) :** on ne sert PAS de la donnée brute commoditisée (ex. prix d'un token — gratuit partout, on serait battu direct). On sert de la donnée **calculée/agrégée/normalisée** qui demande un vrai travail et dont l'agent a besoin pour *agir* :

- Rendements DeFi en temps réel, normalisés et comparables sur N protocoles.
- Signaux de liquidité / risque sur tokens et pools.
- Données on-chain agrégées et nettoyées (wallets, flux, métriques).

Le sous-type exact se fige après vérification du marché (§6, Phase 0).

---

## 3. CONTRAINTES & VALEURS (NON NÉGOCIABLES)

L'agent dev doit respecter ces règles dans toute proposition de feature :

- **Pas de jeu / pari / prédiction** (maysir). → Ne PAS intégrer de données de marchés de prédiction (Polymarket, Kalshi, Predexon, etc.), même si c'est populaire dans l'écosystème.
- **Pas de prêt à intérêt / yield-as-lending** (riba) comme produit. Servir de la *donnée sur* les rendements est ok (c'est de l'info) ; opérer un produit de prêt, non.
- **Modèle économique = % / marge sur le volume d'appels** (style Jupiter / Stripe). Pas d'abonnement comme modèle central.
- **Focalisé et single-purpose** : un endpoint fait une chose et la fait bien (les outils focalisés gagnent la sélection des agents).
- **Gagner sur les métriques objectives** : prix, latence, fiabilité, clarté du schéma.

---

## 4. RÉALITÉ DU MARCHÉ (CADRAGE HONNÊTE — à garder en tête)

Ne pas sur-promettre. Données publiques actuelles :

- Réseau x402 entier : ~100 000–170 000 transactions/jour (tous services confondus).
- Un service de données *au top* : ~1 000–3 600 transactions/jour, et le n°1 ne fait que ~3 000 $ de **volume brut** sur 30 jours (appels sous le centime à quelques centimes).
- Un endpoint **neuf** démarre quasi à zéro et monte en puissance (quelques dizaines/jour au début → quelques centaines/jour sur quelques mois s'il est bon et bien distribué).

**Conséquence :** au marché d'aujourd'hui, même un succès = petit revenu. **Un seul endpoint ≠ 10k/mois.** L'objectif des premiers mois n'est PAS le revenu, c'est : shipper, être fiable, être découvrable partout, apprendre, et se positionner. Le revenu vient de la **croissance du marché + l'empilement d'endpoints + la montée vers le routeur**.

---

## 5. ARCHITECTURE TECHNIQUE

Composants (modulaire — chaque endpoint est indépendant et s'ajoute au fil du temps) :

1. **Data Fetcher** — récupère la donnée depuis des sources publiques/gratuites (§7).
2. **Compute / Normalize Layer** — la valeur ajoutée : agrège, calcule, normalise, nettoie.
3. **API Layer** — sert la donnée en JSON propre, schéma stable et documenté.
4. **x402 Payment Middleware** — génère le `402`, vérifie le paiement, débloque la réponse (§8).
5. **MCP Server Wrapper** — expose l'endpoint comme outil MCP (§9, §10).
6. **Discovery Artifacts** — `llms.txt`, spec OpenAPI, docs en markdown brut, schéma MCP (§10).
7. **Monitoring** — uptime, latence, taux d'erreur, nb d'appels (alimente la fiabilité et, plus tard, la réputation).

**Stack suggérée** (l'agent choisit, mais privilégier le simple et le vibecodable) :
- **TypeScript / Node (Express ou Hono)** OU **Python (FastAPI)**.
- SDK x402 officiel (vérifier le nom/version sur npm ou PyPI — §10).
- Hébergement serverless ou conteneur léger (Railway, Render, Fly, Cloudflare Workers…).
- Un **wallet** dédié pour recevoir l'USDC (clés gérées en variables d'environnement / secret manager, **jamais** en clair dans le repo).

---

## 6. PHASE 0 — VÉRIFICATIONS AVANT DE CODER

1. **Choisir le sous-type de donnée précis** en vérifiant ce qui est sous-servi : regarder **x402scan** et le **x402-directory** (quels services existent déjà, lesquels saturent). Construire dans le trou, pas en doublon.
2. **Vérifier les ToS** de chaque source de données envisagée (revente/redistribution autorisée ? rate limits ? besoin d'une clé ?).
3. **Récupérer la doc live** de x402, du facilitator choisi, de MCP et de BlockRun (§10).
4. **Décider Base vs Solana vs les deux** pour le règlement (le volume est plus gros sur Base, Solana monte ; x402 est multi-chaîne — viser les deux à terme).

---

## 7. SOURCES DE DONNÉES (CANDIDATES — à vérifier en Phase 0)

Critères : utile aux agents + gratuit/pas cher en amont + redistribution autorisée + la valeur vient du calcul/normalisation, pas de la donnée brute.

Pistes crypto/DeFi (vérifier disponibilité, ToS, rate limits) :
- Agrégateurs DeFi publics pour TVL / rendements / pools (ex. type DeFiLlama et équivalents).
- RPC / indexeurs on-chain publics (Ethereum, Base, Solana…) pour la donnée brute on-chain.
- Subgraphs / APIs de DEX pour la liquidité.
- Données de prix publiques (uniquement comme *intrant* d'un calcul, jamais revendues telles quelles).

> Plus tard, portefeuille « 2 niches + 2 gros volumes » :
> - **Gros volume** : recherche web / extraction (plutôt en agrégateur, ToS sensibles) ; données crypto/DeFi (notre point d'entrée).
> - **Niche** : données de l'écosystème dev (stats GitHub, npm, DNS/WHOIS) ; données publiques/registres (filings, registres d'entreprises) — valeur via la structuration.

---

## 8. INTÉGRATION x402 (PAIEMENT)

- x402 = standard ouvert basé sur `HTTP 402`. Règlement en **USDC** ; supporte Base, Ethereum, Polygon, **Solana** (tous les SPL tokens côté Solana).
- Pattern : requête → réponse `402` avec termes (montant, destination, réseau, token) → l'agent paie on-chain → il rejoue la requête avec preuve de paiement → on sert la donnée.
- Utiliser un **facilitator** pour générer le `402` et vérifier le paiement (Coinbase CDP, ou un facilitator open-source/non-custodial). **Vérifier les options et signatures sur la doc live.**
- **Tarification dans le sweet spot : ~0,001 à 0,05 $/appel.** 76 % des services sont à ≤ 0,10 $. Rester compétitif pour gagner la sélection.
- **Testnet d'abord.** Mainnet et vrai USDC seulement après validation complète du flux + revue du code qui touche aux fonds.

---

## 9. OÙ SE LISTER (DISTRIBUTION — « les endroits où se mettre »)

Principe : **sois partout.** Un agent peut te trouver par n'importe quel chemin ; tu ne sais pas lequel. Tous les chemins doivent mener à ton service.

1. **BlockRun (priorité — trafic existant).** Gateway pay-per-call leader (~4,5M appels/mois, Base & Solana). Ils **onboardent des fournisseurs de données chaque semaine** : page « List a data source », contact via **Telegram : t.me/bc1max**. Voir aussi leur plugin Claude Code : `blockrun.ai/claude-code-plugin` et leurs docs `blockrun.ai/docs`.
2. **x402 Bazaar (couche de découverte officielle).** Catalogue lisible par machine ; les services sont découvrables via l'endpoint de discovery du facilitator quand ils activent l'extension « bazaar ». Auto-opt-in si on utilise le facilitator CDP. Doc : `docs.x402.org/extensions/bazaar`.
3. **MCP Registry (officiel)** + **Smithery** + **npm** : exposer l'endpoint comme **serveur MCP** pour que tout agent compatible MCP (Claude, etc.) le découvre et l'utilise.
4. **Autres facilitators** : le spec de discovery est ouvert ; se référencer là où c'est pertinent.

---

## 10. RÉFÉRENCEMENT / DÉCOUVRABILITÉ PAR LES AGENTS (« AEO »)

Être listé ne suffit pas — il faut être **choisi**. La sélection est mécanique (pas du marketing). À implémenter :

- **`llms.txt`** à la racine + **docs disponibles en markdown brut** (ex. ajouter `.md` à une URL renvoie le texte). Un agent lit la doc directement pour décider ; si elle est derrière du JS/auth, il ne te lit pas.
- **Spec OpenAPI propre et complète.**
- **Schéma d'outil MCP clair** (inputs/outputs/pricing bien décrits).
- **Métadonnées machine-readable** : prix, latence typique, schéma, capacités, uptime.
- **Focalisé / single-purpose** : un outil = une chose.
- **Gagner sur les métriques** : prix compétitif, latence basse, taux d'erreur bas, fiabilité. C'est ça qui sépare « 47 appels » de « 47 000 appels ».

### Docs live à récupérer avant d'implémenter
- x402 : `https://x402.org` · `https://docs.x402.org` · spec & SDKs (npm / PyPI).
- MCP : `https://modelcontextprotocol.io` + SDK officiel + MCP Registry.
- BlockRun : `https://blockrun.ai/docs` · `https://blockrun.ai/claude-code-plugin` · contact `https://t.me/bc1max`.
- Vérification marché : `x402scan` + `x402-directory`.

---

## 11. SKILLS & RESSOURCES POUR L'AGENT DEV

Skills/outils Claude Code à mobiliser selon les besoins :
- **frontend-design** — si on fait une landing page + un site de docs (utile pour la crédibilité et le `llms.txt`/docs markdown).
- **product-self-knowledge** — si on embarque l'API Anthropic dans le produit (ex. un endpoint « chat/intelligence » qui utilise un modèle).
- **Plugin BlockRun pour Claude Code** (`blockrun.ai/claude-code-plugin`) — pertinent pour tester l'intégration au gateway.
- **SDK MCP** (officiel) — pour le serveur MCP.
- **SDK x402** (officiel, npm/PyPI) — pour le middleware de paiement.
- SDKs/clients des **sources de données** choisies.

> Avant toute création de fichier de type document (docx/pdf/pptx/xlsx), lire la SKILL.md correspondante. Pour du code/markdown, pas de skill requise.

---

## 12. ROADMAP A → Z (PHASÉE) — avancement au 2026-06-18

> Endpoint #1 = **« liquidité exécutable / coût de sortie & fragilité »** sur **Base** (Python/FastAPI, sourcing
> on-chain). Exactitude prouvée : 0,0000 bps vs `getAmountOut` on-chain (Aerodrome volatile + stable).

- ✅ **Phase 0 — Cadrage.** Fait (sous-niche, ToS, docs live, Base d'abord / Solana = endpoint #2).
- ✅ **Phase 1 — Endpoint local.** Fait. compute/chain/api/monitoring + tests.
- ✅ **Phase 2 — Paiement (testnet).** Fait. Middleware x402 opt-in ; flux 402 → pay → serve validé E2E (Base Sepolia,
  facilitator x402.org, $0 accepté). Mainnet doublement verrouillé (`safety.guard_network`, `ALLOW_MAINNET` absent).
- ✅ **Phase 3 — Découvrabilité.** Fait. `llms.txt`, OpenAPI, docs markdown, serveur MCP (streamable-http), landing `/`.
- 🟡 **Phase 4 — Listing partout.** En cours :
  - ✅ **MCP Registry** : LIVE — `io.github.phenicea/agentdata-liquidity-exit-cost` v0.1.0.
  - ⏸️ **x402 Bazaar** : code prêt (extension gated) ; bloqué côté écosystème (`/discovery/resources` x402.org = 404).
  - 🟡 **x402scan** : nécessite une instance publique payments-ON (2e instance `agentdata-pay`, testnet) — en cours.
  - 🟡 **BlockRun** (`t.me/bc1max`) : kit prêt (OpenAPI/llms.txt/docs/402 démontrable) ; contact = action humaine.
  - ➖ **npm** : non requis (serveur remote se liste sans package).
- ⏳ **Phase 5 — Mainnet + monitoring.** NON commencée — **porte humaine** (revue sécurité fonds avant tout vrai USDC).
  Monitoring déjà actif (uptime, latence p50/p95, erreurs, appels) + `/dashboard`.
- ⏳ **Phase 6 — Portefeuille.** Endpoint #2 (sécurité de tx) = squelette optionnel, non démarré. `PaymentRail` posé
  (interface rail-agnostique + adapter x402 only) pour empiler proprement.
- ⏳ **Phase 7 — Routeur/réputation.** Voir §13. (Monitoring = socle de score déjà en place.)

---

## 13. ÉVOLUTION LONG TERME — ROUTEUR DE RÉPUTATION

Une fois plusieurs endpoints en place et du volume/un historique acquis, monter d'un cran : devenir le **routeur classé par fiabilité** pour une niche (« le meilleur service pour X »), en routant vers les fournisseurs les mieux notés et en prenant un % de routage.

- **Score** pondéré : socle objectif/mesurable lourd (uptime, latence, taux d'erreur, conformité de schéma) + signal comportemental fort (rachat/rétention) + jugement post-achat de l'agent (pondéré bas, croisé sur beaucoup d'agents, anti-outliers).
- **Amorçage** : sonder activement les services soi-même (monitoring synthétique) → scores objectifs initiaux sans avoir besoin de volume.
- **Anti-triche** : pondérer par la réputation/le coût de l'agent qui valide ; privilégier les signaux durs à falsifier ; ne jamais faire payer pour être mieux classé (ça corrompt le signal).
- **Moat** : la donnée de réputation se cumule + effet de réseau.

---

## 14. SÉCURITÉ & ARGENT RÉEL

- **Testnet avant tout.** Mainnet seulement après validation + revue du code de paiement.
- **Clés/secrets** en variables d'environnement / secret manager. Jamais dans le repo.
- **Revue/audit** de tout ce qui touche aux fonds avant d'y exposer du vrai USDC.
- **Rate limiting** et gestion des limites des APIs amont (passer sur du RPC/indexeur payant à gros volume).
- **Monitoring** continu (alertes uptime/erreurs).

---

## 15. DEFINITION OF DONE & MÉTRIQUES

MVP « fait » quand :
- [x] Endpoint live qui sert de la donnée calculée/normalisée en JSON propre. *(Render, testnet.)*
- [x] Flux x402 fonctionnel (testnet validé). *(E2E 402→pay→serve OK ; mainnet = porte humaine, non franchie.)*
- [x] `llms.txt` + OpenAPI + serveur MCP en place.
- [~] Listé sur : **MCP Registry ✅** ; BlockRun / x402 Bazaar / x402scan = en cours (npm non requis).
- [ ] Premiers appels payés reçus. *(testnet $0 ; mainnet non franchi → revenu réel pas encore visé.)*
- [x] Monitoring actif (appels/jour, latence p50/p95, taux d'erreur) + `/dashboard`.

Métriques à suivre ensuite : appels/jour, latence p50/p95, taux d'erreur, taux de rachat, revenu brut, marge.

---

## 16. JOURNAL DES DÉCISIONS CLÉS

- **Domaine** : commerce agentique (agents IA qui paient des services en USDC via x402).
- **Position** : fournisseur de données (pas gateway — BlockRun occupe déjà ce créneau et le fait bien).
- **Produit** : endpoint d'intelligence crypto/DeFi **calculée/normalisée** (pas de prix bruts).
- **Distribution** : se brancher sur le trafic existant (BlockRun) + être partout (Bazaar, MCP).
- **Valeurs** : pas de prédiction/pari (maysir), pas de prêt à intérêt (riba), modèle % sur volume.
- **Chaînes** : viser Base + Solana.
- **Cadrage** : marché encore petit → pari de positionnement, démarrage pas cher, revenu modeste au début.
- **Évolution** : empiler des endpoints → monter vers un routeur de réputation.
- **Écartés en route** : gateway rival de BlockRun (trop tard/dur), x402 « moins cher » (course vers le bas vs standard ouvert gratuit), lending Ika (riba), perps/prédiction (maysir).

### Organisation & exécution (ajouts)
- **Marque** : projet renommé **Phenicea** (namespace MCP `io.github.phenicea/...`, repo `github.com/phenicea/agentdata`).
- **Agents décisionnels** : `ceo-agent` (business) et `cto-agent` (technique) dans `.claude/agents/`. Règle : **toute
  décision business passe d'abord par le CEO, puis on exécute** ; tout code passe par un **pipeline multi-agents**
  (3-5 codeurs supervisés CTO → 3-5 testeurs/sécurité). Décisions tracées dans `decisions/DECISION_LOG.md`.
- **Endpoint #1 figé** : « liquidité exécutable / coût de sortie & fragilité » (pas slippage brut), Base, 3 tiers
  (quote $0.008 / risk $0.02 défaut / deep $0.04 ; testnet $0), sourcing on-chain (droit de redistribution propre).
- **Jalons** : E2E x402 testnet validé (facilitator x402.org accepte $0) ; exactitude AMM prouvée 0,0000 bps vs on-chain ;
  **listing #1 MCP Registry LIVE (2026-06-18)**.
- **Garde-fous argent** : testnet par défaut ; mainnet refusé au démarrage ET par requête sans `ALLOW_MAINNET` ;
  clé privée jamais en repo (seule l'adresse publique `PAY_TO_ADDRESS`). Mainnet/vrai USDC = escalade humaine.
- **NB fichier** : un doublon `CLAUDE (1).md` (téléchargement) traîne à la racine ; la source de vérité est **`CLAUDE.md`**.
