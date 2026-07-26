"""
Property-based tests for SecurityService.

**Feature: fortress-update, Property 36: Input sanitization**
**Validates: Requirements 17.1**

**Feature: fortress-update, Property 37: Rate limiting enforcement**
**Validates: Requirements 17.2**

**Feature: fortress-update, Property 38: Callback signature verification**
**Validates: Requirements 17.12**

**Feature: fortress-update, Property 39: File validation**
**Validates: Requirements 17.4**

**Feature: fortress-update, Property 40: Error message sanitization**
**Validates: Requirements 17.9**

**Feature: fortress-update, Property 41: Access control enforcement**
**Validates: Requirements 17.10**
"""

import os
import sys
import importlib.util
import asyncio
from hypothesis import given, strategies as st, settings, assume

# Import security module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'security.py')
_spec = importlib.util.spec_from_file_location("security", _module_path)
_security_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_security_module)

SecurityService = _security_module.SecurityService
SecurityCheck = _security_module.SecurityCheck
FileInfo = _security_module.FileInfo
MAX_FILE_SIZE_BYTES = _security_module.MAX_FILE_SIZE_BYTES
ALLOWED_FILE_TYPES = _security_module.ALLOWED_FILE_TYPES
DANGEROUS_EXTENSIONS = _security_module.DANGEROUS_EXTENSIONS


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for generating SQL injection patterns
sql_injection_patterns = st.sampled_from([
    "'; DROP TABLE users; --",
    "1' OR '1'='1",
    "1; DELETE FROM users",
    "' UNION SELECT * FROM passwords --",
    "admin'--",
    "1' OR 1=1--",
    "'; INSERT INTO users VALUES('hacker', 'password'); --",
    "SELECT * FROM users WHERE id=1",
    "UPDATE users SET admin=1 WHERE id=1",
    "TRUNCATE TABLE logs",
])

# Strategy for generating XSS patterns
xss_patterns = st.sampled_from([
    "<script>alert('xss')</script>",
    "<img src=x onerror=alert('xss')>",
    "<svg onload=alert('xss')>",
    "<body onload=alert('xss')>",
    "<iframe src='javascript:alert(1)'>",
    "<a href='javascript:alert(1)'>click</a>",
    "javascript:alert('xss')",
    "<div onclick='alert(1)'>click</div>",
])

# Strategy for generating command injection patterns
command_injection_patterns = st.sampled_from([
    "; rm -rf /",
    "| cat /etc/passwd",
    "& whoami",
    "`id`",
    "$(cat /etc/passwd)",
    "|| ls -la",
    "&& rm -rf /",
    "\n cat /etc/passwd",
])

# Strategy for user IDs
user_ids = st.integers(min_value=1, max_value=9999999999)

# Strategy for callback data
callback_data = st.text(
    alphabet=st.characters(
        blacklist_categories=('Cs',),
        blacklist_characters=':'
    ),
    min_size=1,
    max_size=50
)

# Strategy for file sizes
file_sizes = st.integers(min_value=0, max_value=50 * 1024 * 1024)  # 0 to 50MB

# Strategy for MIME types
mime_types = st.sampled_from([
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "video/mp4", "application/pdf", "text/plain",
    "application/x-executable", "application/x-msdownload",
    "application/octet-stream", "text/html",
])

# Strategy for file names
safe_filenames = st.text(
    alphabet=st.characters(
        whitelist_categories=('L', 'N'),
        whitelist_characters='_-'
    ),
    min_size=1,
    max_size=20
).map(lambda x: x + ".txt")

dangerous_filenames = st.sampled_from([
    "virus.exe", "script.bat", "hack.cmd", "malware.scr",
    "payload.ps1", "shell.sh", "backdoor.php", "exploit.py",
])


# ============================================================================
# Property 36: Input Sanitization
# ============================================================================

class TestInputSanitization:
    """
    **Feature: fortress-update, Property 36: Input sanitization**
    **Validates: Requirements 17.1**
    
    For any user input containing SQL injection patterns, XSS tags, or 
    command injection sequences, the sanitized output SHALL have these 
    patterns escaped or removed.
    """
    
    @settings(max_examples=100)
    @given(injection=sql_injection_patterns)
    def test_sql_injection_sanitized(self, injection: str):
        """
        Property: SQL injection patterns are neutralized.
        """
        service = SecurityService()
        result = service.sanitize_input(injection)
        
        # Result should not contain dangerous SQL keywords in executable form
        dangerous_keywords = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'TRUNCATE', 'UNION']
        result_upper = result.upper()
        
        for keyword in dangerous_keywords:
            # Keywords should be removed or the statement should be broken
            assert keyword not in result_upper or '--' not in result
    
    @settings(max_examples=100)
    @given(xss=xss_patterns)
    def test_xss_patterns_escaped(self, xss: str):
        """
        Property: XSS patterns are HTML-escaped.
        """
        service = SecurityService()
        result = service.sanitize_input(xss)
        
        # Result should not contain unescaped HTML tags
        assert '<script>' not in result.lower()
        assert '<img' not in result.lower() or 'onerror' not in result.lower()
        assert '<svg' not in result.lower() or 'onload' not in result.lower()
        assert '<iframe' not in result.lower()
        
        # Angle brackets should be escaped
        if '<' in xss:
            assert '&lt;' in result or '<' not in result
    
    @settings(max_examples=100)
    @given(cmd=command_injection_patterns)
    def test_command_injection_sanitized(self, cmd: str):
        """
        Property: Command injection patterns are removed.
        """
        service = SecurityService()
        result = service.sanitize_input(cmd)
        
        # Dangerous shell metacharacters should be removed
        assert '|' not in result
        assert '`' not in result
        assert '$(' not in result
        assert '&&' not in result
        assert '||' not in result
    
    @settings(max_examples=100)
    @given(text=st.text(min_size=0, max_size=200))
    def test_sanitize_returns_string(self, text: str):
        """
        Property: Sanitization always returns a string.
        """
        service = SecurityService()
        result = service.sanitize_input(text)
        
        assert isinstance(result, str)
    
    def test_empty_input_returns_empty(self):
        """
        Property: Empty input returns empty string.
        """
        service = SecurityService()
        
        assert service.sanitize_input("") == ""
        assert service.sanitize_input(None) == ""



# ============================================================================
# Property 38: Callback Signature Verification
# ============================================================================

class TestCallbackSignatureVerification:
    """
    **Feature: fortress-update, Property 38: Callback signature verification**
    **Validates: Requirements 17.12**
    
    For any callback data, signing then verifying with the same user_id 
    SHALL return true. Verifying with a different user_id SHALL return false.
    """
    
    @settings(max_examples=100)
    @given(data=callback_data, user_id=user_ids)
    def test_sign_then_verify_same_user(self, data: str, user_id: int):
        """
        Property: Signing then verifying with same user_id returns True.
        """
        service = SecurityService()
        
        signed = service.sign_callback_data(data, user_id)
        result = service.verify_callback_signature(signed, user_id)
        
        assert result is True
    
    @settings(max_examples=100)
    @given(data=callback_data, user_id1=user_ids, user_id2=user_ids)
    def test_verify_with_different_user_fails(self, data: str, user_id1: int, user_id2: int):
        """
        Property: Verifying with different user_id returns False.
        """
        assume(user_id1 != user_id2)
        
        service = SecurityService()
        
        signed = service.sign_callback_data(data, user_id1)
        result = service.verify_callback_signature(signed, user_id2)
        
        assert result is False
    
    @settings(max_examples=100)
    @given(data=callback_data, user_id=user_ids)
    def test_signed_data_contains_original(self, data: str, user_id: int):
        """
        Property: Signed data contains the original data.
        """
        service = SecurityService()
        
        signed = service.sign_callback_data(data, user_id)
        
        # Signed format is "data:signature"
        assert signed.startswith(data + ":")
    
    @settings(max_examples=100)
    @given(user_id=user_ids)
    def test_tampered_signature_fails(self, user_id: int):
        """
        Property: Tampered signatures are rejected.
        """
        service = SecurityService()
        
        signed = service.sign_callback_data("original_data", user_id)
        
        # Tamper with the signature
        parts = signed.rsplit(":", 1)
        tampered = parts[0] + ":tampered_sig"
        
        result = service.verify_callback_signature(tampered, user_id)
        
        assert result is False
    
    def test_invalid_format_fails(self):
        """
        Property: Invalid callback data format is rejected.
        """
        service = SecurityService()
        
        # No colon separator
        assert service.verify_callback_signature("no_colon", 123) is False
        
        # Empty string
        assert service.verify_callback_signature("", 123) is False
        
        # None
        assert service.verify_callback_signature(None, 123) is False


# ============================================================================
# Property 37: Rate Limiting Enforcement
# ============================================================================

class TestRateLimitingEnforcement:
    """
    **Feature: fortress-update, Property 37: Rate limiting enforcement**
    **Validates: Requirements 17.2**
    
    For any user sending more than 30 messages within 60 seconds, 
    subsequent messages SHALL be ignored for 5 minutes.
    """
    
    @settings(max_examples=50)
    @given(user_id=user_ids)
    def test_under_limit_allowed(self, user_id: int):
        """
        Property: Users under the rate limit are allowed.
        """
        service = SecurityService()
        
        # First request should always be allowed
        result = asyncio.run(service.check_rate_limit(user_id))
        
        assert result.passed is True
    
    def test_exceeding_limit_blocked(self):
        """
        Property: Users exceeding 30 messages/minute are blocked.
        """
        service = SecurityService()
        user_id = 999999
        
        async def run_test():
            # Send 30 messages (should all pass)
            for i in range(30):
                result = await service.check_rate_limit(user_id)
                assert result.passed is True, f"Request {i+1} should pass"
            
            # 31st message should be blocked
            result = await service.check_rate_limit(user_id)
            return result
        
        result = asyncio.run(run_test())
        
        assert result.passed is False
        assert "Rate limit" in result.reason or "Blocked" in result.reason
    
    def test_blacklisted_user_blocked(self):
        """
        Property: Blacklisted users are always blocked.
        """
        service = SecurityService()
        user_id = 888888
        
        async def run_test():
            # Blacklist the user
            await service.blacklist_user(user_id, "Test blacklist", duration_hours=1)
            
            # User should be blocked
            return await service.check_rate_limit(user_id)
        
        result = asyncio.run(run_test())
        
        assert result.passed is False


# ============================================================================
# Property 39: File Validation
# ============================================================================

class TestFileValidation:
    """
    **Feature: fortress-update, Property 39: File validation**
    **Validates: Requirements 17.4**
    
    For any uploaded file exceeding 20MB, the validation SHALL fail.
    """
    
    @settings(max_examples=100)
    @given(file_size=st.integers(min_value=MAX_FILE_SIZE_BYTES + 1, max_value=100 * 1024 * 1024))
    def test_oversized_files_rejected(self, file_size: int):
        """
        Property: Files larger than 20MB are rejected.
        """
        service = SecurityService()
        
        file_info = FileInfo(
            file_id="test_file",
            file_size=file_size,
            mime_type="image/jpeg",
            file_name="test.jpg"
        )
        
        result = asyncio.run(service.validate_file(file_info))
        
        assert result.passed is False
        assert "too large" in result.reason.lower() or "maximum" in result.reason.lower()
    
    @settings(max_examples=100)
    @given(file_size=st.integers(min_value=1, max_value=MAX_FILE_SIZE_BYTES))
    def test_valid_size_files_accepted(self, file_size: int):
        """
        Property: Files under 20MB with valid type are accepted.
        """
        service = SecurityService()
        
        file_info = FileInfo(
            file_id="test_file",
            file_size=file_size,
            mime_type="image/jpeg",
            file_name="test.jpg"
        )
        
        result = asyncio.run(service.validate_file(file_info))
        
        assert result.passed is True
    
    @settings(max_examples=50)
    @given(filename=dangerous_filenames)
    def test_dangerous_extensions_rejected(self, filename: str):
        """
        Property: Files with dangerous extensions are rejected.
        """
        service = SecurityService()
        
        file_info = FileInfo(
            file_id="test_file",
            file_size=1024,
            mime_type="application/octet-stream",
            file_name=filename
        )
        
        result = asyncio.run(service.validate_file(file_info))
        
        assert result.passed is False
        assert result.should_blacklist is True  # Dangerous file upload attempt



# ============================================================================
# Property 40: Error Message Sanitization
# ============================================================================

class TestErrorMessageSanitization:
    """
    **Feature: fortress-update, Property 40: Error message sanitization**
    **Validates: Requirements 17.9**
    
    For any internal error, the user-facing message SHALL NOT contain 
    stack traces, file paths, or internal variable names.
    """
    
    @settings(max_examples=50)
    @given(error_msg=st.text(min_size=1, max_size=200))
    def test_sanitized_errors_are_safe(self, error_msg: str):
        """
        Property: Sanitized error messages don't contain internal details.
        """
        service = SecurityService()
        
        # Create an exception with potentially sensitive info
        error = Exception(error_msg)
        result = service.sanitize_error_message(error)
        
        # Result should be safe
        assert SecurityService.is_safe_error_message(result)
    
    def test_stack_traces_not_exposed(self):
        """
        Property: Stack traces are never exposed to users.
        """
        service = SecurityService()
        
        try:
            # Generate a real exception with stack trace
            raise ValueError("Internal database connection failed at /home/user/app/db.py:42")
        except Exception as e:
            result = service.sanitize_error_message(e)
        
        # Result should not contain stack trace info
        assert "Traceback" not in result
        assert "/home/" not in result
        assert ".py" not in result
        assert "line" not in result
    
    def test_file_paths_not_exposed(self):
        """
        Property: File paths are never exposed to users.
        """
        service = SecurityService()
        
        error = Exception("Error in /var/www/app/services/database.py at line 123")
        result = service.sanitize_error_message(error)
        
        assert "/var/" not in result
        assert "database.py" not in result
        assert "line 123" not in result
    
    def test_internal_variable_names_not_exposed(self):
        """
        Property: Internal variable names are never exposed.
        """
        service = SecurityService()
        
        error = Exception("self._connection is None, __init__ failed")
        result = service.sanitize_error_message(error)
        
        assert "self." not in result
        assert "__init__" not in result
    
    def test_is_safe_error_message_detects_unsafe(self):
        """
        Property: is_safe_error_message correctly identifies unsafe messages.
        """
        unsafe_messages = [
            "Traceback (most recent call last):",
            'File "/home/user/app.py", line 42',
            "AttributeError: 'NoneType' object has no attribute 'foo'",
            "Error at 0x7f8b8c0d1234",
            "self._connection failed",
            "psycopg2.OperationalError: connection refused",
        ]
        
        for msg in unsafe_messages:
            assert SecurityService.is_safe_error_message(msg) is False, f"Should detect: {msg}"
    
    def test_is_safe_error_message_allows_safe(self):
        """
        Property: is_safe_error_message allows safe messages.
        """
        safe_messages = [
            "Что-то пошло не так. Попробуй ещё раз.",
            "Сервис временно недоступен.",
            "У тебя нет прав на это действие.",
            "Файл слишком большой.",
            "Неверный формат команды.",
        ]
        
        for msg in safe_messages:
            assert SecurityService.is_safe_error_message(msg) is True, f"Should allow: {msg}"


# ============================================================================
# Property 41: Access Control Enforcement
# ============================================================================

class TestAccessControlEnforcement:
    """
    **Feature: fortress-update, Property 41: Access control enforcement**
    **Validates: Requirements 17.10**
    
    For any request to access user X's private data by user Y (where X != Y), 
    the request SHALL be denied.
    """
    
    @settings(max_examples=100)
    @given(user_id=user_ids)
    def test_user_can_access_own_data(self, user_id: int):
        """
        Property: Users can access their own private data.
        """
        service = SecurityService()
        
        result = asyncio.run(service.check_private_data_access(user_id, user_id))
        
        assert result.passed is True
    
    @settings(max_examples=100)
    @given(requester_id=user_ids, target_id=user_ids)
    def test_user_cannot_access_others_data(self, requester_id: int, target_id: int):
        """
        Property: Users cannot access other users' private data.
        """
        assume(requester_id != target_id)
        
        service = SecurityService()
        
        result = asyncio.run(service.check_private_data_access(requester_id, target_id))
        
        assert result.passed is False
        assert "denied" in result.reason.lower() or "access" in result.reason.lower()
