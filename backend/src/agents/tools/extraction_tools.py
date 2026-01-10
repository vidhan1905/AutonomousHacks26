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


class PatientRequest(BaseModel):
    """Extracted patient medical request."""
    description: str = Field(description="Clean, concise description of the patient's medical need or request, without appointment scheduling details")


class PatientCaseSummary(BaseModel):
    """Patient case summary for doctors."""
    case_summary: str = Field(description="Comprehensive summary of the patient's case including symptoms, condition, and medical needs")


# Initialize LLM for extraction
extraction_llm = ChatOpenAI(
    model=settings.openai_model,
    temperature=0,  # Use 0 for extraction to ensure consistency
    api_key=settings.openai_api_key
)

# Create structured output LLM
structured_llm = extraction_llm.with_structured_output(PatientInfo)
structured_request_llm = extraction_llm.with_structured_output(PatientRequest)
structured_case_summary_llm = extraction_llm.with_structured_output(PatientCaseSummary)


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


@tool
def extract_patient_request(message: str) -> dict:
    """
    Extract a clean, focused description of the patient's medical request from natural language.
    Removes appointment scheduling details and focuses on the core medical need.

    Args:
        message: The user's message that may contain medical requests and appointment details

    Returns:
        dict with extracted description field containing the clean medical request

    Example:
        Input: "I need a blood test tomorrow at 10:00 AM"
        Output: {"description": "Patient needs a blood test"}

        Input: "tomorrow at 10:00 AM (Preferred appointment time: 2026-01-11T10:00:00)"
        Output: {"description": "Patient request"}

        Input: "I got my leg in accident and need to see a doctor"
        Output: {"description": "Patient has leg injury from accident, needs medical consultation"}
    """
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert at extracting the core medical request from patient messages.

Your task is to extract what the patient needs help with medically, removing all appointment scheduling details.

EXTRACT:
- Core medical need/request (e.g., "blood test", "leg injury", "chest pain", "follow-up consultation")
- Symptoms or conditions mentioned
- Service requests (e.g., "need a test", "want to see a doctor")

REMOVE:
- Appointment times (e.g., "tomorrow at 10:00 AM", "next Tuesday", "Next Monday at 7:00 PM")
- Date references (e.g., "2026-01-11T10:00:00", "Preferred appointment time")
- Scheduling language (e.g., "schedule", "book", "appointment", "at 7:00 PM", "at 10:00 AM")
- Time preferences and day references (e.g., "Monday", "Tuesday", "next week")

OUTPUT FORMAT:
- Write a concise, doctor-friendly description starting with "Patient" (e.g., "Patient needs a blood test")
- Focus on the medical need, not scheduling
- If no clear medical request is found, return "Patient request"

Examples:
Input: "I need a blood test tomorrow at 10:00 AM"
Output: "Patient needs a blood test"

Input: "tomorrow at 10:00 AM (Preferred appointment time: 2026-01-11T10:00:00)"
Output: "Patient request"

Input: "Next Monday at 7:00 PM"
Output: "Patient request"

Input: "I got my leg in accident and need to see a doctor"
Output: "Patient has leg injury from accident, needs medical consultation"

Input: "I need the blood report"
Output: "Patient needs blood test/report"

Input: "I have chest pain and need urgent help"
Output: "Patient experiencing chest pain, needs urgent medical attention"
"""),
        ("human", "{message}")
    ])

    try:
        chain = extraction_prompt | structured_request_llm
        result = chain.invoke({"message": message})

        return {
            "success": True,
            "description": result.description,
            "message": f"Extracted patient request: {result.description}"
        }
    except Exception as e:
        # Fallback: return a simple description without LLM
        fallback_description = message.split("(")[0].strip() if "(" in message else message.strip()
        # Remove common time phrases
        time_phrases = ["tomorrow", "next week", "at 10:00 AM", "Preferred appointment time"]
        for phrase in time_phrases:
            fallback_description = fallback_description.replace(phrase, "").strip()
        
            return {
                "success": True,
                "description": fallback_description if fallback_description else "Patient request",
                "error": str(e),
                "fallback": True
            }


@tool
def generate_patient_case_summary(
    user_request: str,
    patient_history: Optional[dict] = None,
    patient_details: Optional[dict] = None
) -> dict:
    """
    Generate a comprehensive patient case summary for doctors.
    This should include symptoms, condition, medical needs, and relevant context.

    Args:
        user_request: The patient's current request/description
        patient_history: Optional patient history dictionary
        patient_details: Optional patient details (age, gender, blood group, etc.)

    Returns:
        dict with case_summary field containing the comprehensive case details
    """
    # Build context for the summary
    context_parts = []
    
    if patient_details:
        if patient_details.get("age"):
            context_parts.append(f"Age: {patient_details['age']} years")
        if patient_details.get("gender"):
            context_parts.append(f"Gender: {patient_details['gender']}")
        if patient_details.get("blood_group"):
            context_parts.append(f"Blood Group: {patient_details['blood_group']}")
    
    context_str = "\n".join(context_parts) if context_parts else "No additional patient details available"
    
    history_str = "No significant past medical history" if not patient_history else "Patient has past medical history"
    
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a medical assistant creating a patient case summary for doctors.

Your task is to create a comprehensive, professional case summary that helps doctors understand the patient's condition and needs.

INCLUDE:
- Patient's current symptoms or condition
- Medical need or service requested
- Relevant clinical context
- Any urgency indicators

FORMAT:
- Write in professional medical language
- Be concise but comprehensive
- Focus on clinical information that helps with diagnosis/treatment
- Start with the primary concern

EXAMPLES:
Input: "I need a blood test"
Output: "Patient requires blood test. Routine laboratory work requested for health assessment."

Input: "I got my leg in accident"
Output: "Patient presents with leg injury sustained in an accident. Requires orthopedic evaluation and possible imaging studies."

Input: "I have chest pain and need urgent help"
Output: "Patient reports chest pain requiring urgent medical attention. Immediate cardiac evaluation recommended."

Input: "Next Monday at 7:00 PM"
Output: "Patient request for medical consultation. Specific medical concern to be determined during consultation."
"""),
        ("human", """Patient Request: {user_request}

Patient Context:
{context}

Medical History: {history}

Generate a comprehensive case summary for the doctor.""")
    ])

    try:
        chain = extraction_prompt | structured_case_summary_llm
        result = chain.invoke({
            "user_request": user_request,
            "context": context_str,
            "history": history_str
        })

        return {
            "success": True,
            "case_summary": result.case_summary,
            "message": "Generated patient case summary"
        }
    except Exception as e:
        # Fallback: create a simple summary
        fallback_summary = f"Patient request: {user_request}"
        if patient_details:
            if patient_details.get("age"):
                fallback_summary += f"\nAge: {patient_details['age']} years"
            if patient_details.get("blood_group"):
                fallback_summary += f"\nBlood Group: {patient_details['blood_group']}"
        
        return {
            "success": True,
            "case_summary": fallback_summary,
            "error": str(e),
            "fallback": True
        }
