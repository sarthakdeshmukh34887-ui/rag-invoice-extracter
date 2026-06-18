import time
import random
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from config import GROQ_API_KEY
from schema import OutwardSupplyInvoice

llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0, api_key=GROQ_API_KEY)
structured_llm = llm.with_structured_output(OutwardSupplyInvoice)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert Indian tax compliance engine. Extract GSTR-1 parameters precisely from the text."),
    ("user", "Extract data from this invoice text:\n\n{text}")
])

agent_chain = prompt | structured_llm

def process_invoice_text(text: str) -> dict:
    max_retries = 4  
    base_delay = 12  # Bumped slightly to give the 6,000 TPM bucket more time to drain
    
    for attempt in range(max_retries):
        try:
            response = agent_chain.invoke({"text": text})
            result = response.model_dump()
            result["extraction_status"] = "Success"  # Mark it clear
            return result
            
        except Exception as e:
            if attempt == max_retries - 1:
                # INSTEAD OF CRASHING: Return a fallback dict marking the failure
                return {
                    "extraction_status": f"FAILED: Rate Limit Reached ({str(e)[:50]})",
                    "Invoice Number": "ERROR",
                    "Receiver Name": "ERROR",
                    "Total Invoice Value": 0.0,
                    "Taxable Value": 0.0,
                    "Integrated Tax": 0.0,
                    "Central Tax": 0.0,
                    "State Tax": 0.0
                }
            
            sleep_time = (base_delay * (2 ** attempt)) + random.uniform(1, 4)
            time.sleep(sleep_time)
            continue