"""Fallback interactive menu - works in any terminal."""

import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

console = Console()


def show_menu():
    """Show simple numbered menu (always works)."""
    while True:
        try:
            console.clear()
            console.print("[bold yellow]🎬 CinematchAI - Interactive Mode[/]")
            console.print("[dim]Type a number and press Enter[/]\n")
            
            table = Table(box=None, show_header=False, padding=(0, 2))
            table.add_column(style="bold yellow", min_width=4)
            table.add_column(style="white", min_width=28)
            
            items = [
                ("1", "📊  Corpus Stats"),
                ("2", "🔍  Search Index"),
                ("3", "🌍  Bulk Enrichment"),
                ("4", "📈  Job Progress"),
                ("5", "🔄  Overnight Rotation"),
                ("6", "🗑️   Clear Job Queue"),
                ("7", "📋  List Users"),
                ("8", "👤  View User Details"),
                ("9", "❌  Delete User"),
                ("a", "📊  User Statistics"),
                ("b", "🧪  Test Recommendation"),
                ("c", "🔌  LLM Health Check"),
                ("0", "🚪  Exit"),
            ]
            
            for key, label in items:
                table.add_row(f"[{key}]", label)
            
            console.print(Panel(table, border_style="bright_black"))
            
            choice = console.input("\n[bold yellow]Choose:[/] ").strip().lower()
            
            if choice == "0":
                console.print("\n[yellow]Goodbye! 🎬[/]\n")
                break
            elif choice in [item[0] for item in items]:
                console.print()
                execute_action(choice)
                console.print()
                console.input("[dim]Press Enter to continue...[/]")
            else:
                console.print("[red]Invalid choice[/]")
                import time
                time.sleep(1)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Goodbye! 🎬[/]\n")
            break
        except Exception as e:
            console.print(f"\n[red]Error:[/] {e}")
            import traceback
            console.print(f"[dim]{traceback.format_exc()[:500]}[/]")
            import time
            time.sleep(2)


def execute_action(choice: str):
    """Execute action based on choice."""
    action_map = {
        "1": "stats",
        "2": "search",
        "3": "bulk_enrichment",
        "4": "job_progress",
        "5": "rotation",
        "6": "clear_queue",
        "7": "users_list",
        "8": "users_get",
        "9": "users_delete",
        "a": "users_stats",
        "b": "test_rec",
        "c": "test_llm",
    }
    
    action = action_map.get(choice)
    if not action:
        return
    
    # Import the simplified interactive to reuse its execute_action
    from .interactive_simple import execute_action as run_action
    run_action(action)


def main():
    """Entry point."""
    try:
        show_menu()
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye! 🎬[/]\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
