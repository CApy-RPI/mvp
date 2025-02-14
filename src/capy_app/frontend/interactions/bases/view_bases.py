"""Utility classes for Discord views."""

import discord


class ConfirmDeleteView(discord.ui.View):
    """Confirmation view for profile deletion."""

    def __init__(self):
        super().__init__()
        self.value = None

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm(
        self,
        interaction: discord.Interaction[discord.Client],
        button: discord.ui.Button[discord.ui.View],
    ) -> None:
        await interaction.response.defer()
        self.value = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(
        self,
        interaction: discord.Interaction[discord.Client],
        button: discord.ui.Button[discord.ui.View],
    ) -> None:
        await interaction.response.defer()
        self.value = False
        self.stop()
