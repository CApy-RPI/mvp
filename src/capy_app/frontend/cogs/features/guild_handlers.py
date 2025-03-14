"""Guild settings update handlers.

This module provides handlers for updating guild settings:
- Channel configuration updates
- Role configuration updates

#TODO: Add validation for channel/role permissions
#TODO: Add rollback mechanism for failed updates
"""

import logging
from typing import Any, Dict
import discord
from backend.db.database import Database as db
from .guild_views import ChannelSelectView, RoleSelectView

logger = logging.getLogger("discord.guild.handler")


async def handle_channel_update(
    interaction: discord.Interaction,
    view: ChannelSelectView,
    guild_data: Any,
    channels: Dict[str, str],
) -> bool:
    """Handle channel updates after selection.

    Args:
        interaction: The Discord interaction
        view: Channel selection view
        guild_data: Guild database document
        channels: Channel configuration dictionary

    Returns:
        bool: True if update was successful, False otherwise

    #! Warning: Does not validate channel permissions
    #TODO: Add permission validation
    """
    try:
        if not view.selected_channels:
            return True  # No changes needed

        updates = {
            f"channels__{name}": str(channel_id)  # Convert to string
            for name, channel_id in view.selected_channels.items()
        }
        db.update_document(guild_data, updates)
        return True
    except Exception as e:
        logger.error(f"Failed to update channels: {e}")
        await interaction.edit_original_response(
            content="Failed to update channel settings. Please try again.",
            view=ChannelSelectView(channels),
            embed=None,
        )
        return False


async def handle_role_update(
    interaction: discord.Interaction,
    view: RoleSelectView,
    guild_data: Any,
    roles: Dict[str, str],
) -> bool:
    """Handle role updates after selection.

    Args:
        interaction: The Discord interaction
        view: Role selection view
        guild_data: Guild database document
        roles: Role configuration dictionary

    Returns:
        bool: True if update was successful, False otherwise

    #! Warning: Does not validate role hierarchy
    #TODO: Add role hierarchy validation
    """
    try:
        if not view.selected_roles:
            return True  # No changes needed

        updates = {
            f"roles__{name}": str(role_id)
            for name, role_id in view.selected_roles.items()
        }
        db.update_document(guild_data, updates)
        return True
    except Exception as e:
        logger.error(f"Failed to update roles: {e}")
        await interaction.edit_original_response(
            content="Failed to update role settings. Please try again.",
            view=RoleSelectView(roles),
            embed=None,
        )
        return False
