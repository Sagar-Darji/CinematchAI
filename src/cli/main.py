"""Main CLI entry point for CinematchAI."""

import sys
from pathlib import Path

import rich_click as click
from rich.console import Console

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

console = Console()

# Configure rich-click
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"
click.rich_click.ERRORS_SUGGESTION = "Try running the '--help' flag for more information."
click.rich_click.ERRORS_EPILOGUE = ""


@click.group()
@click.version_option(version="2.0.0", prog_name="cinematch")
@click.pass_context
def cli(ctx):
    """🎬 [bold yellow]CinematchAI[/] - AI-Powered Movie Recommendation System
    
    Modern CLI for managing corpus, enrichment, users, and recommendations.
    
    [dim]Examples:[/]
        cinematch stats
        cinematch enrichment start --lang hi --pages 10
        cinematch users list --format json
        cinematch search "dune"
    """
    ctx.ensure_object(dict)


@click.command()
@click.option("--fancy", is_flag=True, help="Try fancy clickable menu (may not work in all terminals)")
@click.option("--legacy", is_flag=True, help="Use legacy Rich TUI")
def interactive(fancy, legacy):
    """Launch interactive menu (simple numbered menu by default).
    
    Default: Simple numbered menu - works everywhere!
    Type a number (1-9, a-c) and press Enter.
    
    Options:
      --fancy   Try clickable menu with mouse support (experimental)
      --legacy  Original Rich TUI with progress bars
    
    Examples:
      cinematch interactive          # Simple menu (recommended)
      cinematch interactive --fancy  # Try mouse-clickable menu
      cinematch interactive --legacy # Original Rich TUI
    """
    if legacy:
        from scripts.cinematch_cli import main as legacy_main
        console.print("[yellow]Launching legacy Rich TUI...[/]\n")
        legacy_main()
    elif fancy:
        console.print("[yellow]Trying fancy clickable menu...[/]")
        console.print("[dim]If this hangs, press Ctrl+C and use: cinematch interactive[/]\n")
        try:
            from .interactive_simple import main as interactive_main
            interactive_main()
        except Exception as e:
            console.print(f"\n[yellow]Fancy menu not supported in this terminal.[/]")
            console.print(f"[dim]Use: cinematch interactive (without --fancy)[/]\n")
    else:
        # Default to simple menu (always works)
        from .interactive_fallback import main as fallback_main
        fallback_main()


# Import and register commands
from .commands.stats import stats
from .commands.enrichment import enrichment
from .commands.users import users
from .commands.search import search
from .commands.test import test

cli.add_command(stats)
cli.add_command(enrichment)
cli.add_command(users)
cli.add_command(search)
cli.add_command(test)
cli.add_command(interactive)


def main():
    """Entry point for console script."""
    try:
        cli(obj={})
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted by user[/]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
