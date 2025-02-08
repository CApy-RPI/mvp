"""Guild-specific view classes for Discord interactions.

This module provides UI components for guild settings management:
- Channel selection view
- Role selection view
- Settings selection view

#TODO: Add permission requirement checks
#TODO: Add validation for selected channels/roles
"""

from typing import Any, Optional, Dict, cast, Callable, Coroutine
import discord
from discord import ui
from discord.interactions import Interaction
from frontend.utils.interactions.view_bases import BaseDropdownView


class ChannelSelectView(BaseDropdownView):
    """View for selecting guild channels."""

    def __init__(self, channels: Dict[str, str]) -> None:
        """Initialize channel selection view.

        Args:
            channels: Dictionary of channel names and descriptions
        """
        super().__init__()
        self.selected_channels: Dict[str, int] = {}

        for channel_name, description in channels.items():
            select = ui.ChannelSelect[ui.View](
                placeholder=f"Select {channel_name.title()} channel",
                channel_types=[discord.ChannelType.text],
                custom_id=f"channel_{channel_name}",
            )
            
            select.callback = self._create_channel_callback(channel_name)
            self.add_item(select)

    def _create_channel_callback(
        self, channel_name: str
    ) -> Callable[[Interaction[discord.Client]], Coroutine[Any, Any, None]]:
        async def callback(interaction: Interaction[discord.Client]) -> None:
            try:
                interaction_data = cast(Dict[str, Any], interaction.data)
                values = interaction_data.get("values", [])
                if values:
                    self.selected_channels[channel_name] = int(values[0])
                else:
                    self.selected_channels.pop(channel_name, None)
                await interaction.response.defer()
            except Exception:
                await interaction.response.send_message(
                    "Failed to process channel selection.", ephemeral=True
                )
        return callback


class RoleSelectView(BaseDropdownView):
    """View for selecting guild roles."""

    def __init__(self, roles: Dict[str, str]) -> None:
        """Initialize role selection view.

        Args:
            roles: Dictionary of role names and descriptions
        """
        super().__init__()
        self.selected_roles: Dict[str, int] = {}

        for role_name, description in roles.items():
            select = ui.RoleSelect[ui.View](
                placeholder=f"Select {role_name.title()} role",
                custom_id=f"role_{role_name}",
            )
            
            select.callback = self._create_role_callback(role_name)
            self.add_item(select)

    def _create_role_callback(
        self, role_name: str
    ) -> Callable[[Interaction[discord.Client]], Coroutine[Any, Any, None]]:
        async def callback(interaction: Interaction[discord.Client]) -> None:
            try:
                interaction_data = cast(Dict[str, Any], interaction.data)
                values = interaction_data.get("values", [])
                if values:
                    self.selected_roles[role_name] = int(values[0])
                else:
                    self.selected_roles.pop(role_name, None)
                await interaction.response.defer()
            except Exception:
                await interaction.response.send_message(
                    "Failed to process role selection.", ephemeral=True
                )
        return callback


class SettingsSelectView(discord.ui.View):
    """View for selecting which settings to edit."""

    def __init__(self, parent_cog: Any) -> None:
        """Initialize settings selection view.

        Args:
            parent_cog: Reference to the parent cog for callbacks

        #TODO: Add proper typing for parent_cog
        #TODO: Add timeout handling
        """
        super().__init__(timeout=180.0)
        self.parent_cog = parent_cog
        self.message: Optional[discord.Message] = None
        self.current_view: Optional[BaseDropdownView] = None
