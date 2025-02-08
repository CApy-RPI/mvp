"""Utility classes for Discord views."""

import discord


class BaseDropdownView(discord.ui.View):
    """Base view for dropdown menus with Accept/Cancel/Skip buttons."""

    def __init__(self, timeout=180.0):
        super().__init__(timeout=timeout)
        self.value = None  # True for accept, False for cancel, None for timeout
        self.skipped = False  # True if skip was pressed
        self.interaction_done = False
        self.message = None

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.delete()

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = True
        self.interaction_done = True
        self.stop()
        if self.message:
            await self.message.delete()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = False
        self.interaction_done = True
        self.stop()
        if self.message:
            await self.message.delete()
