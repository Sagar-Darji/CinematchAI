"""Test command - test recommendations and LLM."""

import sys
from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

console = Console()


@click.group()
def test():
    """🧪 Test recommendations and LLM connectivity.
    
    Run diagnostic tests on the recommendation system.
    """
    pass


@test.command()
@click.argument("user_id")
@click.option("--k", default=5, help="Number of recommendations", type=int)
@click.option("--format", type=click.Choice(["table", "json"]), default="table")
def recommendation(user_id, k, format):
    """Test recommendations for a user.
    
    Generate movie recommendations and show results.
    
    [dim]Examples:[/]
        cinematch test recommendation test_user
        cinematch test recommendation test_user --k 10
        cinematch test recommendation test_user --format json
    """
    from src.agents.profile_agent import ProfileAgent
    from src.services.recommendation_service import RecommendationService
    from config.settings import get_settings
    
    settings = get_settings()
    
    with console.status(f"[bold green]Generating recommendations for '{user_id}'..."):
        try:
            # Get user profile
            profile_agent = ProfileAgent(user_id, settings)
            profile_data = profile_agent.get_or_build_profile()
            
            # Get recommendations
            rec_service = RecommendationService(settings)
            results = rec_service.get_recommendations(user_id, k=k)
            
        except Exception as e:
            console.print(f"[red]Error:[/] {e}")
            sys.exit(1)
    
    # JSON output
    if format == "json":
        output = {
            "user_id": user_id,
            "profile_exists": bool(profile_data),
            "recommendations": [
                {
                    "movie_id": r.get("movie_id"),
                    "title": r.get("title"),
                    "score": round(r.get("score", 0), 3),
                    "reason": r.get("reason", ""),
                }
                for r in results
            ]
        }
        console.print_json(data=output)
        return
    
    # Table output
    console.print(Panel(
        f"User: [yellow]{user_id}[/]\n"
        f"Profile: [yellow]{'Found' if profile_data else 'Not found'}[/]\n"
        f"Recommendations: [yellow]{len(results)}[/]",
        title="[bold]Test Results[/]",
        border_style="yellow"
    ))
    
    if results:
        tbl = Table(
            "#", "Movie", "Score", "Reason",
            border_style="bright_black",
            box=box.ROUNDED,
            header_style="bold yellow"
        )
        
        for i, r in enumerate(results, 1):
            tbl.add_row(
                str(i),
                r.get("title", "Unknown")[:40],
                f"[yellow]{r.get('score', 0):.2f}[/]",
                r.get("reason", "")[:50],
            )
        
        console.print(tbl)


@test.command()
@click.option("--provider", default="groq", help="LLM provider to test (groq, ollama)")
def llm(provider):
    """Test LLM connectivity and health.
    
    Check if LLM provider is responding correctly.
    
    [dim]Examples:[/]
        cinematch test llm
        cinematch test llm --provider groq
    """
    from config.settings import get_settings
    
    settings = get_settings()
    
    console.print(f"Testing LLM provider: [yellow]{provider}[/]\n")
    
    with console.status("[bold green]Sending test request..."):
        try:
            if provider == "groq":
                from langchain_groq import ChatGroq
                llm = ChatGroq(
                    model=settings.groq_model_name,
                    temperature=0,
                    api_key=settings.groq_api_key,
                )
                response = llm.invoke("Say 'Hello from CinematchAI' in exactly 5 words.")
            else:
                console.print(f"[red]Error:[/] Unsupported provider '{provider}'")
                sys.exit(1)
            
            success = True
            message = str(response.content) if hasattr(response, 'content') else str(response)
            
        except Exception as e:
            success = False
            message = str(e)
    
    # Show results
    if success:
        console.print(Panel(
            f"[bold green]✓ LLM is healthy[/]\n\n"
            f"Provider: [yellow]{provider}[/]\n"
            f"Response: [dim]{message[:100]}[/]",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[bold red]✗ LLM test failed[/]\n\n"
            f"Provider: [yellow]{provider}[/]\n"
            f"Error: [red]{message[:200]}[/]",
            border_style="red"
        ))
        sys.exit(1)
