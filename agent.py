import time
import random
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from schema import OutwardSupplyInvoice

# Safely pull the key from Streamlit Cloud Secrets or local environments
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# UPDATED: Changed model from gemini-1.5-flash to gemini-2.5-flash
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    temperature=0, 
    google_api_key=GEMINI_API_KEY
)
structured_llm = llm.with_structured_output(OutwardSupplyInvoice)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert Indian tax compliance engine. Extract GSTR-1 parameters precisely from the text."),
    ("user", "Extract data from this invoice text:\n\n{text}")
])

agent_chain = prompt | structured_llm

def process_invoice_text(text: str) -> dict:
    max_retries = 5  # Increased to give ample retries
    base_delay = 15  # Increased to 15 seconds to let the 10 RPM window completely drain
    
    for attempt in range(max_retries):
        try:
            response = agent_chain.invoke({"text": text})
            
            result = response.model_dump() if hasattr(response, 'model_dump') else dict(response)
            result["extraction_status"] = "Success"
            return result
            
        except Exception as e:
            if attempt == max_retries - 1:
                return {
                    "extraction_status": f"FAILED: Extraction Issue ({str(e)[:50]})",
                    "customer_name": "ERROR", 
                    "gstin": "ERROR", 
                    "invoice_no": "ERROR"
                }
            
            # Staggers the retry timing with a smart delay curve
            sleep_time = (base_delay * (attempt + 1)) + random.uniform(2, 5)
            time.sleep(sleep_time)
            continue