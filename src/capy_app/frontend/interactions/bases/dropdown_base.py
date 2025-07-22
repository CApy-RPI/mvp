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
from typing import Any, cast

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
        old_view: DynamicDropdownView = cast(DynamicDropdownView, self.view)
        next_page = old_view.page_number + 1

        if next_page >= len(old_view._dropdowns_data):
            logger.debug("Already on last page")
            return await interaction.response.defer()

        new_view = DynamicDropdownView(
            dropdowns=old_view._dropdowns_data,
            page_number=next_page,
            ephemeral=old_view._ephemeral,
            auto_buttons=old_view._auto_buttons,
            add_buttons=old_view._add_buttons,
            collection=old_view._collection,
        )
        new_view._message = old_view._message  # Maintain message reference
        new_view.data_future = old_view.data_future
        await interaction.response.edit_message(view=new_view)


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

        old_view: DynamicDropdownView = cast(DynamicDropdownView, self.view)
        prev_page = old_view.page_number - 1

        if prev_page < 0:
            logger.debug("Already on first page")
            return await interaction.response.defer()

        new_view = DynamicDropdownView(
            dropdowns=old_view._dropdowns_data,
            page_number=prev_page,
            ephemeral=old_view._ephemeral,
            auto_buttons=old_view._auto_buttons,
            add_buttons=old_view._add_buttons,
            collection=old_view._collection,
        )
        new_view._message = old_view._message  # Maintain message reference
        new_view.data_future = old_view.data_future
        await interaction.response.edit_message(view=new_view)


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
        self.selected_values = self.values
        print("type of _collection:", type(self.view._collection))
        print("value of _collection:", self.view._collection)
        runningtotal = 0
        for dropdown in self.view._collection.keys():
            for major in self.view._collection[dropdown]:
                runningtotal += 1
        if runningtotal + len(self.selected_values) <= self.max_values:
            self.view._collection[self.custom_id] = self.selected_values
        else:
            logger.debug(f"Current collection: {runningtotal}")
        logger.debug(
            f"Dropdown {self.custom_id} selected values: {self.selected_values}"
            f"Current collection: {self.view._collection}"
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
        dropdowns: list[dict[str, Any]] | None = None,
        page_number: int = 0,
        ephemeral: bool = True,
        auto_buttons: bool = True,
        add_buttons: bool = False,
        collection: tuple[dict[str, list[str]]] = {},
        **options,
    ) -> None:
        """Initialize the multi-selector view.

        Args:
            timeout: Time in seconds before the view times out
            auto_buttons: Whether to automatically add accept/cancel buttons for multiple dropdowns
        """
        super().__init__(**options)
        self.accepted: bool = False
        self.data_future = asyncio.get_event_loop().create_future()
        self.page_number = page_number
        self._dropdowns_data = dropdowns or []
        self._dropdowns: list[DynamicDropdown] = []
        self._completed: bool = False
        self._collection: tuple[dict[str, list[str]]] = {}
        self._timed_out: bool = False
        self._has_buttons: bool = False
        self._message: Message | None = None
        self._ephemeral: bool = ephemeral
        self._auto_buttons = auto_buttons
        self._add_buttons = add_buttons
        self._collection = collection
        dropdowns = dropdowns or []
        if (
            len(dropdowns) > self.MAX_DROPDOWNS
            or len(dropdowns) > self.MAX_DROPDOWNS - 1
            and (self._auto_buttons or self._add_buttons)
        ):
            raise ValueError(f"Number of dropdowns exceeds Discord limit of {self.MAX_DROPDOWNS}. ")

        # for dropdown in dropdowns:
        #   self._add_dropdown(**dropdown)
        self._clear_dropdown()
        self._add_dropdown(**dropdowns[self.page_number])
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

        try:
            await self._message.edit(content="Selection timed out", view=None)
        except NotFound:
            pass

    def _add_dropdown(
        self,
        selections: list[dict[str, Any]],
        **options,
    ) -> DynamicDropdown:
        dropdown = DynamicDropdown(selections=selections, **options)
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
        **options,
    ) -> DynamicDropdown:
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
        """Wait for user input and return selected values.

        Returns:
            Tuple containing:
            - Dictionary of selections if accepted, None if cancelled
            - Reference to the message object
        """
        if not self.data_future.done():
            if not self._completed:
                logger.debug("Waiting for user selections")
                # await self.wait()
                self._completed = True

            selections = {
                dropdown.custom_id: dropdown.selected_values
                for dropdown in self._dropdowns
                if dropdown.selected_values
            }
            selections = self._collection
            # Dict[str, List[str]]=dropdown id : dropdown selections,
            # for each dropdown in the list of dropdown, if the dropdown has any selected values.

            logger.debug(
                f"Collection complete. Accepted: {self.accepted}, Selections: {selections}"
            )

            # Update message based on result
            if self._message:
                try:
                    if self.accepted:
                        logger.debug("Selections accepted")
                        # await self._message.edit(content="Selections accepted", view=None)
                    elif self._timed_out:
                        logger.debug("Selection timed out")
                        # await self._message.edit(content="Selection timed out", view=None)
                    else:
                        logger.debug("Selection cancelled")
                        # await self._message.edit(content="Selection cancelled", view=None)
                except NotFound:
                    logger.warning("Message not found when trying to update status")
            if self.accepted and not self.data_future.done():
                self.data_future.set_result((selections, self._message))
            self.stop()

    async def get_data(self):
        # Wait for data to be set (e.g. via button interaction)
        return await self.data_future
