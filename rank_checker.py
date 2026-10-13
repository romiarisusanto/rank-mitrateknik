"""Cek ranking Google untuk mitrateknik.co.id via SerpAPI.

Hasil:
  data/history.csv           -> riwayat semua pengecekan (untuk evaluasi)
  reports/YYYY-MM-DD.md      -> laporan per minggu
  LAPORAN.md                 -> laporan terbaru (tampil langsung di GitHub)

Pemakaian:
  SERPAPI_KEY=xxxx python rank_checker.py
  python rank_checker.py --demo      # data contoh tanpa memakai kuota
"""
import csv
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
HISTORY = ROOT / "data" / "history.csv"
REPORTS = ROOT / "reports"
FIELDS = ["tanggal", "kata_kunci", "posisi", "url", "judul", "pesaing_teratas"]
WIB = timezone(timedelta(hours=7))


def load_config():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def load_keywords():
    lines = (ROOT / "keywords.txt").read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]


def host_matches(link, domain):
    host = urlparse(link).netloc.lower()
    return host == domain or host.endswith("." + domain)


def check_keyword(keyword, cfg, api_key):
    import requests

    top_competitor = ""
    for page in range(cfg.get("max_pages", 2)):
        params = {
            "engine": "google",
            "q": keyword,
            "location": cfg["location"],
            "gl": cfg["gl"],
            "hl": cfg["hl"],
            "google_domain": cfg["google_domain"],
            "device": cfg.get("device", "desktop"),
            "start": page * 10,
            "api_key": api_key,
        }
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            if "hasn't returned any results" in data["error"]:
                break
            raise RuntimeError(data["error"])
        results = data.get("organic_results", [])
        for res in results:
            link = res.get("link", "")
            if not top_competitor and not host_matches(link, cfg["domain"]):
                top_competitor = urlparse(link).netloc
            if host_matches(link, cfg["domain"]):
                return {
                    "posisi": res.get("position"),
                    "url": link,
                    "judul": res.get("title", ""),
                    "pesaing_teratas": top_competitor,
                }
        if not results:
            break
    return {"posisi": "", "url": "", "judul": "", "pesaing_teratas": top_competitor}


def demo_result(keyword):
    pos = random.choice([3, 5, 8, 12, 17, ""])
    return {
        "posisi": pos,
        "url": "https://www.mitrateknik.co.id/" if pos else "",
        "judul": "Mitra Teknik (DEMO)" if pos else "",
        "pesaing_teratas": "contoh-pesaing.com",
    }


def read_history():
    if not HISTORY.exists():
        return []
    with HISTORY.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_history(rows):
    """Simpan hasil; jika hari ini sudah dicek, hasil lama hari ini diganti."""
    HISTORY.parent.mkdir(exist_ok=True)
    replace = {(r["tanggal"], r["kata_kunci"]) for r in rows}
    old = [h for h in read_history() if (h["tanggal"], h["kata_kunci"]) not in replace]
    with HISTORY.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(old + rows)


def to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def fmt_pos(p):
    return str(p) if p else "> top " + str(load_config().get("max_pages", 2) * 10)


def build_report(today, rows, history):
    prev_by_kw, best_by_kw = {}, {}
    for h in history:
        if h["tanggal"] < today:
            prev_by_kw[h["kata_kunci"]] = h  # tanggal berurutan, ambil terakhir
        p = to_int(h["posisi"])
        if p and (h["kata_kunci"] not in best_by_kw or p < best_by_kw[h["kata_kunci"]]):
            best_by_kw[h["kata_kunci"]] = p

    lines = [
        f"# Laporan Ranking Google — mitrateknik.co.id",
        "",
        f"**Tanggal cek:** {today}  ",
        f"**Lokasi:** {load_config()['location']} · **Perangkat:** {load_config().get('device')}",
        "",
        "| Kata kunci | Posisi | Minggu lalu | Perubahan | Terbaik | Pesaing #1 | Halaman |",
        "|---|---|---|---|---|---|---|",
    ]
    up = down = top10 = 0
    for r in rows:
        kw, now = r["kata_kunci"], to_int(r["posisi"])
        prev = to_int(prev_by_kw.get(kw, {}).get("posisi"))
        if now and prev:
            diff = prev - now
            change = f"▲ {diff}" if diff > 0 else (f"▼ {-diff}" if diff < 0 else "=")
            up += diff > 0
            down += diff < 0
        elif now and not prev:
            change = "baru masuk" if kw in prev_by_kw else "—"
        elif prev and not now:
            change = "keluar"
            down += 1
        else:
            change = "—"
        top10 += bool(now and now <= 10)
        page = f"[link]({r['url']})" if r["url"] else ""
        lines.append(
            f"| {kw} | **{fmt_pos(now)}** | {fmt_pos(prev) if kw in prev_by_kw else '—'} | {change} "
            f"| {best_by_kw.get(kw, '—')} | {r['pesaing_teratas']} | {page} |"
        )
    lines += [
        "",
        f"**Ringkasan:** {top10} dari {len(rows)} kata kunci di halaman 1 Google · "
        f"{up} naik · {down} turun.",
        "",
        "Riwayat lengkap: [data/history.csv](data/history.csv) · "
        "Arsip mingguan: folder [reports/](reports/)",
    ]
    return "\n".join(lines) + "\n"

DASHBOARD = "https://romiarisusanto.github.io/rank-mitrateknik/"


def notify_telegram(today, rows, history, failed):
    """Kirim ringkasan ke Telegram (jika TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID diset)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return
    import html
    import requests

    prev = {}
    for h in history:
        if h["tanggal"] < today:
            prev[h["kata_kunci"]] = to_int(h["posisi"])
    up = down = top10 = 0
    lines = []
    for r in sorted(rows, key=lambda r: to_int(r["posisi"]) or 999):
        kw, now = r["kata_kunci"], to_int(r["posisi"])
        was = prev.get(kw)
        mark = ""
        if kw in prev:
            if now and was:
                d = was - now
                mark = f" ▲{d}" if d > 0 else (f" ▼{-d}" if d < 0 else " =")
                up += d > 0
                down += d < 0
            elif now and not was:
                mark, up = " 🆕", up + 1
            elif was and not now:
                mark, down = " ⬇️keluar", down + 1
        top10 += bool(now and now <= 10)
        pos = f"<b>{now}</b>" if now else "20+"
        lines.append(f"• {html.escape(kw)}: {pos}{mark}")
    text = (
        f"📊 <b>Ranking Google mitrateknik.co.id</b>\n{today} · Semarang (HP)\n\n"
        f"Halaman 1: <b>{top10}/{len(rows)}</b> · ▲ {up} naik · ▼ {down} turun\n\n"
        + "\n".join(lines)
    )
    if failed:
        text += f"\n\n⚠️ Gagal dicek: {html.escape(', '.join(failed))}"
    text += f'\n\n<a href="{DASHBOARD}">Buka dashboard</a>'
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=30,
        )
        print("Telegram:", r.status_code)
    except Exception as e:  # notifikasi gagal jangan gagalkan cek
        print("Telegram gagal:", e)


def main():
    demo = "--demo" in sys.argv
    cfg = load_config()
    api_key = os.environ.get("SERPAPI_KEY")
    if not demo and not api_key:
        sys.exit("SERPAPI_KEY belum diset. Tambahkan di GitHub > Settings > Secrets.")

    today = datetime.now(WIB).strftime("%Y-%m-%d")
    history = read_history()
    rows, failed = [], []
    for kw in load_keywords():
        try:
            res = demo_result(kw) if demo else check_keyword(kw, cfg, api_key)
        except Exception as e:  # satu kata kunci gagal jangan hentikan semua
            print(f"[GAGAL] {kw}: {e}")
            failed.append(kw)
            continue
        row = {"tanggal": today, "kata_kunci": kw, **res}
        rows.append(row)
        print(f"{kw}: {fmt_pos(res['posisi'])}")

    if not rows:
        sys.exit("Tidak ada hasil.")
    append_history(rows)
    report = build_report(today, rows, history + rows)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"{today}.md").write_text(report, encoding="utf-8")
    (ROOT / "LAPORAN.md").write_text(report, encoding="utf-8")
    print("Laporan tersimpan.")
    notify_telegram(today, rows, history, failed)


if __name__ == "__main__":
    main()
