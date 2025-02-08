"""Guild-specific view classes."""

import discord
from frontend.utils.view_bases import BaseDropdownView


class ChannelSelectView(BaseDropdownView):
    def __init__(self, channels: dict[str, str]):
        super().__init__()
        self.selected_channels = {}

        for channel_name, description in channels.items():
            select = discord.ui.ChannelSelect(
                placeholder=f"Select {channel_name.title()} channel",
                channel_types=[discord.ChannelType.text],
                custom_id=f"channel_{channel_name}",
            )
            select.callback = self.create_callback(channel_name)
            self.add_item(select)

    def create_callback(self, channel_name: str):
        async def callback(interaction: discord.Interaction):
            try:
                values = interaction.data.get("values", [])
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
    def __init__(self, roles: dict[str, str]):
        super().__init__()
        self.selected_roles = {}

        for role_name, description in roles.items():
            select = discord.ui.RoleSelect(
                placeholder=f"Select {role_name.title()} role",
                custom_id=f"role_{role_name}",
            )
            select.callback = self.create_callback(role_name)
            self.add_item(select)

    def create_callback(self, role_name: str):
        async def callback(interaction: discord.Interaction):
            try:
                values = interaction.data.get("values", [])
                if values:
                    self.selected_roles[role_name] = values[0]
                else:
                    self.selected_roles.pop(role_name, None)
                await interaction.response.defer()
            except Exception:
                await interaction.response.send_message(
                    "Failed to process role selection.", ephemeral=True
                )

        return callback


class SettingsSelectView(discord.ui.View):
    def __init__(self, parent_cog):
        super().__init__(timeout=180.0)
        self.parent_cog = parent_cog
        self.message = None
        self.current_view = None
