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

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, row=4)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = True
        self.interaction_done = True
        self.stop()
        if self.message:
            await self.message.delete()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = False
        self.interaction_done = True
        self.stop()
        if self.message:
            await self.message.delete()


class ConfirmDeleteView(discord.ui.View):
    """Confirmation view for profile deletion."""

    def __init__(self):
        super().__init__()
        self.value = None

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.value = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = False
        self.stop()
