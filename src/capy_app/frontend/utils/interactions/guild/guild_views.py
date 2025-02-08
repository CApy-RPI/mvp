"""Guild-specific view classes for Discord interactions.

This module provides UI components for guild settings management:
- Channel selection view
- Role selection view
- Settings selection view

#TODO: Add permission requirement checks
#TODO: Add validation for selected channels/roles
"""

from typing import Any, Callable, Coroutine, Optional, Dict
import discord
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
            select = discord.ui.ChannelSelect(
                placeholder=f"Select {channel_name.title()} channel",
                channel_types=[discord.ChannelType.text],
                custom_id=f"channel_{channel_name}",
            )
            select.callback = self.create_callback(channel_name)
            self.add_item(select)

    def create_callback(
        self, channel_name: str
    ) -> Callable[[discord.Interaction], Coroutine[Any, Any, None]]:
        """Create callback for channel selection.

        Args:
            channel_name: Name of the channel being selected

        Returns:
            Callback function for the channel select
        """

        async def callback(interaction: discord.Interaction) -> None:
            try:
                values = interaction.data.get("values", [])  # type: ignore
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
            select = discord.ui.RoleSelect(
                placeholder=f"Select {role_name.title()} role",
                custom_id=f"role_{role_name}",
            )
            select.callback = self.create_callback(role_name)
            self.add_item(select)

    def create_callback(
        self, role_name: str
    ) -> Callable[[discord.Interaction], Coroutine[Any, Any, None]]:
        """Create callback for role selection.

        Args:
            role_name: Name of the role being selected

        Returns:
            Callback function for the role select
        """

        async def callback(interaction: discord.Interaction) -> None:
            try:
                values = interaction.data.get("values", [])  # type: ignore
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
