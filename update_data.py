import json
from pddiktipy import api
import sinta # <--- INI BAGIAN YANG DIPERBARUI

# Parameter PDDIKTI
nama_dosen = "VICKY SETIA GUNAWAN"
nama_pt = "UNIVERSITAS PERINTIS INDONESIA"
prodi = "BISNIS DIGITAL"

# Parameter SINTA
sinta_id = 6902246  # <--- PASTIKAN SUDAH DIGANTI DENGAN ID SINTA ANDA 

hasil = {
    "status": "error",
    "pesan": "",
    "profil": {},
    "penelitian": [],
    "pengabdian": [],
    "publikasi": [],
    "sinta_score": {},
    "sinta_kategori": {}
}

print("Memulai sinkronisasi data dengan PDDIKTI dan SINTA...")

# 1. AMBIL DATA DARI SINTA
try:
    print(f"Menarik data SINTA untuk ID: {sinta_id}...")
    data_sinta = sinta.author(sinta_id)
    if data_sinta:
        hasil["sinta_score"] = data_sinta.get("score", {})
        hasil["sinta_kategori"] = data_sinta.get("sinta", {})
        print("Data SINTA berhasil ditarik.")
except Exception as e:
    print(f"Peringatan: Gagal menarik data SINTA: {str(e)}")

# 2. AMBIL DATA DARI PDDIKTI
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
            penelitian = client.get_dosen_penelitian(dosen_id)
            if penelitian:
                hasil["penelitian"] = [{"judul": p.get('judul_kegiatan', 'N/A'), "tahun": p.get('tahun_kegiatan', 'N/A')} for p in penelitian]

            pengabdian = client.get_dosen_pengabdian(dosen_id)
            if pengabdian:
                hasil["pengabdian"] = [{"judul": p.get('judul_kegiatan', 'N/A'), "tahun": p.get('tahun_kegiatan', 'N/A')} for p in pengabdian]

            publikasi = client.get_dosen_karya(dosen_id)
            if publikasi:
                hasil["publikasi"] = [{"judul": p.get('judul_kegiatan', 'N/A'), "jenis": p.get('jenis_kegiatan', 'N/A')} for p in publikasi]
            
            print("Data PDDIKTI berhasil ditarik.")

except Exception as e:
    hasil["pesan"] = f"Terjadi kesalahan PDDIKTI: {str(e)}"

# Simpan ke file
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(hasil, f, indent=4, ensure_ascii=False)

print("File data.json berhasil diperbarui!")