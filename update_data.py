import json
import re  # Menggunakan regex untuk menangkap variasi teks Sinta
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

def hit_server_garuda(query_judul):
    """Fungsi internal untuk melakukan request ke domain baru Garuda"""
    judul_encoded = urllib.parse.quote(query_judul)
    url = f"https://garuda.kemdiktisaintek.go.id/documents?select=title&q={judul_encoded}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.find_all("a", href=True):
                if "/journal/view/" in link["href"]:
                    teks_badge = link.get_text().lower().strip()
                    
                    # REGEX FIX: Menangkap format "sinta 3", "s3", "sinta3", "s 3", dll.
                    match = re.search(r's(?:inta)?\s*([1-6])', teks_badge)
                    if match:
                        return f"S{match.group(1)}"
        return ""
    except:
        return ""

def cari_akreditasi_sinta_via_garuda(judul_artikel):
    """Mencari peringkat akreditasi SINTA dengan normalisasi dan fallback query"""
    # 1. Bersihkan spasi ganda, spasi ujung, dan hilangkan titik di akhir judul jika ada
    judul_clean = " ".join(judul_artikel.strip().rstrip('.').split())
    
    # 2. Coba cari menggunakan judul lengkap terlebih dahulu
    status_sinta = hit_server_garuda(judul_clean)
    
    # 3. FALLBACK: Jika tidak ketemu, potong hanya 6 kata pertama (Pencarian Fleksibel Garuda)
    if not status_sinta:
        kata = judul_clean.split()
        if len(kata) > 6:
            judul_pendek = " ".join(kata[:6])
            status_sinta = hit_server_garuda(judul_pendek)
            
    return status_sinta

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

            # 2. Ambil Karya Ilmiah / Publikasi, Filter Klasifikasi, dan Cek Garuda
            publikasi = client.get_dosen_karya(dosen_id)
            if publikasi:
                print(f"Ditemukan {len(publikasi)} karya ilmiah. Memulai crosscheck cerdas ke Garuda...")
                for p in publikasi:
                    judul_keg = p.get('judul_kegiatan', 'N/A')
                    jenis_keg = p.get('jenis_kegiatan', 'N/A')
                    tahun_keg = p.get('tahun_kegiatan') or p.get('tahun_pelaksanaan') or p.get('tahun') or 'N/A'
                    
                    # Pengalihan otomatis jika tidak dipublikasikan
                    if jenis_keg == "Hasil penelitian/pemikiran yang tidak dipublikasikan":
                        hasil["pengabdian"].append({
                            "judul": judul_keg,
                            "tahun": tahun_keg,
                            "kategori": "Penelitian Internal"
                        })
                    else:
                        # Lakukan pengecekan akreditasi ke Garuda
                        print(f"Memeriksa indeks Garuda: {judul_keg[:40]}...")
                        tingkat = cari_akreditasi_sinta_via_garuda(judul_keg)
                        
                        if tingkat:
                            jenis_keg = f"SINTA {tingkat[1:]}" # Menghasilkan teks "SINTA 3", "SINTA 4", dst.
                        
                        hasil["publikasi"].append({
                            "judul": judul_keg,
                            "jenis": jenis_keg,
                            "tahun": tahun_keg
                        })
            
            print("Seluruh proses pemetaan data selesai.")

except Exception as e:
    hasil["status"] = "error"
    hasil["pesan"] = f"Terjadi kesalahan: {str(e)}"

# Simpan hasil akhir ke data.json
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(hasil, f, indent=4, ensure_ascii=False)

print("File data.json berhasil diperbarui secara hibrida & adaptif!")