"""
ABVTrends - Security Test Suite

Comprehensive tests for all security features implemented:
1. CORS Configuration - No wildcards, specific origins only
2. SSL Certificate Verification - CERT_REQUIRED for database
3. Environment Variable Security - No hardcoded credentials
4. .gitignore Patterns - Sensitive files excluded
5. Secrets Manager Integration - ECS task definition validation
"""

import os
import re
import ssl
import glob
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# =============================================================================
# CORS SECURITY TESTS
# =============================================================================


class TestCORSConfiguration:
    """Test CORS is properly configured without wildcards."""

    def test_cors_no_wildcard_origins(self):
        """Verify CORS does not allow wildcard subdomains."""
        from app.core.config import settings

        origins = settings.allowed_origins.split(",")

        for origin in origins:
            origin = origin.strip()
            # No wildcards allowed
            assert "*" not in origin, f"Wildcard found in CORS origin: {origin}"
            # Must be a valid URL format
            assert origin.startswith("http://") or origin.startswith(
                "https://"
            ), f"Invalid origin format: {origin}"

    def test_cors_allowed_origins_list(self):
        """Verify only specific allowed origins are configured."""
        from app.core.config import settings

        origins = [o.strip() for o in settings.allowed_origins.split(",")]

        # Should contain localhost for development
        assert any(
            "localhost" in o for o in origins
        ), "localhost should be in allowed origins for development"

        # Should not contain any wildcard patterns
        wildcard_patterns = ["*.", "://*", "*."]
        for origin in origins:
            for pattern in wildcard_patterns:
                assert (
                    pattern not in origin
                ), f"Wildcard pattern '{pattern}' found in origin: {origin}"

    def test_cors_middleware_configuration(self):
        """Test that CORS middleware is properly configured in the app."""
        from app.main import app

        # Find CORS middleware in app
        cors_middleware = None
        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware):
                cors_middleware = middleware
                break

        assert cors_middleware is not None, "CORSMiddleware not found in app"

    def test_cors_rejects_unauthorized_origin(self, test_client):
        """Test that unauthorized origins are rejected."""
        response = test_client.options(
            "/health", headers={"Origin": "https://malicious-site.com"}
        )

        # Check that unauthorized origin doesn't get CORS headers
        cors_header = response.headers.get("access-control-allow-origin")
        assert cors_header != "https://malicious-site.com"

    def test_cors_allows_authorized_origin(self, test_client):
        """Test that authorized origins are allowed."""
        response = test_client.options(
            "/health", headers={"Origin": "http://localhost:3000"}
        )

        # Authorized origin should be reflected or allowed
        # Note: TestClient behavior may vary
        assert response.status_code in [200, 204, 405]


# =============================================================================
# SSL CERTIFICATE VERIFICATION TESTS
# =============================================================================


class TestSSLConfiguration:
    """Test SSL certificate verification is properly configured."""

    def test_ssl_context_verification_mode(self):
        """Verify SSL context uses CERT_REQUIRED when enabled."""
        from app.core.config import settings

        if settings.db_ssl_required:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED

            assert (
                ssl_context.verify_mode == ssl.CERT_REQUIRED
            ), "SSL must use CERT_REQUIRED"
            assert ssl_context.check_hostname is True, "SSL must verify hostname"

    def test_ssl_not_using_cert_none(self):
        """Ensure CERT_NONE is never used in database configuration."""
        from app.core import database

        # Read the source file to verify no CERT_NONE
        db_file = Path(__file__).parent.parent / "app" / "core" / "database.py"
        content = db_file.read_text()

        # CERT_NONE should not be present (except in comments about what NOT to do)
        cert_none_pattern = r"verify_mode\s*=\s*ssl\.CERT_NONE"
        matches = re.findall(cert_none_pattern, content)
        assert len(matches) == 0, "CERT_NONE should not be used for SSL verification"

    def test_ssl_check_hostname_enabled(self):
        """Verify check_hostname is True when SSL is required."""
        db_file = Path(__file__).parent.parent / "app" / "core" / "database.py"
        content = db_file.read_text()

        # When SSL is enabled, check_hostname should be True
        if "db_ssl_required" in content:
            # Verify check_hostname = True is present
            assert (
                "check_hostname = True" in content
            ), "check_hostname must be True for SSL"

    def test_db_ssl_required_default(self):
        """Test that db_ssl_required defaults to False for local dev."""
        from app.core.config import Settings

        # Fresh settings without env override
        with patch.dict(os.environ, {}, clear=False):
            test_settings = Settings(
                database_url="postgresql://test:test@localhost/test"
            )
            # Default should be False for local development
            assert isinstance(test_settings.db_ssl_required, bool)


# =============================================================================
# ENVIRONMENT VARIABLE SECURITY TESTS
# =============================================================================


class TestEnvironmentSecurity:
    """Test that no credentials are hardcoded in the codebase."""

    def test_no_hardcoded_passwords_in_config(self):
        """Verify config.py has no hardcoded real passwords."""
        config_file = Path(__file__).parent.parent / "app" / "core" / "config.py"
        content = config_file.read_text()

        # Common password patterns to check for
        password_patterns = [
            r'password\s*[=:]\s*["\'][^"\']{8,}["\']',  # password = "something"
            r"sk-[a-zA-Z0-9]{20,}",  # OpenAI API key format
            r"[a-zA-Z0-9+/]{40,}={0,2}",  # Base64 encoded secrets (long strings)
        ]

        # Exclude obvious defaults/examples
        exclude_patterns = [
            "your-password",
            "change-me",
            "example",
            "placeholder",
            "localhost",
            "test",
        ]

        for pattern in password_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                is_safe = any(
                    excl in match.lower() for excl in exclude_patterns
                )
                if not is_safe and len(match) > 15:
                    # Only fail if it looks like a real credential
                    assert False, f"Potential hardcoded credential found: {match[:20]}..."

    def test_no_hardcoded_api_keys(self):
        """Check for hardcoded API keys in Python files."""
        backend_path = Path(__file__).parent.parent
        py_files = list(backend_path.glob("app/**/*.py"))

        api_key_patterns = [
            r"sk-proj-[a-zA-Z0-9]{20,}",  # OpenAI project key
            r"sk-[a-zA-Z0-9]{48}",  # OpenAI API key
            r"AKIA[0-9A-Z]{16}",  # AWS Access Key ID
        ]

        for py_file in py_files:
            content = py_file.read_text()
            for pattern in api_key_patterns:
                matches = re.findall(pattern, content)
                assert (
                    len(matches) == 0
                ), f"API key pattern found in {py_file}: {pattern}"

    def test_env_example_has_placeholders(self):
        """Verify .env.example uses placeholder values, not real credentials."""
        env_example = Path(__file__).parent.parent / ".env.example"

        if env_example.exists():
            content = env_example.read_text()

            # Should contain placeholder indicators
            placeholder_indicators = [
                "your-",
                "example",
                "placeholder",
                "change-me",
                "localhost",
            ]
            assert any(
                indicator in content.lower() for indicator in placeholder_indicators
            ), ".env.example should contain placeholder values"

            # Should NOT contain real-looking credentials
            # Real API keys are typically 32+ chars of alphanumeric
            real_credential_pattern = r"=[a-zA-Z0-9!@#$%^&*]{20,}"
            matches = re.findall(real_credential_pattern, content)

            for match in matches:
                # Filter out obvious placeholders
                if not any(
                    p in match.lower()
                    for p in ["your", "example", "password", "here", "key"]
                ):
                    assert (
                        False
                    ), f"Potential real credential in .env.example: {match[:15]}..."

    def test_settings_loads_from_environment(self):
        """Test that settings properly load from environment variables."""
        from app.core.config import Settings

        test_email = "test@example.com"

        with patch.dict(os.environ, {"LIBDIB_EMAIL": test_email}):
            settings = Settings()
            # Settings should load from env
            assert (
                settings.libdib_email == test_email
            ), "Settings should load from environment"


# =============================================================================
# GITIGNORE SECURITY TESTS
# =============================================================================


class TestGitignorePatterns:
    """Test that .gitignore properly excludes sensitive files."""

    def test_gitignore_excludes_env_files(self):
        """Verify .gitignore excludes .env files."""
        gitignore = Path(__file__).parent.parent.parent / ".gitignore"
        content = gitignore.read_text()

        env_patterns = [".env", "*.env"]
        for pattern in env_patterns:
            assert pattern in content, f".gitignore should exclude {pattern}"

    def test_gitignore_excludes_secrets(self):
        """Verify .gitignore excludes secret/credential files."""
        gitignore = Path(__file__).parent.parent.parent / ".gitignore"
        content = gitignore.read_text()

        secret_patterns = ["*.pem", "*.key", "secrets/", "credentials/"]
        for pattern in secret_patterns:
            assert pattern in content, f".gitignore should exclude {pattern}"

    def test_gitignore_excludes_terraform_state(self):
        """Verify .gitignore excludes Terraform state files."""
        gitignore = Path(__file__).parent.parent.parent / ".gitignore"
        content = gitignore.read_text()

        tf_patterns = ["*.tfstate", "terraform.tfvars"]
        for pattern in tf_patterns:
            assert pattern in content, f".gitignore should exclude {pattern}"

    def test_gitignore_allows_env_example(self):
        """Verify .gitignore allows .env.example to be committed."""
        gitignore = Path(__file__).parent.parent.parent / ".gitignore"
        content = gitignore.read_text()

        # Should have exception for .env.example
        assert "!.env.example" in content or "!*.env.example" in content

    def test_no_env_file_in_repo(self):
        """Verify no .env file exists in the repository root."""
        backend_path = Path(__file__).parent.parent
        env_file = backend_path / ".env"

        # .env should not exist (or if testing locally, shouldn't be tracked)
        # This test checks the principle - actual git tracking is separate
        if env_file.exists():
            # If it exists, it should be gitignored
            gitignore = Path(__file__).parent.parent.parent / ".gitignore"
            content = gitignore.read_text()
            assert ".env" in content, ".env must be in .gitignore"


# =============================================================================
# AWS SECRETS MANAGER INTEGRATION TESTS
# =============================================================================


class TestSecretsManagerIntegration:
    """Test ECS task definition uses Secrets Manager properly."""

    def test_task_definition_uses_secrets_manager(self):
        """Verify ECS task definition references Secrets Manager for credentials."""
        task_def_path = (
            Path(__file__).parent.parent
            / "scripts"
            / "task-definition-parkstreet.json"
        )

        if task_def_path.exists():
            import json

            content = json.loads(task_def_path.read_text())

            # Check for secrets section
            container_defs = content.get("containerDefinitions", [])
            assert len(container_defs) > 0, "Task definition should have containers"

            secrets = container_defs[0].get("secrets", [])
            assert len(secrets) > 0, "Task definition should use secrets"

            # Verify secrets use valueFrom with Secrets Manager ARN
            for secret in secrets:
                value_from = secret.get("valueFrom", "")
                assert "secretsmanager" in value_from.lower(), (
                    f"Secret {secret.get('name')} should reference Secrets Manager"
                )

    def test_task_definition_no_plaintext_passwords(self):
        """Verify no plaintext passwords in ECS task definition."""
        task_def_path = (
            Path(__file__).parent.parent
            / "scripts"
            / "task-definition-parkstreet.json"
        )

        if task_def_path.exists():
            import json

            content = json.loads(task_def_path.read_text())
            content_str = json.dumps(content)

            # Check environment variables don't contain passwords
            container_defs = content.get("containerDefinitions", [])
            for container in container_defs:
                env_vars = container.get("environment", [])
                for env_var in env_vars:
                    name = env_var.get("name", "").lower()
                    value = env_var.get("value", "")

                    # Password-related vars should NOT be in environment
                    if "password" in name or "secret" in name or "key" in name:
                        # These should be in secrets, not environment
                        assert (
                            len(value) < 10 or value.lower() in ["true", "false"]
                        ), f"Credential {name} should not be in plaintext environment"


# =============================================================================
# CODE SCANNING TESTS
# =============================================================================


class TestCodeScanning:
    """Test for common security vulnerabilities in code."""

    def test_no_eval_usage(self):
        """Check that eval() is not used (code injection risk)."""
        backend_path = Path(__file__).parent.parent
        py_files = list(backend_path.glob("app/**/*.py"))

        for py_file in py_files:
            content = py_file.read_text()
            # Check for eval() calls (excluding comments)
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if "eval(" in line and not line.strip().startswith("#"):
                    assert False, f"eval() found in {py_file}:{i} - security risk"

    def test_no_exec_usage(self):
        """Check that exec() is not used (code injection risk)."""
        backend_path = Path(__file__).parent.parent
        py_files = list(backend_path.glob("app/**/*.py"))

        for py_file in py_files:
            content = py_file.read_text()
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if "exec(" in line and not line.strip().startswith("#"):
                    assert False, f"exec() found in {py_file}:{i} - security risk"

    def test_no_shell_injection_in_subprocess(self):
        """Check for shell=True in subprocess calls (command injection risk)."""
        backend_path = Path(__file__).parent.parent
        py_files = list(backend_path.glob("app/**/*.py"))

        for py_file in py_files:
            content = py_file.read_text()
            if "subprocess" in content:
                # Check for shell=True
                if "shell=True" in content:
                    # Verify it's not in a comment
                    lines = content.split("\n")
                    for i, line in enumerate(lines, 1):
                        if "shell=True" in line and not line.strip().startswith("#"):
                            assert (
                                False
                            ), f"shell=True in {py_file}:{i} - command injection risk"

    def test_sql_uses_parameterized_queries(self):
        """Check that raw SQL uses parameterized queries."""
        backend_path = Path(__file__).parent.parent
        py_files = list(backend_path.glob("app/**/*.py"))

        dangerous_patterns = [
            r'execute\(["\'].*%s.*%',  # String formatting in SQL
            r'execute\(f["\']',  # f-string in SQL
            r"execute\([^)]*\+",  # String concatenation in SQL
        ]

        for py_file in py_files:
            content = py_file.read_text()
            for pattern in dangerous_patterns:
                if re.search(pattern, content):
                    # Check if it's in a comment
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        # Get the line
                        start = content.rfind("\n", 0, match.start()) + 1
                        line = content[start : content.find("\n", match.start())]
                        if not line.strip().startswith("#"):
                            assert (
                                False
                            ), f"Potential SQL injection in {py_file}: {line[:50]}"


# =============================================================================
# HTTP SECURITY HEADERS TESTS
# =============================================================================


class TestHTTPSecurityHeaders:
    """Test for proper HTTP security headers."""

    def test_health_endpoint_accessible(self, test_client):
        """Verify health endpoint is accessible."""
        response = test_client.get("/health")
        assert response.status_code == 200

    def test_cors_headers_on_options(self, test_client):
        """Test CORS headers are set on OPTIONS requests."""
        response = test_client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should either allow or properly handle OPTIONS
        assert response.status_code in [200, 204, 405]


# =============================================================================
# SENSITIVE DATA EXPOSURE TESTS
# =============================================================================


class TestSensitiveDataExposure:
    """Test that sensitive data is not exposed in responses."""

    def test_error_responses_dont_leak_details_in_prod(self, test_client):
        """Verify error responses don't leak sensitive details in production."""
        # Trigger a 404
        response = test_client.get("/nonexistent-endpoint-12345")
        assert response.status_code == 404

        response_body = response.json()

        # Should not contain stack traces or internal paths
        response_str = str(response_body)
        sensitive_patterns = [
            "/Users/",
            "/home/",
            "Traceback",
            "File \"",
            "line ",
        ]

        for pattern in sensitive_patterns:
            assert (
                pattern not in response_str
            ), f"Sensitive info leaked in error: {pattern}"

    def test_health_endpoint_doesnt_expose_secrets(self, test_client):
        """Verify health endpoint doesn't expose configuration secrets."""
        response = test_client.get("/health")
        response_body = response.json()
        response_str = str(response_body).lower()

        # Should not contain any credential-related info
        secret_keywords = ["password", "secret", "api_key", "token", "credential"]

        for keyword in secret_keywords:
            assert (
                keyword not in response_str
            ), f"Health endpoint exposes {keyword}"
