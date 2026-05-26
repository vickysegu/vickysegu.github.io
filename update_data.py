import json
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from pddiktipy import api

# --- PARAMETER PENCARIAN DOSEN ---
nama_dosen = "VICKY SETIA GUNAWAN"
nama_pt = "UNIVERSITAS PERINTIS INDONESIA"
prodi = "BISNIS DIGITAL"
scholar_id = "zxh3WngAAAAJ"

hasil = {
    "status": "error",
    "pesan": "",
    "profil": {},
    "pendidikan": [],
    "mengajar": [],
    "pengabdian": [],
    "publikasi": []
}

def cari_nilai_fleksibel(kamus_data, daftar_kata_kunci, kecualikan=None):
    if kecualikan is None: kecualikan = []
    if not isinstance(kamus_data, dict): return 'N/A'
    
    for k in daftar_kata_kunci:
        if k in kamus_data and kamus_data[k]: 
            return str(kamus_data[k]).strip()
            
    for key, val in kamus_data.items():
        key_lower = key.lower()
        is_excluded = any(exc in key_lower for exc in kecualikan)
        if is_excluded: continue
            
        for k in daftar_kata_kunci:
            if k in key_lower and val:
                return str(val).strip()
    return 'N/A'

def parse_semester(sem_str):
    """Memecah string PDDIKTI menjadi Tahun Ajaran dan Tipe Semester (Ganjil/Genap)"""
    sem_str = str(sem_str).strip()
    thn_ajaran = "Tahun Tidak Diketahui"
    tipe = "Lainnya"
    
    # Deteksi pola 5 digit PDDIKTI (ex: 20231 -> 2023/2024 Ganjil)
    match_angka = re.match(r'^(\d{4})([123])$', sem_str)
    if match_angka:
        thn = int(match_angka.group(1))
        thn_ajaran = f"{thn}/{thn+1}"
        tipe_map = {'1': 'Ganjil', '2': 'Genap', '3': 'Pendek'}
        tipe = tipe_map.get(match_angka.group(2), "Lainnya")
        return thn_ajaran, tipe
    
    # Deteksi pola teks manual (ex: 2023/2024 Ganjil)
    match_thn = re.search(r'(\d{4})[/-](\d{4})', sem_str)
    if match_thn:
        thn_ajaran = f"{match_thn.group(1)}/{match_thn.group(2)}"
    else:
        match_thn_single = re.search(r'(\d{4})', sem_str)
        if match_thn_single:
            thn = int(match_thn_single.group(1))
            thn_ajaran = f"{thn}/{thn+1}"
            
    sem_lower = sem_str.lower()
    if 'ganjil' in sem_lower or 'gasal' in sem_lower or 'odd' in sem_lower: tipe = "Ganjil"
    elif 'genap' in sem_lower or 'even' in sem_lower: tipe = "Genap"
    elif 'pendek' in sem_lower or 'antara' in sem_lower: tipe = "Pendek"
        
    if thn_ajaran == "Tahun Tidak Diketahui" and tipe == "Lainnya": return "Periode", sem_str
    return thn_ajaran, tipe

def cari_akreditasi_sinta_via_garuda(judul_artikel):
    judul_clean = " ".join(judul_artikel.strip().rstrip('.').split())
    if not judul_clean: return ""
    judul_encoded = urllib.parse.quote(judul_clean)
    url = f"https://garuda.kemdiktisaintek.go.id/documents?select=title&q={judul_encoded}"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.find_all("a", href=True):
                if "/journal/view/" in link["href"]:
                    teks_badge = link.get_text().lower().strip()
                    match = re.search(r's(?:inta)?\s*([1-6])', teks_badge)
                    if match: return f"SINTA {match.group(1)}"
        return ""
    except:
        return ""

def ambil_data_scholar(scholar_id):
    publikasi_scholar = []
    url = f"https://scholar.google.com/citations?user={scholar_id}&hl=id&pagesize=100"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        req = requests.get(url, headers=headers, timeout=12)
        if req.status_code == 200:
            soup = BeautifulSoup(req.text, 'html.parser')
            for row in soup.find_all("tr", class_="gsc_a_tr"):
                title_elem = row.find("a", class_="gsc_a_at")
                if not title_elem: continue
                judul = title_elem.text.strip()
                link = "https://scholar.google.com" + title_elem['href']
                cites_elem = row.find("a", class_="gsc_a_ac")
                sitasi = cites_elem.text.strip() if cites_elem and cites_elem.text.strip() else "0"
                year_elem = row.find("span", class_="gsc_a_h")
                tahun = year_elem.text.strip() if year_elem and year_elem.text.strip() else "N/A"
                
                tingkat = cari_akreditasi_sinta_via_garuda(judul)
                jenis_keg = tingkat if tingkat else "Jurnal Ilmiah"
                publikasi_scholar.append({"judul": judul, "jenis": jenis_keg, "tahun": tahun, "sitasi": sitasi, "link": link})
    except:
        pass
    return publikasi_scholar

print("Memulai sinkronisasi terintegrasi (PDDIKTI + Scholar)...")

try:
    with api() as client:
        results = client.search_dosen(keyword=nama_dosen)
        dosen_id = None
        
        if results:
            for dosen in results:
                if (nama_pt.lower() in dosen.get('nama_pt', '').lower() and 
                    prodi.lower() in dosen.get('nama_prodi', '').lower()):
                    hasil["profil"] = dosen
                    dosen_id = dosen.get('id')
                    hasil["status"] = "success"
                    break
        
        if not dosen_id:
            hasil["pesan"] = "Profil Dosen tidak ditemukan pada basis data PDDIKTI."
        else:
            # 1. RIWAYAT PENDIDIKAN
            try:
                pendidikan_raw = client.get_dosen_study_history(dosen_id)
                if pendidikan_raw:
                    pend_list = pendidikan_raw.get('data', []) if isinstance(pendidikan_raw, dict) else pendidikan_raw
                    for p in pend_list:
                        jenjang = cari_nilai_fleksibel(p, ['gelar', 'jenjang', 'sp_satdik'], ['id', 'kode'])
                        kampus = cari_nilai_fleksibel(p, ['pt', 'perguruan_tinggi'], ['id', 'kode', 'singkat']).upper()
                        tahun_lulus = cari_nilai_fleksibel(p, ['tahun_lulus', 'thn_lulus', 'tahun'], ['id'])
                        hasil["pendidikan"].append({"jenjang": jenjang, "pt": kampus, "tahun": tahun_lulus})
            except Exception as e:
                print(f"Peringatan riwayat pendidikan: {str(e)}")

            # 2. RIWAYAT MENGAJAR (HIERARKI PARENT-CHILD)
            try:
                mengajar_raw = client.get_dosen_teaching_history(dosen_id)
                if mengajar_raw:
                    mengajar_list = mengajar_raw.get('data', []) if isinstance(mengajar_raw, dict) else mengajar_raw
                    tree_mengajar = {}
                    
                    # Bangun Pohon: Kampus -> Tahun Ajaran -> Semester -> Set(Matkul)
                    for m in mengajar_list:
                        nama_matkul = cari_nilai_fleksibel(m, ['nama_mata_kuliah', 'nm_mk', 'mata_kuliah', 'matkul'], kecualikan=['kode', 'id', 'sks']).title()
                        nama_kampus = cari_nilai_fleksibel(m, ['pt', 'perguruan_tinggi', 'kampus'], kecualikan=['kode', 'id', 'singkat']).upper()
                        semester_raw = cari_nilai_fleksibel(m, ['nama_semester', 'semester', 'smt', 'id_smt'], kecualikan=['id_mk', 'kode'])
                        
                        if nama_matkul != 'N/A' and nama_matkul != 'None':
                            thn_ajaran, tipe_sem = parse_semester(semester_raw)
                            
                            if nama_kampus not in tree_mengajar: tree_mengajar[nama_kampus] = {}
                            if thn_ajaran not in tree_mengajar[nama_kampus]: tree_mengajar[nama_kampus][thn_ajaran] = {}
                            if tipe_sem not in tree_mengajar[nama_kampus][thn_ajaran]: tree_mengajar[nama_kampus][thn_ajaran][tipe_sem] = set()
                            
                            tree_mengajar[nama_kampus][thn_ajaran][tipe_sem].add(nama_matkul)
                    
                    # Konversi Pohon ke List of Dictionaries untuk JSON
                    for kampus in sorted(tree_mengajar.keys()):
                        data_kampus = {"nama_kampus": kampus, "tahun_ajaran": []}
                        for thn in sorted(tree_mengajar[kampus].keys(), reverse=True): # Urut Tahun Terbaru
                            data_thn = {"tahun": thn, "semester": []}
                            for sem in sorted(tree_mengajar[kampus][thn].keys(), reverse=True): # Genap (2) sebelum Ganjil (1)
                                data_thn["semester"].append({
                                    "tipe": sem,
                                    "matkul": sorted(list(tree_mengajar[kampus][thn][sem]))
                                })
                            data_kampus["tahun_ajaran"].append(data_thn)
                        hasil["mengajar"].append(data_kampus)
            except Exception as e:
                print(f"Peringatan riwayat mengajar: {str(e)}")

            # 3. RIWAYAT PENGABDIAN
            try:
                pengabdian = client.get_dosen_pengabdian(dosen_id)
                if pengabdian:
                    pengabdian_list = pengabdian.get('data', []) if isinstance(pengabdian, dict) else pengabdian
                    for p in pengabdian_list:
                        judul = cari_nilai_fleksibel(p, ['judul'], ['id'])
                        tahun = cari_nilai_fleksibel(p, ['tahun'], ['id'])
                        hasil["pengabdian"].append({"judul": judul, "tahun": tahun, "kategori": "Pengabdian"})
            except Exception as e:
                pass

            # 4. RIWAYAT PUBLIKASI
            data_scholar = ambil_data_scholar(scholar_id)
            if data_scholar:
                hasil["publikasi"] = data_scholar
                karya_pddikti = client.get_dosen_karya(dosen_id)
                if karya_pddikti:
                    karya_list = karya_pddikti.get('data', []) if isinstance(karya_pddikti, dict) else karya_pddikti
                    for p in karya_list:
                        jenis = cari_nilai_fleksibel(p, ['jenis'], ['id', 'kode'])
                        if jenis == "Hasil penelitian/pemikiran yang tidak dipublikasikan":
                            hasil["pengabdian"].append({
                                "judul": cari_nilai_fleksibel(p, ['judul'], ['id']),
                                "tahun": cari_nilai_fleksibel(p, ['tahun'], ['id']),
                                "kategori": "Penelitian Internal"
                            })
            else:
                publikasi = client.get_dosen_karya(dosen_id)
                if publikasi:
                    publikasi_list = publikasi.get('data', []) if isinstance(publikasi, dict) else publikasi
                    for p in publikasi_list:
                        judul_keg = cari_nilai_fleksibel(p, ['judul'], ['id'])
                        jenis_keg = cari_nilai_fleksibel(p, ['jenis'], ['id', 'kode'])
                        tahun_keg = cari_nilai_fleksibel(p, ['tahun'], ['id'])
                        
                        if jenis_keg == "Hasil penelitian/pemikiran yang tidak dipublikasikan":
                            hasil["pengabdian"].append({"judul": judul_keg, "tahun": tahun_keg, "kategori": "Penelitian Internal"})
                        else:
                            tingkat = cari_akreditasi_sinta_via_garuda(judul_keg)
                            hasil["publikasi"].append({"judul": judul_keg, "jenis": tingkat if tingkat else jenis_keg, "tahun": tahun_keg})

except Exception as e:
    hasil["status"] = "error"
    hasil["pesan"] = str(e)

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(hasil, f, indent=4, ensure_ascii=False)

print("File data.json hierarkis sukses diperbarui!")
