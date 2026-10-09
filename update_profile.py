#!/usr/bin/env python3
"""
Profil Dosen Integrator untuk GitHub Actions (versi final).
Menggabungkan kekuatan dari update_data.py + update_profile.py.

Sumber data:
- PDDIKTI (via pddiktipy)         : daftar karya, mengajar, pendidikan, pengabdian
- OpenAlex API                    : sitasi + link (gratis, tanpa key, limit longgar)
- Semantic Scholar API            : fallback sitasi
- Portal Garuda Kemdiktisaintek   : akreditasi SINTA
- MANUAL_LINKS                    : fallback link terakhir (benteng terakhir)

Fitur:
- Logging terstruktur
- Retry otomatis untuk request 429/5xx
- Fuzzy matching judul (toleran typo & variasi)
- Dedupe publikasi & pengabdian
- Nama mata kuliah dipertahankan apa adanya dari PDDIKTI
"""

import json
import logging
import os
import re
import sys
import time
import urllib.parse
from typing import Optional

import requests
from bs4 import BeautifulSoup
from pddiktipy import api

# ═══════════════════════════════════════════════════════════════════════════
# KONFIGURASI VIA ENV
# ═══════════════════════════════════════════════════════════════════════════
NAMA_DOSEN  = os.getenv("NAMA_DOSEN",  "VICKY SETIA GUNAWAN")
NAMA_PT     = os.getenv("NAMA_PT",     "UNIVERSITAS PERINTIS INDONESIA")
PRODI       = os.getenv("PRODI",       "BISNIS DIGITAL")
SCHOLAR_ID  = os.getenv("SCHOLAR_ID",  "zxh3WngAAAAJ")
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "data.json")

USER_AGENT  = "GitHubActions-ProfileUpdater/1.0 (+https://github.com/vickysegu)"

# ═══════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# FALLBACK LINK MANUAL (BENTENG TERAKHIR)
# ═══════════════════════════════════════════════════════════════════════════
MANUAL_LINKS = {
    "Beyond experience: how customer engagement transforms AI interactions into Generation Z loyalty":
        "https://scholar.google.com/citations?view_op=view_citation&hl=id&user=zxh3WngAAAAJ&citation_for_view=zxh3WngAAAAJ:d1gIgvwA3N8C",
    "Easily Determining Post-Study System Usability for Anime Community E-Commerce Analysis":
        "https://scholar.google.com/citations?view_op=view_citation&hl=id&user=zxh3WngAAAAJ&citation_for_view=zxh3WngAAAAJ:9yKSN-GCB0IC",
    "Implementasi Sistem Informasi Administrasi Pembayaran SPP Pada SDIT Darul Hikmah Metode Rapid Application Development (RAD)":
        "https://scholar.google.com/citations?view_op=view_citation&hl=id&user=zxh3WngAAAAJ&citation_for_view=zxh3WngAAAAJ:qjMakFHDy7sC",
    "Metode Waterfall Untuk Meningkatkan Kualitas Layanan Nikah dan Rujuk Pada Kantor Urusan Agama (KUA) Kec. Lubuk Batu Jaya":
        "https://scholar.google.com/citations?view_op=view_citation&hl=id&user=zxh3WngAAAAJ&citation_for_view=zxh3WngAAAAJ:2osOgNQ5qMEC",
    "Penerapan Metode Topsis Dalam Menentukan Kualitas Gambir":
        "https://scholar.google.com/citations?view_op=view_citation&hl=id&user=zxh3WngAAAAJ&citation_for_view=zxh3WngAAAAJ:UeHWp8X0CEIC",
    "Sistem Penunjang Keputusan dalam Optimalisasi Pemberian Insentif terhadap Pemasok Menggunakan Metode TOPSIS":
        "https://scholar.google.com/citations?view_op=view_citation&hl=id&user=zxh3WngAAAAJ&citation_for_view=zxh3WngAAAAJ:u5y6OjeaXhIC",
    "Implementasi Metode Prototype dalam Pengembangan Sistem Informasi Inventaris Obat di Apotek Syira Farma":
        "https://scholar.google.com/citations?view_op=view_citation&hl=id&user=zxh3WngAAAAJ&citation_for_view=zxh3WngAAAAJ:Tyk-4Ss8FVUC",
    "RANCANG BANGUN ARSITEKTUR SISTEM INFORMASI MARKETPLACE JASA FOTOGRAFI BERBASIS WEB":
        "https://scholar.google.com/citations?view_op=view_citation&hl=id&user=zxh3WngAAAAJ&citation_for_view=zxh3WngAAAAJ:Y0pCki6q_DkC",
    "INTERNET OF THINGS: Konsep, Implementasi dan Arah Masa Depan":
        "https://scholar.google.com/citations?view_op=view_citation&hl=id&user=zxh3WngAAAAJ&citation_for_view=zxh3WngAAAAJ:W7OEmFMy1HYC",
}

# ═══════════════════════════════════════════════════════════════════════════
# STRUKTUR OUTPUT
# ═══════════════════════════════════════════════════════════════════════════
hasil = {
    "status": "error",
    "pesan": "",
    "profil": {},
    "pendidikan": [],
    "mengajar": [],
    "pengabdian": [],
    "publikasi": [],
}


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS UMUM
# ═══════════════════════════════════════════════════════════════════════════

def cari_nilai_fleksibel(kamus_data: dict, daftar_kata_kunci: list,
                         kecualikan: Optional[list] = None) -> str:
    """Cari nilai dari dict dengan berbagai kemungkinan nama key."""
    if kecualikan is None:
        kecualikan = []
    if not isinstance(kamus_data, dict):
        return "N/A"
    for k in daftar_kata_kunci:
        if k in kamus_data and kamus_data[k]:
            return str(kamus_data[k]).strip()
    for key, val in kamus_data.items():
        key_lower = key.lower()
        if any(exc in key_lower for exc in kecualikan):
            continue
        for k in daftar_kata_kunci:
            if k in key_lower and val:
                return str(val).strip()
    return "N/A"


def parse_semester(sem_str: str) -> str:
    """Normalisasi string semester → 'Ganjil 2024/2025' dst."""
    sem_str = str(sem_str).strip()
    thn_ajaran, tipe = "", ""
    match_angka = re.match(r"^(\d{4})([123])$", sem_str)
    if match_angka:
        thn = int(match_angka.group(1))
        tipe = {"1": "Ganjil", "2": "Genap", "3": "Pendek"}.get(match_angka.group(2), "")
        return f"{tipe} {thn}/{thn+1}".strip()
    match_thn = re.search(r"(\d{4})[/-](\d{4})", sem_str)
    if match_thn:
        thn_ajaran = f"{match_thn.group(1)}/{match_thn.group(2)}"
    else:
        m = re.search(r"(\d{4})", sem_str)
        if m:
            thn = int(m.group(1))
            thn_ajaran = f"{thn}/{thn+1}"
    sem_lower = sem_str.lower()
    if "ganjil" in sem_lower or "gasal" in sem_lower or "odd" in sem_lower:
        tipe = "Ganjil"
    elif "genap" in sem_lower or "even" in sem_lower:
        tipe = "Genap"
    elif "pendek" in sem_lower or "antara" in sem_lower:
        tipe = "Pendek"
    return f"{tipe} {thn_ajaran}".strip() if thn_ajaran else sem_str


def request_with_retry(url: str, headers: Optional[dict] = None,
                       params: Optional[dict] = None,
                       max_retries: int = 3, timeout: int = 20) -> Optional[requests.Response]:
    """GET dengan retry otomatis untuk 429/error jaringan."""
    if headers is None:
        headers = {"User-Agent": USER_AGENT}
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                log.warning(f"Rate limited. Menunggu {wait} detik...")
                time.sleep(wait)
                continue
            return resp
        except requests.RequestException as e:
            log.warning(f"Request gagal (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
    return None


def _normalize_judul(s: str) -> str:
    """Bersihkan judul untuk matching (lowercase, tanpa tanda baca, spasi rapat)."""
    return re.sub(r"[^\w\s]", "", s or "").lower().strip()


def _fuzzy_ratio(a: str, b: str) -> float:
    """Rasio kecocokan kata antara dua judul (0.0 – 1.0)."""
    wa, wb = a.split(), b.split()
    if not wa or not wb:
        return 0.0
    return sum(1 for w in wa if w in wb) / len(wa)


# ═══════════════════════════════════════════════════════════════════════════
# ENRICHMENT: OPENALEX (UTAMA) + SEMANTIC SCHOLAR (FALLBACK) + MANUAL
# ═══════════════════════════════════════════════════════════════════════════

def cari_data_openalex(judul: str) -> dict:
    """Cari sitasi + link via OpenAlex. Return {'sitasi': '0', 'link': ''} jika gagal."""
    judul_clean = " ".join((judul or "").strip().rstrip('."').split())
    if not judul_clean:
        return {"sitasi": "0", "link": ""}

    params = {
        "filter": f"title.search:{judul_clean}",
        "mailto": "github-actions-bot@example.com",
        "per-page": 3,
    }
    resp = request_with_retry("https://api.openalex.org/works", params=params, timeout=15)
    if not resp or resp.status_code != 200:
        return {"sitasi": "0", "link": ""}

    try:
        data = resp.json()
    except Exception:
        return {"sitasi": "0", "link": ""}

    judul_norm = _normalize_judul(judul_clean)
    for paper in data.get("results", []):
        title_api = _normalize_judul(paper.get("title") or "")
        if _fuzzy_ratio(judul_norm, title_api) >= 0.6:
            sitasi = str(paper.get("cited_by_count", 0) or 0)
            link = paper.get("doi") or ""
            if not link and paper.get("primary_location"):
                link = paper["primary_location"].get("landing_page_url") or ""
            return {"sitasi": sitasi, "link": link}
    return {"sitasi": "0", "link": ""}


def cari_sitasi_semantic_scholar(judul: str) -> str:
    """Fallback sitasi via Semantic Scholar."""
    judul_clean = " ".join((judul or "").strip().rstrip('."').split())
    if not judul_clean:
        return "0"
    params = {"query": judul_clean, "fields": "title,citationCount", "limit": 5}
    resp = request_with_retry(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params=params, timeout=15,
    )
    if not resp or resp.status_code != 200:
        return "0"
    try:
        papers = resp.json().get("data", [])
    except Exception:
        return "0"
    judul_norm = _normalize_judul(judul_clean)
    for paper in papers:
        title_api = _normalize_judul(paper.get("title") or "")
        if _fuzzy_ratio(judul_norm, title_api) >= 0.6:
            return str(paper.get("citationCount", 0) or 0)
    return "0"


def cari_link_manual(judul: str) -> str:
    """Cocokkan judul dengan MANUAL_LINKS (fuzzy)."""
    judul_norm = _normalize_judul(judul)
    if not judul_norm:
        return ""
    for stored_title, link in MANUAL_LINKS.items():
        stored_norm = _normalize_judul(stored_title)
        if stored_norm in judul_norm or judul_norm in stored_norm:
            return link
    return ""


def enrichment_publikasi(daftar_publikasi: list) -> list:
    """Perkaya sitasi + link untuk setiap publikasi."""
    total = len(daftar_publikasi)
    log.info(f"Memperkaya {total} publikasi (sitasi + link)...")

    for i, pub in enumerate(daftar_publikasi):
        judul = pub.get("judul", "")
        need_sitasi = pub.get("sitasi", "0") in ("0", "", None)
        need_link = not pub.get("link")

        if not need_sitasi and not need_link:
            log.debug(f"  [{i+1}/{total}] Lengkap: {judul[:50]}...")
            continue

        log.info(f"  [{i+1}/{total}] Melacak: {judul[:50]}...")

        # 1) OpenAlex — kasih sitasi + link sekaligus
        if need_sitasi or need_link:
            oa = cari_data_openalex(judul)
            time.sleep(0.3)  # sopan, OpenAlex longgar
            if need_sitasi and oa["sitasi"] != "0":
                pub["sitasi"] = oa["sitasi"]
                need_sitasi = False
            if need_link and oa["link"]:
                pub["link"] = oa["link"]
                need_link = False

        # 2) Semantic Scholar — fallback sitasi
        if need_sitasi:
            ss = cari_sitasi_semantic_scholar(judul)
            time.sleep(1.0)  # rate limit SS lebih ketat
            if ss != "0":
                pub["sitasi"] = ss
                need_sitasi = False

        # 3) MANUAL_LINKS — benteng terakhir
        if need_link:
            manual = cari_link_manual(judul)
            if manual:
                pub["link"] = manual
                need_link = False

        if need_sitasi:
            pub["sitasi"] = pub.get("sitasi") or "0"
        if need_link:
            pub["link"] = pub.get("link") or ""

    return daftar_publikasi


# ═══════════════════════════════════════════════════════════════════════════
# SINTA VIA GARUDA
# ═══════════════════════════════════════════════════════════════════════════

def cari_akreditasi_sinta_via_garuda(judul_artikel: str) -> str:
    judul_clean = " ".join((judul_artikel or "").strip().rstrip(".").split())
    if not judul_clean:
        return ""
    url = "https://garuda.kemdiktisaintek.go.id/documents"
    params = {"select": "title", "q": judul_clean}
    resp = request_with_retry(url, params=params, timeout=12)
    if not resp or resp.status_code != 200:
        return ""
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        for link in soup.find_all("a", href=True):
            if "/journal/view/" in link["href"]:
                teks = link.get_text().lower().strip()
                m = re.search(r"s(?:inta)?\s*([1-6])", teks)
                if m:
                    return f"SINTA {m.group(1)}"
    except Exception:
        pass
    return ""


# ═══════════════════════════════════════════════════════════════════════════
# DEDUPE & NORMALISASI
# ═══════════════════════════════════════════════════════════════════════════

def dedupe_publikasi(daftar: list) -> list:
    """Gabung publikasi dengan judul mirip, ambil data terlengkap."""
    hasil_dd: dict = {}
    for pub in daftar:
        key = _normalize_judul(pub.get("judul", ""))
        if not key:
            continue
        # Key alternatif: 8 kata pertama (untuk tangkap judul yang beda suffix)
        key_alt = " ".join(key.split()[:8])
        existing = hasil_dd.get(key) or hasil_dd.get(key_alt)

        if existing:
            # Gabung: ambil link yang tidak kosong
            if pub.get("link") and not existing.get("link"):
                existing["link"] = pub["link"]
            # Ambil sitasi tertinggi (numerik)
            try:
                cur_sit = int(existing.get("sitasi") or 0)
                new_sit = int(pub.get("sitasi") or 0)
                if new_sit > cur_sit:
                    existing["sitasi"] = str(new_sit)
            except (ValueError, TypeError):
                pass
            # Prefer jenis "terakreditasi" daripada "Lain-lain"
            if "terakreditasi" in (pub.get("jenis") or "").lower():
                existing["jenis"] = pub["jenis"]
            # Prefer tahun terbaru
            try:
                if int(pub.get("tahun") or 0) > int(existing.get("tahun") or 0):
                    existing["tahun"] = pub["tahun"]
            except (ValueError, TypeError):
                pass
        else:
            hasil_dd[key] = dict(pub)

    return list(hasil_dd.values())


def dedupe_pengabdian(daftar: list) -> list:
    """Gabung pengabdian dengan judul mirip."""
    hasil_dd: dict = {}
    for item in daftar:
        key = _normalize_judul(item.get("judul", ""))
        if not key:
            continue
        key_alt = " ".join(key.split()[:6])
        existing = hasil_dd.get(key) or hasil_dd.get(key_alt)

        if existing:
            # Prefer kategori "Pengabdian" daripada "Penelitian Internal"
            if existing.get("kategori") == "Penelitian Internal" \
               and item.get("kategori") == "Pengabdian":
                existing["kategori"] = "Pengabdian"
            # Prefer tahun lebih awal (asli)
            try:
                if item.get("tahun") and (not existing.get("tahun")
                   or int(item["tahun"]) < int(existing.get("tahun") or 9999)):
                    existing["tahun"] = item["tahun"]
            except (ValueError, TypeError):
                pass
        else:
            hasil_dd[key] = dict(item)

    return list(hasil_dd.values())


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main() -> int:
    log.info("=" * 60)
    log.info("Memulai sinkronisasi profil dosen")
    log.info(f"  Nama    : {NAMA_DOSEN}")
    log.info(f"  PT      : {NAMA_PT}")
    log.info(f"  Prodi   : {PRODI}")
    log.info(f"  Output  : {OUTPUT_FILE}")
    log.info("=" * 60)

    try:
        with api() as client:
            results = client.search_dosen(keyword=NAMA_DOSEN)
            dosen_id = None
            dosen = None

            if results:
                for d in results:
                    if NAMA_PT.lower() in (d.get("nama_pt") or "").lower():
                        dosen = d
                        hasil["profil"] = d
                        dosen_id = d.get("id")
                        hasil["status"] = "success"
                        break

            if not dosen_id:
                msg = f"Dosen '{NAMA_DOSEN}' di PT '{NAMA_PT}' tidak ditemukan."
                hasil["pesan"] = msg
                log.error(msg)
                _write_output()
                return 1

            log.info(f"✓ Dosen ditemukan: {dosen.get('nama')} (ID: {dosen_id})")

            # ── 1. PENDIDIKAN ────────────────────────────────────────────
            try:
                pendidikan_raw = client.get_dosen_study_history(dosen_id)
                if pendidikan_raw:
                    pend_list = pendidikan_raw.get("data", []) \
                        if isinstance(pendidikan_raw, dict) else pendidikan_raw
                    for p in pend_list:
                        hasil["pendidikan"].append({
                            "jenjang": cari_nilai_fleksibel(p, ["gelar", "jenjang", "sp_satdik"], ["id", "kode"]),
                            "pt":      cari_nilai_fleksibel(p, ["pt", "perguruan_tinggi"], ["id", "kode", "singkat"]).upper(),
                            "tahun":   cari_nilai_fleksibel(p, ["tahun_lulus", "thn_lulus", "tahun"], ["id"]),
                            "prodi":   cari_nilai_fleksibel(p, ["prodi", "nama_prodi", "program_studi", "bidang_studi"], ["id", "kode"]),
                        })
                    log.info(f"✓ Pendidikan: {len(hasil['pendidikan'])} entri")
            except Exception as e:
                log.error(f"✗ Gagal ambil pendidikan: {e}")

            # ── 2. MENGAJAR ──────────────────────────────────────────────
            try:
                mengajar_raw = client.get_dosen_teaching_history(dosen_id)
                if mengajar_raw:
                    mengajar_list = mengajar_raw.get("data", []) \
                        if isinstance(mengajar_raw, dict) else mengajar_raw
                    matkul_tree: dict = {}
                    for m in mengajar_list:
                        # Nama matkul TIDAK di-.title() → biarkan PDDIKTI yang kasih nama asli
                        nama_matkul = cari_nilai_fleksibel(
                            m,
                            ["nama_mata_kuliah", "nm_mk", "mata_kuliah", "matkul"],
                            ["kode", "id", "sks"],
                        )
                        nama_kampus = cari_nilai_fleksibel(
                            m, ["pt", "perguruan_tinggi", "kampus"],
                            ["kode", "id", "singkat"],
                        ).upper()
                        semester_raw = cari_nilai_fleksibel(
                            m, ["nama_semester", "semester", "smt", "id_smt"],
                            ["id_mk", "kode"],
                        )

                        if nama_matkul not in ("N/A", "None", ""):
                            matkul_tree.setdefault(nama_kampus, {}).setdefault(nama_matkul, set())
                            if semester_raw not in ("N/A", "None", ""):
                                matkul_tree[nama_kampus][nama_matkul].add(parse_semester(semester_raw))

                    for kampus in sorted(matkul_tree):
                        mk_list = []
                        for mk in sorted(matkul_tree[kampus]):
                            sems = sorted(matkul_tree[kampus][mk], reverse=True)
                            mk_list.append({"nama": mk, "semester": ", ".join(sems) or "N/A"})
                        hasil["mengajar"].append({"nama_kampus": kampus, "mata_kuliah": mk_list})
                    log.info(f"✓ Mengajar: {len(hasil['mengajar'])} kampus")
            except Exception as e:
                log.error(f"✗ Gagal ambil mengajar: {e}")

            # ── 3. PENGABDIAN + PUBLIKASI ────────────────────────────────
            try:
                # Pengabdian resmi
                pengabdian_raw = client.get_dosen_pengabdian(dosen_id)
                if pengabdian_raw:
                    for p in (pengabdian_raw.get("data", []) if isinstance(pengabdian_raw, dict) else pengabdian_raw):
                        hasil["pengabdian"].append({
                            "judul":    cari_nilai_fleksibel(p, ["judul"], ["id"]),
                            "tahun":    cari_nilai_fleksibel(p, ["tahun"], ["id"]),
                            "kategori": "Pengabdian",
                        })

                # Karya ilmiah dari PDDIKTI
                karya_pddikti = client.get_dosen_karya(dosen_id)
                if karya_pddikti:
                    for p in (karya_pddikti.get("data", []) if isinstance(karya_pddikti, dict) else karya_pddikti):
                        judul_keg = cari_nilai_fleksibel(p, ["judul"], ["id"])
                        jenis_keg = cari_nilai_fleksibel(p, ["jenis"], ["id", "kode"])
                        tahun_keg = cari_nilai_fleksibel(p, ["tahun"], ["id"])

                        if jenis_keg == "Hasil penelitian/pemikiran yang tidak dipublikasikan":
                            hasil["pengabdian"].append({
                                "judul":    judul_keg,
                                "tahun":    tahun_keg,
                                "kategori": "Penelitian Internal",
                            })
                        else:
                            tingkat = cari_akreditasi_sinta_via_garuda(judul_keg)
                            link    = cari_link_manual(judul_keg)
                            hasil["publikasi"].append({
                                "judul":  judul_keg,
                                "jenis":  tingkat if tingkat else jenis_keg,
                                "tahun":  tahun_keg,
                                "sitasi": "0",
                                "link":   link,
                            })
                log.info(f"✓ Publikasi PDDIKTI: {len(hasil['publikasi'])}")
                log.info(f"✓ Pengabdian: {len(hasil['pengabdian'])}")
            except Exception as e:
                log.error(f"✗ Gagal ambil publikasi/pengabdian: {e}")

            # ── 4. ENRICHMENT (sitasi + link) ────────────────────────────
            if hasil["publikasi"]:
                hasil["publikasi"] = enrichment_publikasi(hasil["publikasi"])

            # ── 5. DEDUPE ────────────────────────────────────────────────
            if hasil["publikasi"]:
                before = len(hasil["publikasi"])
                hasil["publikasi"] = dedupe_publikasi(hasil["publikasi"])
                sesudah = len(hasil["publikasi"])
                if before != sesudah:
                    log.info(f"✓ Publikasi setelah dedupe: {sesudah} (dari {before})")

            if hasil["pengabdian"]:
                before = len(hasil["pengabdian"])
                hasil["pengabdian"] = dedupe_pengabdian(hasil["pengabdian"])
                sesudah = len(hasil["pengabdian"])
                if before != sesudah:
                    log.info(f"✓ Pengabdian setelah dedupe: {sesudah} (dari {before})")

    except Exception as e:
        hasil["status"] = "error"
        hasil["pesan"]  = str(e)
        log.exception("Error utama:")

    _write_output()
    log.info("=" * 60)
    log.info(f"✓ Selesai. {OUTPUT_FILE} diperbarui.")
    log.info("=" * 60)

    if os.getenv("GITHUB_ACTIONS"):
        print(f"::notice title=Profil Dosen::status={hasil['status']} | "
              f"publikasi={len(hasil['publikasi'])} | "
              f"mengajar={len(hasil['mengajar'])} | "
              f"pendidikan={len(hasil['pendidikan'])} | "
              f"pengabdian={len(hasil['pengabdian'])}")

    return 0


def _write_output():
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(hasil, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
