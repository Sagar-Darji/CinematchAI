"""Simplified interactive TUI - direct function calls."""

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

# Don't use custom style - InquirerPy expects a different format
# Use default style instead


def show_menu():
    """Show main interactive menu."""
    try:
        console.clear()
        console.print("[bold yellow]🎬 CinematchAI - Interactive Mode[/]")
        console.print("[dim]Use arrow keys, mouse click, or type to search. Press Ctrl+C to exit.[/]\n")
    except Exception as e:
        console.print(f"[red]Display error:[/] {e}")
    
    while True:
        try:
            action = inquirer.select(
                message="Choose an action:",
                choices=[
                    Separator("📊 Corpus Management"),
                    Choice(value="stats", name="📊  Corpus Stats"),
                    Choice(value="search", name="🔍  Search Index"),
                    Separator("🌍 Enrichment"),
                    Choice(value="bulk_enrichment", name="🌍  Bulk Enrichment"),
                    Choice(value="job_progress", name="📈  Job Progress"),
                    Choice(value="rotation", name="🔄  Overnight Rotation"),
                    Choice(value="clear_queue", name="🗑️   Clear Job Queue"),
                    Separator("👥 User Management"),
                    Choice(value="users_list", name="📋  List All Users"),
                    Choice(value="users_get", name="👤  View User Details"),
                    Choice(value="users_delete", name="❌  Delete User"),
                    Choice(value="users_stats", name="📊  User Statistics"),
                    Separator("🧪 Testing"),
                    Choice(value="test_rec", name="🧪  Test Recommendation"),
                    Choice(value="test_llm", name="🔌  LLM Health Check"),
                    Separator(""),
                    Choice(value="legacy", name="🎨  Legacy TUI (Rich Menu)"),
                    Choice(value="exit", name="🚪  Exit"),
                ],
                default="stats",
                pointer="👉",
                qmark="🎬",
                instruction="(↑↓ to move, Enter to select, / to search, Ctrl+C to exit)",
                vi_mode=True,
                max_height="80%",
            ).execute()
        except Exception as e:
            console.print(f"\n[red]Menu error:[/] {e}")
            console.print("[yellow]Full error:[/]")
            import traceback
            traceback.print_exc()
            console.print("\n[dim]Try using: cinematch interactive --legacy[/]")
            break
            
            if action == "exit":
                console.print("\n[yellow]Goodbye! 🎬[/]\n")
                break
            elif action == "legacy":
                console.print("\n[yellow]Launching legacy TUI...[/]\n")
                try:
                    from scripts.cinematch_cli import main as legacy_main
                    legacy_main()
                except Exception as e:
                    console.print(f"[red]Error:[/] {e}")
            else:
                console.print()
                execute_action(action)
                console.print()
                input("[dim]Press Enter to continue...[/]")
                console.clear()
                console.print("[bold yellow]🎬 CinematchAI - Interactive Mode[/]")
                console.print("[dim]Use arrow keys, mouse click, or type to search. Press Ctrl+C to exit.[/]\n")
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Goodbye! 🎬[/]\n")
            break


def execute_action(action: str):
    """Execute action by calling functions directly."""
    try:
        if action == "stats":
            # Direct import and execution
            with console.status("[bold green]Loading statistics..."):
                from src.services.enrichment_pipeline import EnrichmentPipeline, LANGUAGE_NAMES
                from rich.panel import Panel
                from rich.table import Table
                from rich import box
                
                pipeline = EnrichmentPipeline()
                tracker_count = pipeline.tracker.count()
                est_mb = tracker_count * 16 / 1024
                counts = pipeline.cloud_db.count()
                availability = pipeline.cloud_db.is_available()
                dist = pipeline.get_language_distribution()
            
            # Display
            console.print(Panel(
                f"[bold white]{tracker_count:,}[/] movies indexed  ·  "
                f"[bold yellow]{_fmt_mb(est_mb)}[/] estimated",
                border_style="yellow",
                title="[bold]Corpus Overview[/]",
            ))
            
            # Backends
            b = Table("Backend", "Vectors", "Status", border_style="bright_black", box=box.SIMPLE)
            for backend, cnt in counts.items():
                up = availability.get(backend, False)
                b.add_row(backend, f"{cnt:,}", "[green]● UP[/]" if up else "[red]● DOWN[/]")
            console.print(b)
            console.print()
            
            # Languages
            if dist:
                total = max(tracker_count, 1)
                l_tbl = Table("Language", "Count", "Share", "Distribution",
                            border_style="bright_black", box=box.ROUNDED, header_style="bold yellow")
                for lang, cnt in sorted(dist.items(), key=lambda x: -x[1])[:10]:
                    name = LANGUAGE_NAMES.get(lang, lang)
                    pct = cnt / total * 100
                    bar_len = int(pct / 2)
                    bar = "[yellow]" + "█" * bar_len + "[/][dim]" + "░" * (50 - bar_len) + "[/]"
                    l_tbl.add_row(name, f"{cnt:,}", f"{pct:.1f}%", bar)
                console.print(l_tbl)
                
        elif action == "search":
            query = inquirer.text(
                message="Enter movie title or TMDB ID:",
                qmark="🔍",
            ).execute()
            
            if query:
                with console.status(f"[bold green]Searching for '{query}'..."):
                    import sqlite3
                    from src.services.enrichment_pipeline import _IndexedTracker
                    from rich.table import Table
                    from rich import box
                    
                    tracker = _IndexedTracker()
                    conn = sqlite3.connect(str(tracker.db_path))
                    conn.row_factory = sqlite3.Row
                    
                    # Try exact ID first
                    rows = conn.execute(
                        "SELECT * FROM enrichment_log WHERE tmdb_id = ?", (query,)
                    ).fetchall()
                    
                    # Search by title
                    if not rows:
                        rows = conn.execute(
                            "SELECT * FROM enrichment_log WHERE source LIKE ? LIMIT 20",
                            (f"%{query}%",),
                        ).fetchall()
                    
                    conn.close()
                
                if not rows:
                    console.print(f"[dim]No results for '{query}'[/]")
                else:
                    tbl = Table("TMDB ID", "Language", "Title", "Usage",
                              border_style="bright_black", box=box.ROUNDED, header_style="bold yellow")
                    for r in rows:
                        rd = dict(r)
                        tbl.add_row(
                            str(rd.get("tmdb_id", "?")),
                            rd.get("original_language", "?"),
                            (rd.get("source") or "")[:50],
                            str(rd.get("usage_count", 0) or 0),
                        )
                    console.print(tbl)
                    console.print(f"\n[dim]Found {len(rows)} results[/]")
                    
        elif action == "bulk_enrichment":
            # Language selection
            from src.services.enrichment_pipeline import LANGUAGE_NAMES
            
            languages = inquirer.checkbox(
                message="Select languages (Space to select, Enter to confirm):",
                choices=[
                    Choice(value=code, name=f"{name} ({code})")
                    for code, name in sorted(LANGUAGE_NAMES.items(), key=lambda x: x[1])
                ],
                qmark="🌍",
                instruction="(Space to select, Enter to confirm, / to search)",
                vi_mode=True,
                transformer=lambda result: f"{len(result)} selected" if result else "None",
            ).execute()
            
            if languages:
                pages = inquirer.number(
                    message="Maximum pages to process:",
                    default=500,
                    min_allowed=1,
                    max_allowed=10000,
                    qmark="📄",
                ).execute()
                
                target = inquirer.number(
                    message="Target corpus size (GB):",
                    default=15.0,
                    min_allowed=0.1,
                    max_allowed=1000.0,
                    float_allowed=True,
                    qmark="💾",
                ).execute()
                
                confirm = inquirer.confirm(
                    message=f"Start enrichment for {len(languages)} languages?",
                    default=True,
                    qmark="❓",
                ).execute()
                
                if confirm:
                    from src.services.enrichment_pipeline import EnrichmentPipeline
                    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
                    
                    pipeline = EnrichmentPipeline()
                    
                    prog = Progress(
                        SpinnerColumn(),
                        TextColumn("[bold yellow]{task.description}"),
                        BarColumn(bar_width=36),
                        TextColumn("{task.completed}/{task.total} pages"),
                        TextColumn("[green]+{task.fields[new]} new[/]"),
                        TimeElapsedColumn(),
                        console=console,
                    )
                    task = prog.add_task("Starting…", total=int(pages), new=0)
                    
                    def _progress_callback(info):
                        job = info.get("current_job", {})
                        lang_code = job.get("language", "?")
                        lang_name = LANGUAGE_NAMES.get(lang_code, lang_code)
                        prog.update(
                            task,
                            completed=info["pages_processed"],
                            description=lang_name,
                            new=info["total_new"]
                        )
                    
                    with prog:
                        result = pipeline.run_bulk_local(
                            target_gb=target,
                            max_pages=int(pages),
                            progress_callback=_progress_callback,
                            languages=languages,
                        )
                    
                    from rich.panel import Panel
                    console.print(Panel(
                        f"[bold green]✓ Enrichment complete![/]\n\n"
                        f"New movies: [yellow]{result['total_new']:,}[/]\n"
                        f"Total corpus: [yellow]{result['total_indexed']:,}[/] movies\n"
                        f"Elapsed: [dim]{result['elapsed']:.1f}s[/]",
                        border_style="green",
                    ))
                    
        elif action == "job_progress":
            with console.status("[bold green]Loading progress..."):
                from src.services.enrichment_pipeline import EnrichmentPipeline, LANGUAGE_NAMES
                from rich.panel import Panel
                from rich.table import Table
                from rich import box
                
                pipeline = EnrichmentPipeline()
                progress = pipeline.get_bulk_progress()
            
            if progress["total_jobs"] == 0:
                console.print(
                    f"[dim]No jobs in queue[/]\n"
                    f"Corpus: [yellow]{progress['total_indexed']:,}[/] movies"
                )
            else:
                done = progress["done"]
                total = progress["total_jobs"]
                console.print(Panel(
                    f"Progress: [yellow]{done}/{total}[/] jobs ({done/total*100:.1f}%)\n"
                    f"Corpus: [yellow]{progress['total_indexed']:,}[/] movies "
                    f"([dim]{_fmt_mb(progress['est_size_mb'])}[/])",
                    border_style="yellow"
                ))
                
                tbl = Table(
                    "Language", "Priority", "Done", "Pending", "Failed", "Movies", "Progress",
                    border_style="bright_black",
                    box=box.ROUNDED,
                    header_style="bold yellow"
                )
                
                for lp in progress["by_language"]:
                    name = LANGUAGE_NAMES.get(lp["language"], lp["language"])
                    pct = (lp["done"] / lp["total"] * 100) if lp["total"] > 0 else 0
                    bar = "[yellow]" + "█" * int(pct / 5) + "[/][dim]" + "░" * (20 - int(pct / 5)) + "[/]"
                    tbl.add_row(
                        name,
                        str(lp["priority"]),
                        str(lp["done"]),
                        str(lp["pending"]),
                        f"[red]{lp['failed']}[/]" if lp["failed"] else "0",
                        str(lp.get("movies_found", 0)),
                        f"{bar} {pct:.0f}%",
                    )
                
                console.print(tbl)
                
        elif action == "rotation":
            with console.status("[bold green]Loading candidates..."):
                from src.services.enrichment_pipeline import EnrichmentPipeline, LANGUAGE_NAMES
                from rich.table import Table
                from rich import box
                
                pipeline = EnrichmentPipeline()
                tracker_count = pipeline.tracker.count()
                candidates = pipeline.tracker.get_rotation_candidates(keep_days=30)
            
            console.print(f"Total corpus: [yellow]{tracker_count:,}[/] movies")
            console.print(f"Rotation candidates (>30 days unused): [yellow]{len(candidates)}[/]\n")
            
            if candidates:
                by_lang = {}
                for c in candidates:
                    lang = c.get("original_language", "?")
                    by_lang[lang] = by_lang.get(lang, 0) + 1
                
                tbl = Table("Language", "Candidates", box=box.SIMPLE, border_style="bright_black")
                for lang, cnt in sorted(by_lang.items(), key=lambda x: -x[1]):
                    tbl.add_row(LANGUAGE_NAMES.get(lang, lang), str(cnt))
                console.print(tbl)
            else:
                console.print("[dim]No rotation candidates[/]")
                
        elif action == "clear_queue":
            from src.services.enrichment_pipeline import EnrichmentPipeline
            
            with console.status("[bold green]Loading queue..."):
                pipeline = EnrichmentPipeline()
                job_counts = pipeline.tracker.count_jobs()
                total = sum(job_counts.values())
            
            if total == 0:
                console.print("[dim]Queue is already empty[/]")
            else:
                console.print(f"Current queue: {job_counts}\n")
                
                clear_type = inquirer.select(
                    message="What to clear?",
                    choices=[
                        Choice(value="all", name="Clear ALL jobs"),
                        Choice(value="failed", name="Clear only FAILED jobs"),
                        Choice(value="pending", name="Clear only PENDING jobs"),
                        Choice(value="cancel", name="Cancel"),
                    ],
                    default="cancel",
                    qmark="🗑️",
                ).execute()
                
                if clear_type != "cancel":
                    confirm = inquirer.confirm(
                        message=f"Clear {clear_type} jobs?",
                        default=False,
                        qmark="❓",
                    ).execute()
                    
                    if confirm:
                        with console.status(f"[bold green]Clearing {clear_type} jobs..."):
                            if clear_type == "all":
                                removed = pipeline.tracker.clear_all_jobs()
                            elif clear_type == "failed":
                                removed = pipeline.tracker.clear_failed_jobs()
                            elif clear_type == "pending":
                                removed = pipeline.tracker.clear_pending_jobs()
                        
                        console.print(f"[green]✓ Cleared {removed} jobs[/]")
                    
        elif action == "users_get":
            user_id = inquirer.text(
                message="Enter user ID:",
                qmark="👤",
            ).execute()
            
            if user_id:
                with console.status(f"[bold green]Loading user '{user_id}'..."):
                    import sqlite3
                    from config.settings import get_settings
                    from rich.panel import Panel
                    from rich.table import Table
                    from rich import box
                    
                    settings = get_settings()
                    db_path = Path(settings.data_dir) / "users.db"
                    
                    conn = sqlite3.connect(str(db_path))
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    
                    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                    user = cursor.fetchone()
                    
                    if not user:
                        console.print(f"[red]Error:[/] User '{user_id}' not found")
                        conn.close()
                    else:
                        cursor.execute("""
                            SELECT movie_id, movie_title, rating, timestamp
                            FROM ratings
                            WHERE user_id = ?
                            ORDER BY timestamp DESC
                            LIMIT 20
                        """, (user_id,))
                        ratings = cursor.fetchall()
                        conn.close()
                        
                        console.print(Panel(
                            f"User ID: [yellow]{user['user_id']}[/]\n"
                            f"Created: [dim]{user['created_at']}[/]\n"
                            f"Ratings: [yellow]{len(ratings)}[/]",
                            title="[bold]User Profile[/]",
                            border_style="yellow"
                        ))
                        
                        if ratings:
                            console.print("\n[bold]Recent Ratings:[/]")
                            tbl = Table("Movie", "Rating", "Date", border_style="bright_black", box=box.SIMPLE)
                            for r in ratings[:10]:
                                tbl.add_row(
                                    r["movie_title"][:40],
                                    f"[yellow]{r['rating']}[/]★",
                                    r["timestamp"][:10] if r["timestamp"] else "—"
                                )
                            console.print(tbl)
                            
        elif action == "users_delete":
            user_id = inquirer.text(
                message="Enter user ID to delete:",
                qmark="❌",
            ).execute()
            
            if user_id:
                confirm = inquirer.confirm(
                    message=f"⚠️  Delete user '{user_id}' permanently?",
                    default=False,
                    qmark="❓",
                ).execute()
                
                if confirm:
                    with console.status(f"[bold green]Deleting user '{user_id}'..."):
                        import sqlite3
                        from config.settings import get_settings
                        from rich.panel import Panel
                        
                        settings = get_settings()
                        db_path = Path(settings.data_dir) / "users.db"
                        
                        conn = sqlite3.connect(str(db_path))
                        cursor = conn.cursor()
                        
                        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                        if not cursor.fetchone():
                            console.print(f"[red]Error:[/] User '{user_id}' not found")
                        else:
                            cursor.execute("DELETE FROM ratings WHERE user_id = ?", (user_id,))
                            ratings_deleted = cursor.rowcount
                            cursor.execute("DELETE FROM user_context WHERE user_id = ?", (user_id,))
                            cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                            conn.commit()
                            
                            console.print(Panel(
                                f"[bold green]✓ User deleted[/]\n\n"
                                f"User: [dim]{user_id}[/]\n"
                                f"Ratings removed: [yellow]{ratings_deleted}[/]",
                                border_style="green"
                            ))
                        
                        conn.close()
                    
        elif action == "users_list":
            with console.status("[bold green]Loading users..."):
                import sqlite3
                from config.settings import get_settings
                from rich.table import Table
                from rich import box
                
                settings = get_settings()
                db_path = Path(settings.data_dir) / "users.db"
                
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        u.user_id,
                        COUNT(r.id) as rating_count,
                        ROUND(AVG(r.rating), 2) as avg_rating,
                        u.created_at
                    FROM users u
                    LEFT JOIN ratings r ON u.user_id = r.user_id
                    GROUP BY u.user_id
                    ORDER BY u.created_at DESC
                    LIMIT 50
                """)
                rows = cursor.fetchall()
                conn.close()
            
            if not rows:
                console.print("[dim]No users found[/]")
            else:
                tbl = Table("User ID", "Ratings", "Avg Rating", "Created",
                          border_style="bright_black", box=box.ROUNDED, header_style="bold yellow")
                for row in rows:
                    tbl.add_row(
                        row["user_id"],
                        str(row["rating_count"]),
                        str(row["avg_rating"]) if row["avg_rating"] else "—",
                        row["created_at"][:10] if row["created_at"] else "—",
                    )
                console.print(tbl)
                console.print(f"\n[dim]Showing {len(rows)} users[/]")
                
        elif action == "users_stats":
            with console.status("[bold green]Loading statistics..."):
                import sqlite3
                from config.settings import get_settings
                from rich.panel import Panel
                
                settings = get_settings()
                db_path = Path(settings.data_dir) / "users.db"
                
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM users")
                total_users = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM ratings")
                total_ratings = cursor.fetchone()[0]
                
                cursor.execute("SELECT ROUND(AVG(rating), 2) FROM ratings")
                avg_rating = cursor.fetchone()[0]
                
                conn.close()
            
            console.print(Panel(
                f"Total users: [yellow]{total_users}[/]\n"
                f"Total ratings: [yellow]{total_ratings}[/]\n"
                f"Average rating: [yellow]{avg_rating}[/]★",
                title="[bold]User Statistics[/]",
                border_style="yellow"
            ))
            
        elif action == "test_rec":
            user_id = inquirer.text(
                message="Enter user ID:",
                qmark="👤",
            ).execute()
            
            if user_id:
                k = inquirer.number(
                    message="Number of recommendations:",
                    default=5,
                    min_allowed=1,
                    max_allowed=50,
                    qmark="🔢",
                ).execute()
                
                from src.agents.profile_agent import ProfileAgent
                from src.services.recommendation_service import RecommendationService
                from config.settings import get_settings
                from rich.panel import Panel
                from rich.table import Table
                from rich import box
                
                settings = get_settings()
                
                with console.status(f"[bold green]Generating recommendations for '{user_id}'..."):
                    try:
                        profile_agent = ProfileAgent(user_id, settings)
                        profile_data = profile_agent.get_or_build_profile()
                        
                        rec_service = RecommendationService(settings)
                        results = rec_service.get_recommendations(user_id, k=int(k))
                        
                    except Exception as e:
                        console.print(f"[red]Error:[/] {e}")
                        results = []
                        profile_data = None
                
                console.print(Panel(
                    f"User: [yellow]{user_id}[/]\n"
                    f"Profile: [yellow]{'Found' if profile_data else 'Not found'}[/]\n"
                    f"Recommendations: [yellow]{len(results)}[/]",
                    title="[bold]Test Results[/]",
                    border_style="yellow"
                ))
                
                if results:
                    tbl = Table("#", "Movie", "Score", "Reason",
                              border_style="bright_black", box=box.ROUNDED, header_style="bold yellow")
                    
                    for i, r in enumerate(results, 1):
                        tbl.add_row(
                            str(i),
                            r.get("title", "Unknown")[:40],
                            f"[yellow]{r.get('score', 0):.2f}[/]",
                            r.get("reason", "")[:50],
                        )
                    
                    console.print(tbl)
            
        elif action == "test_llm":
            from config.settings import get_settings
            from rich.panel import Panel
            
            settings = get_settings()
            console.print(f"Testing LLM provider: [yellow]groq[/]\n")
            
            with console.status("[bold green]Sending test request..."):
                try:
                    from langchain_groq import ChatGroq
                    llm = ChatGroq(
                        model=settings.groq_model_name,
                        temperature=0,
                        api_key=settings.groq_api_key,
                    )
                    response = llm.invoke("Say 'Hello from CinematchAI' in exactly 5 words.")
                    success = True
                    message = str(response.content) if hasattr(response, 'content') else str(response)
                except Exception as e:
                    success = False
                    message = str(e)
            
            if success:
                console.print(Panel(
                    f"[bold green]✓ LLM is healthy[/]\n\n"
                    f"Provider: [yellow]groq[/]\n"
                    f"Response: [dim]{message[:100]}[/]",
                    border_style="green"
                ))
            else:
                console.print(Panel(
                    f"[bold red]✗ LLM test failed[/]\n\n"
                    f"Error: [red]{message[:200]}[/]",
                    border_style="red"
                ))
                
    except Exception as e:
        console.print(f"\n[red]Error:[/] {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()[:500]}[/]")


def _fmt_mb(mb: float) -> str:
    """Format megabytes."""
    if mb < 1024:
        return f"{mb:.1f} MB"
    return f"{mb/1024:.1f} GB"


def main():
    """Entry point."""
    try:
        show_menu()
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye! 🎬[/]\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
