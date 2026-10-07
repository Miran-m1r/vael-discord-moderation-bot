from __future__ import annotations

def add_cog(bot, cog) -> None:
    result = bot.add_cog(cog)
    return result


def load_extension(bot, name: str) -> None:
    result = bot.load_extension(name)
    return result
