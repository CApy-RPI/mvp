"""Utility classes for Discord views."""

import logging
from typing import Any

import discord
from discord import ButtonStyle, Interaction, Message
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
        self._message: Message | None = None
        self._completed: bool = False
        self._timed_out: bool = False
        self.value: bool | None = None
        self.interaction: Interaction | None = None

    async def _send_status_message(self, content: str) -> None:
        """Update status message."""
        if self._message:
            try:
                await self._message.edit(content=content, view=None)
            except NotFound:
                logger.warning("Message not found when updating status")

    async def initiate_from_interaction(
        self, interaction: Interaction, content: str
    ) -> tuple[bool | None, Message | None]:
        """Show buttons from a new interaction."""
        await interaction.response.send_message(
            content=content,
            view=self,
            ephemeral=self._ephemeral,
        )
        self._message = await interaction.original_response()
        return await self._get_data()

    async def initiate_from_message(self, message: Message, content: str) -> tuple[bool | None, Message | None]:
        """Show buttons on an existing message."""
        self._message = await message.edit(content=content, view=self)
        return await self._get_data()

    async def _get_data(self) -> tuple[bool | None, Message | None]:
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
    async def accept(self, interaction: Interaction, _button: discord.ui.Button[Any]) -> None:
        """Handle accept button press."""
        # Store the interaction so the caller can respond to it
        self.interaction = interaction
        self.value = True
        self._completed = True
        self.stop()

    @discord.ui.button(label="Cancel", style=ButtonStyle.danger)
    async def cancel(self, interaction: Interaction, _button: discord.ui.Button[Any]) -> None:
        """Handle cancel button press."""
        # Store the interaction so the caller can respond to it
        self.interaction = interaction
        self.value = False
        self._completed = True
        self.stop()
        self.stop()


class ConfirmDeleteView(AcceptCancelView):
    """Confirmation view for deletion with custom labels."""

    def __init__(self, **options) -> None:
        super().__init__(**options)
        self.accept.label = "Confirm Delete"
        self.accept.style = ButtonStyle.danger
        self.cancel.style = ButtonStyle.secondary


class ConfirmView(AcceptCancelView):
    """Customizable confirmation view with configurable button labels and styles."""

    def __init__(
        self,
        confirm_text: str = "Confirm",
        confirm_style: ButtonStyle = ButtonStyle.primary,
        cancel_text: str = "Cancel",
        cancel_style: ButtonStyle = ButtonStyle.secondary,
        **options,
    ) -> None:
        super().__init__(**options)
        self.accept.label = confirm_text  # type: ignore
        self.accept.style = confirm_style  # type: ignore
        self.cancel.label = cancel_text  # type: ignore
        self.cancel.style = cancel_style  # type: ignore


class EditView(BaseButtonView):
    """Button view for editing."""

    def __init__(self, callback, **options) -> None:
        """Initialize a view with an Edit button.

        Args:
            callback: Function to call when the edit button is clicked
        """
        super().__init__(**options)
        self._callback = callback

    @discord.ui.button(label="Edit", style=ButtonStyle.primary)
    async def edit_button(self, interaction: Interaction, _button: discord.ui.Button[Any]) -> None:
        """Handle edit button press."""
        await self._callback(interaction)

    @discord.ui.button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel_button(self, interaction: Interaction, _button: discord.ui.Button[Any]) -> None:
        """Handle cancel button press."""
        await interaction.response.defer()
        self.value = False
        self._completed = True
        await self._send_status_message("Edit cancelled")
        self.stop()
