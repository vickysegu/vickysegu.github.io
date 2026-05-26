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
                publikasi_scholar.append({
                    "judul": judul, "jenis": tingkat if tingkat else "Jurnal Ilmiah", "tahun": tahun, "sitasi": sitasi, "link": link
                })
    except:
        pass
    return publikasi_scholar

print("Memulai sinkronisasi terintegrasi...")

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
            hasil["pesan"] = "Profil Dosen tidak ditemukan."
        else:
            # 1. PENDIDIKAN
            try:
                pendidikan_raw = client.get_dosen_study_history(dosen_id)
                if pendidikan_raw:
                    p_list = pendidikan_raw.get('data', []) if isinstance(pendidikan_raw, dict) else pendidikan_raw
                    for p in p_list:
                        hasil["pendidikan"].append({
                            "jenjang": p.get('jenjang_pendidikan') or p.get('jenjang') or '-',
                            "kampus": p.get('nama_perguruan_tinggi') or p.get('kampus') or '-',
                            "gelar": p.get('gelar_akademik') or p.get('gelar') or '-',
                            "tahun": p.get('tahun_lulus') or '-'
                        })
            except Exception as e: print("Pendidikan Error:", e)

            # 2. MENGAJAR (Dikelompokkan)
            try:
                mengajar_raw = client.get_dosen_teaching_history(dosen_id)
                if mengajar_raw:
                    m_list = mengajar_raw.get('data', []) if isinstance(mengajar_raw, dict) else mengajar_raw
                    mk_dict = {}
                    for m in m_list:
                        mk = str(m.get('nama_mata_kuliah') or m.get('mata_kuliah') or '').strip().title()
                        smt = str(m.get('nama_semester') or m.get('id_semester') or '').strip()
                        if mk and mk != 'None':
                            if mk not in mk_dict: mk_dict[mk] = set()
                            if smt and smt != 'None': mk_dict[mk].add(smt)
                    
                    for mk, smts in mk_dict.items():
                        smt_list = sorted(list(smts), reverse=True)
                        hasil["mengajar"].append({"matkul": mk, "semester": ", ".join(smt_list)})
            except Exception as e: print("Mengajar Error:", e)

            # 3. PENGABDIAN
            pengabdian = client.get_dosen_pengabdian(dosen_id)
            if pengabdian:
                p_list = pengabdian.get('data', []) if isinstance(pengabdian, dict) else pengabdian
                for p in p_list:
                    hasil["pengabdian"].append({
                        "judul": p.get('judul_kegiatan', 'N/A'), "tahun": p.get('tahun_kegiatan') or 'N/A', "kategori": "Pengabdian"
                    })

            # 4. PUBLIKASI & INTERNAL
            data_scholar = ambil_data_scholar(scholar_id)
            if data_scholar:
                hasil["publikasi"] = data_scholar
                karya = client.get_dosen_karya(dosen_id)
                if karya:
                    k_list = karya.get('data', []) if isinstance(karya, dict) else karya
                    for k in k_list:
                        if k.get('jenis_kegiatan') == "Hasil penelitian/pemikiran yang tidak dipublikasikan":
                            hasil["pengabdian"].append({"judul": k.get('judul_kegiatan', ''), "tahun": k.get('tahun_kegiatan') or 'N/A', "kategori": "Penelitian Internal"})
            else:
                karya = client.get_dosen_karya(dosen_id)
                if karya:
                    k_list = karya.get('data', []) if isinstance(karya, dict) else karya
                    for k in k_list:
                        jdl = k.get('judul_kegiatan', '').strip()
                        jns = k.get('jenis_kegiatan', 'N/A')
                        thn = k.get('tahun_kegiatan') or 'N/A'
                        if jns == "Hasil penelitian/pemikiran yang tidak dipublikasikan":
                            hasil["pengabdian"].append({"judul": jdl, "tahun": thn, "kategori": "Penelitian Internal"})
                        else:
                            tkt = cari_akreditasi_sinta_via_garuda(jdl)
                            hasil["publikasi"].append({"judul": jdl, "jenis": tkt if tkt else jns, "tahun": thn})
            
            print("Proses ekstraksi selesai.")

except Exception as e:
    hasil["status"], hasil["pesan"] = "error", str(e)

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(hasil, f, indent=4, ensure_ascii=False)
