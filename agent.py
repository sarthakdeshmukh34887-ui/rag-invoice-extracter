import time
import random
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from config import GROQ_API_KEY
from schema import OutwardSupplyInvoice

# Set up the high-speed Groq model with structured output mapping
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0, api_key=GROQ_API_KEY)
structured_llm = llm.with_structured_output(OutwardSupplyInvoice)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert Indian tax compliance engine. Extract GSTR-1 parameters precisely from the text."),
    ("user", "Extract data from this invoice text:\n\n{text}")
])

agent_chain = prompt | structured_llm

def process_invoice_text(text: str) -> dict:
    max_retries = 4  # Increased retries to handle tight free-tier ceilings
    base_delay = 10  # Increased to 10 seconds to allow the Groq 6,000 TPM bucket to drain completely
    
    for attempt in range(max_retries):
        try:
            response = agent_chain.invoke({"text": text})
            return response.model_dump()
            
        except Exception as e:
            # Catching ALL exceptions here forces LangChain's wrapped rate-limit 
            # errors into our recovery sleep logic
            if attempt == max_retries - 1:
                raise e  # Completely out of retries, bubble up the error to app.py
            
            # Calculate exponential delay with random jitter to spread out threads
            sleep_time = (base_delay * (2 ** attempt)) + random.uniform(1, 4)
            time.sleep(sleep_time)
            continue