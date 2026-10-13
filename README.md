# Pemantau Ranking Google — mitrateknik.co.id

Mengecek posisi www.mitrateknik.co.id di Google (lokasi Semarang) **otomatis setiap Senin 07:00 WIB**
lewat GitHub Actions + SerpAPI, lalu menyimpan laporan untuk evaluasi.

## Lihat hasil
- **[LAPORAN.md](LAPORAN.md)** — laporan terbaru (posisi, perubahan vs minggu lalu, posisi terbaik, pesaing #1)
- `reports/` — arsip laporan tiap minggu
- `data/history.csv` — riwayat lengkap (bisa dibuka di Excel)

## Pengaturan
1. **Kunci SerpAPI:** Settings → Secrets and variables → Actions → New repository secret
   → nama `SERPAPI_KEY`, isi API key dari dashboard SerpAPI.
2. **Kata kunci:** edit `keywords.txt` (satu per baris).
3. **Lokasi / perangkat / kedalaman:** edit `config.json`
   (`max_pages: 2` = cek sampai posisi 20; tiap halaman memakai 1 kuota pencarian).
4. **Cek manual:** tab Actions → "Cek Ranking Mingguan" → Run workflow.

## Kuota SerpAPI gratis
Pemakaian per bulan ≈ jumlah kata kunci × max_pages × 4–5 minggu.
Contoh: 5 kata kunci × 2 halaman × 5 = 50 pencarian. Pastikan di bawah kuota paket Anda.
