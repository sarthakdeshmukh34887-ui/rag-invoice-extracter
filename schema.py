from pydantic import BaseModel, Field
from typing import Optional, Any

class OutwardSupplyInvoice(BaseModel):
    customer_name: str = Field(description="Name of the buyer or customer organization.")
    gstin: Optional[str] = Field(description="15-character GSTIN identifier of the buyer. Return blank or None if B2C.")
    invoice_no: str = Field(description="The unique Invoice Number / Bill sequence number.")
    invoice_date: str = Field(description="Invoice date precisely extracted in DD-MM-YYYY string format.")
    
    # 🔄 Changed all numeric fields to Any to capture both string formats ("123") and floats (123) smoothly
    invoice_value: Any = Field(default=0.0, description="The Grand Total or gross total value of the invoice including all taxes.")
    tax_rate: Any = Field(description="The percentage rate of tax applied (e.g., 18 or 9).")
    taxable_value: Any = Field(description="Total taxable value before GST taxes are calculated.")
    
    igst: Any = Field(default=0.0, description="Integrated Tax (IGST) numerical value. 0 if intra-state or not applied.")
    cgst: Any = Field(default=0.0, description="Central Tax (CGST) numerical value. 0 if inter-state or not applied.")
    sgst: Any = Field(default=0.0, description="State Tax (SGST) numerical value. 0 if inter-state or not applied.")
    cess: Any = Field(default=0.0, description="Cess tax amount if applicable. Defaults to 0.0.")
    
    state_of_supply: str = Field(description="Indian State or UT name where transaction was fulfilled (e.g., Maharashtra, Delhi, Gujarat, Karnataka).")
    reverse_charge: str = Field(description="Indicate 'Yes' or 'No' if reverse charge is applicable. Default to 'No' unless specified.")
    hsn_code: str = Field(description="Extract all unique HSN/SAC codes from the item tables. If multiple are present, join them with a comma and space (e.g., '8471, 8504').")