# Intégration x402 — paiement à l'appel (testnet d'abord)

> Statut : Phase 2. **Testnet uniquement.** Aucune valeur mainnet active par défaut.
> Le middleware x402 est **OPT-IN** : désactivé tant que `X402_ENABLED` n'est pas mis à `true`.
> Quand il est désactivé, l'app FastAPI existante (et les 42 tests de la Phase 1) tourne inchangée.

Cette page explique comment AgentData encaisse un appel d'API via le protocole
[x402](https://docs.x402.org) : le flux `402 → pay → serve`, le rôle du facilitator,
la séparation stricte testnet/mainnet, et le flag de configuration qui active tout ça.

---

## 1. À quoi sert x402 ici

L'endpoint `GET /v1/liquidity/exit-cost` sert de l'intelligence DeFi calculée
(coût de sortie size-aware, depeg-risk, fragilité). x402 transforme cet endpoint en
**ressource payable à l'appel** : pas de compte, pas de clé API, pas d'abonnement —
**le paiement EST l'authentification**. Un agent paie en USDC et reçoit le JSON.

Le prix dépend du **tier** demandé (query param `tier`), depuis la source de prix unique
`src/agentdata/api/pricing.py` :

| Tier  | Param         | Prix mainnet (cible) | Prix testnet |
|-------|---------------|----------------------|--------------|
| quote | `tier=quote`  | $0.008               | **$0**       |
| risk  | `tier=risk` (défaut) | $0.02         | **$0**       |
| deep  | `tier=deep`   | $0.04                | **$0**       |

Sur testnet, `price_string()` force tous les prix à `$0`. Aucun montant mainnet n'est
jamais actif sans bascule explicite (voir §6).

---

## 2. Le flux 402 → pay → serve

```
Agent                         AgentData (middleware x402)            Facilitator
  |                                   |                                   |
  |  GET /v1/liquidity/exit-cost?...  |                                   |
  |---------------------------------->|                                   |
  |                                   | (pas de preuve de paiement)       |
  |     402 Payment Required          |                                   |
  |     + payment requirements        |                                   |
  |<----------------------------------|                                   |
  |                                   |                                   |
  | (l'agent paie on-chain en USDC,   |                                   |
  |  construit la preuve de paiement) |                                   |
  |                                   |                                   |
  |  GET ... + en-tête de paiement    |                                   |
  |---------------------------------->|   verify(payload, requirements)   |
  |                                   |---------------------------------->|
  |                                   |        ok / rejeté                |
  |                                   |<----------------------------------|
  |                                   |   settle(payload, requirements)   |
  |                                   |---------------------------------->|
  |                                   |        réglé                      |
  |                                   |<----------------------------------|
  |     200 OK + JSON (exit-cost)     |                                   |
  |<----------------------------------|                                   |
```

1. **Requête sans preuve** → le middleware répond `402` avec les *payment requirements*
   (montant pour le tier demandé, asset USDC, réseau CAIP-2, adresse de réception, scheme).
2. **L'agent paie** on-chain et rejoue la requête avec un en-tête de paiement.
3. **verify / settle** : le middleware fait vérifier puis régler la preuve par le facilitator.
4. **serve** : si tout est bon, le middleware débloque la réponse JSON de l'endpoint.

Le SDK x402 (`PaymentMiddlewareASGI`) gère **l'intégralité** du cycle
`402 → verify → settle → serve` en interne contre le facilitator. Le code serveur
n'appelle pas verify/settle manuellement dans le chemin standard.

---

## 3. Rôle du facilitator

Le **facilitator** est le service qui vérifie (`/verify`) et règle (`/settle`) les
paiements on-chain pour le compte du vendeur. AgentData ne custodie rien et n'a pas
besoin de parler directement à la chaîne pour encaisser : il délègue au facilitator.

- **Testnet** (par défaut) : `https://x402.org/facilitator` — facilitator public et
  gratuit sur Base Sepolia. C'est la valeur par défaut de `FACILITATOR_URL` côté testnet
  (voir `src/agentdata/config.py`).
- **Mainnet** : aucune URL par défaut. Elle est fixée délibérément au moment de
  l'escalade mainnet, jamais par défaut.

> Note testnet : il n'est pas confirmé à 100 % que le facilitator testnet accepte un
> montant `$0` pour `verify`/`settle`. Si l'E2E testnet le rejette, on pourra fixer un
> montant testnet **symbolique non nul** (toujours en USDC de test, jamais de vrai USDC)
> via la config — sans toucher au code. Cf. TODO en fin de page.

---

## 4. Le flag X402_ENABLED (opt-in)

Le middleware x402 est **désactivé par défaut**. Il ne s'active que si l'environnement
porte `X402_ENABLED=true`. Le câblage dans `src/agentdata/api/app.py` est fait par
l'intégrateur (CTO), pas par les codeurs des modules de paiement.

- `X402_ENABLED` absent ou `false` (**défaut**) → `app.add_middleware(...)` n'est jamais
  appelé. L'app FastAPI de la Phase 1 est intacte ; les 42 tests existants passent
  inchangés.
- `X402_ENABLED=true` → le middleware est monté sur la route
  `GET /v1/liquidity/exit-cost`, avec un prix résolu **par tier** (lecture du query
  param `tier`) depuis `pricing.py`.

Cette barrière garantit qu'activer le paiement est un choix explicite, et que rien ne
casse l'existant tant qu'on ne l'a pas demandé.

---

## 5. Variables d'environnement

Définies dans `.env.example` (à copier en `.env`, jamais committé). Voir ce fichier pour
la liste complète ; les variables propres à x402 :

| Variable          | Rôle                                                              | Défaut                          |
|-------------------|------------------------------------------------------------------|---------------------------------|
| `X402_ENABLED`    | Active (opt-in) le middleware x402. `true` pour encaisser.        | `false`                         |
| `NETWORK_MODE`    | `testnet` / `mainnet`. Pilote prix, réseau et facilitator.        | `testnet`                       |
| `PAY_TO_ADDRESS`  | Adresse **publique** de réception de l'USDC.                      | (vide)                          |
| `FACILITATOR_URL` | URL du facilitator. Vide → défaut testnet selon `NETWORK_MODE`.   | `https://x402.org/facilitator` (testnet) |

**Secrets :** seule l'**adresse publique** (`PAY_TO_ADDRESS`) va en env. La **clé privée
du wallet ne va JAMAIS** dans le code, le repo ou `.env` committé — uniquement dans un
secret manager / variable d'env runtime (CLAUDE.md §14).

---

## 6. Séparation testnet / mainnet — mainnet = escalade humain

La séparation est pilotée par `NETWORK_MODE` (cf. `src/agentdata/config.py`) :

| Aspect        | `testnet` (défaut)                  | `mainnet`                            |
|---------------|-------------------------------------|--------------------------------------|
| Réseau CAIP-2 | `eip155:84532` (Base Sepolia)       | `eip155:8453` (Base mainnet)         |
| Prix          | **$0** (forcés)                     | $0.008 / $0.02 / $0.04 (par tier)    |
| Facilitator   | `https://x402.org/facilitator`      | aucune valeur par défaut             |
| USDC          | USDC de test                        | **vrai USDC**                        |

**Le passage en mainnet est un point d'escalade humain — jamais décidé côté agents.**
Sont concernés : `NETWORK_MODE=mainnet`, l'activation des prix réels, l'exposition au
vrai USDC, et le listing BlockRun sur trafic payant (DECISION_LOG, handoff CEO point D ;
ADR-001 §4). Le code est conçu pour que la bascule mainnet soit **un changement de config
revu**, pas une réécriture : aucune valeur mainnet n'est active par défaut.

---

## 7. Tests

Les tests de paiement (`tests/test_payment.py`) **moquent le facilitator** : aucun réseau,
aucun fonds. Ils vérifient :

- un `402` est émis quand aucune preuve de paiement n'est fournie ;
- le montant du `402` est correct **par tier** (quote / risk / deep) ;
- en testnet, le montant est **$0** ;
- la réponse est débloquée après une preuve valide (moquée) ;
- une preuve avec montant falsifié est rejetée.

---

## 8. TODO / points à confirmer en doc live

Conformément au mandat « ne devine jamais une signature x402 » :

- **Lecture du query param `tier` dans le callback de prix dynamique** : la `DynamicPrice`
  reçoit un `HTTPRequestContext` ; l'accesseur exact pour récupérer la query string
  (via `.adapter` / `FastAPIAdapter`) n'est pas vérifié de bout en bout. Implémenté
  derrière un seam `_tier_from_ctx()` avec TODO — à confirmer par introspection à
  l'implémentation. Repli possible : une `RouteConfig` par tier (route unique +
  `DynamicPrice` reste préféré).
- **Montant testnet $0** : à confirmer que le facilitator testnet accepte `$0` pour
  verify/settle. Sinon, fixer un montant testnet symbolique non nul via config
  (USDC de test, jamais de vrai USDC).
- **Adresse du contrat USDC** : auto-résolue par `ExactEvmServerScheme` selon le réseau.
  Vérifier le champ `asset` dans le `402` émis lors de l'E2E plutôt que de coder une
  adresse en dur.
