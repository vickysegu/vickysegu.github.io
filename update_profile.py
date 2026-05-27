#!/usr/bin/env python3
"""
Profil Dosen Integrator untuk GitHub Actions.
Menggabungkan data dari PDDIKTI, SINTA/Garuda, Semantic Scholar, dan link manual.
Tidak melakukan scraping Google Scholar (terlalu sering diblokir di CI/CD).
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

# ─── KONFIGURASI VIA ENVIRONMENT ──────────────────────────────────────────
NAMA_DOSEN = os.getenv("NAMA_DOSEN", "VICKY SETIA GUNAWAN")
NAMA_PT    = os.getenv("NAMA_PT",    "UNIVERSITAS PERINTIS INDONESIA")
PRODI      = os.getenv("PRODI",      "BISNIS DIGITAL")
SCHOLAR_ID = os.getenv("SCHOLAR_ID", "zxh3WngAAAAJ")

# ─── LOGGING ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ─── LINK MANUAL JURNAL (jika tidak terdeteksi otomatis) ─────────────────
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

# ─── STRUKTUR OUTPUT ──────────────────────────────────────────────────────
hasil = {
    "status": "error",
    "pesan": "",
    "profil": {},
    "pendidikan": [],
    "mengajar": [],
    "pengabdian": [],
    "publikasi": [],
}

# ─── HELPERS ─────────────────────────────────────────────────────────────

def cari_nilai_fleksibel(kamus_data: dict, daftar_kata_kunci: list, kecualikan: Optional[list] = None) -> str:
    """Ambil nilai dari dict berdasarkan beberapa kunci, dengan toleransi."""
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
    """Ubah string semester menjadi format 'Ganjil 2024/2025'."""
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

def request_with_retry(url: str, headers: dict = None, params: dict = None, max_retries: int = 3) -> Optional[requests.Response]:
    """Kirim GET request dengan mekanisme retry sederhana."""
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=20)
            if resp.status_code == 429:  # Too Many Requests
                wait = 10 * (attempt + 1)
                log.warning(f"Rate limited. Menunggu {wait} detik...")
                time.sleep(wait)
                continue
            return resp
        except requests.RequestException as e:
            log.warning(f"Request gagal (attempt {attempt+1}): {e}")
            time.sleep(5)
    return None

# ─── SITASI DARI SEMANTIC SCHOLAR ────────────────────────────────────────

def cari_sitasi_semantic_scholar(judul: str) -> str:
    """Cari jumlah sitasi di Semantic Scholar. Return '0' jika tidak ditemukan."""
    judul_clean = " ".join(judul.strip().rstrip('."').split())
    if not judul_clean:
        return "0"

    params = {
        "query": judul_clean,
        "fields": "title,year,citationCount",
        "limit": 5,
    }
    headers = {"User-Agent": "GitHubActions-AcademicUpdater/1.0"}
    resp = request_with_retry("https://api.semanticscholar.org/graph/v1/paper/search", headers=headers, params=params)

    if resp and resp.status_code == 200:
        data = resp.json()
        papers = data.get("data", [])
        judul_lower = judul_clean.lower()
        for paper in papers:
            result_title = (paper.get("title") or "").lower()
            # Pencocokan berbasis kata (toleransi minimal 60% kata cocok)
            common = sum(1 for w in judul_lower.split() if w in result_title)
            total = len(judul_lower.split())
            if total > 0 and common / total >= 0.6:
                count = paper.get("citationCount", 0)
                return str(count) if count else "0"
    return "0"

def enrichment_sitasi_batch(daftar_publikasi: list) -> list:
    """Perbarui 'sitasi' untuk semua publikasi, dengan rate limit 1 req/detik."""
    log.info(f"Memperkaya sitasi untuk {len(daftar_publikasi)} publikasi...")
    for i, pub in enumerate(daftar_publikasi):
        if pub.get("sitasi", "0") not in ("0", "", None):
            log.debug(f"[{i+1}] Sudah ada sitasi ({pub['sitasi']}): {pub['judul'][:50]}...")
            continue
        sitasi = cari_sitasi_semantic_scholar(pub["judul"])
        pub["sitasi"] = sitasi
        log.info(f"[{i+1}] {sitasi} sitasi: {pub['judul'][:60]}...")
        time.sleep(1.2)  # aman: 100 request/5 menit
    return daftar_publikasi

# ─── AKREDITASI SINTA VIA GARUDA ─────────────────────────────────────────

def cari_akreditasi_sinta_via_garuda(judul_artikel: str) -> str:
    """Ambil akreditasi SINTA dari portal Garuda."""
    judul_clean = " ".join(judul_artikel.strip().rstrip('.').split())
    if not judul_clean:
        return ""
    judul_encoded = urllib.parse.quote(judul_clean)
    url = f"https://garuda.kemdiktisaintek.go.id/documents?select=title&q={judul_encoded}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = request_with_retry(url, headers=headers)
        if resp and resp.status_code == 200:
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

# ─── CARI LINK MANUAL ────────────────────────────────────────────────────

def cari_link_manual(judul: str) -> str:
    """Cocokkan judul dengan daftar link manual."""
    judul_bersih = re.sub(r'[^\w\s]', '', judul).lower().strip()
    for simpan_judul, link in MANUAL_LINKS.items():
        simpan_bersih = re.sub(r'[^\w\s]', '', simpan_judul).lower().strip()
        if simpan_bersih in judul_bersih or judul_bersih in simpan_bersih:
            return link
    return ""

# ─── MAIN ────────────────────────────────────────────────────────────────

def main():
    log.info("Memulai sinkronisasi data dosen...")
    try:
        with api() as client:
            # Cari dosen
            results = client.search_dosen(keyword=NAMA_DOSEN)
            dosen_id = None
            if results:
                for dosen in results:
                    if NAMA_PT.lower() in dosen.get("nama_pt", "").lower():
                        hasil["profil"] = dosen
                        dosen_id = dosen.get("id")
                        hasil["status"] = "success"
                        break

            if not dosen_id:
                hasil["pesan"] = f"Dosen '{NAMA_DOSEN}' di PT '{NAMA_PT}' tidak ditemukan."
                log.error(hasil["pesan"])
                sys.exit(1)

            log.info(f"Dosen ditemukan: {dosen.get('nama')} (ID: {dosen_id})")

            # 1. Pendidikan
            try:
                pendidikan_raw = client.get_dosen_study_history(dosen_id)
                if pendidikan_raw:
                    pend_list = pendidikan_raw.get("data", []) if isinstance(pendidikan_raw, dict) else pendidikan_raw
                    for p in pend_list:
                        hasil["pendidikan"].append({
                            "jenjang": cari_nilai_fleksibel(p, ["gelar", "jenjang", "sp_satdik"], ["id", "kode"]),
                            "pt": cari_nilai_fleksibel(p, ["pt", "perguruan_tinggi"], ["id", "kode", "singkat"]).upper(),
                            "tahun": cari_nilai_fleksibel(p, ["tahun_lulus", "thn_lulus", "tahun"], ["id"]),
                            "prodi": cari_nilai_fleksibel(p, ["prodi", "nama_prodi", "program_studi", "bidang_studi"], ["id", "kode"]),
                        })
                    log.info(f"Pendidikan: {len(hasil['pendidikan'])} entri.")
            except Exception as e:
                log.error(f"Gagal mengambil pendidikan: {e}")

            # 2. Mengajar
            try:
                mengajar_raw = client.get_dosen_teaching_history(dosen_id)
                if mengajar_raw:
                    mengajar_list = mengajar_raw.get("data", []) if isinstance(mengajar_raw, dict) else mengajar_raw
                    matkul_tree = {}
                    for m in mengajar_list:
                        nama_matkul = cari_nilai_fleksibel(m, ["nama_mata_kuliah", "nm_mk", "mata_kuliah", "matkul"], ["kode", "id", "sks"]).title()
                        nama_kampus = cari_nilai_fleksibel(m, ["pt", "perguruan_tinggi", "kampus"], ["kode", "id", "singkat"]).upper()
                        semester_raw = cari_nilai_fleksibel(m, ["nama_semester", "semester", "smt", "id_smt"], ["id_mk", "kode"])
                        if nama_matkul not in ("N/A", "None"):
                            matkul_tree.setdefault(nama_kampus, {}).setdefault(nama_matkul, set())
                            if semester_raw not in ("N/A", "None"):
                                matkul_tree[nama_kampus][nama_matkul].add(parse_semester(semester_raw))
                    for kampus in sorted(matkul_tree):
                        mk_list = []
                        for mk in sorted(matkul_tree[kampus]):
                            sems = sorted(matkul_tree[kampus][mk], reverse=True)
                            mk_list.append({"nama": mk, "semester": ", ".join(sems) or "N/A"})
                        hasil["mengajar"].append({"nama_kampus": kampus, "mata_kuliah": mk_list})
                    log.info(f"Mengajar: {len(hasil['mengajar'])} kampus.")
            except Exception as e:
                log.error(f"Gagal mengambil mengajar: {e}")

            # 3. Pengabdian & publikasi (dari PDDIKTI)
            try:
                # Pengabdian resmi
                pengabdian_raw = client.get_dosen_pengabdian(dosen_id)
                if pengabdian_raw:
                    for p in (pengabdian_raw.get("data", []) if isinstance(pengabdian_raw, dict) else pengabdian_raw):
                        hasil["pengabdian"].append({
                            "judul": cari_nilai_fleksibel(p, ["judul"], ["id"]),
                            "tahun": cari_nilai_fleksibel(p, ["tahun"], ["id"]),
                            "kategori": "Pengabdian",
                        })

                # Karya (publikasi & penelitian internal)
                karya_pddikti = client.get_dosen_karya(dosen_id)
                if karya_pddikti:
                    for p in (karya_pddikti.get("data", []) if isinstance(karya_pddikti, dict) else karya_pddikti):
                        judul_keg = cari_nilai_fleksibel(p, ["judul"], ["id"])
                        jenis_keg = cari_nilai_fleksibel(p, ["jenis"], ["id", "kode"])
                        tahun_keg = cari_nilai_fleksibel(p, ["tahun"], ["id"])

                        if jenis_keg == "Hasil penelitian/pemikiran yang tidak dipublikasikan":
                            hasil["pengabdian"].append({
                                "judul": judul_keg,
                                "tahun": tahun_keg,
                                "kategori": "Penelitian Internal",
                            })
                        else:
                            tingkat = cari_akreditasi_sinta_via_garuda(judul_keg)
                            link = cari_link_manual(judul_keg)
                            hasil["publikasi"].append({
                                "judul": judul_keg,
                                "jenis": tingkat if tingkat else jenis_keg,
                                "tahun": tahun_keg,
                                "sitasi": "0",  # akan diperbarui
                                "link": link,
                            })
                log.info(f"Publikasi awal: {len(hasil['publikasi'])} | Pengabdian: {len(hasil['pengabdian'])}")
            except Exception as e:
                log.error(f"Gagal mengambil publikasi/pengabdian: {e}")

            # 4. Perkaya sitasi
            if hasil["publikasi"]:
                hasil["publikasi"] = enrichment_sitasi_batch(hasil["publikasi"])

    except Exception as e:
        hasil["status"] = "error"
        hasil["pesan"] = str(e)
        log.exception("Error utama:")

    # Tulis output
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(hasil, f, indent=4, ensure_ascii=False)

    log.info("✔ data.json berhasil dibuat.")
    # Jika dalam GitHub Actions, cetak ringkasan
    if os.getenv("GITHUB_ACTIONS"):
        print(f"::notice title=Profil Dosen::Status: {hasil['status']}, Publikasi: {len(hasil['publikasi'])}")

if __name__ == "__main__":
    main()
