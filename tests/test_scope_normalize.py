"""Tests for scope normalization."""

from aiperture.permissions.scope_normalize import normalize_scope


class TestNormalizeShellScope:
    """Shell command normalization."""

    def test_git_log_variants(self):
        assert normalize_scope("shell", "execute", "git log --oneline -5") == "git log*"
        assert normalize_scope("shell", "execute", "git log --stat") == "git log*"
        assert normalize_scope("shell", "execute", "git log") == "git log*"

    def test_git_status(self):
        assert normalize_scope("shell", "execute", "git status") == "git status*"

    def test_git_diff_variants(self):
        assert normalize_scope("shell", "execute", "git diff HEAD~3") == "git diff*"
        assert normalize_scope("shell", "execute", "git diff --staged") == "git diff*"

    def test_npm_test(self):
        assert normalize_scope("shell", "execute", "npm test -- --watch") == "npm test*"
        assert normalize_scope("shell", "execute", "npm test") == "npm test*"

    def test_npm_run(self):
        assert normalize_scope("shell", "execute", "npm run build") == "npm run*"

    def test_simple_command(self):
        assert normalize_scope("shell", "execute", "ls -la /home/user") == "ls*"

    def test_pytest(self):
        assert normalize_scope("shell", "execute", "pytest tests/test_foo.py -v") == "pytest*"

    def test_make(self):
        assert normalize_scope("shell", "execute", "make test") == "make test*"
        assert normalize_scope("shell", "execute", "make lint") == "make lint*"

    def test_docker_commands(self):
        assert normalize_scope("shell", "execute", "docker ps -a") == "docker ps*"
        assert normalize_scope("shell", "execute", "docker build -t myimage .") == "docker build*"

    def test_pip_commands(self):
        assert normalize_scope("shell", "execute", "pip install requests") == "pip install*"
        assert normalize_scope("shell", "execute", "pip list") == "pip list*"

    def test_cargo_commands(self):
        assert normalize_scope("shell", "execute", "cargo test --release") == "cargo test*"
        assert normalize_scope("shell", "execute", "cargo build") == "cargo build*"

    def test_bash_tool(self):
        """'bash' tool works the same as 'shell'."""
        assert normalize_scope("bash", "execute", "git status") == "git status*"

    def test_terminal_tool(self):
        """'terminal' tool works the same as 'shell'."""
        assert normalize_scope("terminal", "execute", "ls -la") == "ls*"


class TestNormalizeFilesystemScope:
    """Filesystem scope normalization."""

    def test_same_directory_files(self):
        assert (
            normalize_scope("filesystem", "read", "src/components/Button.tsx")
            == "src/components/*.tsx"
        )
        assert (
            normalize_scope("filesystem", "read", "src/components/Card.tsx")
            == "src/components/*.tsx"
        )

    def test_docs_markdown(self):
        assert normalize_scope("filesystem", "read", "docs/guide.md") == "docs/*.md"

    def test_root_file(self):
        assert normalize_scope("filesystem", "read", "config.yaml") == "*.yaml"

    def test_nested_path(self):
        assert (
            normalize_scope("filesystem", "write", "src/utils/helpers/format.py")
            == "src/utils/helpers/*.py"
        )

    def test_file_tool(self):
        """'file' tool works the same as 'filesystem'."""
        assert normalize_scope("file", "read", "src/main.py") == "src/*.py"

    def test_fs_tool(self):
        """'fs' tool works the same as 'filesystem'."""
        assert normalize_scope("fs", "read", "src/main.py") == "src/*.py"


class TestNormalizeEdgeCases:
    """Edge cases and non-normalizable scopes."""

    def test_glob_returns_none(self):
        assert normalize_scope("shell", "execute", "src/**/*.py") is None
        assert normalize_scope("filesystem", "read", "src/*.py") is None

    def test_empty_returns_none(self):
        assert normalize_scope("shell", "execute", "") is None

    def test_unknown_tool_returns_none(self):
        assert normalize_scope("api", "post", "users/create") is None

    def test_no_extension_returns_none(self):
        assert normalize_scope("filesystem", "read", "Makefile") is None

    def test_wildcard_returns_none(self):
        assert normalize_scope("shell", "execute", "ls *") is None
        assert normalize_scope("filesystem", "read", "src/*.py") is None
