from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from app.database.models import User, DuoTeam, DuoStat
import random

# ELO calculation constants
K_FACTOR = 32
DEFAULT_RATING = 1000

async def get_or_create_duo_stat(session: AsyncSession, duo_team_id: int) -> DuoStat:
    duo_stat_res = await session.execute(
        select(DuoStat).filter_by(duo_team_id=duo_team_id)
    )
    duo_stat = duo_stat_res.scalars().first()
    if not duo_stat:
        duo_stat = DuoStat(duo_team_id=duo_team_id, rating=DEFAULT_RATING)
        session.add(duo_stat)
        await session.flush()
    return duo_stat

async def calculate_elo_change(
    rating_a: int, rating_b: int, outcome: str
) -> tuple[int, int]:
    """
    Calculates the ELO rating changes for two players/teams.
    outcome: "win" for player A, "loss" for player A, "draw"
    """
    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    expected_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))

    if outcome == "win":
        score_a, score_b = 1, 0
    elif outcome == "loss":
        score_a, score_b = 0, 1
    elif outcome == "draw":
        score_a, score_b = 0.5, 0.5
    else:
        raise ValueError("Outcome must be 'win', 'loss', or 'draw'")

    change_a = K_FACTOR * (score_a - expected_a)
    change_b = K_FACTOR * (score_b - expected_b)

    return round(change_a), round(change_b)

async def update_duo_elo(
    session: AsyncSession,
    winning_duo_team_id: int | None,
    losing_duo_team_id: int | None,
    draw: bool = False
):
    """
    Updates the ELO ratings for duos after a match.
    """
    duo_a_stat: DuoStat | None = None
    duo_b_stat: DuoStat | None = None

    if winning_duo_team_id:
        duo_a_stat = await get_or_create_duo_stat(session, winning_duo_team_id)
    if losing_duo_team_id:
        duo_b_stat = await get_or_create_duo_stat(session, losing_duo_team_id)

    if draw:
        if duo_a_stat and duo_b_stat:
            change_a, change_b = await calculate_elo_change(
                duo_a_stat.rating, duo_b_stat.rating, "draw"
            )
            duo_a_stat.rating += change_a
            duo_b_stat.rating += change_b
        elif duo_a_stat: # One duo only implies one sided
            duo_a_stat.rating += K_FACTOR / 2 # Minor gain for one-sided draw if that ever happens
    elif duo_a_stat and duo_b_stat: # A wins, B loses
        change_a, change_b = await calculate_elo_change(
            duo_a_stat.rating, duo_b_stat.rating, "win"
        )
        duo_a_stat.rating += change_a
        duo_b_stat.rating += change_b
        duo_a_stat.wins += 1
        duo_b_stat.losses += 1
    elif duo_a_stat: # Only A participated and won (e.g., vs AI or forfeit)
        duo_a_stat.rating += K_FACTOR / 2
        duo_a_stat.wins += 1
    elif duo_b_stat: # Only B participated and won
        duo_b_stat.rating += K_FACTOR / 2
        duo_b_stat.wins += 1
    
    # In case the opponent wasn't a duo, but a single player etc.
    # We would need to handle that logic from the handler / pvp command
    # and call update_duo_elo only for the winning duo.
    
    await session.commit()
