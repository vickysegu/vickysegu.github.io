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
    """Mencari data secara pintar dengan mengecualikan kolom 'kode' atau 'id'"""
    if kecualikan is None: kecualikan = []
    if not isinstance(kamus_data, dict): return 'N/A'
    
    # 1. Coba kecocokan persis (Exact match) terlebih dahulu
    for k in daftar_kata_kunci:
        if k in kamus_data and kamus_data[k]: 
            return str(kamus_data[k]).strip()
            
    # 2. Coba kecocokan parsial (Fuzzy Search)
    for key, val in kamus_data.items():
        key_lower = key.lower()
        
        # Abaikan jika nama kolom mengandung kata terlarang (seperti 'kode' atau 'id')
        is_excluded = any(exc in key_lower for exc in kecualikan)
        if is_excluded:
            continue
            
        for k in daftar_kata_kunci:
            if k in key_lower and val:
                return str(val).strip()
    return 'N/A'

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
                    if match:
                        return f"SINTA {match.group(1)}"
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

            # 2. RIWAYAT MENGAJAR (Dengan Pengecualian Kata 'kode' dan 'id')
            try:
                mengajar_raw = client.get_dosen_teaching_history(dosen_id)
                if mengajar_raw:
                    mengajar_list = mengajar_raw.get('data', []) if isinstance(mengajar_raw, dict) else mengajar_raw
                    matkul_dict = {}
                    
                    for m in mengajar_list:
                        # Kunci Solusi: Mengecualikan kolom bernama "kode_mk" atau "id_mk"
                        nama_matkul = cari_nilai_fleksibel(m, ['nama_mata_kuliah', 'nm_mk', 'mata_kuliah', 'matkul'], kecualikan=['kode', 'id', 'sks']).title()
                        nama_kampus = cari_nilai_fleksibel(m, ['pt', 'perguruan_tinggi', 'kampus'], kecualikan=['kode', 'id', 'singkat']).upper()
                        semester = cari_nilai_fleksibel(m, ['nama_semester', 'semester', 'smt'], kecualikan=['id', 'kode'])
                        
                        if nama_matkul != 'N/a' and nama_matkul != 'None':
                            kunci = f"{nama_matkul} | {nama_kampus}"
                            if kunci not in matkul_dict:
                                matkul_dict[kunci] = {"matkul": nama_matkul, "kampus": nama_kampus, "semester": set()}
                            
                            if semester != 'N/A' and semester != 'None':
                                matkul_dict[kunci]["semester"].add(semester)
                    
                    for kunci, data_mk in matkul_dict.items():
                        sorted_sems = sorted(list(data_mk["semester"]), reverse=True)
                        hasil["mengajar"].append({
                            "matkul": data_mk["matkul"],
                            "kampus": data_mk["kampus"],
                            "semester": ", ".join(sorted_sems) if sorted_sems else "N/A"
                        })
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
                print(f"Peringatan riwayat pengabdian: {str(e)}")

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
            
            print("Ekstraksi data selesai.")

except Exception as e:
    hasil["status"] = "error"
    hasil["pesan"] = str(e)

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(hasil, f, indent=4, ensure_ascii=False)

print("File data.json sukses diperbarui!")
