"""
Healthcare Database Categories and Validation Module

This package provides category definitions and validation functions for the
hospital AI platform database schema.

Usage:
    from backend.src.data import categories, validators
    
    # Use categories
    from backend.src.data.categories import SERVICE_TYPE_CATEGORIES, GENDER_CATEGORIES
    
    # Use validators
    from backend.src.data.validators import validate_service_type, validate_phone_number
"""

from . import categories
from . import validators

__all__ = ["categories", "validators"]
