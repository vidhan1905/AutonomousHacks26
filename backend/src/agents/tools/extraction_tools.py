"""Tools for extracting structured information from natural language."""
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import Optional
from backend.src.config import settings


class PatientInfo(BaseModel):
    """Extracted patient information."""
    name: Optional[str] = Field(None, description="Full name of the patient")
    phone: Optional[str] = Field(None, description="Phone number exactly as provided")
    date_of_birth: Optional[str] = Field(None, description="Date of birth in YYYY-MM-DD format")


# Initialize LLM for extraction
extraction_llm = ChatOpenAI(
    model=settings.openai_model,
    temperature=0,  # Use 0 for extraction to ensure consistency
    api_key=settings.openai_api_key
)

# Create structured output LLM
structured_llm = extraction_llm.with_structured_output(PatientInfo)


@tool
def extract_patient_info(message: str) -> dict:
    """
    Extract patient information (name, phone, date of birth) from a natural language message.

    Args:
        message: The user's message that may contain patient information

    Returns:
        dict with extracted fields: name, phone, date_of_birth

    Example:
        Input: "My name is April Maldonado, 001-852-326-5094x079 and 1955-02-28"
        Output: {"name": "April Maldonado", "phone": "001-852-326-5094x079", "date_of_birth": "1955-02-28"}
    """
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert at extracting patient information from natural language text.

Extract the following information if present:
1. **name**: Full name of the person (first name and last name)
2. **phone**: Phone number EXACTLY as provided (preserve all formatting like hyphens, dots, 'x', etc.)
3. **date_of_birth**: Date of birth converted to YYYY-MM-DD format

IMPORTANT RULES:
- For phone numbers: Keep the EXACT format provided (e.g., "001-852-326-5094x079" stays as "001-852-326-5094x079")
- For dates: Convert to YYYY-MM-DD format (e.g., "Feb 28, 1955" → "1955-02-28", "1955-02-28" → "1955-02-28")
- If a field is not present, leave it as null
- Extract only explicit information - do not infer or guess

Examples:
Input: "My name is April Maldonado, 001-852-326-5094x079 and 1955-02-28"
Output: {{"name": "April Maldonado", "phone": "001-852-326-5094x079", "date_of_birth": "1955-02-28"}}

Input: "I'm John Smith, phone is +1-555-123-4567"
Output: {{"name": "John Smith", "phone": "+1-555-123-4567", "date_of_birth": null}}

Input: "My name is Sarah Johnson and I was born on March 15, 1990"
Output: {{"name": "Sarah Johnson", "phone": null, "date_of_birth": "1990-03-15"}}
"""),
        ("human", "{message}")
    ])

    try:
        chain = extraction_prompt | structured_llm
        result = chain.invoke({"message": message})

        # Convert Pydantic model to dict, excluding None values
        extracted = {}
        if result.name:
            extracted["name"] = result.name
        if result.phone:
            extracted["phone"] = result.phone
        if result.date_of_birth:
            extracted["date_of_birth"] = result.date_of_birth

        return {
            "success": True,
            "extracted": extracted,
            "message": f"Extracted {len(extracted)} field(s) from message"
        }
    except Exception as e:
        return {
            "success": False,
            "extracted": {},
            "error": str(e)
        }
