import json
import urllib.parse
import requests
from bs4 import BeautifulSoup
from pddiktipy import api

# --- PARAMETER PENCARIAN DOSEN ---
nama_dosen = "VICKY SETIA GUNAWAN"
nama_pt = "UNIVERSITAS PERINTIS INDONESIA"
prodi = "BISNIS DIGITAL"

# --- STRUKTUR DATA AWAL ---
hasil = {
    "status": "error",
    "pesan": "",
    "profil": {},
    "pengabdian": [],
    "publikasi": []
}

def cari_akreditasi_sinta_via_garuda(judul_artikel):
    """Mencari peringkat akreditasi SINTA via situs Garuda (Domain Baru)"""
    judul_encoded = urllib.parse.quote(judul_artikel)
    url = f"https://garuda.kemdiktisaintek.go.id/documents?select=title&q={judul_encoded}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.find_all("a", href=True):
                if "/journal/view/" in link["href"]:
                    teks_badge = link.get_text().strip()
                    if teks_badge.startswith("S") and teks_badge[1:].isdigit():
                        return teks_badge
        return ""
    except:
        return ""

print("Memulai sinkronisasi data dari PDDIKTI...")

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
            hasil["pesan"] = f"Dosen '{nama_dosen}' tidak ditemukan di PDDIKTI."
        else:
            # 1. Ambil Riwayat Pengabdian Masyarakat Asli
            pengabdian = client.get_dosen_pengabdian(dosen_id)
            if pengabdian:
                for p in pengabdian:
                    tahun = p.get('tahun_kegiatan') or p.get('tahun_pelaksanaan') or p.get('tahun') or 'N/A'
                    hasil["pengabdian"].append({
                        "judul": p.get('judul_kegiatan', 'N/A'),
                        "tahun": tahun,
                        "kategori": "Pengabdian"
                    })

            # 2. Ambil Karya Ilmiah / Publikasi & Filter Pemindahan Kategori
            publikasi = client.get_dosen_karya(dosen_id)
            if publikasi:
                print(f"Ditemukan {len(publikasi)} karya ilmiah. Memulai proses filter dan cek Garuda...")
                for p in publikasi:
                    judul_keg = p.get('judul_kegiatan', 'N/A')
                    jenis_keg = p.get('jenis_kegiatan', 'N/A')
                    tahun_keg = p.get('tahun_kegiatan') or p.get('tahun_pelaksanaan') or p.get('tahun') or 'N/A'
                    
                    # LOGIKA PEMINDAHAN: Jika tidak dipublikasikan, pindahkan ke Pengabdian/Internal
                    if jenis_keg == "Hasil penelitian/pemikiran yang tidak dipublikasikan":
                        hasil["pengabdian"].append({
                            "judul": judul_keg,
                            "tahun": tahun_keg,
                            "kategori": "Penelitian Internal"
                        })
                    else:
                        # Jika dipublikasikan, cek tingkat SINTA via Garuda
                        print(f"Mengecek di Garuda: {judul_keg[:40]}...")
                        tingkat = cari_akreditasi_sinta_via_garuda(judul_keg)
                        
                        if tingkat:
                            jenis_keg = f"SINTA {tingkat[1:]}"
                        
                        hasil["publikasi"].append({
                            "judul": judul_keg,
                            "jenis": jenis_keg,
                            "tahun": tahun_keg
                        })
            
            print("Proses sinkronisasi dan klasifikasi data selesai.")

except Exception as e:
    hasil["status"] = "error"
    hasil["pesan"] = f"Terjadi kesalahan: {str(e)}"

# Simpan hasil akhir ke data.json
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(hasil, f, indent=4, ensure_ascii=False)

print("File data.json berhasil diperbarui secara hibrida!")