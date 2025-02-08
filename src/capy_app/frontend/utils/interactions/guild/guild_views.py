"""Guild-specific view classes for Discord interactions."""

from typing import Any, Optional, Dict, cast, Callable, Coroutine
import discord
from discord import ui
from discord.interactions import Interaction
from frontend.utils.interactions.view_bases import BaseDropdownView


class ChannelSelectView(BaseDropdownView):
    """View for selecting guild channels."""

    def __init__(self, channels: Dict[str, str]) -> None:
        super().__init__()
        self.selected_channels: Dict[str, int] = {}

        for name, desc in channels.items():
            select = ui.ChannelSelect(
                placeholder=f"Select {name.title()} channel",
                channel_types=[discord.ChannelType.text],
                custom_id=f"channel_{name}",
            )
            select.callback = self._create_callback(name)
            self.add_item(select)

    def _create_callback(
        self, name: str
    ) -> Callable[[Interaction], Coroutine[Any, Any, None]]:
        async def callback(interaction: Interaction) -> None:
            data = cast(Dict[str, Any], interaction.data)
            values = data.get("values", [])

            if values:
                self.selected_channels[name] = int(values[0])
            else:
                self.selected_channels.pop(name, None)

            await interaction.response.defer()

        return callback


class RoleSelectView(BaseDropdownView):
    """View for selecting guild roles."""

    def __init__(self, roles: Dict[str, str]) -> None:
        super().__init__()
        self.selected_roles: Dict[str, int] = {}

        for name, desc in roles.items():
            select = ui.RoleSelect(
                placeholder=f"Select {name.title()} role", custom_id=f"role_{name}"
            )
            select.callback = self._create_callback(name)
            self.add_item(select)

    def _create_callback(
        self, name: str
    ) -> Callable[[Interaction], Coroutine[Any, Any, None]]:
        async def callback(interaction: Interaction) -> None:
            data = cast(Dict[str, Any], interaction.data)
            values = data.get("values", [])

            if values:
                self.selected_roles[name] = int(values[0])
            else:
                self.selected_roles.pop(name, None)

            await interaction.response.defer()

        return callback


class SettingsSelectView(discord.ui.View):
    """View for selecting which settings to edit."""

    def __init__(self) -> None:
        super().__init__(timeout=180.0)
        self.selected_setting: Optional[str] = None

        select = discord.ui.Select(
            placeholder="Choose what to edit",
            options=[
                discord.SelectOption(
                    label="Channels",
                    value="channels",
                    description="Edit channel settings",
                ),
                discord.SelectOption(
                    label="Roles", value="roles", description="Edit role settings"
                ),
                discord.SelectOption(
                    label="All", value="all", description="Edit all settings"
                ),
            ],
            custom_id="settings_select",
        )

        select.callback = self._create_callback()
        self.add_item(select)

    def _create_callback(self) -> Callable[[Interaction], Coroutine[Any, Any, None]]:
        async def callback(interaction: Interaction) -> None:
            data = cast(Dict[str, Any], interaction.data)
            values = data.get("values", [])

            if values:
                self.selected_setting = values[0]
            else:
                self.selected_setting = None

            await interaction.response.defer()
            self.stop()

        return callback


class ClearSettingsView(BaseDropdownView):
    """View for selecting which settings to clear."""

    def __init__(self) -> None:
        super().__init__(timeout=180.0)
        self.selected_setting: Optional[str] = None

        select = discord.ui.Select(
            placeholder="Choose what to clear",
            options=[
                discord.SelectOption(
                    label="Channels",
                    value="channels",
                    description="Clear all channel settings",
                ),
                discord.SelectOption(
                    label="Roles", value="roles", description="Clear all role settings"
                ),
                discord.SelectOption(
                    label="All", value="all", description="Clear all server settings"
                ),
            ],
            custom_id="clear_select",
        )

        async def clear_callback(interaction: Interaction) -> None:
            self.selected_setting = select.values[0]

        select.callback = clear_callback
        self.add_item(select)
