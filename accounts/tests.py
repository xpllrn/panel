"""
Tests for the accounts app.
Covers utility functions, model validators, and user model methods.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from accounts.models import LoginOTPChallenge, UserDevice, aadhar_validator, ifsc_validator, pan_validator, phone_validator, pincode_validator
from accounts.utils import combine_name, split_full_name, validate_password_strength

User = get_user_model()


class SplitFullNameTests(TestCase):
    """Tests for the split_full_name utility function."""

    def test_splits_two_part_name(self):
        """Should correctly split 'John Doe' into first and last name."""
        first, last = split_full_name("John Doe")
        self.assertEqual(first, "John")
        self.assertEqual(last, "Doe")

    def test_single_name(self):
        """Should handle single name, leaving last name empty."""
        first, last = split_full_name("John")
        self.assertEqual(first, "John")
        self.assertEqual(last, "")

    def test_three_part_name(self):
        """Should keep middle and last together in last_name."""
        first, last = split_full_name("John Michael Doe")
        self.assertEqual(first, "John")
        self.assertEqual(last, "Michael Doe")

    def test_empty_string(self):
        """Should return empty strings for empty input."""
        first, last = split_full_name("")
        self.assertEqual(first, "")
        self.assertEqual(last, "")

    def test_none_input(self):
        """Should handle None gracefully."""
        first, last = split_full_name(None)
        self.assertEqual(first, "")
        self.assertEqual(last, "")

    def test_whitespace_only(self):
        """Should handle whitespace-only input."""
        first, last = split_full_name("   ")
        self.assertEqual(first, "")
        self.assertEqual(last, "")

    def test_leading_trailing_whitespace(self):
        """Should trim leading/trailing whitespace."""
        first, last = split_full_name("  John Doe  ")
        self.assertEqual(first, "John")
        self.assertEqual(last, "Doe")


class CombineNameTests(TestCase):
    """Tests for the combine_name utility function."""

    def test_combines_first_and_last(self):
        """Should combine first and last into full name."""
        result = combine_name("John", "Doe")
        self.assertEqual(result, "John Doe")

    def test_first_only(self):
        """Should return just first name if last is empty."""
        result = combine_name("John", "")
        self.assertEqual(result, "John")

    def test_last_only(self):
        """Should return just last name if first is empty."""
        result = combine_name("", "Doe")
        self.assertEqual(result, "Doe")

    def test_both_empty(self):
        """Should return empty string if both are empty."""
        result = combine_name("", "")
        self.assertEqual(result, "")

    def test_none_values(self):
        """Should handle None values gracefully."""
        result = combine_name(None, None)
        self.assertEqual(result, "")

    def test_trims_whitespace(self):
        """Should trim whitespace from inputs."""
        result = combine_name("  John  ", "  Doe  ")
        self.assertEqual(result, "John Doe")


class PasswordValidationTests(TestCase):
    """Tests for password validation utility."""

    def test_valid_password(self):
        """Should accept a strong password."""
        is_valid, errors = validate_password_strength("SecureP@ss123!")
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    def test_short_password(self):
        """Should reject password shorter than 8 characters."""
        is_valid, errors = validate_password_strength("Short1!")
        self.assertFalse(is_valid)
        self.assertTrue(len(errors) > 0)

    def test_common_password(self):
        """Should reject common passwords."""
        is_valid, errors = validate_password_strength("password123")
        self.assertFalse(is_valid)

    def test_empty_password(self):
        """Should reject empty password."""
        is_valid, errors = validate_password_strength("")
        self.assertFalse(is_valid)
        self.assertIn("Password is required", errors)

    def test_none_password(self):
        """Should handle None password."""
        is_valid, errors = validate_password_strength(None)
        self.assertFalse(is_valid)


class PANValidatorTests(TestCase):
    """Tests for PAN number validation."""

    def test_valid_pan(self):
        """Should accept valid PAN format."""
        try:
            pan_validator("ABCDE1234F")
        except ValidationError:
            self.fail("Valid PAN raised ValidationError")

    def test_lowercase_pan(self):
        """Should reject lowercase PAN."""
        with self.assertRaises(ValidationError):
            pan_validator("abcde1234f")

    def test_wrong_format(self):
        """Should reject wrong format."""
        with self.assertRaises(ValidationError):
            pan_validator("12345ABCDE")

    def test_short_pan(self):
        """Should reject PAN shorter than 10 chars."""
        with self.assertRaises(ValidationError):
            pan_validator("ABCD1234")


class AadhaarValidatorTests(TestCase):
    """Tests for Aadhaar number validation."""

    def test_valid_aadhar(self):
        """Should accept valid 12-digit Aadhaar."""
        try:
            aadhar_validator("234567890123")
        except ValidationError:
            self.fail("Valid Aadhaar raised ValidationError")

    def test_starts_with_zero(self):
        """Should reject Aadhaar starting with 0."""
        with self.assertRaises(ValidationError):
            aadhar_validator("012345678901")

    def test_starts_with_one(self):
        """Should reject Aadhaar starting with 1."""
        with self.assertRaises(ValidationError):
            aadhar_validator("123456789012")

    def test_short_aadhar(self):
        """Should reject Aadhaar shorter than 12 digits."""
        with self.assertRaises(ValidationError):
            aadhar_validator("2345678901")


class PhoneValidatorTests(TestCase):
    """Tests for Indian phone number validation."""

    def test_valid_phone_starting_6(self):
        """Should accept phone starting with 6."""
        try:
            phone_validator("6123456789")
        except ValidationError:
            self.fail("Valid phone raised ValidationError")

    def test_valid_phone_starting_9(self):
        """Should accept phone starting with 9."""
        try:
            phone_validator("9876543210")
        except ValidationError:
            self.fail("Valid phone raised ValidationError")

    def test_starts_with_5(self):
        """Should reject phone starting with 5."""
        with self.assertRaises(ValidationError):
            phone_validator("5123456789")

    def test_short_phone(self):
        """Should reject phone shorter than 10 digits."""
        with self.assertRaises(ValidationError):
            phone_validator("912345678")


class IFSCValidatorTests(TestCase):
    """Tests for IFSC code validation."""

    def test_valid_ifsc(self):
        """Should accept valid IFSC format."""
        try:
            ifsc_validator("SBIN0001234")
        except ValidationError:
            self.fail("Valid IFSC raised ValidationError")

    def test_wrong_fifth_char(self):
        """Should reject IFSC without 0 at 5th position."""
        with self.assertRaises(ValidationError):
            ifsc_validator("SBIN1001234")

    def test_short_ifsc(self):
        """Should reject IFSC shorter than 11 chars."""
        with self.assertRaises(ValidationError):
            ifsc_validator("SBIN000123")


class PincodeValidatorTests(TestCase):
    """Tests for Indian pincode validation."""

    def test_valid_pincode(self):
        """Should accept valid 6-digit pincode."""
        try:
            pincode_validator("400001")
        except ValidationError:
            self.fail("Valid pincode raised ValidationError")

    def test_starts_with_zero(self):
        """Should reject pincode starting with 0."""
        with self.assertRaises(ValidationError):
            pincode_validator("012345")

    def test_short_pincode(self):
        """Should reject pincode shorter than 6 digits."""
        with self.assertRaises(ValidationError):
            pincode_validator("40001")


class UserModelTests(TestCase):
    """Tests for User model methods."""

    def setUp(self):
        """Create a test user."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="TestPass123!",
            first_name="Test",
            last_name="User",
        )

    def test_display_name_property(self):
        """Should return first_name + last_name as display name."""
        self.assertEqual(self.user.display_name, "Test User")

    def test_str_representation(self):
        """Should return formatted string representation."""
        self.assertIn("testuser", str(self.user))

    def test_get_role_display_name(self):
        """Should return human-readable role name."""
        self.user.role = "admin"
        display = self.user.get_role_display_name()
        self.assertEqual(display, "Admin")

    def test_default_role_is_member(self):
        """New users should have 'member' role by default."""
        new_user = User.objects.create_user(username="newuser", email="new@example.com", password="NewPass123!")
        self.assertEqual(new_user.role, "member")


class OtpLoginFlowTests(TestCase):
    """Tests for OTP login endpoints and device registration."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="otpuser",
            email="otp@example.com",
            password="TestPass123!",
            role="member",
            status="active",
            is_active=True,
        )

    def test_login_start_creates_challenge(self):
        response = self.client.post(
            reverse("api:auth_login_start"),
            {"username": "otpuser", "password": "TestPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get("success"))
        self.assertTrue(LoginOTPChallenge.objects.filter(user=self.user).exists())

    def test_verify_otp_rejects_invalid_code(self):
        start = self.client.post(
            reverse("api:auth_login_start"),
            {"username": "otpuser", "password": "TestPass123!"},
            format="json",
        )
        challenge_token = start.data["challenge_token"]
        verify = self.client.post(
            reverse("api:auth_verify_otp"),
            {"challenge_token": challenge_token, "otp": "000000"},
            format="json",
        )
        self.assertEqual(verify.status_code, 400)
        self.assertFalse(verify.data.get("success"))

    def test_register_and_unregister_device(self):
        self.client.force_authenticate(self.user)
        register = self.client.post(
            reverse("api:register_device_token"),
            {"token": "test-device-token", "platform": "android"},
            format="json",
        )
        self.assertEqual(register.status_code, 200)
        self.assertTrue(UserDevice.objects.filter(user=self.user, token="test-device-token", is_active=True).exists())

        unregister = self.client.post(
            reverse("api:unregister_device_token"),
            {"token": "test-device-token"},
            format="json",
        )
        self.assertEqual(unregister.status_code, 200)
        self.assertTrue(UserDevice.objects.filter(user=self.user, token="test-device-token", is_active=False).exists())
