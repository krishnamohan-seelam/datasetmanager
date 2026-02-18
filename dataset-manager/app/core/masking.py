"""
Data masking engine for Dataset Manager
"""

import re
from typing import Any, Optional, Dict
from enum import Enum


class MaskingRule(str, Enum):
    """Built-in masking rules"""

    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    NAME = "name"
    IP = "ip"
    CUSTOM = "custom"
    
    # Frontend aligned rules
    REDACT = "redact"
    HASH = "hash"
    PARTIAL_EMAIL = "partial_email"
    PARTIAL_TEXT = "partial_text"
    NUMERIC_ROUND = "numeric_round"


class DataMasker:
    """Centralized data masking utilities"""

    @staticmethod
    def mask_redact(value: Any) -> str:
        """Fully redact the value"""
        return "********"

    @staticmethod
    def mask_hash(value: Any) -> str:
        """Return a truncated hash of the value"""
        if value is None:
            return None
        import hashlib
        return hashlib.sha256(str(value).encode()).hexdigest()[:12] + "..."

    @staticmethod
    def mask_numeric_round(value: Any) -> Any:
        """Round numeric values to nearest 10 or 100"""
        try:
            num = float(value)
            if abs(num) > 100:
                return round(num / 100) * 100
            return round(num / 10) * 10
        except (ValueError, TypeError):
            return "***"
            
    # Existing methods... (I will keep them in the actual replace call)

    @staticmethod
    def mask_email(email: str) -> str:
        """
        Mask email address
        Example: john.doe@example.com -> jo***@example.com
        """
        if not email or "@" not in email:
            return "***@***.***"

        local, domain = email.split("@")
        if len(local) <= 2:
            return f"{local}@{domain}"

        return f"{local[:2]}***@{domain}"

    @staticmethod
    def mask_phone(phone: str) -> str:
        """
        Mask phone number
        Example: +1-555-123-4567 -> ***-***-4567
        """
        if not phone:
            return "***-***-****"

        # Remove non-digit characters to get last 4 digits
        digits = re.sub(r"\D", "", phone)
        if len(digits) >= 4:
            return "***-***-" + digits[-4:]
        return "***-***-****"

    @staticmethod
    def mask_ssn(ssn: str) -> str:
        """
        Mask SSN (Social Security Number)
        Example: 123-45-6789 -> ***-**-6789
        """
        if not ssn:
            return "***-**-****"

        digits = re.sub(r"\D", "", ssn)
        if len(digits) == 9:
            return f"***-**-{digits[-4:]}"
        return "***-**-****"

    @staticmethod
    def mask_credit_card(card: str) -> str:
        """
        Mask credit card number
        Example: 4532-1234-5678-9010 -> ****-****-****-9010
        """
        if not card:
            return "****-****-****-****"

        digits = re.sub(r"\D", "", card)
        if len(digits) >= 4:
            return "****-****-****-" + digits[-4:]
        return "****-****-****-****"

    @staticmethod
    def mask_name(name: str) -> str:
        """
        Mask full name
        Example: John Michael Doe -> J*** M*** D***
        """
        if not name:
            return "***"

        parts = name.split()
        masked_parts = [
            part[0] + "***" if len(part) > 1 else "*" for part in parts
        ]
        return " ".join(masked_parts)

    @staticmethod
    def mask_ip(ip: str) -> str:
        """
        Mask IP address
        Example: 192.168.1.100 -> 192.168.***.***
        """
        if not ip:
            return "***.***.***.***"

        parts = ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.***.**"
        return "***.***.***.***"

    @staticmethod
    def mask_custom(value: str, pattern: str) -> str:
        """
        Apply custom regex masking

        Args:
            value: Value to mask
            pattern: Regex pattern to match (unmatched parts shown as *)

        Returns:
            Masked value
        """
        if not value or not pattern:
            return "*" * len(value) if value else "***"

        try:
            # Replace all non-matching characters with *
            result = re.sub(pattern, "*", value)
            return result
        except re.error:
            return "*" * len(value)

    @staticmethod
    def mask_value(
        value: Any,
        mask_rule: str,
        user_role: str = "viewer",
        allow_unmask_roles: Optional[list] = None,
    ) -> Any:
        """
        Apply masking rule to value based on user role

        Args:
            value: Value to mask
            mask_rule: Masking rule name (e.g., 'email', 'phone')
            user_role: User role ('admin', 'contributor', 'viewer')
            allow_unmask_roles: Roles allowed to see unmasked data (default: ['admin'])

        Returns:
            Masked or unmasked value
        """
        if allow_unmask_roles is None:
            allow_unmask_roles = ["admin"]

        # Don't mask for admin users
        if user_role in allow_unmask_roles:
            return value

        # Don't mask None or empty values
        if value is None or value == "":
            return value

        # Convert to string if not already
        str_value = str(value)

        # Apply appropriate masking rule
        if mask_rule in [MaskingRule.EMAIL, MaskingRule.PARTIAL_EMAIL]:
            return DataMasker.mask_email(str_value)
        elif mask_rule == MaskingRule.PHONE:
            return DataMasker.mask_phone(str_value)
        elif mask_rule == MaskingRule.SSN:
            return DataMasker.mask_ssn(str_value)
        elif mask_rule == MaskingRule.CREDIT_CARD:
            return DataMasker.mask_credit_card(str_value)
        elif mask_rule in [MaskingRule.NAME, MaskingRule.PARTIAL_TEXT]:
            return DataMasker.mask_name(str_value)
        elif mask_rule == MaskingRule.IP:
            return DataMasker.mask_ip(str_value)
        elif mask_rule == MaskingRule.REDACT:
            return DataMasker.mask_redact(str_value)
        elif mask_rule == MaskingRule.HASH:
            return DataMasker.mask_hash(str_value)
        elif mask_rule == MaskingRule.NUMERIC_ROUND:
            return DataMasker.mask_numeric_round(str_value)
        elif mask_rule.startswith("custom:"):
            pattern = mask_rule.replace("custom:", "")
            return DataMasker.mask_custom(str_value, pattern)
        else:
            # Unknown rule, don't mask
            return value
