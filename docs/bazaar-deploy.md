# Runbook fondateur — déployer l'instance PAY `agentdata-pay` (x402 + Bazaar, testnet)

> Statut : **TESTNET UNIQUEMENT** — Base Sepolia (`eip155:84532`). **JAMAIS de mainnet, jamais de vrai USDC.**
> Ce runbook est pour le **fondateur**. Le pipeline d'agents ne crée AUCUNE instance Render et ne publie rien :
> il prépare la config (`render-bazaar.yaml`) ; **vous** déployez et vérifiez.

Objectif : faire vivre une **2e** Web Service Render, `agentdata-pay`, avec le middleware x402 **activé**
(`X402_ENABLED=true`). C'est cette instance — et **elle seule** — qui :

1. émet un vrai `HTTP 402` sur la route payante, et
2. **auto-opt-in** l'extension de découverte **« bazaar »** (déclarée sur la `RouteConfig` ; le SDK l'active
   dès que le middleware est monté → voir `src/agentdata/payment/middleware.py`).

> ⚠️ **NE PAS toucher au listing #1.** L'instance existante
> `agentdata-liquidity-exit-cost` (<https://agentdata-liquidity-exit-cost.onrender.com>) reste
> `X402_ENABLED=false`, prix `$0`, **pas de 402**, **pas d'extension bazaar**, schéma inchangé. Son compteur
> d'uptime (déclencheur listing #1) tourne — on ne le perturbe pas. La 2e instance est **séparée** ; les deux
> partagent le **même repo** et la **même app** (`agentdata.asgi:app`) mais des variables d'env différentes.

---

## 0. Prérequis

- Le repo est sur GitHub (branche `master`), connecté à Render.
- Le fichier `render-bazaar.yaml` est présent à la racine (fourni).
- **Adresse publique de réception** (vendeur) testnet : `0x5E442c144687De1D311855d65E87584BdEe7541A`.
  C'est la **seule** valeur sensible — et elle est **publique**. La **clé privée** n'est **jamais** requise
  côté vendeur, **jamais** en repo, **jamais** en variable d'env Render.
- Aucune dépense : Render **free tier**, sans carte. (Toute bascule vers un plan payant = **escalade humain**.)

---

## 1. Créer la 2e instance Render `agentdata-pay`

Deux options ; la première (Blueprint) lit directement `render-bazaar.yaml`.

### Option A — Blueprint (recommandé)

1. Render Dashboard → **New** → **Blueprint**.
2. Sélectionner le repo, branche `master`.
3. Render détecte les services Blueprint. **Important** : le repo contient **deux** fichiers de blueprint —
   `render.yaml` (listing #1, à NE PAS recréer) et `render-bazaar.yaml` (cette instance). Si Render ne vous
   laisse pointer que sur `render.yaml`, utilisez l'**Option B** ci-dessous pour créer `agentdata-pay`
   manuellement à partir des mêmes réglages.
4. Valider la création du service `agentdata-pay` (type `web`, runtime `python`, plan `free`, region `oregon`).

### Option B — Web Service manuel (si le Blueprint ne cible pas le bon fichier)

1. Render Dashboard → **New** → **Web Service** → connecter le repo, branche `master`.
2. Renseigner exactement (valeurs de `render-bazaar.yaml`) :
   - **Name** : `agentdata-pay`
   - **Runtime** : `Python`
   - **Plan** : `Free`
   - **Region** : `Oregon`
   - **Build Command** :
     `pip install ".[mcp]" "x402[fastapi,evm,extensions]==2.13.*"`
   - **Start Command** :
     `uvicorn agentdata.asgi:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path** : `/health`
   - **Auto-Deploy** : `On`

### Variables d'environnement (les deux options)

À renseigner dans **Environment** (onglet du service). Les valeurs `sync: false` ne sont **pas** dans le repo :
vous les saisissez dans le dashboard.

| Clé | Valeur | Source | Note |
|---|---|---|---|
| `X402_ENABLED` | `true` | fichier | **LA** différence avec le listing #1 : monte le middleware → 402 + bazaar. |
| `NETWORK_MODE` | `testnet` | fichier | Base Sepolia. **NE PAS** mettre `mainnet`. |
| `POOL_SOURCE` | `fixture` | fichier | Pools déterministes offline, aucun RPC/secret amont. |
| `PAY_TO_ADDRESS` | `0x5E442c144687De1D311855d65E87584BdEe7541A` | **dashboard** | Adresse **publique** uniquement. Requise quand x402 est activé. |
| `FACILITATOR_URL` | *(laisser vide)* | dashboard | Vide ⇒ défaut testnet `https://x402.org/facilitator`. |
| `TESTNET_SYMBOLIC_PRICE_USDC` | *(laisser vide)* | dashboard | **Laisser vide** (= `$0`). Repli uniquement (§5). |

> ⛔ **NE JAMAIS** déclarer `ALLOW_MAINNET` sur cette instance. Son absence garantit que l'app **refuse de
> démarrer** en mainnet (`safety.guard_network`, ADR-001 §4). C'est une borne, pas un oubli.

> ⛔ **NE JAMAIS** ajouter une clé privée de wallet en variable d'env. Le vendeur n'en a pas besoin.

Déclencher le **premier déploiement** (Render le fait automatiquement à la création, sinon **Manual Deploy**).

---

## 2. Keep-alive gratuit (neutraliser le sommeil free tier)

Le free tier Render **dort après ~15 min** d'inactivité (cold start 30–60 s). Pour garder le service chaud et
faire courir l'uptime, branchez un **pinger externe gratuit** (sans carte) :

1. Créer un compte sur **cron-job.org** (ou **UptimeRobot**).
2. Nouvelle tâche : **URL** = `https://agentdata-pay.onrender.com/health` (adaptez au host réel affiché par
   Render après le déploiement), **intervalle** ≈ **10 min**, méthode `GET` ou `HEAD` (la route `/health`
   accepte les deux).
3. Vérifier que le moniteur reçoit des `200`.

> C'est suffisant pour du testnet/preview : il n'y a pas encore de trafic d'agents réel à servir, on entretient
> juste la chaleur du process et la mesure d'uptime.

---

## 3. Vérifier le 402 public (la route payante émet bien un paiement requis)

Une fois le service **Live** (host attribué par Render, ex. `https://agentdata-pay.onrender.com`) :

```bash
# 1) Santé : doit indiquer testnet.
curl -s https://agentdata-pay.onrender.com/health
# -> {"status":"ok","network":"testnet","pool_source":"fixture"}

# 2) Route payante SANS preuve de paiement -> doit renvoyer HTTP 402.
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://agentdata-pay.onrender.com/v1/liquidity/exit-cost?token=WETH&size=10000&tier=risk"
# -> 402

# 3) Voir les termes de paiement (corps du 402) : montant, asset USDC, réseau, pay_to.
curl -s -D - -o - \
  "https://agentdata-pay.onrender.com/v1/liquidity/exit-cost?token=WETH&size=10000&tier=risk"
# Attendu : status 402 + payment requirements (network=eip155:84532, pay_to=0x5E44...,
# montant = $0 testnet par défaut, scheme exact).
```

Checks attendus :

- `/health` → `200` avec `"network":"testnet"`.
- La route payante **sans** en-tête `X-PAYMENT` → **`402`** (et **non** `200`). Si vous obtenez `200`, le
  middleware n'est pas monté → vérifier `X402_ENABLED=true` et redéployer.
- Le `402` doit citer `eip155:84532` (Base Sepolia) et l'adresse `pay_to` publique.

> Le flux complet `402 → pay → serve` (signer un paiement avec un wallet testnet financé) se valide via le
> runbook séparé `docs/e2e-testnet.md`. Ce runbook-ci se limite à **déployer** l'instance PAY et **vérifier la
> présence** du 402 + de l'extension bazaar.

---

## 4. Vérifier la découverte (bazaar)

L'extension bazaar est **déclarative** : elle est portée par la `RouteConfig` de la route payante (voir
`src/agentdata/payment/middleware.py`) et **auto-activée** par le SDK dès que le middleware est monté
(`X402_ENABLED=true`). Aucun appel manuel d'enregistrement. Le **catalogue** est ensuite servi par le
**facilitator** à `GET {facilitator}/discovery/resources`.

Lancer le check (lecture seule, pas de clé) :

```bash
# Interroge le facilitator par défaut (https://x402.org/facilitator) et cherche notre service.
python scripts/check_bazaar_discovery.py

# Ou en précisant le facilitator / un identifiant de notre service :
python scripts/check_bazaar_discovery.py \
  --facilitator https://x402.org/facilitator \
  --name "Liquidity Exit Cost"
```

Interprétation des résultats :

- **Notre service apparaît** → la découverte bazaar fonctionne de bout en bout. C'est le critère du listing #2.
- **`/discovery/resources` n'existe pas / 404 / non-JSON** → **attendu aujourd'hui** sur le facilitator testnet
  public `x402.org` (vérifié 2026-06-16 : `308 → 404` HTML, pas de catalogue servi). Ce n'est **pas** un bug de
  notre côté : nous **déclarons** correctement l'extension côté serveur ; l'**apparition** dépend d'un
  facilitator qui implémente l'endpoint de découverte. À revérifier quand `x402.org` l'exposera, ou via un
  facilitator qui le supporte (ex. CDP). Le script le signale clairement et **n'échoue pas brutalement**.

> **Seam / TODO connu** : la vérification « apparition effective dans le catalogue » (critère CEO listing #2)
> reste à reconfirmer une fois qu'un facilitator sert réellement `/discovery/resources`. La **déclaration**
> côté serveur est, elle, en place et vérifiable (le 402 sort, l'extension est sur la route).

---

## 5. Repli — le facilitator refuse un montant `$0`

Par défaut, le prix testnet est **`$0`**. Il n'est pas garanti que le facilitator testnet accepte un paiement
de valeur 0 (un `transferWithAuthorization` à 0 est un no-op que certains facilitators refusent). **Si et
seulement si** votre E2E (`docs/e2e-testnet.md`) montre que le `settle` échoue sur montant 0 :

1. Dans le dashboard Render du service `agentdata-pay`, mettre
   `TESTNET_SYMBOLIC_PRICE_USDC = 0.001` (= $0.001, 1000 unités atomiques USDC 6 décimales).
2. Redéployer. Le `402` portera désormais ce montant symbolique **testnet**.
3. Financer le wallet **acheteur** jetable en USDC de test Base Sepolia (faucet Circle) — côté **vendeur**,
   rien à financer.

> Ce montant symbolique est **testnet uniquement** et **sans effet en mainnet** (garde-fou). Il reste un repli :
> on garde `$0` par défaut tant que le facilitator l'accepte.

---

## 6. Bornes (rappel non négociable)

- **Testnet only.** Base Sepolia `eip155:84532`. **Aucun** mainnet, **aucun** vrai USDC.
- `ALLOW_MAINNET` **jamais** déclaré → l'app refuse de démarrer en mainnet.
- **Listing #1 intact** : `agentdata-liquidity-exit-cost` reste `X402_ENABLED=false`, `$0`, pas de 402, pas de
  bazaar, schéma inchangé. Cette instance PAY est **séparée**.
- **Aucun secret en repo** : seule l'adresse **publique** `pay_to` est utilisée ; la clé privée n'est jamais
  nécessaire ni stockée.
- **Le déploiement est une action humaine** : le pipeline d'agents prépare la config, le fondateur déploie.
- Tout passage **mainnet** / plan Render **payant** / activation pricing réel = **escalade humain**
  (CLAUDE.md §0/§14, ADR-001 §4).
