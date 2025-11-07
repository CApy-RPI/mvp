"""Base classes for creating dynamic dropdown menus in Discord interactions.

This module provides a flexible framework for creating both single and multi-select
dropdown menus with optional accept/cancel buttons. It supports:
- Dynamic option creation from dictionaries
- Sequential and concurrent dropdown displays
- Automatic button addition for multi-dropdown views
- Message lifecycle management
"""

import asyncio
import logging
from contextlib import suppress
from typing import Any

from discord import ButtonStyle, Interaction, Message, SelectOption
from discord.errors import NotFound
from discord.ui import Button, Select, View

from config import settings

# Configure logging
logger = logging.getLogger(f"discord.interactions.{__name__.lower()}")
logger.setLevel(settings.LOG_LEVEL)


class RightButton(Button["DynamicDropdownView"]):
    """Button that goes to the next page of the dropdown"""

    def __init__(self) -> None:
        super().__init__(
            style=ButtonStyle.blurple,
            label=">",
            custom_id="right",
            row=4,  # Put buttons on the last row
        )

    async def callback(self, interaction: Interaction) -> None:
        """Handle accept button click."""
        assert self.view is not None
        logger.debug("Right button clicked")
        if self.view.page_number + 1 >= len(self.view._dropdowns_data):
            logger.debug("Already on last page")
            await interaction.response.defer()
            return

        await self.view.turn_page(1)
        await interaction.response.edit_message(view=self.view)


class LeftButton(Button["DynamicDropdownView"]):
    def __init__(self) -> None:
        super().__init__(
            style=ButtonStyle.blurple,
            label="<",
            custom_id="left",
            row=4,
        )

    async def callback(self, interaction: Interaction) -> None:
        assert self.view is not None
        logger.debug("Left button clicked")

        if self.view.page_number - 1 < 0:
            logger.debug("Already on first page")
            await interaction.response.defer()
            return

        await self.view.turn_page(-1)
        await interaction.response.edit_message(view=self.view)


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
        self.view._set_data()
        self.view.stop()
        # Only respond once: defer if no other response is sent
        #  if not interaction.response.is_done():
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
        self.view._set_data()
        self.view.stop()
        if self.view._message is not None:
            await self.view._message.edit(content="Selection cancelled", view=None)
        await interaction.response.defer()


class DynamicDropdown(Select["DynamicDropdownView"]):
    """A dropdown menu with dynamic options and configurable selection limits."""

    MAX_OPTIONS = 25  # Discord's limit for options in a select menu

    def __init__(
        self,
        selections: list[dict[str, Any]] | None = None,
        disable_on_select: bool = False,
        default_values: list[str] | None = None,
        **options,
    ) -> None:
        self.selected_values: list[str] = []
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
        assert self.view is not None
        view: DynamicDropdownView = self.view

        # Calculate current total selections across all dropdowns
        runningtotal = 0
        for dropdown in view._collection:
            for _major in view._collection[dropdown]:
                runningtotal += 1

        # Get previous selections for this dropdown to calculate the net change
        previous_selections = len(view._collection.get(self.custom_id, []))
        net_change = len(self.values) - previous_selections

        # Global limit of 2 majors total across all dropdowns
        global_limit = 2

        if runningtotal + net_change <= global_limit:
            # Accept the selection
            self.selected_values = self.values
            view._collection[self.custom_id] = self.selected_values

            logger.debug(
                f"Dropdown {self.custom_id} selected values: {self.selected_values}. "
                f"Current collection: {view._collection}"
            )

            if self._disable_on_select:
                self.disabled = True
                logger.debug(f"Dropdown {self.custom_id} disabled after selection")

            if not view._has_buttons:
                view.accepted = True
                view.stop()
                view._set_data()

            await interaction.response.defer()
        else:
            # Reject the selection and restore previous state
            total_after_change = runningtotal + net_change
            await interaction.response.send_message(
                f"You can only select up to {global_limit} majors total. "
                f"This selection would result in {total_after_change} majors.",
                ephemeral=True,
            )

            # Reset the dropdown to its previous state
            previous_values = view._collection.get(self.custom_id, [])
            self.selected_values = previous_values.copy()

            # Update the dropdown options to reflect the previous selection
            for option in self.options:
                option.default = option.value in previous_values

            return


class DynamicDropdownView(View):
    """A view that can contain multiple dropdowns with optional accept/cancel buttons."""

    MAX_DROPDOWNS = 5  # Discord's limit for components in a view

    def __init__(
        self,
        dropdowns: list[dict[str, Any]] | None = None,
        page_number: int = 0,
        ephemeral: bool = True,
        buttons: tuple[bool, bool] = (True, False),  # auto, add
        collection: dict[str, list[str]] | None = None,
        **options,
    ) -> None:
        """Initialize the multi-selector view.

        Args:
            timeout: Time in seconds before the view times out
            auto_buttons: Whether to automatically add accept/cancel buttons for multiple dropdowns
        """
        super().__init__(**options)
        self.accepted: bool = False
        self.data_future: asyncio.Future[tuple[dict[str, list[str]] | None, Message | None]] = (
            asyncio.get_event_loop().create_future()
        )
        self.page_number = page_number

        logger.debug(f"Dropdowns passed arg: {dropdowns}")
        self._dropdowns: list[DynamicDropdown] = []
        self._completed: bool = False
        self._timed_out: bool = False
        self._has_buttons: bool = False
        self._message: Message | None = None
        self._ephemeral: bool = ephemeral
        self._auto_buttons, self._add_buttons = buttons
        self._collection = collection if collection is not None else {}
        dropdowns = dropdowns or []
        # Flatten all dropdown configs into chunks
        all_chunks = []
        for dropdown_config in dropdowns:
            selections = dropdown_config.get("selections", [])
            chunks = self.chunk_selections(selections)
            total = len(chunks)
            for idx, chunk in enumerate(chunks, start=1):
                config_copy = dropdown_config.copy()
                config_copy["selections"] = chunk
                # If the dropdown exceeds 25 options, clarify pagination within the same category
                if total > 1 and "placeholder" in config_copy and isinstance(config_copy["placeholder"], str):
                    config_copy["placeholder"] = f"{config_copy['placeholder']} (page {idx}/{total})"
                all_chunks.append(config_copy)
        self._dropdowns_data = all_chunks
        self._clear_dropdown()

        if self.page_number < len(self._dropdowns_data):
            self._add_dropdown(**self._dropdowns_data[self.page_number])
        else:
            logger.warning(f"Page number {self.page_number} out of range for dropdowns_data")
        self._add_accept_cancel_buttons_if_needed()

    async def initiate_from_interaction(
        self,
        interaction: Interaction,
        content: str = "Make your selections:",
    ) -> tuple[dict[str, list[str]] | None, Message | None]:
        """Send initial message and wait for selections."""
        self._add_accept_cancel_buttons_if_needed()
        view = self
        await interaction.response.send_message(content, view=self, ephemeral=self._ephemeral)
        self._message = await interaction.original_response()
        self._collection.clear()
        data = await view.get_data()
        return data

    async def initiate_from_message(
        self,
        message: Message,
        content: str = "Make your selections:",
    ) -> tuple[dict[str, list[str]] | None, Message | None]:
        """Update existing message and wait for selections."""
        self._add_accept_cancel_buttons_if_needed()
        view = self
        self._message = await message.edit(content=content, view=view)
        self._ephemeral = message.flags.ephemeral
        self._collection.clear()
        data = await view.get_data()
        return data

    async def on_timeout(self) -> None:
        if self._completed:
            return

        self._timed_out = True
        if not self._message:
            return

        with suppress(NotFound):
            await self._message.edit(content="Selection timed out", view=None)

    def chunk_selections(self, selections: list[dict[str, Any]], chunk_size: int = 25) -> list[list[dict[str, Any]]]:
        """Split selections into chunks of up to chunk_size each."""
        return [selections[i : i + chunk_size] for i in range(0, len(selections), chunk_size)]

    def _add_dropdown(
        self,
        selections: list[dict[str, Any]],
        **options,
    ) -> DynamicDropdown:
        # Get the custom_id from options to check for existing selections
        custom_id = options.get("custom_id", "")
        existing_selections = self._collection.get(custom_id, [])

        # Calculate current global selections to determine max_values for this dropdown
        runningtotal = sum(len(majors) for majors in self._collection.values())
        global_limit = 2

        # Calculate how many more majors can be selected globally
        remaining_global_slots = global_limit - runningtotal

        # Get the original max_values from options, defaulting to 2
        original_max_values = options.get("max_values", 2)

        if remaining_global_slots <= 0 and not existing_selections:
            # If no slots remaining and this dropdown has no existing selections, disable it
            options["disabled"] = True
            options["placeholder"] = options.get("placeholder", "Select majors") + " (2 majors already selected)"
            # Keep max_values at 1 when disabled (Discord requirement)
            options["max_values"] = 1
        else:
            # Adjust max_values to respect global limit
            # Allow existing selections plus any remaining global slots
            available_slots = len(existing_selections) + remaining_global_slots
            options["max_values"] = min(original_max_values, max(1, available_slots))

            if remaining_global_slots < original_max_values and remaining_global_slots > 0:
                # Update placeholder to show limited selection availability
                options["placeholder"] = (
                    options.get("placeholder", "Select majors") + f" (max {remaining_global_slots} more)"
                )

        # Pass existing selections as default values
        dropdown = DynamicDropdown(selections, default_values=existing_selections, **options)

        # Code to update the max value according to the running total: doesn't work because
        # dropdowns cannot have a max value of 0, which breaks the command.
        # runningtotal=0
        # for dropdown1 in self._collection.keys():
        #        for major in self._collection[dropdown1]:
        #            runningtotal+=1
        # dropdown.max_values=dropdown.maxvalues-runningtotal
        self._dropdowns.append(dropdown)
        self.add_item(dropdown)
        return dropdown

    def _clear_dropdown(
        self,
    ) -> None:
        for dropdown in self._dropdowns:
            self.remove_item(dropdown)
        self._dropdowns.clear()

    def _add_accept_cancel_buttons_if_needed(self) -> None:
        """Adds accept and cancel buttons to the view."""
        if self._has_buttons:
            logger.warning("Buttons already added to view")
            return

        if not self._add_buttons and (not self._auto_buttons or len(self._dropdowns) == 1):
            return

        if self.page_number > 0:
            self.add_item(LeftButton())
        self.add_item(AcceptButton())
        self.add_item(CancelButton())
        if self.page_number < len(self._dropdowns_data) - 1:
            self.add_item(RightButton())

        self._has_buttons = True

    def _set_data(self) -> tuple[dict[str, list[str]] | None, Message | None]:
        """Finalize and set the selection data into the future.

        Returns a tuple of (selections or None, message).
        """
        if self.data_future.done():
            # Future already resolved; try to return its result
            try:
                return self.data_future.result()
            except Exception:
                return (None, self._message)

        if not self._completed:
            logger.debug("Finalizing user selections")
            self._completed = True

        selections: dict[str, list[str]] = self._collection

        logger.debug(
            f"Collection complete. Accepted: {self.accepted}, Timed out: {self._timed_out}, Selections: {selections}"
        )

        # Optionally log message state; avoid editing here to keep method side-effect light
        if self._message:
            try:
                if self.accepted:
                    logger.debug("Selections accepted")
                elif self._timed_out:
                    logger.debug("Selection timed out")
                else:
                    logger.debug("Selection cancelled")
            except NotFound:
                logger.warning("Message not found when trying to update status")

        result: tuple[dict[str, list[str]] | None, Message | None]
        result = ((selections if self.accepted else None), self._message)

        if not self.data_future.done():
            self.data_future.set_result(result)
        self.stop()
        return result

    async def get_data(self) -> tuple[dict[str, list[str]] | None, Message | None]:
        # Wait for data to be set (e.g. via button interaction)
        return await self.data_future

    async def turn_page(self, number):
        self.page_number += number
        self.clear_items()
        self._has_buttons = False
        self._add_dropdown(**self._dropdowns_data[self.page_number])
        self._add_accept_cancel_buttons_if_needed()
