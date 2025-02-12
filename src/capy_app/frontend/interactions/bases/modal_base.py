"""Base classes for creating dynamic modal dialogs in Discord interactions.

This module provides a flexible framework for creating modal dialogs with
dynamic text input fields. It supports:
- Dynamic text input field creation
- Input validation
- Message lifecycle management
- Both interaction and message-based initialization
"""

from typing import Dict, Optional, List, Any, TypeVar
import logging
from discord import Interaction, Message, ButtonStyle
from discord.ui import Modal, Button, View
from discord.ui.text_input import TextInput
from discord.errors import NotFound

from config import settings


# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

V = TypeVar("V", bound="View")


class DynamicField(TextInput[V]):
    def __init__(
        self,
        **options,
    ) -> None:
        super().__init__(**options)
        self.custom_id = self.label.lower().replace(" ", "_")


class DynamicModal(Modal):
    """A modal dialog with dynamic text input fields."""

    def __init__(
        self,
        fields: Optional[List[Dict[str, Any]]] = [],
        **options,
    ) -> None:
        """Initialize the modal dialog."""
        super().__init__(**options)
        self.values: Dict[str, str] = {}
        self.success: bool = False

        self._fields: List[DynamicField[View]] = []
        self._interaction: Optional[Interaction] = None

        for field in fields:
            self._add_field(**field)

    def _add_field(self, **options) -> DynamicField[View]:
        field: DynamicField[View] = DynamicField(**options)
        self._fields.append(field)
        self.add_item(field)
        return field

    async def on_submit(self, interaction: Interaction) -> None:
        """Handle modal submission.

        Args:
            interaction: Discord interaction from the submission
        """
        self._interaction = interaction
        self.values = {
            field.custom_id: field.value
            for field in self.children
            if isinstance(field, DynamicField)
        }
        self.success = True
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self) -> None:
        """Handle modal timeout."""
        self.success = False


class ModalTriggerButton(Button["DynamicModalView"]):
    """Button that triggers a modal when clicked."""

    def __init__(
        self,
        modal: DynamicModal,
        **options,
    ) -> None:
        super().__init__(**options)
        self._modal = modal

    async def callback(self, interaction: Interaction) -> None:
        """Show the modal when button is clicked."""
        await interaction.response.send_modal(self._modal)


class DynamicModalView(View):
    """Base view for handling modal dialogs."""

    def __init__(
        self,
        modal: Optional[List[Dict[str, Any]]] = [],
        ephemeral: bool = True,
        **options,
    ) -> None:
        super().__init__(**options)
        self._ephemeral = ephemeral
        self._modal: Optional[DynamicModal] = None
        self._message: Optional[Message] = None
        self._interaction: Optional[Interaction] = None
        self._completed: bool = False
        self._timed_out: bool = False

        self._add_modal(**modal)

    def _add_modal(
        self,
        **options,
    ) -> DynamicModal:
        """Add a modal to the view with optional fields."""
        if self._modal is not None:
            logger.error("Attempted to add second modal to view")
            raise ValueError("View already has a modal")

        modal = DynamicModal(**options)

        self._modal = modal
        logger.debug(f"Added modal '{self._modal.title}' to view")
        return modal

    async def _send_status_message(self, content: str) -> None:
        """Create initial status message after modal is sent."""
        if self._message:
            await self._message.edit(content=content, view=None)
        elif self._interaction:
            self._message = await self._interaction.followup.send(
                content=content,
                ephemeral=self._ephemeral,
                wait=True,  # Return message object
            )

    async def initiate_from_interaction(
        self,
        interaction: Interaction,
    ) -> tuple[Optional[Dict[str, str]], Optional[Message]]:
        """Show modal directly from interaction."""
        if self._modal is None:
            raise ValueError("No modal added to view")

        await interaction.response.send_modal(self._modal)
        self._interaction = interaction
        return await self._get_data()

    async def initiate_from_message(
        self,
        message: Message,
    ) -> tuple[Optional[Dict[str, str]], Optional[Message]]:
        """Show modal from existing message."""
        if self._modal is None:
            raise ValueError("No modal added to view")

        if self._modal.interaction is not None:
            await self._modal.interaction.response.send_modal(self._modal)
            self._message = message
            return await self._get_data()

        logger.error("Modal has no interaction to send modal from")
        return None, message

    async def _get_data(self) -> tuple[Optional[Dict[str, str]], Optional[Message]]:
        """Wait for user input and return form values and message.

        Returns:
            Tuple containing:
            - Dictionary of field values if submitted successfully, None if cancelled
            - Reference to the message object
        """
        if not self._completed and self._modal:
            logger.debug("Waiting for modal submission")
            await self._modal.wait()
            self._completed = True

        if self._modal and self._modal.success:
            logger.debug("Modal submitted successfully")
            await self._send_status_message("Form submitted successfully")
            return_values = self._modal.values, self._message
        else:
            status = (
                "Form input timed out"
                if self._timed_out
                else "Form submission cancelled"
            )
            logger.debug(status)
            await self._send_status_message(status)
            return_values = None, self._message

        self.stop()
        return return_values

    async def on_timeout(self) -> None:
        """Handle view timeout."""
        # Ignore if already completed
        if self._completed:
            return

        self._timed_out = True
        if not self._message:
            return

        try:
            logger.debug("View timed out, updating message")
            await self._send_status_message("Form input timed out")
        except NotFound:
            logger.warning("Message not found when handling timeout")


class ButtonDynamicModalView(DynamicModalView):
    """Modal view that shows a button to trigger the modal."""

    def __init__(
        self,
        message_prompt: Optional[str] = None,
        button_label: str = "Open Form",
        button_style: ButtonStyle = ButtonStyle.primary,
        **options,
    ) -> None:
        """Initialize the modal view with a trigger button.

        Args:
            message_prompt: Optional initial message to show with the button.
            button_label: Label for the button that triggers the modal.
            button_style: Style for the button that triggers the modal.
        """
        super().__init__(**options)
        self._message_prompt = message_prompt
        self._button_label = button_label
        self._button_style = button_style

    async def initiate_from_interaction(
        self,
        interaction: Interaction,
        prompt: Optional[str] = None,
    ) -> tuple[Optional[Dict[str, str]], Optional[Message]]:
        """Show button and modal from interaction."""
        if self._modal is None:
            raise ValueError("No modal added to view")

        self.add_item(
            ModalTriggerButton(
                modal=self._modal,
                label=self._button_label,
                style=self._button_style,
            )
        )

        content = (
            prompt
            or self._message_prompt
            or f"Click the button to open '{self._modal.title}'"
        )
        await interaction.response.send_message(
            content=content,
            view=self,
            ephemeral=self._ephemeral,
        )
        self._message = await interaction.original_response()
        return await self._get_data()

    async def initiate_from_message(
        self,
        message: Message,
        prompt: Optional[str] = None,
    ) -> tuple[Optional[Dict[str, str]], Optional[Message]]:
        """Update message with button and wait for modal submission."""
        if self._modal is None:
            raise ValueError("No modal added to view")

        self.add_item(
            ModalTriggerButton(
                modal=self._modal,
                label=self._button_label,
                style=self._button_style,
            )
        )

        content = (
            prompt
            or self._message_prompt
            or f"Click the button to open '{self._modal.title}'"
        )
        await message.edit(
            content=content,
            view=self,
        )
        self._message = message
        return await self._get_data()
