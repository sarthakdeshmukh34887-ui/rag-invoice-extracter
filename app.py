import os
import re
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import GROQ_API_KEY
from parsers import extract_text
from agent import process_invoice_text

GST_STATE_CODES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh",
    "24": "Gujarat", "25": "Daman and Diu", "26": "Dadra and Nagar Haveli", "27": "Maharashtra",
    "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
    "34": "Puducherry", "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh",
    "38": "Ladakh"
}

def sanitize_numeric(value) -> float:
    if value is None:
        return 0.0
    try:
        cleaned = re.sub(r'[^\d\.]', '', str(value))
        return float(cleaned) if cleaned else 0.0
    except Exception:
        return 0.0

def compute_tax_matrices(record: dict) -> dict:
    HOME_PREFIX = "27"  # Default (Maharashtra)
    gstin = str(record.get('gstin', '')).strip().replace(" ", "").upper()
    
    state_of_supply = "Unknown"
    if len(gstin) >= 2 and gstin[:2].isdigit():
        prefix = gstin[:2]
        state_of_supply = GST_STATE_CODES.get(prefix, "Other State")
    record['state_of_supply'] = state_of_supply

    taxable = sanitize_numeric(record.get('taxable_value'))
    cess = sanitize_numeric(record.get('cess'))
    
    rate = 18  
    record['tax_rate'] = rate
    record['taxable_value'] = taxable
    record['cess'] = cess
    
    total_tax = round(taxable * (rate / 100.0), 2)
    
    if gstin.startswith(HOME_PREFIX):
        record['igst'] = 0.0
        record['cgst'] = round(total_tax / 2.0, 2)
        record['sgst'] = round(total_tax / 2.0, 2)
    else:
        record['igst'] = total_tax
        record['cgst'] = 0.0
        record['sgst'] = 0.0
        
    record['invoice_value'] = round(taxable + record['igst'] + record['cgst'] + record['sgst'] + cess, 2)
    return record

def get_chronological_sort_key(invoice_no) -> int:
    if not invoice_no: 
        return 0
    match = re.search(r'(\d+)\s*$', str(invoice_no).strip())
    return int(match.group(1)) if match else 0

# --- 🛠️ WORKER FUNCTION FOR MULTITHREADING ---
def process_single_file(file_data, file_name):
    """Worker function to process an individual file concurrently."""
    try:
        temp_path = f"temp_runtime_{file_name}"
        with open(temp_path, "wb") as f:
            f.write(file_data)
        
        raw_text = extract_text(temp_path)
        if os.path.exists(temp_path):
            os.remove(temp_path)

        if not raw_text.strip():
            return {"error": f"Skipped {file_name} - Empty document text."}

        # Calls the auto-retry wrapper function inside agent.py
        extracted_json = process_invoice_text(raw_text)
        final_record = compute_tax_matrices(extracted_json)
        final_record['source_file'] = file_name
        return {"success": True, "record": final_record}
        
    except Exception as e:
        return {"error": f"Error parsing {file_name}: {str(e)}"}

# --- 🚀 STREAMLIT FRONTEND DASHBOARD ---
st.set_page_config(page_title="GSTR-1 AI Toolkit Dashboard", layout="wide")
st.title("⚡ Ultra-Fast GSTR-1 AI Extractor Engine")
st.caption("Parallel Execution Mode Active")

if not GROQ_API_KEY:
    user_api_key = st.sidebar.text_input("Provide Groq API Key:", type="password")
    if user_api_key:
        os.environ["GROQ_API_KEY"] = user_api_key
else:
    st.sidebar.success("🔑 API Key verified from system environment config.")

uploaded_files = st.file_uploader("Upload your batch invoice files:", accept_multiple_files=True, type=['pdf', 'docx'])

if st.button("Process Folder Package Batch", type="primary"):
    if not os.getenv("GROQ_API_KEY"):
        st.error("Please add an active Groq API Key.")
        st.stop()
    if not uploaded_files:
        st.warning("Please upload at least one valid invoice.")
        st.stop()

    processed_records = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_files = len(uploaded_files)
    status_text.text(f"🚀 Spinning up parallel workers for {total_files} files...")

    # Capped at max_workers=3 to control token volumes alongside backoff delays
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(process_single_file, file.getbuffer().tobytes(), file.name): file.name 
            for file in uploaded_files
        }
        
        for idx, future in enumerate(as_completed(futures)):
            filename = futures[future]
            try:
                result = future.result()
                if "success" in result:
                    processed_records.append(result["record"])
                    st.write(f"✅ Success -> **{filename}** (Inv No: {result['record'].get('invoice_no')})")
                else:
                    st.warning(result["error"])
            except Exception as e:
                st.error(f"❌ Thread failure on {filename}: {str(e)}")
            
            progress_bar.progress((idx + 1) / total_files)
            status_text.text(f"⚡ Progress: [{idx+1}/{total_files}] files completed.")

    status_text.text("✨ Parallel processing complete!")

    if processed_records:
        df = pd.DataFrame(processed_records)
        
        df['sort_key'] = df['invoice_no'].apply(get_chronological_sort_key)
        df = df.sort_values(by='sort_key', ascending=True).drop(columns=['sort_key'])

        column_order = [
            'customer_name', 'gstin', 'invoice_no', 'invoice_date', 
            'invoice_value', 'tax_rate', 'taxable_value', 'igst', 
            'cgst', 'sgst', 'cess', 'state_of_supply', 'reverse_charge', 
            'hsn_code', 'source_file'
        ]
        existing_cols = [c for c in column_order if c in df.columns]
        df = df[existing_cols]

        st.subheader("📊 Structured Spreadsheet Run View")
        st.dataframe(df, use_container_width=True)

        csv_buffer = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Structured GSTR-1 CSV Report",
            data=csv_buffer,
            file_name="gstr1_outward_supplies_register.csv",
            mime="text/csv"
        )