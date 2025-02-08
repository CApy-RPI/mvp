"""Provides menu and prompt interaction utilities for Discord commands."""

import typing
import asyncio
import discord
from discord.ext import commands

PromptValue = typing.Union[int, str]
PromptResult = typing.Optional[typing.Tuple[str, PromptValue]]
PromptResults = typing.Dict[str, PromptValue]


class MenuTimeout(commands.CommandError):
    """Exception raised when menu selection times out."""


async def _handle_reaction_menu(
    ctx: commands.Context[typing.Any],
    menu_msg: discord.Message,
    options: typing.Dict[str, str],
    timeout: float,
) -> typing.Optional[str]:
    """Handle reaction-based menu interaction."""
    for emoji in options:
        await menu_msg.add_reaction(emoji)

    try:
        reaction, _ = await ctx.bot.wait_for(
            "reaction_add",
            timeout=timeout,
            check=lambda r, u: (
                u == ctx.author
                and str(r.emoji) in options
                and r.message.id == menu_msg.id
            ),
        )
        return options[str(reaction.emoji)]
    finally:
        await menu_msg.clear_reactions()


async def _handle_message_menu(
    ctx: commands.Context[typing.Any],
    options: typing.Dict[str, str],
    timeout: float,
) -> typing.Optional[str]:
    """Handle message-based menu interaction."""
    try:
        msg = await ctx.bot.wait_for(
            "message",
            timeout=timeout,
            check=lambda m: (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content in options
            ),
        )
        await msg.delete()
        return options[msg.content]
    except asyncio.TimeoutError:
        return None


async def prompt_menu(
    ctx: commands.Context[typing.Any],
    options: typing.Dict[str, str],
    prompt: str,
    reaction_mode: bool = True,
    timeout: float = 30.0,
    title: str = "Menu",
    color: discord.Color = discord.Color.blurple(),
) -> typing.Optional[str]:
    """Create an interactive Discord menu.

    Args:
        ctx: Command context
        options: Mapping of emojis to their values
        prompt: Menu prompt text
        reaction_mode: Use reactions instead of messages
        timeout: Selection timeout in seconds
        title: Embed title
        color: Embed color

    Returns:
        Selected option value or None if timed out
    """
    embed = discord.Embed(title=title, description=prompt, color=color)
    menu_msg = await ctx.send(embed=embed)

    try:
        if reaction_mode:
            result = await _handle_reaction_menu(ctx, menu_msg, options, timeout)
        else:
            result = await _handle_message_menu(ctx, options, timeout)

        if result:
            return result

        # Handle timeout
        await menu_msg.edit(
            embed=discord.Embed(
                title="Menu Expired",
                description="Selection timed out.",
                color=discord.Color.red(),
            )
        )
        return None

    finally:
        await menu_msg.delete()


async def prompt_one(
    ctx: commands.Context[typing.Any],
    description: str,
    title: str = "Input Needed",
    color: discord.Color = discord.Color.blurple(),
    timeout: float = 30.0,
) -> typing.Optional[typing.Any]:
    """Prompt user for a single input response.

    Args:
        ctx: Command context
        description: What to ask the user
        title: Prompt title
        color: Embed color
        timeout: How long to wait for response

    Returns:
        User's message response or None if timed out
    """
    embed = discord.Embed(title=title, description=description, color=color)
    prompt_msg = await ctx.send(embed=embed)

    try:
        response = await ctx.bot.wait_for(
            "message",
            timeout=timeout,
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
        )
        if not response.content:
            return None
        return response

    except asyncio.TimeoutError:
        await prompt_msg.edit(
            embed=discord.Embed(
                title="Timeout",
                description="No response received.",
                color=discord.Color.red(),
            )
        )
        return None
    finally:
        await prompt_msg.delete()


async def prompt_many(
    ctx: commands.Context[typing.Any],
    prompts: typing.List[str],
    title: str = "Input Needed",
    color: discord.Color = discord.Color.blurple(),
    timeout: float = 30.0,
) -> typing.List[discord.Message]:
    """Prompt user for multiple inputs in sequence.

    Args:
        ctx: Command context
        prompts: List of questions to ask
        title: Base title for prompts
        color: Embed color
        timeout: Timeout per prompt

    Returns:
        List of user message responses, may be partial if timeout occurred
    """
    responses = []
    for i, prompt in enumerate(prompts, 1):
        embed = discord.Embed(
            title=f"{title} ({i}/{len(prompts)})",
            description=prompt,
            color=color,
        )
        prompt_msg = await ctx.send(embed=embed)

        try:
            response = await ctx.bot.wait_for(
                "message",
                timeout=timeout,
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            )
            responses.append(response)
            await prompt_msg.delete()

        except asyncio.TimeoutError:
            await prompt_msg.edit(
                embed=discord.Embed(
                    title="Timeout",
                    description="Input collection cancelled.",
                    color=discord.Color.red(),
                )
            )
            break

    return responses
