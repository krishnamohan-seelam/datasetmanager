"""
Unit tests for data masking engine
"""

import pytest
from app.core.masking import DataMasker, MaskingRule


class TestDataMasker:
    """Tests for DataMasker class"""

    def test_mask_email(self):
        """Test email masking"""
        # Standard email
        result = DataMasker.mask_email("john.doe@example.com")
        assert result == "jo***@example.com"

        # Short email
        result = DataMasker.mask_email("a@test.com")
        assert result == "a@test.com" or "***@test.com" in result

        # Empty email
        result = DataMasker.mask_email("")
        assert result == "***@***.***"

    def test_mask_phone(self):
        """Test phone masking"""
        # Standard phone
        result = DataMasker.mask_phone("+1-555-123-4567")
        assert result == "***-***-4567"

        # Just digits
        result = DataMasker.mask_phone("15551234567")
        assert "4567" in result

        # Empty phone
        result = DataMasker.mask_phone("")
        assert "***" in result

    def test_mask_ssn(self):
        """Test SSN masking"""
        # Standard SSN
        result = DataMasker.mask_ssn("123-45-6789")
        assert result == "***-**-6789"

        # Without dashes
        result = DataMasker.mask_ssn("123456789")
        assert "6789" in result

    def test_mask_credit_card(self):
        """Test credit card masking"""
        # Standard card
        result = DataMasker.mask_credit_card("4532-1234-5678-9010")
        assert result == "****-****-****-9010"

        # Without dashes
        result = DataMasker.mask_credit_card("4532123456789010")
        assert "9010" in result

    def test_mask_name(self):
        """Test name masking"""
        # Full name
        result = DataMasker.mask_name("John Michael Doe")
        assert "J***" in result and "D***" in result

        # Single name
        result = DataMasker.mask_name("John")
        assert result == "J***"

    def test_mask_ip(self):
        """Test IP masking"""
        # Standard IP
        result = DataMasker.mask_ip("192.168.1.100")
        assert result.startswith("192.168")
        assert "***" in result

    def test_mask_value_admin_no_masking(self):
        """Test that admin role doesn't mask data"""
        result = DataMasker.mask_value(
            "john.doe@example.com", MaskingRule.EMAIL, user_role="admin"
        )
        assert result == "john.doe@example.com"

    def test_mask_value_viewer_with_masking(self):
        """Test that viewer role masks data"""
        result = DataMasker.mask_value(
            "john.doe@example.com", MaskingRule.EMAIL, user_role="viewer"
        )
        assert result != "john.doe@example.com"
        assert "@example.com" in result

    def test_mask_none_value(self):
        """Test masking None values"""
        result = DataMasker.mask_value(None, MaskingRule.EMAIL, user_role="viewer")
        assert result is None

    def test_custom_masking(self):
        """Test custom regex masking"""
        # Should replace digits with *
        result = DataMasker.mask_custom("ABC123DEF456", r"\d")
        assert "***" in result


class TestMaskingRules:
    """Test masking rule application"""

    def test_all_builtin_rules(self):
        """Test all built-in masking rules"""
        test_data = {
            MaskingRule.EMAIL: "test@example.com",
            MaskingRule.PHONE: "555-123-4567",
            MaskingRule.SSN: "123-45-6789",
            MaskingRule.CREDIT_CARD: "4532-1234-5678-9010",
            MaskingRule.NAME: "John Doe",
            MaskingRule.IP: "192.168.1.1",
        }

        for rule, value in test_data.items():
            result = DataMasker.mask_value(value, rule, user_role="viewer")
            # Result should be different from original (masked)
            assert result != value or result == "***"
