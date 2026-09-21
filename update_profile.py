#!/usr/bin/env python3
"""Backup bulanan: merge data.json + enrich via OpenAlex & Crossref."""
import json, os, time, logging
from pathlib import Path
import requests

NAMA_DOSEN = os.getenv("NAMA_DOSEN", "VICKY SETIA GUNAWAN")
NAMA_PT    = os.getenv("NAMA_PT",    "UNIVERSITAS PERINTIS INDONESIA")
DATA_FILE  = "data.json"
UA = {"User-Agent": "ProfilDosen-Updater/3.0"}

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

_hits = 0
def get_json(url, params=None, retries=2):
    global _hits
    if _hits >= 3:
        log.warning("Terlalu banyak 429, berhenti memanggil API.")
        return None
    for i in range(retries+1):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=20)
            if r.status_code == 200: return r.json()
            if r.status_code == 429:
                _hits += 1; time.sleep(5*(i+1)); continue
            return None
        except Exception: time.sleep(1)
    return None

def enrich_openalex(judul):
    clean = " ".join(judul.strip().rstrip('.').split())
    if not clean: return "0", ""
    d = get_json("https://api.openalex.org/works",
                 params={"search": clean, "per-page": 3,
                         "mailto": "vicky@example.com"})
    if not d: return "0", ""
    jl = clean.lower(); words = [w for w in jl.split() if len(w)>2]
    for w in d.get("results", []):
        t = (w.get("title") or "").lower()
        common = sum(1 for x in words if x in t)
        if words and common/len(words) >= 0.6:
            cit = str(w.get("cited_by_count", 0) or 0)
            doi = w.get("doi") or ""
            if not doi and w.get("primary_location"):
                doi = w["primary_location"].get("landing_page_url","") or ""
            return cit, doi
    return "0", ""

def enrich_crossref(judul):
    clean = " ".join(judul.strip().rstrip('.').split())
    if not clean: return "0", ""
    d = get_json("https://api.crossref.org/works",
                 params={"query.bibliographic": clean, "rows": 3,
                         "mailto": "vicky@example.com"})
    if not d: return "0", ""
    words = [w for w in clean.lower().split() if len(w)>2]
    for it in (d.get("message") or {}).get("items", []):
        titles = it.get("title") or []
        if not titles: continue
        t = titles[0].lower()
        common = sum(1 for x in words if x in t)
        if words and common/len(words) >= 0.6:
            cit = str(it.get("is-referenced-by-count", 0) or 0)
            doi = it.get("DOI","")
            return cit, (f"https://doi.org/{doi}" if doi else "")
    return "0", ""

def enrich_publikasi(arr):
    log.info(f"Enrich {len(arr)} publikasi...")
    for i, p in enumerate(arr, 1):
        butuh_cit  = not p.get("sitasi") or p["sitasi"] in ("0", 0)
        butuh_link = not p.get("link")
        if not butuh_cit and not butuh_link: continue
        cit, doi = enrich_openalex(p.get("judul",""))
        if butuh_cit and cit != "0": p["sitasi"] = cit; butuh_cit = False
        if butuh_link and doi: p["link"] = doi; butuh_link = False
        if butuh_cit or butuh_link:
            cit2, doi2 = enrich_crossref(p.get("judul",""))
            if butuh_cit and cit2 != "0": p["sitasi"] = cit2
            if butuh_link and doi2: p["link"] = doi2
        log.info(f"  [{i}/{len(arr)}] ✓{p.get('sitasi','0')} {p.get('judul','')[:55]}")
        time.sleep(1.5)
    return arr

def main():
    p = Path(DATA_FILE)
    if not p.exists():
        log.error(f"{DATA_FILE} tidak ditemukan. Jalankan editor dulu.")
        return
    with open(p, encoding="utf-8") as f:
        data = json.load(f)

    # Enrich publikasi
    if data.get("publikasi"):
        data["publikasi"] = enrich_publikasi(data["publikasi"])

    # Simpan
    data["status"] = "success"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    log.info(f"✔ {DATA_FILE} diperbarui.")

if __name__ == "__main__":
    main()
