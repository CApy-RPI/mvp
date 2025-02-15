"""Base classes for creating dynamic dropdown menus in Discord interactions.

This module provides a flexible framework for creating both single and multi-select
dropdown menus with optional accept/cancel buttons. It supports:
- Dynamic option creation from dictionaries
- Sequential and concurrent dropdown displays
- Automatic button addition for multi-dropdown views
- Message lifecycle management
"""

from typing import Dict, Optional, List, Tuple, Any, cast
import logging
from discord import SelectOption, Interaction, ButtonStyle, Message
from discord.ui import Select, View, Button
from discord.errors import NotFound

from config import settings

# Configure logging
logger = logging.getLogger(f"discord.interactions.{__name__.lower()}")
logger.setLevel(settings.LOG_LEVEL)


class AcceptButton(Button["DynamicDropdownView"]):
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


class CancelButton(Button["DynamicDropdownView"]):
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


class DynamicDropdown(Select["DynamicDropdownView"]):
    """A dropdown menu with dynamic options and configurable selection limits."""

    MAX_OPTIONS = 25  # Discord's limit for options in a select menu

    def __init__(
        self,
        selections: Optional[List[Dict[str, Any]]] = None,
        disable_on_select: bool = False,
        default_values: Optional[List[str]] = None,
        **options,
    ) -> None:
        self.selected_values: List[str] = []
        self._disable_on_select = disable_on_select
        self._default_values = default_values or []

        select_options = []
        if selections is not None:
            for selection in selections:
                option = SelectOption(**selection)
                if self._default_values and option.value in self._default_values:
                    option.default = True
                select_options.append(option)

            # Validate and truncate selections if needed
            if len(select_options) > self.MAX_OPTIONS:
                logger.warning(
                    f"Dropdown options exceeded Discord limit of {self.MAX_OPTIONS}. "
                    f"Truncating from {len(select_options)} options."
                )
                select_options = select_options[: self.MAX_OPTIONS]

        super().__init__(
            options=select_options,
            **options,
        )

        # Initialize with default values
        if self._default_values:
            self.selected_values = self._default_values.copy()

    async def callback(self, interaction: Interaction) -> None:
        """Handle dropdown selection."""
        self.selected_values = self.values
        logger.debug(
            f"Dropdown {self.custom_id} selected values: {self.selected_values}"
        )

        if self._disable_on_select:
            self.disabled = True
            logger.debug(f"Dropdown {self.custom_id} disabled after selection")

        view = cast(DynamicDropdownView, self.view)
        if not view._has_buttons:
            view.accepted = True
            view.stop()

        await interaction.response.defer()


class DynamicDropdownView(View):
    """A view that can contain multiple dropdowns with optional accept/cancel buttons."""

    MAX_DROPDOWNS = 5  # Discord's limit for components in a view

    def __init__(
        self,
        dropdowns: Optional[List[Dict[str, Any]]] = None,
        ephemeral: bool = True,
        auto_buttons: bool = True,
        add_buttons: bool = False,
        **options,
    ) -> None:
        """Initialize the multi-selector view.

        Args:
            timeout: Time in seconds before the view times out
            auto_buttons: Whether to automatically add accept/cancel buttons for multiple dropdowns
        """
        super().__init__(**options)
        self.accepted: bool = False

        self._dropdowns: List[DynamicDropdown] = []
        self._completed: bool = False
        self._timed_out: bool = False
        self._has_buttons: bool = False
        self._message: Optional[Message] = None
        self._ephemeral: bool = ephemeral
        self._auto_buttons = auto_buttons
        self._add_buttons = add_buttons

        dropdowns = dropdowns or []
        if (
            len(dropdowns) > self.MAX_DROPDOWNS
            or len(dropdowns) > self.MAX_DROPDOWNS - 1
            and (self._auto_buttons or self._add_buttons)
        ):
            raise ValueError(
                f"Number of dropdowns exceeds Discord limit of {self.MAX_DROPDOWNS}. "
            )

        for dropdown in dropdowns:
            self._add_dropdown(**dropdown)

    async def initiate_from_interaction(
        self,
        interaction: Interaction,
        content: str = "Make your selections:",
    ) -> tuple[Dict[str, List[str]] | None, Message | None]:
        """Send initial message and wait for selections."""
        self._add_accept_cancel_buttons_if_needed()

        await interaction.response.send_message(
            content, view=self, ephemeral=self._ephemeral
        )
        self._message = await interaction.original_response()
        return await self._get_data()

    async def initiate_from_message(
        self,
        message: Message,
        content: str = "Make your selections:",
    ) -> tuple[Dict[str, List[str]] | None, Message | None]:
        """Update existing message and wait for selections."""
        self._add_accept_cancel_buttons_if_needed()

        self._message = await message.edit(content=content, view=self)
        self._ephemeral = message.flags.ephemeral
        return await self._get_data()

    async def on_timeout(self) -> None:
        if self._completed:
            return

        self._timed_out = True
        if not self._message:
            return

        try:
            await self._message.edit(content="Selection timed out", view=None)
        except NotFound:
            pass

    def _add_dropdown(
        self,
        selections: List[Dict[str, Any]],
        **options,
    ) -> DynamicDropdown:
        dropdown = DynamicDropdown(selections=selections, **options)
        self._dropdowns.append(dropdown)
        self.add_item(dropdown)
        return dropdown

    def _add_accept_cancel_buttons_if_needed(self) -> None:
        """Adds accept and cancel buttons to the view."""
        if self._has_buttons:
            logger.warning("Buttons already added to view")
            return

        if not self._add_buttons and (
            not self._auto_buttons or len(self._dropdowns) == 1
        ):
            return

        self.add_item(AcceptButton())
        self.add_item(CancelButton())
        self._has_buttons = True

    async def _get_data(self) -> Tuple[Dict[str, List[str]] | None, Message | None]:
        """Wait for user input and return selected values.

        Returns:
            Tuple containing:
            - Dictionary of selections if accepted, None if cancelled
            - Reference to the message object
        """
        if not self._completed:
            logger.debug("Waiting for user selections")
            await self.wait()
            self._completed = True

        selections = {
            dropdown.custom_id: dropdown.selected_values
            for dropdown in self._dropdowns
            if dropdown.selected_values
        }

        logger.debug(
            f"Collection complete. Accepted: {self.accepted}, Selections: {selections}"
        )

        # Update message based on result
        if self._message:
            try:
                if self.accepted:
                    logger.debug("Selections accepted")
                    await self._message.edit(content="Selections accepted", view=None)
                elif self._timed_out:
                    logger.debug("Selection timed out")
                    await self._message.edit(content="Selection timed out", view=None)
                else:
                    logger.debug("Selection cancelled")
                    await self._message.edit(content="Selection cancelled", view=None)
            except NotFound:
                logger.warning("Message not found when trying to update status")

        self.stop()
        return selections if self.accepted else None, self._message
