import os
import re
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    if record.get('extraction_status', '').startswith('FAILED'):
        return record

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
    if not invoice_no or str(invoice_no) == "ERROR": 
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
            return {
                "success": True, 
                "record": {
                    "extraction_status": "FAILED: Empty File Text Content",
                    "customer_name": "ERROR", "gstin": "ERROR", "invoice_no": "ERROR"
                }
            }

        # Calls the updated agent.py which targets Gemini 1.5 Flash safely
        extracted_json = process_invoice_text(raw_text)
        final_record = compute_tax_matrices(extracted_json)
        final_record['source_file'] = file_name
        return {"success": True, "record": final_record}
        
    except Exception as e:
        return {
            "success": True, 
            "record": {
                "extraction_status": f"FAILED: Thread Crash ({str(e)[:40]})",
                "customer_name": "ERROR", "gstin": "ERROR", "invoice_no": "ERROR", "source_file": file_name
            }
        }

# --- 🚀 STREAMLIT FRONTEND DASHBOARD ---
st.set_page_config(page_title="GSTR-1 AI Toolkit Dashboard", layout="wide")
st.title("⚡ Ultra-Fast GSTR-1 AI Extractor Engine")
st.caption("Parallel Execution & Gemini 1.5 Flash Active")

# Fetch Gemini API Key from secrets setup configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    user_api_key = st.sidebar.text_input("Provide Gemini API Key:", type="password")
    if user_api_key:
        os.environ["GEMINI_API_KEY"] = user_api_key
else:
    st.sidebar.success("🔑 API Key verified from system environment config.")

uploaded_files = st.file_uploader("Upload your batch invoice files:", accept_multiple_files=True, type=['pdf', 'docx'])

if st.button("Process Folder Package Batch", type="primary"):
    if not os.getenv("GEMINI_API_KEY"):
        st.error("Please add an active Gemini API Key.")
        st.stop()
    if not uploaded_files:
        st.warning("Please upload at least one valid invoice.")
        st.stop()

    processed_records = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_files = len(uploaded_files)
    status_text.text(f"🚀 Spinning up parallel workers for {total_files} files...")

    # Capped at max_workers=3 to safely balance Gemini's 15 Requests Per Minute rule pacing
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(process_single_file, file.getbuffer().tobytes(), file.name): file.name 
            for file in uploaded_files
        }
        
        for idx, future in enumerate(as_completed(futures)):
            filename = futures[future]
            try:
                result = future.result()
                record = result["record"]
                if 'source_file' not in record or not record['source_file']:
                    record['source_file'] = filename
                
                processed_records.append(record)
                
                status_flag = record.get("extraction_status", "Success")
                if "FAILED" in status_flag:
                    st.warning(f"⚠️ Caught -> **{filename}** | Status: {status_flag}")
                else:
                    st.write(f"✅ Success -> **{filename}** (Inv No: {record.get('invoice_no')})")
                    
            except Exception as e:
                emergency_record = {
                    "extraction_status": "FAILED: Critical Processing Halt",
                    "customer_name": "ERROR", "invoice_no": "ERROR", "source_file": filename
                }
                processed_records.append(emergency_record)
                st.error(f"❌ Thread failure on {filename}: {str(e)}")
            
            progress_bar.progress((idx + 1) / total_files)
            status_text.text(f"⚡ Progress: [{idx+1}/{total_files}] files managed.")

    status_text.text("✨ Parallel processing execution cycle complete!")

    if processed_records:
        df = pd.DataFrame(processed_records)
        
        df['extraction_status'] = df['extraction_status'].fillna('Success')
        df['invoice_no'] = df['invoice_no'].fillna('ERROR')
        
        df['sort_key'] = df['invoice_no'].apply(get_chronological_sort_key)
        df = df.sort_values(by='sort_key', ascending=True).drop(columns=['sort_key'])

        column_order = [
            'extraction_status', 'customer_name', 'gstin', 'invoice_no', 'invoice_date', 
            'invoice_value', 'tax_rate', 'taxable_value', 'igst', 
            'cgst', 'sgst', 'cess', 'state_of_supply', 'reverse_charge', 
            'hsn_code', 'source_file'
        ]
        
        for col in column_order:
            if col not in df.columns:
                df[col] = 0.0 if col in ['invoice_value', 'taxable_value', 'igst', 'cgst', 'sgst', 'cess'] else ""

        df = df[column_order]

        st.subheader("📊 Structured Spreadsheet Run View")
        st.dataframe(df, use_container_width=True)

        csv_buffer = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Structured GSTR-1 CSV Report",
            data=csv_buffer,
            file_name="gstr1_outward_supplies_register.csv",
            mime="text/csv"
        )