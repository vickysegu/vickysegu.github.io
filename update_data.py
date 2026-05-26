import json
import requests
from bs4 import BeautifulSoup
from pddiktipy import api

# --- PARAMETER PENCARIAN DOSEN ---
nama_dosen = "VICKY SETIA GUNAWAN"
nama_pt = "UNIVERSITAS PERINTIS INDONESIA"
prodi = "BISNIS DIGITAL"
scholar_id = "zxh3WngAAAAJ"  # ID Google Scholar Anda

# --- KAMUS PEMETAAN SINTA MANUAL ---
PETA_SINTA_MANUAL = {
    "Penerapan Metode Topsis Dalam Menentukan Kualitas Gambir": "SINTA 3",
    "Sistem Penunjang Keputusan dalam Optimalisasi Pemberian Insentif terhadap Pemasok Menggunakan Metode TOPSIS": "SINTA 4",
    "Easily Determining Post-Study System Usability for Anime Community E-Commerce Analysis": "SINTA 3",
    "Implementasi Sistem Informasi Administrasi Pembayaran SPP Pada SDIT Darul Hikmah Metode Rapid Application Development (RAD)": "SINTA 4",
    "Beyond experience: how customer engagement transforms AI interactions into Generation Z loyalty": "SINTA 2",
    "Implementasi Metode Prototype dalam Pengembangan Sistem Informasi Inventaris Obat di Apotek Syira Farma.": "SINTA 4",
    "Metode Waterfall Untuk Meningkatkan Kualitas Layanan Nikah dan Rujuk Pada Kantor Urusan Agama (KUA) Kec. Lubuk Batu Jaya": "SINTA 5",
    "Perancangan Aplikasi Jual Beli Tandan Buah Sawit (Tbs) Pada Pengepul H. Muslimin Berbasis Web": "SINTA 5",
    "RANCANG BANGUN ARSITEKTUR SISTEM INFORMASI MARKETPLACE JASA FOTOGRAFI BERBASIS WEB": "SINTA 4",
    "PENERAPAN WEB TRANSAKSI TANDAN BUAH SAWIT (TBS) PADA PENGEPUL H. MUSLIMIN": "Lain-lain",
    "INTERNET OF THINGS: Konsep, Implementasi dan Arah Masa Depan": "Buku Referensi"
}

hasil = {
    "status": "error",
    "pesan": "",
    "profil": {},
    "pengabdian": [],
    "publikasi": []
}

def ambil_data_scholar(scholar_id):
    """Mencoba mengambil data publikasi, link, dan sitasi dari Google Scholar"""
    publikasi_scholar = []
    url = f"https://scholar.google.com/citations?user={scholar_id}&hl=id&pagesize=100"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        req = requests.get(url, headers=headers, timeout=15)
        if req.status_code == 200:
            soup = BeautifulSoup(req.text, 'html.parser')
            rows = soup.find_all("tr", class_="gsc_a_tr")
            
            for row in rows:
                title_elem = row.find("a", class_="gsc_a_at")
                if not title_elem: continue
                
                judul = title_elem.text.strip()
                link = "https://scholar.google.com" + title_elem['href']
                
                # Mengambil Sitasi
                cites_elem = row.find("a", class_="gsc_a_ac")
                sitasi = cites_elem.text.strip() if cites_elem and cites_elem.text.strip() else "0"
                
                # Mengambil Tahun
                year_elem = row.find("span", class_="gsc_a_h")
                tahun = year_elem.text.strip() if year_elem and year_elem.text.strip() else "N/A"
                
                # Mencocokkan dengan Kamus SINTA
                jenis_keg = "Jurnal Ilmiah"
                judul_lookup = judul.rstrip('.')
                for key_judul, label_sinta in PETA_SINTA_MANUAL.items():
                    if key_judul.lower().rstrip('.') == judul_lookup.lower():
                        jenis_keg = label_sinta
                        break
                
                publikasi_scholar.append({
                    "judul": judul,
                    "jenis": jenis_keg,
                    "tahun": tahun,
                    "sitasi": sitasi,
                    "link": link
                })
    except Exception as e:
        print(f"Google Scholar Error/Diblokir: {e}")
        
    return publikasi_scholar

print("Memulai sinkronisasi hibrida (Google Scholar + PDDIKTI)...")

try:
    with api() as client:
        # 1. TARIK PROFIL PDDIKTI
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
            hasil["pesan"] = f"Dosen '{nama_dosen}' tidak ditemukan di PDDIKTI."
        else:
            # 2. TARIK PENGABDIAN (Dari PDDIKTI)
            pengabdian = client.get_dosen_pengabdian(dosen_id)
            if pengabdian:
                for p in pengabdian:
                    thn = p.get('tahun_kegiatan') or p.get('tahun_pelaksanaan') or p.get('tahun') or 'N/A'
                    hasil["pengabdian"].append({
                        "judul": p.get('judul_kegiatan', 'N/A'),
                        "tahun": thn,
                        "kategori": "Pengabdian"
                    })

            # 3. TARIK PUBLIKASI (Prioritas 1: Google Scholar)
            print("Mencoba menarik data jurnal dan sitasi dari Google Scholar...")
            data_scholar = ambil_data_scholar(scholar_id)
            
            if len(data_scholar) > 0:
                print(f"Sukses! Mendapatkan {len(data_scholar)} publikasi dari Scholar.")
                hasil["publikasi"] = data_scholar
                
                # Tambahkan pemikiran tidak dipublikasikan ke pengabdian dari PDDIKTI (sebagai pelengkap)
                karya_pddikti = client.get_dosen_karya(dosen_id)
                if karya_pddikti:
                    for p in karya_pddikti:
                        if p.get('jenis_kegiatan') == "Hasil penelitian/pemikiran yang tidak dipublikasikan":
                            thn_int = p.get('tahun_kegiatan') or p.get('tahun_pelaksanaan') or p.get('tahun') or 'N/A'
                            hasil["pengabdian"].append({
                                "judul": p.get('judul_kegiatan', ''),
                                "tahun": thn_int,
                                "kategori": "Penelitian Internal"
                            })
            else:
                # FALLBACK (Prioritas 2: PDDIKTI jika Scholar diblokir)
                print("Scholar diblokir/gagal. Menggunakan jalur cadangan (PDDIKTI)...")
                publikasi = client.get_dosen_karya(dosen_id)
                if publikasi:
                    for p in publikasi:
                        judul_keg = p.get('judul_kegiatan', '').strip()
                        jenis_keg = p.get('jenis_kegiatan', 'N/A')
                        tahun_keg = p.get('tahun_kegiatan') or p.get('tahun_pelaksanaan') or p.get('tahun') or 'N/A'
                        
                        if jenis_keg == "Hasil penelitian/pemikiran yang tidak dipublikasikan":
                            hasil["pengabdian"].append({
                                "judul": judul_keg, "tahun": tahun_keg, "kategori": "Penelitian Internal"
                            })
                        else:
                            judul_lookup = judul_keg.rstrip('.')
                            for key_judul, label_sinta in PETA_SINTA_MANUAL.items():
                                if key_judul.lower().rstrip('.') == judul_lookup.lower():
                                    jenis_keg = label_sinta
                                    break
                            
                            hasil["publikasi"].append({
                                "judul": judul_keg, "jenis": jenis_keg, "tahun": tahun_keg
                            })
            
            print("Proses sinkronisasi dan klasifikasi data selesai.")

except Exception as e:
    hasil["status"] = "error"
    hasil["pesan"] = f"Terjadi kesalahan: {str(e)}"

# Simpan hasil akhir
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(hasil, f, indent=4, ensure_ascii=False)

print("File data.json berhasil diperbarui!")