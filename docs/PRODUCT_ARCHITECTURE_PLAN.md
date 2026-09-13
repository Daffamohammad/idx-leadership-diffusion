# IDX Leadership Diffusion — Product Architecture & Feature Contract

**Status:** DESIGN-FIRST / no live call pada fase ini  
**Tanggal:** 2026-09-13  
**Diagram target:** [`architecture_north_star.html`](architecture_north_star.html)  
**Specification:** [`architecture_north_star.json`](architecture_north_star.json)

## 1. Keputusan utama

Kita membangun kontrak arsitektur dan feature boundary terlebih dahulu,
kemudian melakukan live call yang kecil, terukur, dan dapat direplay. Sistem
dibagi menjadi dua jalur yang tidak boleh tercampur secara diam-diam:

1. **Market-data plane** menghasilkan observasi harga, benchmark, taxonomy,
   dan feature kuantitatif.
2. **Research-evidence plane** menemukan, mengambil, mem-parsing, dan
   menyimpan evidence dari dokumen/web dengan provenance lengkap.

You.com dan Tavily membantu discovery serta source retrieval. LlamaIndex /
LlamaParse membantu document parsing. Tidak satu pun dari output teks tersebut
secara default boleh mengubah return, breadth, diffusion, concentration,
leadership, atau confirmation metric.

`yfinance` dipertahankan sebagai market-data support dan replayable harness.
Sectors tetap jalur market-wide yang dituju, tetapi hanya boleh dipromosikan
menjadi sumber utama setelah auth, coverage, price basis, parity, dan biaya
terverifikasi.

## 2. Cara membaca screenshot penggunaan

Screenshot yang dilampirkan diperlakukan sebagai **bukti keadaan UI pada saat
itu**, bukan instruksi atau izin untuk melakukan API call. Angka yang terlihat
adalah `58` pada program Sectors Hackathon 2026, `600` credits, dan `942`
requests this period, dengan tanggal kedaluwarsa yang juga tampil di UI.
Angka tersebut time-specific; sistem tidak menganggapnya sebagai saldo live
tanpa pemeriksaan baru. Tidak ada live API call yang dilakukan untuk membuat
artifact ini.

## 3. Target architecture

| Plane | Tanggung jawab | Output | Status repo |
| --- | --- | --- | --- |
| Market data | Sectors dan yfinance melalui provider contract | canonical price, benchmark, security master, taxonomy | Fondasi provider dan pipeline sudah ada |
| Research discovery | You.com untuk recall/research; Tavily untuk targeted search | kandidat URL, hasil search, citation envelope | Client dan bounded context command sudah ada |
| Document ingestion | crawl/extract, lalu adapter LlamaIndex/LlamaParse untuk PDF/HTML terpilih | raw document, parsed pages, tables, source hash | LlamaParse reducer sudah ada; adapter umum masih target |
| Evidence | entity resolution, claim normalization, quality gates | typed claims, evidence records, context sidecars | Evidence model dan sidecar path sudah ada |
| Analytics | feature, aggregation, signal, transition, sensitivity | deterministic group/security metrics | Sudah menjadi core pipeline |
| Snapshot | point-in-time bundle, manifest, quality, provenance | replayable snapshot untuk UI | Sudah ada |
| Product surface | React SPA dan Streamlit membaca snapshot | read-only analyst workflow | Sudah ada; tidak boleh membuka provider connection |
| Control plane | cache, request ledger, budget preflight, credentials, data gaps | audit trail dan fail-closed decision | Sudah sebagian ada; perlu dijadikan kontrak lintas provider |

Jalur utama: **market provider → provider gateway → canonical data →
deterministic analytics → snapshot → snapshot reader → product surface**.

Jalur research: **You.com/Tavily discovery → official source → crawl/extract →
LlamaIndex/LlamaParse → typed claim + provenance → evidence sidecar**.

## 4. Pembagian kerja antar provider

| Pekerjaan | Primary | Secondary / fallback | Tidak boleh dilakukan |
| --- | --- | --- | --- |
| Harga harian dan benchmark | Sectors bila live contract lolos; yfinance untuk support/replay | Fixture/cache | Menggunakan search result sebagai harga |
| Discovery luas | You.com | Tavily untuk verifikasi selektif | Menjalankan dua provider untuk setiap query |
| Targeted search dan crawl | Tavily | You extract bila diperlukan | Crawl tanpa limit depth/breadth/URL |
| Dokumen PDF resmi | LlamaParse melalui adapter LlamaIndex target | Parser fixture/offline | Mengirim seluruh dokumen tanpa page budget |
| HTML/table terpilih | Tavily extract atau LlamaIndex reader | You contents | Memasukkan free-form text langsung ke feature engine |
| Synthesis naratif | You.com research, bila eksplisit diminta | Tidak ada | Menjadikan answer model sebagai angka atau confirmation |

Aturan praktis: pilih satu provider utama per pekerjaan. Provider kedua hanya
dipakai untuk cross-check atau mengisi gap yang sudah tercatat, bukan sebagai
duplikasi default.

## 5. Kontrak data yang harus dibekukan sebelum implementasi lanjut

### 5.1 Raw request envelope

Setiap request menyimpan tujuan dan dampaknya, bukan hanya response:

```text
run_id
provider
operation
endpoint
request_fingerprint
purpose
input_scope
estimated_cost
actual_cost
cache_hit
http_attempts
rows_or_documents_returned
status
error_code
retrieved_at
source_as_of
```

`request_fingerprint` harus stabil untuk operasi dan parameter yang sama.
Cache hit tidak boleh menambah HTTP attempt. Retry dihitung sebagai attempt,
dan tetap berada di bawah request cap.

### 5.2 Research document envelope

Dokumen hasil crawl/extract disimpan terpisah dari market snapshot:

```text
document_id
source_url
canonical_url
source_domain
document_type
published_at
retrieved_at
content_hash
raw_artifact_path
parser_name
parser_version
page_or_section
extraction_status
```

Raw response dan parsed representation harus dipertahankan terpisah. Parser
boleh memperbaiki bentuk tabel, tetapi tidak boleh diam-diam mengubah nilai,
unit, sign, period, atau header.

### 5.3 Typed claim envelope

Claim yang ingin dikaitkan ke issuer atau group minimal memiliki:

```text
claim_id
entity_type / entity_id
claim_type
value / unit / currency
period_start / period_end
published_at / retrieved_at
source_url / content_hash / page_or_section
parser_name / parser_version
completeness_denominator
reconciliation_status
quantitative_use
evidence_status
```

`quantitative_use` default-nya `false`. Claim hanya boleh dipromosikan ke
feature/confirmation jika entity match exact, periode dan unit jelas,
denominator tersedia, nilai lolos validasi, dan rekonsiliasi deterministik
berhasil. Jika salah satu syarat gagal, hasilnya tetap `CONTEXT_ONLY`,
`DATA_GAP`, atau `UNCONFIRMED`.

### 5.4 Snapshot contract

Snapshot kuantitatif tetap membawa `provider_mode`, `as_of`, `coverage`,
`method_version`, `feature_version`, `price_basis`, dan provenance. Evidence
research disimpan sebagai sidecar yang direferensikan oleh snapshot, bukan
sebagai kolom bebas yang bisa mengubah ranking.

Empat dimensi ini tetap independen:

- **Leadership:** relative performance / rank.
- **Diffusion:** seberapa luas partisipasi constituent.
- **Concentration:** seberapa terkonsentrasi kontribusinya.
- **Confirmation:** evidence fundamental/flow/event yang lolos gate.

## 6. Feature map produk

### Core MVP — harus stabil dahulu

| Feature | Fungsi | Data minimum | Evidence UI |
| --- | --- | --- | --- |
| Market Overview | kondisi market, coverage, benchmark, status data | snapshot + quality | `REAL SNAPSHOT` |
| Sector / Group Explorer | ranking dan drilldown group | group snapshot + constituents | `REAL SNAPSHOT` |
| Leadership Map | posisi Leadership terpisah dari Diffusion | return/excess-return | `REAL SNAPSHOT` |
| Diffusion & Breadth | broadening, narrowing, eligible denominator | breadth + diffusion v2 | `REAL SNAPSHOT` |
| Concentration | top contributor, signed share, HHI | contribution decomposition | `REAL SNAPSHOT` |
| Ticker Analysis | price history dan group context | security master + history | `REAL SNAPSHOT` / `DATA GAP` |
| What Changed | transition dan materiality | comparable prior snapshot | `REAL SNAPSHOT` / `NO COMPARABLE HISTORY` |
| Methodology & Data Quality | definisi, provider mode, gaps, limits | manifest + quality + provenance | selalu terlihat |

### Research layer — dibangun setelah contract offline lulus

| Feature | Fungsi | Batas |
| --- | --- | --- |
| Research Evidence Panel | menampilkan source, tanggal, hash, dan parsed excerpt | context/evidence only |
| Official Release Cards | IHSG, net foreign market-level, PER/PBV dari release resmi | bukan per-ticker confirmation |
| Research Events | event/filing/corporate-action context | tidak mengubah signal tanpa claim gate |
| Group Context | ringkasan source-backed yang terkait group | label `CONTEXT ONLY` bila belum typed |
| Source Explorer | melihat URL, crawl path, parser version, extraction warnings | auditability, bukan recommendation |

### Deferred enrichment — jangan dibangun paralel sebelum core evidence siap

- free-float weighted aggregation;
- per-ticker foreign flow dan broker activity;
- fundamentals periodized dan corporate actions;
- industry/sub-industry taxonomy;
- alerts atau scheduled refresh;
- forward-return diagnostic.

Setiap item di atas perlu source-specific contract dan parity/coverage test.
Nama feature tidak boleh dipakai sebagai bukti bahwa datanya sudah tersedia.

## 7. API economy dan fail-closed policy

### Default mode

- Design, unit test, snapshot build test, dan UI render memakai fixture/cache.
- Tidak ada live call dari browser, UI render, atau import module.
- Setiap provider live harus punya `allow_live` dan `allow_credit_spend` gate.
- LlamaParse juga membutuhkan gate upload cloud dan gate credit spend.
- Preflight menghitung estimated reserve dan menolak run sebelum request jika
  budget tidak cukup.
- Cache dipakai sebelum request; request key dan response hash ditulis ke
  ledger.
- Retry dibatasi dan dihitung sebagai request; retry tidak boleh tersembunyi.
- Provider failure tidak diam-diam berpindah ke provider lain.

### Run manifest sebelum live call

Sebelum eksekusi, run harus menjawab:

1. Feature apa yang ingin diisi?
2. Source/provider mana yang primary?
3. Scope entity, URL, halaman, dan periode berapa?
4. Berapa estimated requests/credits dan hard ceiling-nya?
5. Apa output artifact dan success criterion-nya?
6. Bagaimana cara menghentikan run jika cost, response shape, atau coverage
   menyimpang?

Sesudah run, manifest mencatat actual request delta, actual cost bila tersedia,
cache reuse, rows/documents yang diterima, serta `DATA GAP` yang tersisa.
Tidak boleh menyimpulkan efektivitas atau efisiensi hanya dari HTTP 200.

## 8. Tahapan implementasi dan gate

### Phase A — Architecture freeze (sekarang, zero live call)

- [x] North-star architecture diagram.
- [x] Market/research plane boundary.
- [x] Provider responsibility matrix.
- [x] Feature map dan evidence labels.
- [x] Budget, ledger, cache, dan fail-closed rules.

**Gate:** semua feature punya input, output, provenance, dan status data yang
jelas.

### Phase B — Offline contracts and fixtures

- Buat `research/contracts.py` untuk document, claim, source, dan extraction
  status.
- Buat fixture You/Tavily untuk search, extract, crawl, error, retry, cache hit,
  dan malformed payload.
- Buat fixture LlamaIndex/LlamaParse untuk PDF multi-page, table header, unit,
  decimal separator, missing page, dan unreconciled value.
- Buat entity-resolution fixture untuk ticker/group/source alias.

**Gate:** seluruh parser dan reducer dapat diuji tanpa network dan tanpa
credential; `quantitative_use=false` menjadi default yang teruji.

### Phase C — Bounded provider probe

- Pilih satu pekerjaan dan satu primary provider.
- Satu query/source/page scope terlebih dahulu.
- Jalankan hanya setelah run manifest dan budget reserve disetujui.
- Simpan raw response, parsed artifact, ledger, dan quality report.

**Gate:** request count, actual cost, response shape, source provenance, dan
coverage dapat direkonsiliasi. Jika tidak, stop dan tandai `DATA GAP`.

### Phase D — Quantitative core parity

- YFinance replay dan Sectors fixture tetap menjadi regression path.
- Sectors live hanya setelah auth, full-universe pagination, price basis,
  benchmark, taxonomy, parity, dan credit economics terbukti.
- Feature engine tetap provider-independent.
- Tidak ada enrichment research yang boleh mengubah snapshot core sebelum
  promotion gate tersedia.

**Gate:** snapshot market dapat direbuild dari manifest dan provider mode
terlihat di UI.

### Phase E — Research ingestion

- Tambahkan interface parser generic.
- Implementasikan adapter LlamaIndex/LlamaParse untuk dokumen terpilih.
- Normalisasi evidence ke typed claim envelope.
- Tampilkan sidecar pada Research Evidence / Methodology / Group Context.

**Gate:** setiap excerpt dapat ditelusuri ke URL, hash, page/section,
retrieved_at, parser version, dan status kualitas.

### Phase F — Promotion to confirmation

- Hanya claim yang memenuhi entity, period, unit, denominator, reconciliation,
  completeness, dan source authority yang dapat dipertimbangkan sebagai
  confirmation input.
- Promotion dilakukan melalui versi schema/methodology baru dan regression
  tests.
- Jika bukti tidak cukup, UI tetap menunjukkan `CONTEXT ONLY`, `DATA GAP`, atau
  `UNCONFIRMED`.

## 9. Target module layout

Target ini adalah namespace desain; tidak semua file perlu dibuat sekaligus:

```text
src/idx_leadership/
├── providers/                 # market providers + search clients
├── research/
│   ├── contracts.py           # document, claim, source, status
│   ├── discovery.py           # You/Tavily routing + deduplication
│   ├── retrieval.py           # bounded crawl/extract
│   ├── entity_resolution.py   # ticker/group/source mapping
│   ├── claims.py              # deterministic claim normalization
│   └── parsers/
│       ├── base.py
│       └── llamaindex.py       # LlamaIndex/LlamaParse adapter
├── features/                  # no vendor objects
├── signals/                   # deterministic states/transitions
└── data/                      # cache, manifest, snapshot readers/writers

data/
├── raw/<provider>/             # replayable vendor responses
├── normalized/<run>/           # canonical rows and quality reports
├── evidence/<run>/             # documents, claims, hashes, sidecars
└── snapshots/<snapshot_id>/    # quantitative point-in-time bundle
```

## 10. Definition of ready untuk feature baru

Feature baru belum dianggap ready hanya karena endpoint dapat dipanggil. Ia
harus memiliki:

- contract input/output dan schema version;
- source authority serta entity/time/unit semantics;
- offline fixture dan failure case;
- cache key, request budget, dan ledger fields;
- deterministic quality checks dan denominator;
- explicit status `READY`, `READY_WITH_GAPS`, `DATA_GAP`, atau `UNCONFIRMED`;
- snapshot/sidecar provenance;
- UI badge yang tidak melebih-lebihkan coverage;
- regression test yang membuktikan tidak ada look-ahead atau silent fallback.

## 11. Known gaps yang tetap terbuka

- LlamaParse adapter yang ada masih spesifik pada IDX Daily Statistics; adapter
  generic LlamaIndex adalah target arsitektur, bukan implementasi yang boleh
  diasumsikan sudah selesai.
- `pyproject.toml` saat ini menyediakan optional `llama-cloud`, bukan bukti
  bahwa seluruh LlamaIndex reader/parser stack sudah terpasang.
- Sectors live credit economics, full-universe coverage, price basis, dan
  provider parity tetap perlu evidence per run.
- yfinance mendukung price history/replay, tetapi tidak otomatis menjadi
  authoritative source untuk taxonomy, flow, fundamentals, atau corporate
  actions.
- Research search/extract/crawl tetap unstructured sampai claim promotion gate
  lulus.

## 12. Next execution order

1. Bekukan document/claim/source contracts dan offline fixtures.
2. Implementasikan generic parser interface dengan LlamaIndex adapter sebagai
   plugin terisolasi.
3. Satukan You/Tavily routing, deduplication, preflight, cache, dan ledger di
   satu research orchestrator.
4. Jalankan satu bounded probe yang memiliki manifest dan budget approval.
5. Baru integrasikan evidence sidecar ke UI; jangan ubah quantitative snapshot.
6. Setelah parity dan completeness terbukti, ajukan feature promotion secara
   terpisah.
