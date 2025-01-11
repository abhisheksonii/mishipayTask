from django.core.exceptions import ValidationError
import re

def validate_phone_number(value):
    if not re.match(r'^\d{10}$', value):
        raise ValidationError('Phone number must be exactly 10 digits.')

def validate_email(value):
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
        raise ValidationError('Invalid email format.') 