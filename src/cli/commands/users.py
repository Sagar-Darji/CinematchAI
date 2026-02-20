"""Users command - manage user accounts."""

import sys
from pathlib import Path
import sqlite3

import rich_click as click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

console = Console()


@click.group()
def users():
    """👥 Manage user accounts and profiles.
    
    View, create, delete users and inspect their ratings.
    """
    pass


@users.command()
@click.option("--format", type=click.Choice(["table", "json"]), default="table")
@click.option("--limit", default=50, help="Maximum users to show", type=int)
def list(format, limit):
    """List all users with stats.
    
    [dim]Examples:[/]
        cinematch users list
        cinematch users list --limit 10
        cinematch users list --format json
    """
    from config.settings import get_settings
    
    settings = get_settings()
    db_path = Path(settings.data_dir) / "users.db"
    
    with console.status("[bold green]Loading users..."):
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                u.user_id,
                u.created_at,
                COUNT(r.id) as rating_count,
                ROUND(AVG(r.rating), 2) as avg_rating,
                MAX(r.timestamp) as last_rating
            FROM users u
            LEFT JOIN ratings r ON u.user_id = r.user_id
            GROUP BY u.user_id
            ORDER BY u.created_at DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
    
    if not rows:
        console.print("[dim]No users found[/]")
        return
    
    # JSON output
    if format == "json":
        users_data = [
            {
                "user_id": row["user_id"],
                "created_at": row["created_at"],
                "rating_count": row["rating_count"],
                "avg_rating": row["avg_rating"],
                "last_rating": row["last_rating"],
            }
            for row in rows
        ]
        console.print_json(data={"total": len(users_data), "users": users_data})
        return
    
    # Table output
    tbl = Table(
        "User ID", "Ratings", "Avg Rating", "Created", "Last Activity",
        border_style="bright_black",
        box=box.ROUNDED,
        header_style="bold yellow"
    )
    
    for row in rows:
        tbl.add_row(
            row["user_id"],
            str(row["rating_count"]),
            str(row["avg_rating"]) if row["avg_rating"] else "—",
            row["created_at"][:10] if row["created_at"] else "—",
            row["last_rating"][:10] if row["last_rating"] else "—",
        )
    
    console.print(tbl)
    console.print(f"\n[dim]Showing {len(rows)} users[/]")


@users.command()
@click.argument("user_id")
@click.option("--format", type=click.Choice(["table", "json"]), default="table")
def get(user_id, format):
    """Get detailed user information.
    
    Shows profile, ratings, and context data.
    
    [dim]Examples:[/]
        cinematch users get test_user
        cinematch users get test_user --format json
    """
    from config.settings import get_settings
    
    settings = get_settings()
    db_path = Path(settings.data_dir) / "users.db"
    
    with console.status(f"[bold green]Loading user '{user_id}'..."):
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get user info
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            console.print(f"[red]Error:[/] User '{user_id}' not found")
            conn.close()
            sys.exit(1)
        
        # Get ratings
        cursor.execute("""
            SELECT movie_id, movie_title, rating, timestamp
            FROM ratings
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 20
        """, (user_id,))
        ratings = cursor.fetchall()
        
        # Get context
        cursor.execute("""
            SELECT context_data
            FROM user_context
            WHERE user_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
        """, (user_id,))
        context_row = cursor.fetchone()
        conn.close()
    
    # JSON output
    if format == "json":
        output = {
            "user_id": user["user_id"],
            "created_at": user["created_at"],
            "rating_count": len(ratings),
            "ratings": [
                {
                    "movie_id": r["movie_id"],
                    "movie_title": r["movie_title"],
                    "rating": r["rating"],
                    "timestamp": r["timestamp"],
                }
                for r in ratings
            ],
        }
        if context_row:
            output["has_context"] = True
        console.print_json(data=output)
        return
    
    # Table output
    console.print(Panel(
        f"User ID: [yellow]{user['user_id']}[/]\n"
        f"Created: [dim]{user['created_at']}[/]\n"
        f"Ratings: [yellow]{len(ratings)}[/]\n"
        f"Context: [yellow]{'Yes' if context_row else 'No'}[/]",
        title="[bold]User Profile[/]",
        border_style="yellow"
    ))
    
    if ratings:
        console.print("\n[bold]Recent Ratings:[/]")
        tbl = Table(
            "Movie", "Rating", "Date",
            border_style="bright_black",
            box=box.SIMPLE
        )
        for r in ratings[:10]:
            tbl.add_row(
                r["movie_title"][:40],
                f"[yellow]{r['rating']}[/]★",
                r["timestamp"][:10] if r["timestamp"] else "—"
            )
        console.print(tbl)


@users.command()
@click.argument("user_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def delete(user_id, yes):
    """Delete a user and all their data.
    
    [red]Warning:[/] This permanently removes the user and all ratings.
    
    [dim]Examples:[/]
        cinematch users delete test_user
        cinematch users delete test_user --yes
    """
    from config.settings import get_settings
    
    settings = get_settings()
    db_path = Path(settings.data_dir) / "users.db"
    
    # Confirm deletion
    if not yes:
        confirm = console.input(f"\n[bold red]Delete user '{user_id}' permanently? (yes/no):[/] ")
        if confirm.lower() not in ["yes", "y"]:
            console.print("[dim]Cancelled[/]")
            return
    
    with console.status(f"[bold green]Deleting user '{user_id}'..."):
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if not cursor.fetchone():
            console.print(f"[red]Error:[/] User '{user_id}' not found")
            conn.close()
            sys.exit(1)
        
        # Delete ratings
        cursor.execute("DELETE FROM ratings WHERE user_id = ?", (user_id,))
        ratings_deleted = cursor.rowcount
        
        # Delete context
        cursor.execute("DELETE FROM user_context WHERE user_id = ?", (user_id,))
        
        # Delete user
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        
        conn.commit()
        conn.close()
    
    console.print(Panel(
        f"[bold green]✓ User deleted[/]\n\n"
        f"User: [dim]{user_id}[/]\n"
        f"Ratings removed: [yellow]{ratings_deleted}[/]",
        border_style="green"
    ))


@users.command()
def stats():
    """Show overall user statistics.
    
    [dim]Examples:[/]
        cinematch users stats
    """
    from config.settings import get_settings
    
    settings = get_settings()
    db_path = Path(settings.data_dir) / "users.db"
    
    with console.status("[bold green]Loading statistics..."):
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Total users
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()[0]
        
        # Total ratings
        cursor.execute("SELECT COUNT(*) as count FROM ratings")
        total_ratings = cursor.fetchone()[0]
        
        # Average rating
        cursor.execute("SELECT ROUND(AVG(rating), 2) as avg FROM ratings")
        avg_rating = cursor.fetchone()[0]
        
        # Active users (rated in last 30 days)
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as count 
            FROM ratings 
            WHERE timestamp > datetime('now', '-30 days')
        """)
        active_users = cursor.fetchone()[0]
        
        conn.close()
    
    console.print(Panel(
        f"Total users: [yellow]{total_users}[/]\n"
        f"Active (30d): [yellow]{active_users}[/]\n"
        f"Total ratings: [yellow]{total_ratings}[/]\n"
        f"Average rating: [yellow]{avg_rating}[/]★",
        title="[bold]User Statistics[/]",
        border_style="yellow"
    ))
