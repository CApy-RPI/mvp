"""Helper functions for creating Discord embeds with consistent colors."""

import discord
from .. import config_colors as colors


def error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        title=title, description=description, color=colors.STATUS_ERROR
    )


def success_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        title=title, description=description, color=colors.STATUS_RESOLVED
    )


def info_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=colors.STATUS_INFO)


def warning_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        title=title, description=description, color=colors.STATUS_WARNING
    )


def important_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        title=title, description=description, color=colors.STATUS_IMPORTANT
    )


def unmarked_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        title=title, description=description, color=colors.STATUS_UNMARKED
    )


def ignored_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        title=title, description=description, color=colors.STATUS_IGNORED
    )
