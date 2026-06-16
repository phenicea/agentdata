# Runbook — Publication npm (package du serveur MCP)

> **Statut : PRÉPARÉ — NON EXÉCUTÉ.** Commandes exactes ; **`npm login` / `npm publish` = actions du FONDATEUR.**
> Aucun agent ne publie réellement.
>
> Source : doc live `modelcontextprotocol.io/registry/quickstart` (Steps 1-2) + `docs.npmjs.com` (`npm-publish`),
> fetchée le 2026-06-16. Signatures issues de la doc live, jamais devinées (CLAUDE.md §0).

---

## 0. IMPORTANT — npm n'est PAS sur le chemin critique pour le listing #1

Notre listing #1 est un **serveur MCP DISTANT** (`remotes[].type=streamable-http` dans
[`../server.json`](../server.json)). Le registre MCP **accepte un serveur remote avec une URL seule, sans
aucun artefact npm** (confirmé doc live `remote-servers`).

➡️ Pour publier le listing #1, suivre **[`publish-mcp-registry.md`](./publish-mcp-registry.md)**. **Pas besoin de npm.**

Le scope **`@phenicea`** est tenu **uniquement comme réservation de marque**. Le
[`../package.json`](../package.json) actuel ne contient que des métadonnées (`mcpName`, `files: ["server.json"]`) ;
il n'y a **pas** de package stdio à expédier aujourd'hui.

**Le process ci-dessous ne s'applique QUE SI/QUAND on expédie un jour un package MCP stdio installable.**

---

## 1. Règle de matching de nom (invariant registre — confirmée doc live)

Confirmé live (quickstart + troubleshooting) : **`server.json.name` DOIT être identique à `package.json.mcpName`.**

Avec l'auth GitHub, les deux **doivent** commencer par `io.github.<user-ou-org>/`. Ici :

```
package.json.mcpName == server.json.name == io.github.phenicea/agentdata-liquidity-exit-cost
```

Le registre **valide que le package npm publié contient bien ce `mcpName`** (sinon :
`Registry validation failed for package`). Le `name` npm public, lui, reste scopé marque :
`@phenicea/agentdata-liquidity-exit-cost`.

---

## 2. Préparer `package.json` (si on expédie un package un jour)

État actuel : voir [`../package.json`](../package.json) (déjà figé au namespace Phenicea). Pour une vraie
expédition stdio, s'assurer que sont présents :

```jsonc
{
  "name": "@phenicea/agentdata-liquidity-exit-cost",   // scope marque, publié public
  "version": "0.1.0",
  "mcpName": "io.github.phenicea/agentdata-liquidity-exit-cost", // == server.json.name (invariant)
  "publishConfig": { "access": "public" },             // requis : scopé = restricted par défaut
  "files": ["server.json", /* + artefacts build si stdio */]
}
```

---

## 3. Construire les artefacts (si nécessaire)

```bash
npm install        # ou: npm ci  (pour un build reproductible)
npm run build      # uniquement si un package stdio buildable existe
```

> Aujourd'hui : pas de build (package = métadonnées seules). Étape no-op tant qu'aucun code stdio n'est expédié.

---

## 4. Authentifier — **ACTION FONDATEUR**

⚠️ **NE PAS exécuter par un agent.**

```bash
npm login          # (ou: npm adduser)
# La 2FA peut demander un OTP.
```

---

## 5. Publier — **ACTION FONDATEUR**

⚠️ **NE PAS exécuter par un agent.** Pour un package **scopé**, `--access public` est **REQUIS**
(sinon le scope est `restricted` par défaut et le package n'est pas installable publiquement).

```bash
npm publish --access public
```

---

## 6. Vérifier (lecture seule — OK pour un agent)

```
https://www.npmjs.com/package/@phenicea/agentdata-liquidity-exit-cost
```

---

## 7. Ordre registre (si npm devient un jour requis)

Confirmé live : **publier le package npm D'ABORD, puis `mcp-publisher publish`.**
Le registre MCP n'héberge que des métadonnées et **valide contre l'artefact déjà publié** (le `mcpName` doit y être présent).

1. `npm publish --access public`  (§5)
2. `mcp-publisher publish`        (voir [`publish-mcp-registry.md`](./publish-mcp-registry.md) §5)

> Rappel : pour notre listing #1 **remote**, cette séquence n'est PAS nécessaire — le remote se liste sans npm.

---

## 8. (Optionnel, PRÉPARÉ seulement) — Publication npm via GitHub Actions

```yaml
# .github/workflows/publish-npm.yml  (PRÉPARÉ — déclenchement manuel ; seulement si un package stdio existe)
name: Publish to npm
on:
  workflow_dispatch:        # jamais auto
permissions:
  contents: read
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          registry-url: "https://registry.npmjs.org"
      - run: npm ci
      - run: npm run build
      - run: npm publish --access public
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}   # secret ajouté par le fondateur
```

> Secret `NPM_TOKEN` (= NODE_AUTH_TOKEN) à fournir par le fondateur. Jamais en repo (CLAUDE.md §14).

---

## 9. TODO restants

- [ ] **DÉCISION** : décider si on expédie un jour un package stdio. Tant que le listing reste **remote**,
  npm n'est **pas** requis — laisser `@phenicea` en réservation de marque.
- [ ] **HUMAIN** : confirmer la disponibilité/possession du scope `@phenicea` (fallback `@phenicea-ai` →
  ajuster `package.json.name` ET re-vérifier l'invariant `mcpName == server.json.name`).
- [ ] **HUMAIN** (si expédition) : §4 (`npm login`) puis §5 (`npm publish --access public`).
- [ ] **HUMAIN** (si CI) : fournir le secret `NPM_TOKEN`.

**Hors périmètre (rappels) :** aucune touche mainnet ; aucun vrai USDC ; aucune publication réelle ici.
