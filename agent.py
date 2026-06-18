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
    max_retries = 3
    base_delay = 5  # Start with a 5 second wait
    
    for attempt in range(max_retries):
        try:
            response = agent_chain.invoke({"text": text})
            return response.model_dump()
            
        except Exception as e:
            error_str = str(e)
            # Catch 429 Rate Limit error codes
            if "429" in error_str or "rate_limit_exceeded" in error_str:
                if attempt == max_retries - 1:
                    raise e  # Out of retries, throw the error
                
                # Calculate exponential delay with a bit of random jitter to separate threads
                sleep_time = (base_delay * (2 ** attempt)) + random.uniform(1, 3)
                time.sleep(sleep_time)
                continue
                
            raise e  # If it's a different error entirely, raise it immediately