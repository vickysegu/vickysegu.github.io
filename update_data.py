import json
from pddiktipy import api

nama_dosen = "VICKY SETIA GUNAWAN"
nama_pt = "UNIVERSITAS PERINTIS INDONESIA"
prodi = "BISNIS DIGITAL"

hasil = {
    "status": "error",
    "pesan": "",
    "profil": {},
    "penelitian": [],
    "pengabdian": [],
    "publikasi": []
}

try:
    print("Memulai sinkronisasi data dengan PDDIKTI...")
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
            hasil["pesan"] = f"Dosen '{nama_dosen}' tidak ditemukan."
        else:
            # 1. Ambil Riwayat Penelitian
            penelitian = client.get_dosen_penelitian(dosen_id)
            if penelitian:
                hasil["penelitian"] = [{"judul": p.get('judul_kegiatan', 'N/A'), "tahun": p.get('tahun_kegiatan', 'N/A')} for p in penelitian]

            # 2. Ambil Riwayat Pengabdian
            pengabdian = client.get_dosen_pengabdian(dosen_id)
            if pengabdian:
                hasil["pengabdian"] = [{"judul": p.get('judul_kegiatan', 'N/A'), "tahun": p.get('tahun_kegiatan', 'N/A')} for p in pengabdian]

            # 3. Ambil Karya Ilmiah / Publikasi
            publikasi = client.get_dosen_karya(dosen_id)
            if publikasi:
                hasil["publikasi"] = [{"judul": p.get('judul_kegiatan', 'N/A'), "jenis": p.get('jenis_kegiatan', 'N/A')} for p in publikasi]
            
            print("Data berhasil ditarik.")

except Exception as e:
    hasil["pesan"] = f"Terjadi kesalahan: {str(e)}"

# Simpan hasil ke file data.json
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(hasil, f, indent=4, ensure_ascii=False)

print("File data.json berhasil diperbarui!")