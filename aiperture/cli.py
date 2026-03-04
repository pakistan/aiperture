"""AIperture CLI entry point."""

import sys

from aiperture import plugins


def main():
    plugins.load_all()
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        print("AIperture — The permission layer for AI agents\n")  # noqa: T201
        print("Commands:")  # noqa: T201
        print("  mcp-serve    Run as MCP server (stdio transport)")  # noqa: T201
        print("  serve        Run HTTP API server")  # noqa: T201
        print("  init-db      Initialize the database")  # noqa: T201
        print("  configure    Interactive setup wizard")  # noqa: T201
        print("  bootstrap    Seed permission decisions from a preset")  # noqa: T201
        print("  revoke       Revoke auto-approval for a permission pattern")  # noqa: T201
        sys.exit(0)

    cmd = args[0]

    if cmd == "mcp-serve":
        from aiperture.mcp_server import serve
        serve()

    elif cmd == "serve":
        import uvicorn

        import aiperture.config
        from aiperture.api.app import create_app

        app = create_app()
        settings = aiperture.config.settings
        uvicorn.run(app, host=settings.api_host, port=settings.api_port)

    elif cmd == "init-db":
        from aiperture.db import init_db
        init_db()
        print("Database initialized.")  # noqa: T201

    elif cmd == "configure":
        _configure()

    elif cmd == "bootstrap":
        _bootstrap(args[1:])

    elif cmd == "revoke":
        _revoke(args[1:])

    else:
        print(f"Unknown command: {cmd}")  # noqa: T201
        sys.exit(1)


def _bootstrap(args: list[str]):
    """Apply a bootstrap preset to seed permission decisions."""
    from aiperture.db import init_db
    from aiperture.permissions.presets import apply_preset, get_preset_names

    init_db()

    if not args or args[0] in ("--help", "-h"):
        names = get_preset_names()
        print("Usage: aiperture bootstrap <preset_name>")  # noqa: T201
        print(f"\nAvailable presets: {', '.join(names)}")  # noqa: T201
        print("\n  developer  — filesystem reads, git, test runners, linters")  # noqa: T201
        print("  readonly   — filesystem reads and safe shell commands only")  # noqa: T201
        print("  minimal    — nothing pre-approved (fresh start)")  # noqa: T201
        return

    preset_name = args[0]
    org_id = "default"
    if len(args) > 1 and args[1].startswith("--org="):
        org_id = args[1].split("=", 1)[1]

    try:
        total = apply_preset(preset_name, organization_id=org_id)
        print(f"Applied '{preset_name}' preset: {total} decisions seeded.")  # noqa: T201
        print("These patterns will now auto-approve immediately.")  # noqa: T201
    except KeyError as e:
        print(f"Error: {e}")  # noqa: T201
        sys.exit(1)


def _revoke(args: list[str]):
    """Revoke auto-approval for a permission pattern."""
    from aiperture.db import init_db
    from aiperture.permissions.engine import PermissionEngine

    if len(args) < 3 or args[0] in ("--help", "-h"):
        print("Usage: aiperture revoke <tool> <action> <scope> [--org=ORG_ID]")  # noqa: T201
        print("\nExample: aiperture revoke shell execute 'rm -rf*'")  # noqa: T201
        return

    init_db()
    tool, action, scope = args[0], args[1], args[2]
    org_id = "default"
    for a in args[3:]:
        if a.startswith("--org="):
            org_id = a.split("=", 1)[1]

    engine = PermissionEngine()
    count = engine.revoke_pattern(tool, action, scope, revoked_by="cli", organization_id=org_id)
    print(f"Revoked {count} decision(s) for {tool}.{action} on {scope}")  # noqa: T201


def _configure(input_fn=None, env_file_path=None):
    """Interactive setup wizard for tunable settings.

    Args:
        input_fn: Override for input() — used in tests.
        env_file_path: Override for .aiperture.env path — used in tests.
    """
    import aiperture.config
    from aiperture.config import Settings

    _input = input_fn or input
    env_path = env_file_path or ".aiperture.env"

    print("\nAIperture Configuration Wizard")  # noqa: T201
    print("=" * 40)  # noqa: T201
    print("Press Enter to keep the current value shown in [brackets].\n")  # noqa: T201

    updates: dict = {}
    field_types = {
        name: field.annotation
        for name, field in Settings.model_fields.items()
        if name in Settings.TUNABLE_FIELDS
    }

    for field in sorted(Settings.TUNABLE_FIELDS):
        current = getattr(aiperture.config.settings, field)
        desc = Settings.TUNABLE_DESCRIPTIONS.get(field, "")
        ftype = field_types.get(field)

        prompt = f"  {field} — {desc}\n    [{current}]: "
        raw = _input(prompt).strip()

        if not raw:
            continue  # keep current value

        try:
            if ftype is bool:
                value = raw.lower() in ("true", "1", "yes", "on")
            elif ftype is int:
                value = int(raw)
            elif ftype is float:
                value = float(raw)
            else:
                value = raw
            updates[field] = value
        except (ValueError, TypeError) as e:
            print(f"    Invalid value for {field}: {e}. Keeping current.")  # noqa: T201

    if updates:
        try:
            aiperture.config.update_settings(updates, env_file_path=env_path)
            print(f"\nSaved {len(updates)} setting(s) to {env_path}")  # noqa: T201
        except ValueError as e:
            print(f"\nConfiguration error: {e}")  # noqa: T201
            sys.exit(1)
    else:
        print("\nNo changes made.")  # noqa: T201

    # Offer to init-db
    init = _input("\nInitialize database now? [Y/n]: ").strip().lower()
    if init in ("", "y", "yes"):
        from aiperture.db import init_db
        init_db()
        print("Database initialized.")  # noqa: T201

    print("\nDone! Run 'aiperture serve' to start the API server.")  # noqa: T201


if __name__ == "__main__":
    main()
