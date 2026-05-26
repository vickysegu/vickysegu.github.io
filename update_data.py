import json
import re
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup
from pddiktipy import api

# ─── PARAMETER PENCARIAN DOSEN ───────────────────────────────────────────────
nama_dosen = "VICKY SETIA GUNAWAN"
nama_pt    = "UNIVERSITAS PERINTIS INDONESIA"
prodi      = "BISNIS DIGITAL"
scholar_id = "zxh3WngAAAAJ"

# ─── FALLBACK LINK JURNAL ────────────────────────────────────────────────────
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

hasil = {
    "status": "error", "pesan": "",
    "profil": {}, "pendidikan": [],
    "mengajar": [], "pengabdian": [], "publikasi": []
}

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def cari_nilai_fleksibel(kamus_data, daftar_kata_kunci, kecualikan=None):
    if kecualikan is None: kecualikan = []
    if not isinstance(kamus_data, dict): return 'N/A'
    for k in daftar_kata_kunci:
        if k in kamus_data and kamus_data[k]: return str(kamus_data[k]).strip()
    for key, val in kamus_data.items():
        key_lower = key.lower()
        if any(exc in key_lower for exc in kecualikan): continue
        for k in daftar_kata_kunci:
            if k in key_lower and val: return str(val).strip()
    return 'N/A'

def parse_semester(sem_str):
    sem_str = str(sem_str).strip()
    thn_ajaran, tipe = "", ""
    match_angka = re.match(r'^(\d{4})([123])$', sem_str)
    if match_angka:
        thn = int(match_angka.group(1))
        tipe = {'1': 'Ganjil', '2': 'Genap', '3': 'Pendek'}.get(match_angka.group(2), "")
        return f"{tipe} {thn}/{thn+1}".strip()
    match_thn = re.search(r'(\d{4})[/-](\d{4})', sem_str)
    if match_thn:
        thn_ajaran = f"{match_thn.group(1)}/{match_thn.group(2)}"
    else:
        m = re.search(r'(\d{4})', sem_str)
        if m:
            thn = int(m.group(1))
            thn_ajaran = f"{thn}/{thn+1}"
    sem_lower = sem_str.lower()
    if   'ganjil' in sem_lower or 'gasal' in sem_lower or 'odd' in sem_lower: tipe = "Ganjil"
    elif 'genap'  in sem_lower or 'even'  in sem_lower:                        tipe = "Genap"
    elif 'pendek' in sem_lower or 'antara' in sem_lower:                       tipe = "Pendek"
    return f"{tipe} {thn_ajaran}".strip() if thn_ajaran else sem_str

# ─── SEMANTIC SCHOLAR API ─────────────────────────────────────────────────────
# Gratis, tidak memerlukan API key, tidak diblokir GitHub Actions.
# Docs: https://api.semanticscholar.org/api-docs/

def cari_sitasi_semantic_scholar(judul: str) -> str:
    """
    Cari jumlah sitasi dari Semantic Scholar berdasarkan judul.
    Return string angka sitasi, atau "0" jika tidak ditemukan.
    """
    judul_clean = " ".join(judul.strip().rstrip('."').split())
    if not judul_clean:
        return "0"
    params = {
        "query":  judul_clean,
        "fields": "title,year,citationCount",
        "limit":  5,
    }
    headers = {
        "User-Agent": "academic-profile-updater/1.0 (contact: github-actions)",
    }
    try:
        resp = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params=params, headers=headers, timeout=15
        )
        if resp.status_code == 200:
            data  = resp.json()
            papers = data.get("data", [])
            # Cocokan judul (fuzzy: cek apakah judul query ada di judul hasil)
            judul_lower = judul_clean.lower()
            for paper in papers:
                result_title = (paper.get("title") or "").lower()
                # Cukup 60% karakter judul cocok (toleransi typo/kapitalisasi)
                common = sum(1 for w in judul_lower.split() if w in result_title)
                total  = len(judul_lower.split())
                if total > 0 and common / total >= 0.6:
                    count = paper.get("citationCount", 0)
                    return str(count) if count else "0"
    except Exception as e:
        print(f"  [SemanticScholar] Gagal untuk '{judul[:50]}...': {e}")
    return "0"

def enrichment_sitasi_batch(daftar_publikasi: list) -> list:
    """
    Perbarui field 'sitasi' setiap publikasi menggunakan Semantic Scholar.
    Jaga rate-limit: 1 request/detik (batas bebas = 100 req/5 menit).
    """
    print(f"[SemanticScholar] Mengambil sitasi untuk {len(daftar_publikasi)} publikasi...")
    for i, pub in enumerate(daftar_publikasi):
        # Skip jika sudah punya sitasi valid dari Scholar scraping
        if pub.get("sitasi", "0") not in ("0", "", None):
            print(f"  [{i+1}] Sitasi sudah ada ({pub['sitasi']}): {pub['judul'][:50]}...")
            continue
        sitasi = cari_sitasi_semantic_scholar(pub["judul"])
        pub["sitasi"] = sitasi
        label = f"✓ {sitasi}" if sitasi != "0" else "— tidak ditemukan"
        print(f"  [{i+1}] {label}: {pub['judul'][:55]}...")
        time.sleep(1.1)   # rate-limit aman
    return daftar_publikasi

# ─── SINTA VIA GARUDA ────────────────────────────────────────────────────────

def cari_akreditasi_sinta_via_garuda(judul_artikel: str) -> str:
    judul_clean   = " ".join(judul_artikel.strip().rstrip('.').split())
    if not judul_clean: return ""
    judul_encoded = urllib.parse.quote(judul_clean)
    url = f"https://garuda.kemdiktisaintek.go.id/documents?select=title&q={judul_encoded}"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.find_all("a", href=True):
                if "/journal/view/" in link["href"]:
                    teks = link.get_text().lower().strip()
                    m    = re.search(r's(?:inta)?\s*([1-6])', teks)
                    if m: return f"SINTA {m.group(1)}"
    except: pass
    return ""

# ─── GOOGLE SCHOLAR SCRAPING (tetap dicoba, mungkin berhasil di lokal) ───────

def ambil_data_scholar(scholar_id: str) -> list:
    url     = f"https://scholar.google.com/citations?user={scholar_id}&hl=id&pagesize=100"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    }
    try:
        req  = requests.get(url, headers=headers, timeout=15)
        if req.status_code != 200:
            print(f"[Scholar] HTTP {req.status_code} — akan gunakan fallback pddikti + SemanticScholar")
            return []
        soup = BeautifulSoup(req.text, 'html.parser')
        rows = soup.find_all("tr", class_="gsc_a_tr")
        if not rows:
            print("[Scholar] Tidak ada baris terdeteksi (mungkin diblokir/CAPTCHA).")
            return []
        print(f"[Scholar] Berhasil: {len(rows)} publikasi ditemukan.")
        hasil_scholar = []
        for row in rows:
            title_el = row.find("a", class_="gsc_a_at")
            if not title_el: continue
            judul  = title_el.text.strip()
            link   = "https://scholar.google.com" + title_el['href']
            cite_el = row.find("a", class_="gsc_a_ac")
            sitasi = cite_el.text.strip() if cite_el and cite_el.text.strip() else "0"
            year_el = row.find("span", class_="gsc_a_h")
            tahun  = year_el.text.strip() if year_el and year_el.text.strip() else "N/A"
            tingkat = cari_akreditasi_sinta_via_garuda(judul)
            hasil_scholar.append({
                "judul":  judul,
                "jenis":  tingkat if tingkat else "Jurnal Ilmiah",
                "tahun":  tahun,
                "sitasi": sitasi,
                "link":   link,
            })
        return hasil_scholar
    except Exception as e:
        print(f"[Scholar] Exception: {e}")
        return []

# ─── MAIN ─────────────────────────────────────────────────────────────────────

print("Memulai sinkronisasi terintegrasi...")

try:
    with api() as client:
        results  = client.search_dosen(keyword=nama_dosen)
        dosen_id = None
        if results:
            for dosen in results:
                if nama_pt.lower() in dosen.get('nama_pt', '').lower():
                    hasil["profil"] = dosen
                    dosen_id = dosen.get('id')
                    hasil["status"] = "success"
                    break

        if dosen_id:

            # ── 1. PENDIDIKAN (+ prodi) ─────────────────────────────────────
            try:
                pendidikan_raw = client.get_dosen_study_history(dosen_id)
                if pendidikan_raw:
                    pend_list = pendidikan_raw.get('data', []) if isinstance(pendidikan_raw, dict) else pendidikan_raw
                    for p in pend_list:
                        jenjang     = cari_nilai_fleksibel(p, ['gelar', 'jenjang', 'sp_satdik'], ['id', 'kode'])
                        kampus      = cari_nilai_fleksibel(p, ['pt', 'perguruan_tinggi'], ['id', 'kode', 'singkat']).upper()
                        tahun_lulus = cari_nilai_fleksibel(p, ['tahun_lulus', 'thn_lulus', 'tahun'], ['id'])
                        nama_prodi  = cari_nilai_fleksibel(
                            p,
                            ['prodi', 'nama_prodi', 'program_studi', 'bidang_studi',
                             'sp_jenjang', 'nama_bidang', 'nm_prodi', 'bidang'],
                            ['id', 'kode']
                        )
                        hasil["pendidikan"].append({
                            "jenjang": jenjang, "pt": kampus,
                            "tahun": tahun_lulus, "prodi": nama_prodi,
                        })
            except Exception as e:
                print(f"[pendidikan] error: {e}")

            # ── 2. MENGAJAR ──────────────────────────────────────────────────
            try:
                mengajar_raw = client.get_dosen_teaching_history(dosen_id)
                if mengajar_raw:
                    mengajar_list = mengajar_raw.get('data', []) if isinstance(mengajar_raw, dict) else mengajar_raw
                    matkul_tree   = {}
                    for m in mengajar_list:
                        nama_matkul  = cari_nilai_fleksibel(m, ['nama_mata_kuliah', 'nm_mk', 'mata_kuliah', 'matkul'], ['kode', 'id', 'sks']).title()
                        nama_kampus  = cari_nilai_fleksibel(m, ['pt', 'perguruan_tinggi', 'kampus'], ['kode', 'id', 'singkat']).upper()
                        semester_raw = cari_nilai_fleksibel(m, ['nama_semester', 'semester', 'smt', 'id_smt'], ['id_mk', 'kode'])
                        if nama_matkul not in ('N/A', 'None'):
                            matkul_tree.setdefault(nama_kampus, {}).setdefault(nama_matkul, set())
                            if semester_raw not in ('N/A', 'None'):
                                matkul_tree[nama_kampus][nama_matkul].add(parse_semester(semester_raw))
                    for kampus in sorted(matkul_tree):
                        data_kampus = {"nama_kampus": kampus, "mata_kuliah": []}
                        for mk in sorted(matkul_tree[kampus]):
                            sems = sorted(matkul_tree[kampus][mk], reverse=True)
                            data_kampus["mata_kuliah"].append({"nama": mk, "semester": ", ".join(sems) or "N/A"})
                        hasil["mengajar"].append(data_kampus)
            except Exception as e:
                print(f"[mengajar] error: {e}")

            # ── 3. PENGABDIAN ────────────────────────────────────────────────
            try:
                pengabdian_raw = client.get_dosen_pengabdian(dosen_id)
                if pengabdian_raw:
                    for p in (pengabdian_raw.get('data', []) if isinstance(pengabdian_raw, dict) else pengabdian_raw):
                        hasil["pengabdian"].append({
                            "judul":    cari_nilai_fleksibel(p, ['judul'], ['id']),
                            "tahun":    cari_nilai_fleksibel(p, ['tahun'], ['id']),
                            "kategori": "Pengabdian",
                        })
            except Exception as e:
                print(f"[pengabdian] error: {e}")

            # ── 4. PUBLIKASI ─────────────────────────────────────────────────
            # Langkah A: coba Google Scholar dulu
            data_scholar = ambil_data_scholar(scholar_id)

            if data_scholar:
                # Scholar berhasil → pakai datanya, tapi tetap enrich sitasi via
                # Semantic Scholar untuk publikasi yang sitasinya masih 0
                hasil["publikasi"] = data_scholar

                # Ambil penelitian internal dari pddikti
                karya_pddikti = client.get_dosen_karya(dosen_id)
                if karya_pddikti:
                    for p in (karya_pddikti.get('data', []) if isinstance(karya_pddikti, dict) else karya_pddikti):
                        if cari_nilai_fleksibel(p, ['jenis'], ['id', 'kode']) == \
                           "Hasil penelitian/pemikiran yang tidak dipublikasikan":
                            hasil["pengabdian"].append({
                                "judul": cari_nilai_fleksibel(p, ['judul'], ['id']),
                                "tahun": cari_nilai_fleksibel(p, ['tahun'], ['id']),
                                "kategori": "Penelitian Internal",
                            })
            else:
                # Langkah B: Scholar diblokir → bangun daftar dari pddikti
                print("[fallback] Membangun daftar publikasi dari pddikti...")
                karya_pddikti = client.get_dosen_karya(dosen_id)
                if karya_pddikti:
                    for p in (karya_pddikti.get('data', []) if isinstance(karya_pddikti, dict) else karya_pddikti):
                        judul_keg = cari_nilai_fleksibel(p, ['judul'], ['id'])
                        jenis_keg = cari_nilai_fleksibel(p, ['jenis'], ['id', 'kode'])
                        tahun_keg = cari_nilai_fleksibel(p, ['tahun'], ['id'])

                        if jenis_keg == "Hasil penelitian/pemikiran yang tidak dipublikasikan":
                            hasil["pengabdian"].append({
                                "judul": judul_keg, "tahun": tahun_keg,
                                "kategori": "Penelitian Internal",
                            })
                        else:
                            tingkat = cari_akreditasi_sinta_via_garuda(judul_keg)

                            # Cari link manual
                            link_terselamatkan = ""
                            judul_lookup = judul_keg.lower().rstrip('.')
                            for dict_judul, dict_link in MANUAL_LINKS.items():
                                if dict_judul.lower().rstrip('.') in judul_lookup \
                                   or judul_lookup in dict_judul.lower():
                                    link_terselamatkan = dict_link
                                    break

                            hasil["publikasi"].append({
                                "judul":  judul_keg,
                                "jenis":  tingkat if tingkat else jenis_keg,
                                "tahun":  tahun_keg,
                                "sitasi": "0",          # akan diperbarui di bawah
                                "link":   link_terselamatkan,
                            })

            # ── Langkah C: Enrich SEMUA publikasi dengan Semantic Scholar ────
            # (bekerja baik Scholar berhasil maupun tidak)
            if hasil["publikasi"]:
                hasil["publikasi"] = enrichment_sitasi_batch(hasil["publikasi"])

except Exception as e:
    hasil["status"] = "error"
    hasil["pesan"]  = str(e)
    print(f"[ERROR] {e}")

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(hasil, f, indent=4, ensure_ascii=False)

print("✓ File data.json sukses diperbarui dengan sitasi dari Semantic Scholar!")
