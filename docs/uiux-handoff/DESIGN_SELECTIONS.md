# Kurasi desain — IDX Leadership Diffusion

Tanggal pemeriksaan: 3 Oktober 2026. Ini pilihan untuk implementasi eksternal, bukan daftar dependency yang sudah terpasang. Situs diperiksa melalui halaman/dokumentasi publik; seluruh demo belum diuji secara visual atau diaudit kode/lisensinya satu per satu.

## Pilihan utama

| Kebutuhan | Pilihan | Penerapan |
| --- | --- | --- |
| Button dan kontrol | [shadcn/ui, varian Radix](https://ui.shadcn.com/docs/components/radix/button) | Button primary/secondary/outline/ghost/icon, input, badge, segmented tabs, table, empty/skeleton states. Adaptasi token proyek; adopsi komponen secara selektif. |
| Interaksi kompleks | [Radix Primitives](https://www.radix-ui.com/primitives) | Tooltip pada rail, dropdown, popover, tabs, dialog/sheet dengan focus management. Pertahankan native dialog yang bekerja bila tidak ada kebutuhan tambahan. |
| Ikon | [Radix Icons](https://www.radix-ui.com/icons) | Satu keluarga SVG untuk navigasi dan aksi; gunakan ekspor yang benar-benar tersedia. Jangan mencampur Lucide/Tabler yang muncul dalam contoh shadcn. |
| Font UI | [General Sans — Fontshare](https://www.fontshare.com/fonts/general-sans) | Body, judul, tombol dan label: 400/500/600. Pilihan editorial saya untuk tabel dan workspace riset. Pertahankan Geist sebagai fallback bila font gagal tersedia. |
| Font angka | Geist Mono yang sudah digunakan proyek | Ticker, angka tabel, tanggal pendek; tabular numbers dan alignment kanan. Jangan memakai monospace untuk seluruh narasi. |
| Logo | SVG asli pada `app/web/src/components/BrandMark.tsx` | Rapikan optical alignment, clear space, compact/expanded lockup, favicon dan warna dark mode. Pertahankan nama dan identitas proyek. |
| Layout | [Astryx](https://astryx.atmeta.com/components) | Referensi App Shell, Side Nav, Metadata List, Table, Tab List dan Bottom Sheet; adaptasi hierarki, bukan instalasi seluruh design system. |
| Motion | [Transitions.dev](https://transitions.dev/library.html) | Referensi tab indicator, tooltip, disclosure dan toast. CSS singkat dan interruptible; reduced motion wajib. |
| Polish opsional | [beUI](https://beui.dev/) | Referensi Tabs, Tooltip, Drawer, Command Palette; ambil pola yang membantu orientasi dan keyboard. Motion library tidak wajib. |
| Evidence/context | [Beautiful UI](https://www.beautifului.dev/) | Referensi Context Cards, Filter/Records Table, Sidebar Nav dan Search. Sumber, periode, coverage dan detail penelitian tetap terlihat. |

Radix menyatakan primitives mendukung keyboard, semantics dan focus management. Tetap uji perilaku hasil integrasi, bukan menganggap dependency menjamin aksesibilitas aplikasi. Radix Icons menggunakan grid asli 15×15; uji kejernihan pada ukuran final yang dipilih. Fontshare mengidentifikasi General Sans sebagai Closed Source: simpan lisensi keluarga yang diunduh; jangan mengasumsikan SIL OFL atau izin modifikasi file font. [Radix](https://www.radix-ui.com/primitives), [Icons](https://www.radix-ui.com/icons), [Fontshare catalogue](https://www.fontshare.com/), [Fontshare license explanation](https://fontshare.com/licenses/sil-ofl).

## Status semua 13 library pengguna

| Library | Keputusan | Alasan dan batas |
| --- | --- | --- |
| [ObsidianUI](https://www.obsidianui.dev/components#component-gallery) | Cadangan landing page | Gallery menonjolkan komponen interaktif/animasi; marquee, art gallery dan text-stream tidak diperlukan untuk dashboard riset inti. Jangan menambah Motion hanya untuk dekorasi. |
| [Bencho](https://bencho.dev/) | Referensi interaksi opsional | Search, hover dan label-input dapat menginspirasi feedback. Demo heat map bukan model financial treemap yang siap dianggap sesuai. |
| [Fontshare](https://fontshare.com/) | Dipilih | General Sans; validasi lisensi dan font assets saat implementasi. Satoshi adalah alternatif jika ada masalah aset; jangan memakai keduanya bersamaan. |
| [Transitions.dev](https://transitions.dev/library.html) | Dipilih sebagai referensi motion | Tab indicator/tooltip/disclosure sesuai. Pilih contoh free dan jangan menganggap komponen Pro sudah dimiliki. |
| [beUI](https://beui.dev/) | Dipilih selektif sebagai referensi | Ada Tabs, Tooltip, Drawer, Command Palette. Hindari magnetic button, metallic/glass effects, bouncy slider dan angka berputar pada data pasar. |
| [Radix Primitives](https://www.radix-ui.com/primitives) | Fondasi interaksi terpilih | Adopsi per komponen untuk kebutuhan keyboard/focus/overlay, tanpa rewrite seluruh aplikasi. |
| [Radix Icons](https://www.radix-ui.com/icons) | Keluarga ikon terpilih | Satu set untuk sidebar, search, profile, chart controls dan actions. |
| [shadcn/ui](https://ui.shadcn.com/) | Fondasi kontrol terpilih | Tentukan varian Radix secara eksplisit; URL generik beberapa komponen saat pemeriksaan mengarah ke Base UI. Jangan memasang dua primitive systems. |
| [Beautiful UI](https://www.beautifului.dev/) | Referensi evidence dan table | Pilih context/filter/search patterns; chat, AI thinking trace dan approval cards bukan fitur yang diminta. |
| [Astryx](https://astryx.atmeta.com/components) | Referensi layout terpilih | Shell, navigation, metadata, table, responsive overlays relevan. Lisensi source/assets perlu dicek sebelum menyalin. |
| [Reverse UI](https://reverseui.com/#components-section) | Tidak dipakai pada core | Gallery berisi logo/particle/visual effects. Identitas proyek sudah memiliki logo; efek tersebut tidak membantu membaca data. |
| [Kinetics](https://kinetics.colorion.co/#library) | Tidak dipakai pada core | Physics/spring bukan kebutuhan utama. Jangan menambah engine motion kedua atau memakai gerak sebagai satu-satunya feedback. |
| [UI Arc](https://uiarc.dev/components/) | Cadangan, perlu verifikasi komponen | URL /components tidak terbaca melalui alat riset; homepage [uiarc.dev](https://uiarc.dev/) dapat diperiksa. Jangan mengklaim katalog di URL yang gagal sudah diaudit. |

## Aturan desain implementasi

- Dashboard finansial yang tenang: tiga kartu utama, hierarki jelas, detail saat diminta. Banyak angka boleh; dekorasi dan badge berulang dikurangi.
- Brand coral dipakai untuk identitas/aksi terpilih, hijau/merah untuk perubahan bertanda dengan angka dan label. Jangan memakai merah/hijau sebagai instruksi beli/jual.
- Gunakan token semantic untuk light/dark mode. Ganti global inversion/filter jika merusak warna chart/widget; jangan sekadar membalik seluruh root.
- Font body 14–16px; tabel 12–14px; metadata 11–12px. Angka tabular, decimal alignment dan unit konsisten. Hindari huruf uppercase mikro untuk semua teks.
- Spacing dari skala konsisten; table rows terbaca; radius kecil dan konsisten; borders untuk struktur, shadow ringan untuk overlay.
- Tombol default 36–40px, target sentuh mobile 44px; icon-only action wajib accessible name dan tooltip/focus cue. Navigation menggunakan link asli.
- Hover/focus/selected/disabled/loading/error/empty states wajib dirancang. Hindari transition: all, animated counters dan page-load choreography pada workspace.
- Motion sekitar 120–180ms untuk feedback sederhana, 180–240ms untuk overlay; respect prefers-reduced-motion. Search, sort dan filter tidak menunggu animasi.
- Bukan kewajiban memasang semua library. Reuse React/Router/Tailwind/Recharts; tambahkan paket hanya untuk kebutuhan konkret yang tidak ditangani kode/platform yang ada.

## Dependency dan lisensi

Pada baseline belum ada Radix/shadcn/Motion dependencies. Model eksternal harus mencatat nama/version, alasan, bundle impact dan license untuk setiap penambahan; pakai registry/vendor resmi, lockfile, named icon imports. Jangan menjalankan installer massal atau mengganti framework, router, charts dan package manager.

Pilih sumber kode free yang memiliki lisensi sesuai; referensi visual tidak otomatis memberi izin mengambil semua aset. Tidak membeli Pro, font berbayar, subscription atau layanan baru. Klaim kompatibilitas React 19/Tailwind 4/Vite harus dibuktikan melalui build aktual.
