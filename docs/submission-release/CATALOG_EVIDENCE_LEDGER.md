# Catalog evidence ledger

## Membership rules

Catalog membership and signal eligibility are separate. A group below the five-contributor signal minimum remains browsable. Relationship evidence is attached to each Konglo constituent; the release distinguishes disclosed shareholding, issuer-documented control, and a named listed parent. Parent labels do not imply self-ownership. No indirect ownership chain is inferred from a shared family name, sector, director, or project.

Every Konglo member retains the source URL and evidence date. Direct holding amounts and holder names come from the dated IDX 1% ownership register; issuer-control rows also retain the linked issuer disclosure. Membership, relationship rows, and source files are hash-bound by `historical_comparison` in the release manifest.

## Konglo portfolios

The release carries the 22 existing documented portfolios below. It contains 64 distinct portfolio membership rows; 61 have complete price contributors in the matched replay. Membership overlaps across portfolios are retained. Nineteen portfolios are below the five-contributor signal floor and remain visible in the catalog.

| Portfolio | Catalog members | Replay contributors |
|---|---:|---:|
| Adaro Strategic Investments holdings | 2 | 2 |
| APP Purinusa disclosed holdings | 3 | 3 |
| Astra corporate holdings | 5 | 5 |
| Barito Pacific corporate holdings | 3 | 3 |
| EMTEK corporate holdings | 3 | 3 |
| Harita Jayaraya disclosed holdings | 3 | 2 |
| Hartono / Dwimuria holdings | 1 | 1 |
| Indofood corporate holdings | 4 | 4 |
| Kalbe Farma corporate holdings | 2 | 2 |
| Mega Corpora disclosed holdings | 2 | 2 |
| MNC Asia corporate holdings | 3 | 2 |
| Multipolar / Inti Anugerah holdings | 7 | 7 |
| Panin corporate holdings | 7 | 7 |
| Paraga / Ekacentra disclosed holdings | 1 | 1 |
| Prajogo Pangestu disclosed holdings | 2 | 2 |
| Protelindo disclosed holdings | 2 | 1 |
| Saratoga corporate holdings | 2 | 2 |
| Sinar Mas corporate holdings | 3 | 3 |
| Sungai Budi / Budi Delta holdings | 2 | 2 |
| Tancorp Global disclosed holdings | 2 | 2 |
| Tiara Marga Trakindo holdings | 2 | 2 |
| Victoria Investama holdings | 3 | 3 |

The candidate review considered additional requested ecosystems and names including Jardine, Djarum, CT Corp, Lippo, Bakrie, Triputra, Happy Hapsoro/Rukun Raharja, Mayapada, Rajawali, Ciputra, Pakuwon and Kawan Lama. The cached candidate research for proposed additions is marked provisional or unverified and does not establish each ownership link. No extra portfolio or constituent was added on that basis. Those additions remain open pending dated issuer/IDX evidence for every link.

## Curated themes

Curated themes are a separate analyst-defined catalog, mapped only from exact member sets in the dated IDXIC activity classification as of 27 August 2026. They are not renamed IDXIC subindustries. Memberships may overlap across themes; the count column is per-theme and should not be summed as a unique-stock universe.

| Curated theme | Included IDXIC members |
|---|---:|
| Alternative energy equipment | 2 |
| Banks | 48 |
| Coal | 47 |
| Construction & infrastructure | 58 |
| Consumer staples | 82 |
| Copper & base metals | 32 |
| Electric utilities | 10 |
| Gold | 5 |
| Healthcare | 41 |
| Insurance | 19 |
| Logistics & transport | 44 |
| Oil & gas | 21 |
| Property | 93 |
| Retail | 37 |
| Telecommunications | 22 |

Each theme has a definition, parent category, inclusion/exclusion rules, source activity IDs and dated constituent evidence in the manifest-bound analysis asset. The 102 IDXIC activities remain a separate classification route.

The following requested candidates are not published as themes because the dated activity evidence does not isolate them: palm-oil exposure (Plantations & Crops is broader), nickel and EV batteries, digital finance, and data centres. Alternative Energy Equipment is not described as renewable generation exposure. Shipping, toll roads and related construction remain within broader documented IDXIC activities rather than being claimed as dedicated source categories.

## Primary source references

- IDX 1% ownership register dated 30 September 2026, retained in the release evidence folder and referenced by each direct holding row.
- Issuer control evidence for Barito Pacific / TPIA and Dwimuria / BBCA, retained with its source date and URL.
- Captured IDXIC activity membership dated 27 August 2026, retained in the selected snapshot and bound by its source hash.
- Curated theme definitions: [`config/market_expansion/curated_themes.json`](../../config/market_expansion/curated_themes.json), SHA-256 recorded inside `historical_comparison-v2`.
