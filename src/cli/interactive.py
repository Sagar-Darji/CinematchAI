"""Interactive TUI with mouse and keyboard support."""

import sys
from pathlib import Path

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator
from rich.console import Console

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

console = Console()

# Custom style for InquirerPy (matching CinematchAI theme)
CUSTOM_STYLE = {
    "questionmark": "#e5c07b bold",
    "answermark": "#98c379",
    "answer": "#61afef bold",
    "input": "#61afef",
    "question": "bold",
    "answered_question": "",
    "instruction": "#7c7c7c",
    "long_instruction": "#7c7c7c",
    "pointer": "#61afef bold",
    "checkbox": "#98c379",
    "separator": "#7c7c7c",
    "skipped": "#7c7c7c",
    "validator": "",
    "marker": "#e5c07b bold",
    "fuzzy_prompt": "#c678dd",
    "fuzzy_info": "#7c7c7c",
    "fuzzy_border": "#7c7c7c",
    "fuzzy_match": "#c678dd bold",
    "spinner_pattern": "#e5c07b bold",
    "spinner_text": "",
}


def show_interactive_menu():
    """Show main interactive menu with mouse support."""
    console.clear()
    console.print("[bold yellow]🎬 CinematchAI - Interactive Mode[/]")
    console.print("[dim]Use arrow keys, mouse click, or type to search[/]\n")
    
    while True:
        action = inquirer.select(
            message="Choose an action:",
            choices=[
                Separator("📊 Corpus Management"),
                Choice(value="stats", name="📊  View Corpus Statistics"),
                Choice(value="search", name="🔍  Search Indexed Movies"),
                Separator("🌍 Enrichment"),
                Choice(value="enrichment_start", name="🚀  Start Bulk Enrichment"),
                Choice(value="enrichment_status", name="📈  View Job Progress"),
                Choice(value="enrichment_rotation", name="🔄  Show Rotation Candidates"),
                Separator("👥 User Management"),
                Choice(value="users_list", name="📋  List All Users"),
                Choice(value="users_get", name="👤  View User Details"),
                Choice(value="users_delete", name="❌  Delete User"),
                Choice(value="users_stats", name="📊  User Statistics"),
                Separator("🧪 Testing & Diagnostics"),
                Choice(value="test_rec", name="🎬  Test Recommendations"),
                Choice(value="test_llm", name="🔌  Test LLM Health"),
                Separator(""),
                Choice(value="legacy", name="🎨  Legacy TUI (Rich Menu)"),
                Choice(value="exit", name="🚪  Exit"),
            ],
            default="stats",
            pointer="👉",
            style=CUSTOM_STYLE,
            qmark="🎬",
            amark="✓",
            instruction="(↑↓/jk to move, Enter/Click to select, / to search, Ctrl+C to exit)",
            vi_mode=True,  # Enable vim keybindings
            show_cursor=False,
            max_height="80%",
        ).execute()
        
        if action == "exit":
            console.print("\n[yellow]Goodbye! 🎬[/]\n")
            break
        elif action == "legacy":
            # Launch legacy Rich TUI
            console.print("\n[yellow]Launching legacy TUI...[/]\n")
            from scripts.cinematch_cli import main as legacy_main
            legacy_main()
        else:
            # Execute action
            console.print()
            execute_action(action)
            
            # Pause before returning to menu
            console.print()
            input("[dim]Press Enter to continue...[/]")
            console.clear()
            console.print("[bold yellow]🎬 CinematchAI - Interactive Mode[/]")
            console.print("[dim]Use arrow keys, mouse click, or type to search[/]\n")


def execute_action(action: str):
    """Execute the selected action."""
    try:
        if action == "stats":
            from src.cli.commands.stats import stats
            from click.testing import CliRunner
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(stats, [], catch_exceptions=False, obj={})
            if result.output:
                console.print(result.output)
            if result.exception:
                raise result.exception
            
        elif action == "search":
            query = inquirer.text(
                message="Enter movie title or TMDB ID:",
                style=CUSTOM_STYLE,
                qmark="🔍",
            ).execute()
            
            if query:
                from src.cli.commands.search import search
                from click.testing import CliRunner
                runner = CliRunner(mix_stderr=False)
                result = runner.invoke(search, [query], catch_exceptions=False, obj={})
                if result.output:
                    console.print(result.output)
                if result.exception:
                    raise result.exception
                
        elif action == "enrichment_start":
            # Language selection with fuzzy search
            from src.services.enrichment_pipeline import LANGUAGE_NAMES
            
            languages = inquirer.checkbox(
                message="Select languages (Space to select, Enter to confirm):",
                choices=[
                    Choice(value=code, name=f"{name} ({code})")
                    for code, name in sorted(LANGUAGE_NAMES.items(), key=lambda x: x[1])
                ],
                style=CUSTOM_STYLE,
                qmark="🌍",
                amark="✓",
                instruction="(Space to select, Enter to confirm, / to search)",
                vi_mode=True,
                transformer=lambda result: f"{len(result)} languages selected",
            ).execute()
            
            if languages:
                pages = inquirer.number(
                    message="Maximum pages to process:",
                    default=500,
                    min_allowed=1,
                    max_allowed=10000,
                    style=CUSTOM_STYLE,
                    qmark="📄",
                ).execute()
                
                target = inquirer.number(
                    message="Target corpus size (GB):",
                    default=15.0,
                    min_allowed=0.1,
                    max_allowed=1000.0,
                    float_allowed=True,
                    style=CUSTOM_STYLE,
                    qmark="💾",
                ).execute()
                
                confirm = inquirer.confirm(
                    message=f"Start enrichment for {len(languages)} languages?",
                    default=True,
                    style=CUSTOM_STYLE,
                    qmark="❓",
                ).execute()
                
                if confirm:
                    from src.cli.commands.enrichment import start
                    from click.testing import CliRunner
                    runner = CliRunner(mix_stderr=False)
                    
                    args = []
                    for lang in languages:
                        args.extend(["--lang", lang])
                    args.extend(["--pages", str(int(pages)), "--target", str(target), "--yes"])
                    
                    result = runner.invoke(start, args, catch_exceptions=False, obj={})
                    if result.output:
                        console.print(result.output)
                    if result.exception:
                        raise result.exception
                    
        elif action == "enrichment_status":
            from src.cli.commands.enrichment import status
            from click.testing import CliRunner
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(status, [], catch_exceptions=False, obj={})
            if result.output:
                console.print(result.output)
            if result.exception:
                raise result.exception
            
        elif action == "enrichment_rotation":
            from src.cli.commands.enrichment import rotation
            from click.testing import CliRunner
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(rotation, [], catch_exceptions=False, obj={})
            if result.output:
                console.print(result.output)
            if result.exception:
                raise result.exception
            
        elif action == "users_list":
            from src.cli.commands.users import list
            from click.testing import CliRunner
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(list, [], catch_exceptions=False, obj={})
            if result.output:
                console.print(result.output)
            if result.exception:
                raise result.exception
            
        elif action == "users_get":
            user_id = inquirer.text(
                message="Enter user ID:",
                style=CUSTOM_STYLE,
                qmark="👤",
            ).execute()
            
            if user_id:
                from src.cli.commands.users import get
                from click.testing import CliRunner
                runner = CliRunner(mix_stderr=False)
                result = runner.invoke(get, [user_id], catch_exceptions=False, obj={})
                if result.output:
                    console.print(result.output)
                if result.exception:
                    raise result.exception
                
        elif action == "users_delete":
            user_id = inquirer.text(
                message="Enter user ID to delete:",
                style=CUSTOM_STYLE,
                qmark="❌",
            ).execute()
            
            if user_id:
                confirm = inquirer.confirm(
                    message=f"⚠️  Delete user '{user_id}' permanently?",
                    default=False,
                    style=CUSTOM_STYLE,
                    qmark="❓",
                ).execute()
                
                if confirm:
                    from src.cli.commands.users import delete
                    from click.testing import CliRunner
                    runner = CliRunner(mix_stderr=False)
                    result = runner.invoke(delete, [user_id, "--yes"], catch_exceptions=False, obj={})
                    if result.output:
                        console.print(result.output)
                    if result.exception:
                        raise result.exception
                    
        elif action == "users_stats":
            from src.cli.commands.users import stats
            from click.testing import CliRunner
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(stats, [], catch_exceptions=False, obj={})
            if result.output:
                console.print(result.output)
            if result.exception:
                raise result.exception
            
        elif action == "test_rec":
            user_id = inquirer.text(
                message="Enter user ID:",
                style=CUSTOM_STYLE,
                qmark="👤",
            ).execute()
            
            if user_id:
                k = inquirer.number(
                    message="Number of recommendations:",
                    default=5,
                    min_allowed=1,
                    max_allowed=50,
                    style=CUSTOM_STYLE,
                    qmark="🔢",
                ).execute()
                
                from src.cli.commands.test import recommendation
                from click.testing import CliRunner
                runner = CliRunner(mix_stderr=False)
                result = runner.invoke(recommendation, [user_id, "--k", str(int(k))], catch_exceptions=False, obj={})
                if result.output:
                    console.print(result.output)
                if result.exception:
                    raise result.exception
                
        elif action == "test_llm":
            from src.cli.commands.test import llm
            from click.testing import CliRunner
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(llm, [], catch_exceptions=False, obj={})
            if result.output:
                console.print(result.output)
            if result.exception:
                raise result.exception
            
    except KeyboardInterrupt:
        console.print("\n[dim]Action cancelled[/]")
    except Exception as e:
        console.print(f"\n[red]Error:[/] {e}")
        console.print("[dim]Tip: Try using direct commands instead:[/]")
        console.print(f"[dim]  cinematch {action.replace('_', ' ')}[/]")
        if "--verbose" in sys.argv:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/]")


def main():
    """Entry point for interactive TUI."""
    try:
        show_interactive_menu()
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye! 🎬[/]\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
