"""Base classes for creating dynamic dropdown menus in Discord interactions.

This module provides a flexible framework for creating both single and multi-select
dropdown menus with optional accept/cancel buttons. It supports:
- Dynamic option creation from dictionaries
- Sequential and concurrent dropdown displays
- Automatic button addition for multi-dropdown views
- Message lifecycle management
"""

from typing import Dict, Optional, List, Tuple
import logging
from discord import SelectOption, Interaction, ButtonStyle, Message
from discord.ui import Select, View, Button
from discord.errors import NotFound

from config import settings

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)


class AcceptButton(Button["MultiSelectorView"]):
    """Button that confirms selections and stops the view."""

    def __init__(self) -> None:
        super().__init__(
            style=ButtonStyle.green,
            label="Accept",
            custom_id="accept",
            row=4,  # Put buttons on the last row
        )

    async def callback(self, interaction: Interaction) -> None:
        """Handle accept button click."""
        assert self.view is not None
        logger.debug("Accept button clicked")
        self.view.accepted = True
        self.view.stop()
        await interaction.response.defer()


class CancelButton(Button["MultiSelectorView"]):
    """Button that cancels selections and stops the view."""

    def __init__(self) -> None:
        super().__init__(
            style=ButtonStyle.red,
            label="Cancel",
            custom_id="cancel",
            row=4,  # Put buttons on the last row
        )

    async def callback(self, interaction: Interaction) -> None:
        """Handle cancel button click."""
        assert self.view is not None
        logger.debug("Cancel button clicked")
        self.view.accepted = False
        self.view.stop()
        await interaction.response.defer()


class DynamicDropdown(Select["MultiSelectorView"]):
    """A dropdown menu with dynamic options and configurable selection limits."""

    def __init__(
        self,
        options_dict: Dict[str, Dict[str, str]],
        placeholder: str = "Make a selection",
        min_values: int = 1,
        max_values: int = 1,
        disable_on_select: bool = False,
        custom_id: str = "",
        row: int = 0,
    ) -> None:
        """Initialize the dropdown with options from a dictionary.

        Args:
            options_dict: Dictionary of options {label: {"value": val, "description": desc}}
            placeholder: Text shown when no selection is made
            min_values: Minimum number of selections required
            max_values: Maximum number of selections allowed
            disable_on_select: Whether to disable the dropdown after selection
            custom_id: Unique identifier for the dropdown
            row: Discord UI row number (0-4)
        """
        self.disable_on_select = disable_on_select
        self.selected_values: List[str] = []

        options = [
            SelectOption(
                label=label,
                value=data.get("value", label),
                description=data.get("description", ""),
            )
            for label, data in options_dict.items()
        ]

        super().__init__(
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            options=options,
            custom_id=custom_id,
            row=row,
        )

    async def callback(self, interaction: Interaction) -> None:
        """Handle dropdown selection."""
        self.selected_values = self.values
        logger.debug(
            f"Dropdown {self.custom_id} selected values: {self.selected_values}"
        )

        if self.disable_on_select:
            self.disabled = True
            logger.debug(f"Dropdown {self.custom_id} disabled after selection")

        if isinstance(self.view, MultiSelectorView) and not self.view._has_buttons:
            self.view.stop()

        await interaction.response.defer()


class MultiSelectorView(View):
    """A view that can contain multiple dropdowns with optional accept/cancel buttons."""

    def __init__(
        self,
        timeout: float = 180.0,
        auto_buttons: bool = True,
    ) -> None:
        """Initialize the multi-selector view.

        Args:
            timeout: Time in seconds before the view times out
            auto_buttons: Whether to automatically add accept/cancel buttons for multiple dropdowns
        """
        super().__init__(timeout=timeout)
        self.dropdowns: List[DynamicDropdown] = []
        self.accepted: bool = False
        self.timeout: bool = False
        self._has_buttons: bool = False
        self._collected_data: bool = False
        self.message: Optional[Message] = None
        self.ephemeral: bool = True
        self.auto_buttons = auto_buttons

    async def initiate_message_from_interaction(
        self,
        interaction: Interaction,
        content: str = "Make your selections:",
        ephemeral: bool = True,
    ) -> Message:
        """Send initial message and store its reference.

        Args:
            interaction: Discord interaction to respond to
            content: Message content to display
            ephemeral: Whether the message should be ephemeral

        Returns:
            The sent message object
        """
        # Add buttons automatically for multiple dropdowns
        if self.auto_buttons and len(self.dropdowns) > 1:
            logger.debug("Auto-adding buttons for multiple dropdowns")
            self.add_accept_cancel_buttons()

        self.ephemeral = ephemeral
        await interaction.response.send_message(content, view=self, ephemeral=ephemeral)
        self.message = await interaction.original_response()
        return self.message

    async def initiate_message_from_message(
        self,
        message: Message,
        content: str = "Make your selections:",
    ) -> Message:
        """Updates an existing message with this view."""
        if self.auto_buttons and len(self.dropdowns) > 1:
            self.add_accept_cancel_buttons()

        self.message = await message.edit(content=content, view=self)
        self.ephemeral = message.flags.ephemeral
        return self.message

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(content="Selection timed out", view=None)
            except NotFound:
                pass

    async def get_data(self) -> Tuple[Dict[str, List[str]] | None, Message | None]:
        """Wait for user input and return selected values.

        Returns:
            Tuple containing:
            - Dictionary of selections if accepted, None if cancelled
            - Reference to the message object
        """
        if not self._collected_data:
            logger.debug("Waiting for user selections")
            await self.wait()
            self._collected_data = True

        selections = {
            dropdown.custom_id: dropdown.selected_values
            for dropdown in self.dropdowns
            if dropdown.selected_values
        }

        logger.debug(
            f"Collection complete. Accepted: {self.accepted}, Selections: {selections}"
        )

        # Update message based on result
        if self.message:
            try:
                if self.accepted:
                    await self.message.edit(content="Selections accepted", view=None)
                elif self.timeout:
                    await self.message.edit(content="Selection timed out", view=None)
                else:
                    await self.message.edit(content="Selection cancelled", view=None)
            except NotFound:
                logger.warning("Message not found when trying to update status")

        return (selections, self.message) if self.accepted else (None, self.message)

    def add_dropdown(
        self,
        options_dict: Dict[str, Dict[str, str]],
        placeholder: str = "Make a selection",
        min_values: int = 1,
        max_values: int = 1,
        disable_on_select: bool = False,
        custom_id: str = "",
        row: int = 0,
    ) -> DynamicDropdown:
        dropdown = DynamicDropdown(
            options_dict=options_dict,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            disable_on_select=disable_on_select,
            custom_id=custom_id or f"dropdown_{len(self.dropdowns)}",
            row=row,
        )
        self.dropdowns.append(dropdown)
        self.add_item(dropdown)
        return dropdown

    def add_accept_cancel_buttons(self) -> None:
        """Adds accept and cancel buttons to the view."""
        if self._has_buttons:
            return

        self.add_item(AcceptButton())
        self.add_item(CancelButton())
        self._has_buttons = True
