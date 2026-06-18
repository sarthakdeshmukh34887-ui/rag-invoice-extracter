import time
import random
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from schema import OutwardSupplyInvoice

# Safely pull the key from Streamlit Cloud Secrets or local environments
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Gemini 1.5 Flash with structured data mapping layout
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash", 
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
    max_retries = 3
    base_delay = 4  # Lower delay since we are only pacing the 15 Requests Per Minute rule
    
    for attempt in range(max_retries):
        try:
            response = agent_chain.invoke({"text": text})
            
            # Gemini returns a beautifully formatted dict or Pydantic model directly
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
            
            # Paces out requests to stay comfortably within the 15 RPM speed window
            sleep_time = base_delay + random.uniform(1, 3)
            time.sleep(sleep_time)
            continue