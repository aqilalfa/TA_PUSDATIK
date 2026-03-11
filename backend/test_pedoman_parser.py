import re
import json

def parse_pedoman(text: str, filename: str = "") -> dict:
    result = {
        "metadata_dokumen": {
            "jenis_dokumen": "Pedoman Menteri PANRB",
            "nomor": "",
            "tahun": "",
            "tentang": "",
            "status": ""
        },
        "narasi_pedoman": [],
        "instrumen_indikator": []
    }
    
    # 1. Clean Text from jdih footer
    text = re.sub(r"-\d+-\s+jdih\.menpan\.go\.id", "", text, flags=re.IGNORECASE)
    
    # 2. Extract Metadata from first 1000 chars
    first_lines = text[:1000].split('\n')
    for idx, line in enumerate(first_lines):
        line = line.strip()
        
        m_no = re.search(r"NOMOR\s+(\d+)\s+TAHUN\s+(\d+)", line, re.IGNORECASE)
        if m_no and not result["metadata_dokumen"]["nomor"]:
            result["metadata_dokumen"]["nomor"] = m_no.group(1)
            result["metadata_dokumen"]["tahun"] = m_no.group(2)
            
        if line.upper() == "TENTANG":
            if idx + 1 < len(first_lines):
                tentang_text = first_lines[idx+1].strip()
                result["metadata_dokumen"]["tentang"] = tentang_text
                
        if re.search(r"Mencabut.*", line, re.IGNORECASE):
            result["metadata_dokumen"]["status"] = line
            
    # Default status if not found in first lines
    if not result["metadata_dokumen"]["status"]:
        result["metadata_dokumen"]["status"] = "Berlaku"

    # 3. Extract Narasi
    # Look for BAB I, BAB II, etc.
    # The narasi part ends when we hit the detailed indicators, e.g. "I. DOMAIN KEBIJAKAN"
    
    # Split by BAB
    babs = re.finditer(r"^BAB\s+([IVXLCDM]+)\s*\n+(.*?)(?=\n^BAB\s+[IVXLCDM]+|\n^I\.\s*\nDOMAIN|\Z)", text, re.MULTILINE | re.IGNORECASE | re.DOTALL)
    
    for b in babs:
        bab_no = b.group(1).upper()
        bab_content = b.group(2).strip()
        
        # Extract title from first line of content
        content_lines = bab_content.split('\n')
        bab_judul = content_lines[0].strip()
        bab_body = "\n".join(content_lines[1:])
        
        current_bab = {
            "bab_nomor": bab_no,
            "bab_judul": bab_judul,
            "sub_bab": []
        }
        
        # Extract Sub-babs (A. Latar Belakang, B. Maksud dan Tujuan, etc)
        # Note: sometimes it's A. B. C.
        sub_matches = re.finditer(r"^([A-Z])\.\s+(.*?)\n(.*?)(?=\n^[A-Z]\.\s+|\Z)", bab_body, re.MULTILINE | re.DOTALL)
        
        has_sub = False
        for s in sub_matches:
            has_sub = True
            huruf = s.group(1)
            judul = s.group(2).strip()
            isi = re.sub(r"\n+", " ", s.group(3)).strip() # Join lines
            
            current_bab["sub_bab"].append({
                "huruf": huruf,
                "judul": judul,
                "isi_teks": isi
            })
            
        if not has_sub and bab_body.strip():
             current_bab["sub_bab"].append({
                "huruf": "",
                "judul": "Umum",
                "isi_teks": re.sub(r"\n+", " ", bab_body).strip()
             })
             
        result["narasi_pedoman"].append(current_bab)
        
    # 4. Extract Instrumen Indikator
    # They start around "I. DOMAIN KEBIJAKAN"
    # Format:
    # INDIKATOR 1
    # Domain ... Aspek Ind Kuesioner ... D1 A1 ID-1
    # Tingkat Kematangan Kebijakan Internal Arsitektur SPBE Instansi Pusat/Pemerintah Daerah.
    # Deskripsi Indikator: ...
    # Level 1 ... Kriteria Level ... Kriteria Bukti Dukung ...
    
    ind_blocks = re.split(r"^INDIKATOR\s+\d+", text, flags=re.MULTILINE)
    
    # ind_blocks[0] is preamble before INDIKATOR 1
    for i, block in enumerate(ind_blocks[1:], 1):
        ind = {
            "domain": "",
            "indikator_nomor": i,
            "indikator_nama": "",
            "deskripsi": "",
            "kriteria_level": {},
            "kriteria_bukti_dukung": {}
        }
        
        # Lines in block
        lines = block.strip().split('\n')
        
        # The name of the indicator usually follows "D1 A1 ID-X" or similar
        # Let's cleanly extract it using regex
        
        # 1. Nama Indikator
        # Often it comes right after D1 A1 ID-1
        m_nama = re.search(r"ID-\d+\s*\n(.*?)(?=\nDeskripsi Indikator|$)", block, re.DOTALL | re.IGNORECASE)
        if m_nama:
            ind["indikator_nama"] = m_nama.group(1).replace('\n', ' ').strip()
            
        # 2. Deskripsi
        m_desk = re.search(r"Deskripsi Indikator.*?:(.*?)(?=\nKetentuan Penilaian|\nLevel 1|$)", block, re.DOTALL | re.IGNORECASE)
        if m_desk:
            ind["deskripsi"] = m_desk.group(1).replace('\n', ' ').strip()
            
        # 3. Levels
        for level in range(1, 6):
            # Kriteria Level
            pat_kriteria = rf"Level {level}.*?Kriteria Level(.*?)(?=Kriteria pemenuhan|Kriteria Bukti Dukung|Level {level+1}|$)"
            m_krit = re.search(pat_kriteria, block, re.DOTALL | re.IGNORECASE)
            if m_krit:
                ind["kriteria_level"][str(level)] = m_krit.group(1).replace('\n', ' ').strip()
                
            # Kriteria Bukti Dukung
            pat_bukti = rf"Level {level}.*?Kriteria Bukti Dukung(.*?)(?=Level {level+1}|$)"
            m_bukti = re.search(pat_bukti, block, re.DOTALL | re.IGNORECASE)
            if m_bukti:
                ind["kriteria_bukti_dukung"][str(level)] = m_bukti.group(1).replace('\n', ' ').strip()

        # Extract domain from preamble or from the text
        if "Arsitektur" in ind["indikator_nama"] or "Peta Rencana" in ind["indikator_nama"]:
            ind["domain"] = "Kebijakan SPBE"
        elif "Tata Kelola" in block[:500]:
            ind["domain"] = "Tata Kelola SPBE"
        elif "Manajemen" in block[:500]:
            ind["domain"] = "Manajemen SPBE"
        elif "Layanan" in block[:500]:
            ind["domain"] = "Layanan SPBE"
        else:
            ind["domain"] = "Kebijakan SPBE" # Default fallback
            
        result["instrumen_indikator"].append(ind)

    return result

if __name__ == "__main__":
    with open(r'd:\aqil\pusdatik\backend\test_pedoman.txt', 'r', encoding='utf-8') as f:
        text = f.read()
    
    parsed = parse_pedoman(text, filename="PEDOMAN_PANRB.pdf")
    with open(r'd:\aqil\pusdatik\backend\test_pedoman_parsed.json', 'w', encoding='utf-8') as f:
        f.write(json.dumps(parsed, indent=2, ensure_ascii=False))
    print("Done! Check test_pedoman_parsed.json")
