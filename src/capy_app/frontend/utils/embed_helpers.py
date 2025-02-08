import discord
from frontend.utils import embed_colors as colors


def error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=colors.ERROR)


def success_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=colors.SUCCESS)


def info_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=colors.INFO)


def primary_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=colors.PRIMARY)


def warning_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=colors.WARNING)
