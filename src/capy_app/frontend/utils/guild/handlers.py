"""Guild settings update handlers."""

import logging
from typing import Any
import discord
from backend.db.database import Database as db
from .views import ChannelSelectView, RoleSelectView

logger = logging.getLogger("discord.guild.handler")


async def handle_channel_update(
    interaction: discord.Interaction,
    view: ChannelSelectView,
    guild_data: Any,
    channels: dict[str, str],
) -> bool:
    """Handle channel updates after selection.
    
    Args:
        interaction: The Discord interaction
        view: Channel selection view
        guild_data: Guild database document
        channels: Channel configuration dictionary
    
    Returns:
        bool: True if update was successful, False otherwise
    """
    if not view.selected_channels:
        await interaction.edit_original_response(
            content="No channels were selected. Select channels to update:",
            view=ChannelSelectView(channels),
            embed=None
        )
        return False

    try:
        updates = {f"channels__{name}": id for name, id in view.selected_channels.items()}
        db.update_document(guild_data, updates)
        return True
    except Exception as e:
        logger.error(f"Failed to update channels: {e}")
        await interaction.edit_original_response(
            content="Failed to update channel settings. Please try again:",
            view=ChannelSelectView(channels),
            embed=None
        )
        return False


async def handle_role_update(
    interaction: discord.Interaction,
    view: RoleSelectView,
    guild_data: Any,
    roles: dict[str, str],
) -> bool:
    """Handle role updates after selection.
    
    Args:
        interaction: The Discord interaction
        view: Role selection view
        guild_data: Guild database document
        roles: Role configuration dictionary
    
    Returns:
        bool: True if update was successful, False otherwise
    """
    if not view.selected_roles:
        await interaction.edit_original_response(
            content="No roles were selected. Select roles to update:",
            view=RoleSelectView(roles),
            embed=None
        )
        return False

    try:
        updates = {f"roles__{name}": id for name, id in view.selected_roles.items()}
        db.update_document(guild_data, updates)
        return True
    except Exception as e:
        logger.error(f"Failed to update roles: {e}")
        await interaction.edit_original_response(
            content="Failed to update role settings. Please try again:",
            view=RoleSelectView(roles),
            embed=None
        )
        return False
