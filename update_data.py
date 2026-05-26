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
                        hasil["pendidikan"].append({
                            "jenjang": p.get('gelar_akademik') or p.get('jenjang_pendidikan') or 'N/A',
                            "pt": p.get('nama_perguruan_tinggi') or 'N/A',
                            "tahun": p.get('tahun_lulus') or 'N/A'
                        })
            except Exception as e:
                print(f"Peringatan riwayat pendidikan: {str(e)}")

            # 2. RIWAYAT MENGAJAR (Dengan Grouping Semester Terpadat)
            try:
                mengajar_raw = client.get_dosen_teaching_history(dosen_id)
                if mengajar_raw:
                    mengajar_list = mengajar_raw.get('data', []) if isinstance(mengajar_raw, dict) else mengajar_raw
                    matkul_dict = {}
                    
                    for m in mengajar_list:
                        nama_matkul = str(m.get('nama_mata_kuliah') or 'N/A').strip().title()
                        semester = str(m.get('nama_semester') or 'N/A')
                        
                        if nama_matkul != 'N/A' and nama_matkul != 'None':
                            if nama_matkul not in matkul_dict:
                                matkul_dict[nama_matkul] = set()
                            if semester != 'N/A' and semester != 'None':
                                matkul_dict[nama_matkul].add(semester)
                    
                    for matkul, sem_set in matkul_dict.items():
                        # Urutkan semester dari yang terbaru
                        sorted_sems = sorted(list(sem_set), reverse=True)
                        hasil["mengajar"].append({
                            "matkul": matkul,
                            "semester": ", ".join(sorted_sems) if sorted_sems else "N/A"
                        })
            except Exception as e:
                print(f"Peringatan riwayat mengajar: {str(e)}")

            # 3. RIWAYAT PENGABDIAN
            pengabdian = client.get_dosen_pengabdian(dosen_id)
            if pengabdian:
                pengabdian_list = pengabdian.get('data', []) if isinstance(pengabdian, dict) else pengabdian
                for p in pengabdian_list:
                    hasil["pengabdian"].append({
                        "judul": p.get('judul_kegiatan', 'N/A'),
                        "tahun": p.get('tahun_kegiatan') or p.get('tahun') or 'N/A',
                        "kategori": "Pengabdian"
                    })

            # 4. RIWAYAT PUBLIKASI (Hibrida Cerdas)
            data_scholar = ambil_data_scholar(scholar_id)
            if data_scholar:
                hasil["publikasi"] = data_scholar
                karya_pddikti = client.get_dosen_karya(dosen_id)
                if karya_pddikti:
                    karya_list = karya_pddikti.get('data', []) if isinstance(karya_pddikti, dict) else karya_pddikti
                    for p in karya_list:
                        if p.get('jenis_kegiatan') == "Hasil penelitian/pemikiran yang tidak dipublikasikan":
                            hasil["pengabdian"].append({
                                "judul": p.get('judul_kegiatan', ''),
                                "tahun": p.get('tahun_kegiatan') or p.get('tahun') or 'N/A',
                                "kategori": "Penelitian Internal"
                            })
            else:
                publikasi = client.get_dosen_karya(dosen_id)
                if publikasi:
                    publikasi_list = publikasi.get('data', []) if isinstance(publikasi, dict) else publikasi
                    for p in publikasi_list:
                        judul_keg = p.get('judul_kegiatan', '').strip()
                        jenis_keg = p.get('jenis_kegiatan', 'N/A')
                        tahun_keg = p.get('tahun_kegiatan') or p.get('tahun') or 'N/A'
                        
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
