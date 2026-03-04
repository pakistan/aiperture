"""Tests for sensitive paths — scope normalization skip for sensitive files."""

import aiperture.config
from aiperture.permissions.scope_normalize import normalize_scope


class TestSensitivePaths:
    """Sensitive paths should NOT be normalized."""

    def test_secrets_file_not_normalized(self):
        result = normalize_scope("filesystem", "read", "src/secrets.py")
        assert result is None  # Not normalized to src/*.py

    def test_env_file_not_normalized(self):
        assert normalize_scope("filesystem", "read", ".env.production") is None

    def test_pem_file_not_normalized(self):
        assert normalize_scope("filesystem", "read", "certs/server.pem") is None

    def test_key_file_not_normalized(self):
        assert normalize_scope("filesystem", "read", "ssh/id_rsa.key") is None

    def test_credential_file_not_normalized(self):
        assert normalize_scope("filesystem", "read", "config/credentials.json") is None

    def test_password_file_not_normalized(self):
        assert normalize_scope("filesystem", "read", "data/passwords.txt") is None

    def test_token_file_not_normalized(self):
        assert normalize_scope("filesystem", "read", "auth/token.json") is None

    def test_private_key_not_normalized(self):
        assert normalize_scope("filesystem", "read", "keys/private.pem") is None

    def test_id_rsa_not_normalized(self):
        assert normalize_scope("filesystem", "read", "home/.ssh/id_rsa.pub") is None

    def test_dot_env_not_normalized(self):
        assert normalize_scope("filesystem", "read", ".env") is None


class TestNormalPathsStillNormalized:
    """Normal (non-sensitive) paths should still be normalized."""

    def test_regular_py_file(self):
        assert normalize_scope("filesystem", "read", "src/main.py") == "src/*.py"

    def test_regular_tsx_file(self):
        assert normalize_scope("filesystem", "read", "src/components/Button.tsx") == "src/components/*.tsx"

    def test_regular_md_file(self):
        assert normalize_scope("filesystem", "read", "docs/guide.md") == "docs/*.md"

    def test_shell_commands_unaffected(self):
        assert normalize_scope("shell", "execute", "git log --oneline") == "git log*"


class TestCustomSensitivePatterns:
    """Custom sensitive patterns via config."""

    def test_custom_pattern(self):
        original = aiperture.config.settings.sensitive_patterns
        try:
            object.__setattr__(
                aiperture.config.settings,
                "sensitive_patterns",
                "*custom_secret*,*.vault",
            )
            # Custom pattern should block normalization
            assert normalize_scope("filesystem", "read", "data/custom_secret.json") is None
            assert normalize_scope("filesystem", "read", "config/prod.vault") is None
            # Default patterns should no longer match
            assert normalize_scope("filesystem", "read", "src/secrets.py") == "src/*.py"
        finally:
            object.__setattr__(aiperture.config.settings, "sensitive_patterns", original)

    def test_empty_patterns_allows_all(self):
        original = aiperture.config.settings.sensitive_patterns
        try:
            object.__setattr__(aiperture.config.settings, "sensitive_patterns", "")
            # Nothing blocked
            assert normalize_scope("filesystem", "read", "src/secrets.py") == "src/*.py"
        finally:
            object.__setattr__(aiperture.config.settings, "sensitive_patterns", original)
