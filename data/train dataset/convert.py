import pandas as pd
import json

excel_path = r'd:\aqil\pusdatik\data\train dataset\star_prompt_injection_id.xlsx'
json_path = r'd:\aqil\pusdatik\data\train dataset\star_prompt_injection_id.json'

try:
    df = pd.read_excel(excel_path)
    df.to_json(json_path, orient='records', force_ascii=False, indent=4)
    print("Conversion successful. File saved to", json_path)
except Exception as e:
    print("Error during conversion:", e)
