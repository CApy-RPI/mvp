"""Utility classes for Discord views."""

import logging
from typing import Optional, Any, Dict, Tuple
import discord
from discord import Message, Interaction, ButtonStyle
from discord.errors import NotFound
from config import settings

# Configure logging
logger = logging.getLogger(f"discord.interactions.{__name__.lower()}")
logger.setLevel(settings.LOG_LEVEL)


class BaseButtonView(discord.ui.View):
    """Base view for button interactions."""

    def __init__(self, ephemeral: bool = True, **options) -> None:
        super().__init__(**options)
        self._ephemeral = ephemeral
        self._message: Optional[Message] = None
        self._completed: bool = False
        self._timed_out: bool = False
        self.value: Optional[bool] = None

    async def _send_status_message(self, content: str) -> None:
        """Update status message."""
        if self._message:
            try:
                await self._message.edit(content=content, view=None)
            except NotFound:
                logger.warning("Message not found when updating status")

    async def initiate_from_interaction(
        self, interaction: Interaction, content: str
    ) -> Tuple[Optional[bool], Optional[Message]]:
        """Show buttons from a new interaction."""
        await interaction.response.send_message(
            content=content,
            view=self,
            ephemeral=self._ephemeral,
        )
        self._message = await interaction.original_response()
        return await self._get_data()

    async def initiate_from_message(
        self, message: Message, content: str
    ) -> Tuple[Optional[bool], Optional[Message]]:
        """Show buttons on an existing message."""
        self._message = await message.edit(content=content, view=self)
        return await self._get_data()

    async def _get_data(self) -> Tuple[Optional[bool], Optional[Message]]:
        """Wait for user input and return result."""
        if not self._completed:
            await self.wait()
            self._completed = True

        if self._timed_out:
            await self._send_status_message("Operation timed out")
            return None, self._message

        return self.value, self._message

    async def on_timeout(self) -> None:
        """Handle view timeout."""
        if self._completed:
            return

        self._timed_out = True
        await self._send_status_message("Operation timed out")


class AcceptCancelView(BaseButtonView):
    """View with accept and cancel buttons."""

    @discord.ui.button(label="Accept", style=ButtonStyle.success)
    async def accept(
        self, interaction: Interaction, button: discord.ui.Button[Any]
    ) -> None:
        """Handle accept button press."""
        await interaction.response.defer()
        self.value = True
        self._completed = True
        await self._send_status_message("Operation accepted")
        self.stop()

    @discord.ui.button(label="Cancel", style=ButtonStyle.danger)
    async def cancel(
        self, interaction: Interaction, button: discord.ui.Button[Any]
    ) -> None:
        """Handle cancel button press."""
        await interaction.response.defer()
        self.value = False
        self._completed = True
        await self._send_status_message("Operation cancelled")
        self.stop()


class ConfirmDeleteView(AcceptCancelView):
    """Confirmation view for deletion with custom labels."""

    def __init__(self, **options) -> None:
        super().__init__(**options)
        self.accept.label = "Confirm Delete"  # type: ignore
        self.accept.style = ButtonStyle.danger  # type: ignore
        self.cancel.style = ButtonStyle.secondary  # type: ignore
