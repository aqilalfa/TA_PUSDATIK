import sys
import asyncio
sys.path.insert(0, r'd:\aqil\pusdatik\backend')

from app.core.ingestion.pdf_processor import process_pdf_background

async def main():
    print("Ingesting Permenpan 5...")
    await process_pdf_background(
        'Permenpan RB Nomor 5 Tahun 2020.pdf', 
        b'', 
        background_task_id='123', 
        is_sync=True, 
        temp_file_path=r'd:\aqil\pusdatik\backend\data\sample_docs\Permenpan RB Nomor 5 Tahun 2020.pdf'
    )
    
    print("Ingesting SE 18...")
    await process_pdf_background(
        'SE Menteri PAN-RB Nomor 18 Tahun 2022.pdf', 
        b'', 
        background_task_id='124', 
        is_sync=True, 
        temp_file_path=r'd:\aqil\pusdatik\backend\data\sample_docs\SE Menteri PAN-RB Nomor 18 Tahun 2022.pdf'
    )

if __name__ == '__main__':
    asyncio.run(main())
