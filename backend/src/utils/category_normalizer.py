"""Category normalization utility for SQL queries.

This module normalizes user input to valid database category values before
executing SQL queries. It uses LLM to map synonyms and variations to exact
database category values.
"""
from typing import Optional, Dict, Tuple, List, Union
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
import logging

from backend.src.data.categories import (
    SERVICE_TYPE_CATEGORIES,
    TICKET_STATUS_CATEGORIES,
    TICKET_ASSIGNMENT_STATUS_CATEGORIES,
    APPOINTMENT_STATUS_CATEGORIES,
    CONVERSATION_STATUS_CATEGORIES,
    PRIORITY_VALUES,
    PRIORITY_SCALE
)
from backend.src.config import settings

logger = logging.getLogger(__name__)

# Map (table_name, column_name) to valid category lists
CATEGORY_MAPPINGS: Dict[Tuple[str, str], Union[List[str], List[int]]] = {
    ("service_persons", "service_type"): SERVICE_TYPE_CATEGORIES,
    ("tickets", "service_type"): SERVICE_TYPE_CATEGORIES,
    ("tickets", "status"): TICKET_STATUS_CATEGORIES,
    ("tickets", "priority"): PRIORITY_VALUES,  # Special handling for integer
    ("tickets", "assignment_status"): TICKET_ASSIGNMENT_STATUS_CATEGORIES,
    ("appointments", "status"): APPOINTMENT_STATUS_CATEGORIES,
    ("conversations", "status"): CONVERSATION_STATUS_CATEGORIES,
}


class CategoryNormalizationResult(BaseModel):
    """Result of category normalization."""
    normalized_value: Union[str, int] = Field(description="Normalized category value")
    confidence: str = Field(description="Confidence level: high, medium, or low")
    reasoning: str = Field(description="Brief reasoning for the normalization")


def get_valid_categories(table_name: str, column_name: str) -> Optional[Union[List[str], List[int]]]:
    """Get valid categories for a table.column pair.
    
    Args:
        table_name: Database table name (e.g., "tickets")
        column_name: Column name (e.g., "service_type")
    
    Returns:
        List of valid category values, or None if not found
    """
    return CATEGORY_MAPPINGS.get((table_name, column_name))


async def normalize_category_value(
    table_name: str,
    column_name: str,
    user_input: Union[str, int],
    context: Optional[str] = None
) -> Union[str, int]:
    """
    Normalize user input to valid database category value using LLM.
    
    Args:
        table_name: Database table name (e.g., "tickets")
        column_name: Column name (e.g., "service_type")
        user_input: User-provided value (e.g., "urgent" or 2)
        context: Optional context about the query/operation
    
    Returns:
        Normalized category value (e.g., "emergency" or 2)
    
    Raises:
        ValueError: If normalization fails or value is invalid
    """
    # If input is already an integer and column is priority, validate it
    if column_name == "priority" and isinstance(user_input, int):
        if user_input in PRIORITY_VALUES:
            return user_input
        else:
            raise ValueError(f"Invalid priority value: {user_input}. Must be one of {PRIORITY_VALUES}")
    
    # Get valid categories
    valid_categories = get_valid_categories(table_name, column_name)
    if not valid_categories:
        logger.warning(f"No category mapping found for {table_name}.{column_name}, returning original value")
        return user_input
    
    # If user input is already a valid category, return it
    if isinstance(user_input, str) and user_input.lower() in [str(c).lower() for c in valid_categories]:
        # Return the exact case from valid_categories
        for cat in valid_categories:
            if str(cat).lower() == user_input.lower():
                return cat
    
    # If user input is already an integer in valid categories, return it
    if isinstance(user_input, int) and user_input in valid_categories:
        return user_input
    
    # Convert user input to string for LLM processing
    user_input_str = str(user_input)
    
    # Special handling for priority column
    if column_name == "priority":
        return await _normalize_priority(user_input_str, context)
    
    # Use LLM to normalize
    try:
        llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.1,  # Low temperature for consistent normalization
            api_key=settings.openai_api_key
        )
        structured_llm = llm.with_structured_output(CategoryNormalizationResult)
        
        # Build prompt with valid categories
        valid_categories_str = ", ".join([f'"{cat}"' for cat in valid_categories])
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""You are a category normalization assistant for a hospital database.

Your task is to map user input to the EXACT valid category value from the provided list.

Table: {table_name}
Column: {column_name}
Valid Categories: [{valid_categories_str}]

RULES:
1. Return the EXACT value from the valid categories list (case-sensitive)
2. Map synonyms and variations to the correct category:
   - "urgent" → "emergency" (for service_type)
   - "mental health" → "psychiatry" (for service_type)
   - "heart" → "cardiology" (for service_type)
   - "broken bone" → "orthopedics" (for service_type)
   - "skin issue" → "dermatology" (for service_type)
   - "child" → "pediatrics" (for service_type)
   - "women's health" → "gynecology" (for service_type)
3. If the input is already a valid category, return it as-is
4. If you cannot determine the correct category, return the closest match from the list
5. NEVER return a value that is not in the valid categories list

Context: {context or "No additional context provided"}"""),
            ("human", "User input: {user_input}\n\nNormalize this to an exact value from the valid categories list.")
        ])
        
        chain = prompt | structured_llm
        result = chain.invoke({"user_input": user_input_str})
        
        normalized = result.normalized_value
        
        # Validate the normalized value is in valid categories
        if isinstance(normalized, str):
            # Case-insensitive check
            normalized_lower = normalized.lower()
            valid_lower = [str(c).lower() for c in valid_categories]
            if normalized_lower not in valid_lower:
                # Try to find closest match
                logger.warning(f"LLM returned '{normalized}' which is not in valid categories. Attempting fallback.")
                # Fallback: return original if no match
                if user_input_str.lower() in valid_lower:
                    for cat in valid_categories:
                        if str(cat).lower() == user_input_str.lower():
                            return cat
                raise ValueError(f"Normalized value '{normalized}' is not in valid categories: {valid_categories}")
            # Return exact case from valid_categories
            for cat in valid_categories:
                if str(cat).lower() == normalized_lower:
                    return cat
        
        return normalized
        
    except Exception as e:
        logger.error(f"Error normalizing category value: {e}")
        # Fallback: if user input is close to a valid category, try to match it
        user_input_lower = user_input_str.lower()
        for cat in valid_categories:
            if str(cat).lower() == user_input_lower:
                return cat
        # If all else fails, raise error
        raise ValueError(f"Failed to normalize '{user_input}' for {table_name}.{column_name}: {str(e)}")


async def _normalize_priority(user_input: str, context: Optional[str] = None) -> int:
    """Normalize priority text to integer value (1-5).
    
    Args:
        user_input: User-provided priority value (e.g., "urgent", "critical")
        context: Optional context
    
    Returns:
        Integer priority value (1-5)
    """
    user_input_lower = user_input.lower().strip()
    
    # Direct integer check
    try:
        priority_int = int(user_input)
        if priority_int in PRIORITY_VALUES:
            return priority_int
    except ValueError:
        pass
    
    # Text to priority mapping
    priority_mapping = {
        "critical": 1,
        "emergency": 1,
        "life-threatening": 1,
        "urgent": 2,
        "high": 2,
        "immediate": 2,
        "needs immediate attention": 2,
        "medium": 3,
        "moderate": 3,
        "moderate urgency": 3,
        "low": 4,
        "routine": 4,
        "very low": 5,
        "non-urgent": 5,
    }
    
    # Check direct mapping
    if user_input_lower in priority_mapping:
        return priority_mapping[user_input_lower]
    
    # Check if any key phrase is in the input
    for key, value in priority_mapping.items():
        if key in user_input_lower:
            return value
    
    # Use LLM as fallback
    try:
        llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.1,
            api_key=settings.openai_api_key
        )
        
        class PriorityResult(BaseModel):
            priority: int = Field(description="Priority value (1-5)")
            reasoning: str = Field(description="Reasoning for the priority")
        
        structured_llm = llm.with_structured_output(PriorityResult)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""You are a priority normalization assistant.

Map the user's priority description to an integer value (1-5):
1: Critical/Emergency (life-threatening)
2: High (urgent, needs immediate attention)
3: Medium (moderate urgency)
4: Low (routine)
5: Very Low (non-urgent)

Context: {context or "No additional context"}"""),
            ("human", "User input: {user_input}\n\nReturn the appropriate priority integer (1-5).")
        ])
        
        chain = prompt | structured_llm
        result = chain.invoke({"user_input": user_input})
        
        if result.priority in PRIORITY_VALUES:
            return result.priority
        else:
            raise ValueError(f"LLM returned invalid priority: {result.priority}")
            
    except Exception as e:
        logger.error(f"Error normalizing priority: {e}")
        # Default fallback
        return 3  # Medium priority as safe default


def normalize_category_value_sync(
    table_name: str,
    column_name: str,
    user_input: Union[str, int],
    context: Optional[str] = None
) -> Union[str, int]:
    """
    Synchronous wrapper for normalize_category_value.
    Uses asyncio to run the async function.
    
    Args:
        table_name: Database table name
        column_name: Column name
        user_input: User-provided value
        context: Optional context
    
    Returns:
        Normalized category value
    """
    import asyncio
    import concurrent.futures
    
    def run_in_thread():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(
                normalize_category_value(table_name, column_name, user_input, context)
            )
        finally:
            new_loop.close()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_thread)
        return future.result(timeout=10)
