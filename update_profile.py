#!/usr/bin/env python3
"""
update_profile.py — v3.1 (Robust, Dual Email)
Backup bulanan: enrich sitasi & link publikasi via OpenAlex + Crossref.
Tidak menimpa data lama — hanya mengisi field kosong.
"""

import json
import os
import time
import logging
from pathlib import Path
import requests

# ─── KONFIGURASI ──────────────────────────────────────────────────────────
EMAIL_PRIMARY   = "vicky.setia.gunawan@upertis.ac.id"   # untuk API polite pool
EMAIL_SECONDARY = "visegu27@gmail.com"                  # kontak cadangan

DATA_FILE = "data.json"

# User-Agent sopan: menyertakan kedua email
UA = {
    "User-Agent": (
        f"ProfilDosen-Updater/3.1 "
        f"(mailto:{EMAIL_PRIMARY}; cc:{EMAIL_SECONDARY})"
    )
}

# ─── LOGGING ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ─── HTTP HELPER + CIRCUIT BREAKER ────────────────────────────────────────
_hits = 0
_MAX_HITS = 3

def get_json(url, params=None, retries=2):
    """GET JSON dengan retry + stop kalau kena 429 berkali-kali."""
    global _hits
    if _hits >= _MAX_HITS:
        log.warning("Terlalu banyak 429, berhenti memanggil API.")
        return None
    for i in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=20)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                _hits += 1
                log.warning(f"429 hit #{_hits}. Backoff...")
                time.sleep(5 * (i + 1))
                continue
            return None
        except Exception:
            time.sleep(1)
    return None

# ─── OPENALEX ─────────────────────────────────────────────────────────────
def enrich_openalex(judul):
    """Return (sitasi_str, doi_url)."""
    clean = " ".join(judul.strip().rstrip('.').split())
    if not clean:
        return "0", ""
    d = get_json(
        "https://api.openalex.org/works",
        params={
            "search": clean,
            "per-page": 3,
            "mailto": EMAIL_PRIMARY,
        },
    )
    if not d:
        return "0", ""
    words = [w for w in clean.lower().split() if len(w) > 2]
    for w in d.get("results", []):
        t = (w.get("title") or "").lower()
        common = sum(1 for x in words if x in t)
        if words and common / len(words) >= 0.6:
            cit = str(w.get("cited_by_count", 0) or 0)
            doi = w.get("doi") or ""
            if not doi and w.get("primary_location"):
                doi = w["primary_location"].get("landing_page_url", "") or ""
            return cit, doi
    return "0", ""

# ─── CROSSREF ─────────────────────────────────────────────────────────────
def enrich_crossref(judul):
    """Fallback: Crossref. Return (sitasi_str, doi_url)."""
    clean = " ".join(judul.strip().rstrip('.').split())
    if not clean:
        return "0", ""
    d = get_json(
        "https://api.crossref.org/works",
        params={
            "query.bibliographic": clean,
            "rows": 3,
            "mailto": EMAIL_PRIMARY,
        },
    )
    if not d:
        return "0", ""
    words = [w for w in clean.lower().split() if len(w) > 2]
    for it in (d.get("message") or {}).get("items", []):
        titles = it.get("title") or []
        if not titles:
            continue
        t = titles[0].lower()
        common = sum(1 for x in words if x in t)
        if words and common / len(words) >= 0.6:
            cit = str(it.get("is-referenced-by-count", 0) or 0)
            doi = it.get("DOI", "")
            return cit, (f"https://doi.org/{doi}" if doi else "")
    return "0", ""

# ─── ENRICH BATCH PUBLIKASI ───────────────────────────────────────────────
def enrich_publikasi(arr):
    log.info(f"Enrich {len(arr)} publikasi via OpenAlex + Crossref...")
    for i, p in enumerate(arr, 1):
        butuh_cit  = not p.get("sitasi") or str(p["sitasi"]) in ("0", "")
        butuh_link = not p.get("link")
        if not butuh_cit and not butuh_link:
            log.info(f"  [{i}/{len(arr)}] ⊘ Sudah lengkap: {p.get('judul','')[:55]}")
            continue

        # 1. OpenAlex
        cit, doi = enrich_openalex(p.get("judul", ""))
        if butuh_cit and cit != "0":
            p["sitasi"] = cit
            butuh_cit = False
        if butuh_link and doi:
            p["link"] = doi
            butuh_link = False

        # 2. Fallback Crossref
        if butuh_cit or butuh_link:
            cit2, doi2 = enrich_crossref(p.get("judul", ""))
            if butuh_cit and cit2 != "0":
                p["sitasi"] = cit2
            if butuh_link and doi2:
                p["link"] = doi2

        log.info(f"  [{i}/{len(arr)}] ✓ sitasi={p.get('sitasi','0')} "
                 f"| {p.get('judul','')[:55]}")
        time.sleep(1.5)  # sopan ke API
    return arr

# ─── MAIN ─────────────────────────────────────────────────────────────────
def main():
    p = Path(DATA_FILE)
    if not p.exists():
        log.error(f"{DATA_FILE} tidak ditemukan. Jalankan editor dulu.")
        return

    with open(p, encoding="utf-8") as f:
        data = json.load(f)

    log.info(f"Base: {len(data.get('publikasi', []))} publikasi, "
             f"{len(data.get('pendidikan', []))} pendidikan, "
             f"{len(data.get('mengajar', []))} kampus.")

    # Enrich publikasi
    if data.get("publikasi"):
        data["publikasi"] = enrich_publikasi(data["publikasi"])

    # Simpan
    data["status"] = "success"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    log.info(f"✔ {DATA_FILE} diperbarui. "
             f"Total publikasi: {len(data.get('publikasi', []))}.")

if __name__ == "__main__":
    main()
