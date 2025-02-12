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
from discord import Interaction, TextStyle, Message, ButtonStyle
from discord.ui import Modal, Button, View
from discord.ui.text_input import TextInput as TextInput
from discord.errors import NotFound

from config import settings


# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

V = TypeVar("V", bound=View)


class DynamicTextInput(TextInput[V]):
    """A text input field with customizable validation."""

    def __init__(
        self,
        label: str,
        placeholder: str = "",
        default: str = "",
        min_length: int = 1,
        max_length: int = 4000,
        required: bool = True,
        style: TextStyle = TextStyle.short,
        custom_id: str = "",
    ) -> None:
        """Initialize the text input field.

        Args:
            label: Label shown above the input field
            placeholder: Text shown when field is empty
            default: Default value for the field
            min_length: Minimum input length
            max_length: Maximum input length
            required: Whether the field is required
            style: TextStyle.short or TextStyle.paragraph
            custom_id: Unique identifier for the field
        """
        super().__init__(
            label=label,
            placeholder=placeholder,
            default=default,
            min_length=min_length,
            max_length=max_length,
            required=required,
            style=style,
            custom_id=custom_id or label.lower().replace(" ", "_"),
        )


class DynamicModal(Modal):
    """A modal dialog with dynamic text input fields."""

    def __init__(
        self,
        title: str,
        timeout: float = 180.0,
    ) -> None:
        """Initialize the modal dialog."""
        super().__init__(title=title, timeout=timeout)
        self.fields: List[DynamicTextInput[View]] = []
        self.values: Dict[str, str] = {}
        self.success: bool = False
        self.interaction: Optional[Interaction] = None

    def add_field(
        self,
        label: str,
        placeholder: str = "",
        default: str = "",
        min_length: int = 1,
        max_length: int = 4000,
        required: bool = True,
        style: TextStyle = TextStyle.short,
        custom_id: str = "",
    ) -> DynamicTextInput[View]:
        """Add a text input field to the modal.

        Args:
            label: Label shown above the input field
            placeholder: Text shown when field is empty
            default: Default value for the field
            min_length: Minimum input length
            max_length: Maximum input length
            required: Whether the field is required
            style: TextStyle.short or TextStyle.paragraph
            custom_id: Unique identifier for the field

        Returns:
            The created text input field
        """
        field: DynamicTextInput[View] = DynamicTextInput(
            label=label,
            placeholder=placeholder,
            default=default,
            min_length=min_length,
            max_length=max_length,
            required=required,
            style=style,
            custom_id=custom_id,
        )
        self.fields.append(field)
        self.add_item(field)
        return field

    async def on_submit(self, interaction: Interaction) -> None:
        """Handle modal submission.

        Args:
            interaction: Discord interaction from the submission
        """
        self.interaction = interaction
        self.values = {
            field.custom_id: field.value
            for field in self.children
            if isinstance(field, TextInput)
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
        label: str = "Open Modal",
        style: ButtonStyle = ButtonStyle.primary,
        custom_id: str = "modal_trigger",
        row: int = 0,
    ) -> None:
        super().__init__(
            style=style,
            label=label,
            custom_id=custom_id,
            row=row,
        )
        self.modal = modal

    async def callback(self, interaction: Interaction) -> None:
        """Show the modal when button is clicked."""
        await interaction.response.send_modal(self.modal)


class DynamicModalView(View):
    """Base view for handling modal dialogs."""

    def __init__(
        self,
        timeout: float = 180.0,
        ephemeral: bool = True,
    ) -> None:
        super().__init__(timeout=timeout)
        self.ephemeral = ephemeral
        self.modal: Optional[DynamicModal] = None
        self.message: Optional[Message] = None
        self.interaction: Optional[Interaction] = None
        self._completed: bool = False
        self.timeout: bool = False

    def add_modal(
        self,
        title: str,
        fields: Optional[List[Dict[str, Any]]] = None,
        timeout: float = 180.0,
    ) -> DynamicModal:
        """Add a modal to the view with optional fields."""
        if self.modal is not None:
            logger.error("Attempted to add second modal to view")
            raise ValueError("View already has a modal")

        modal = DynamicModal(title=title, timeout=timeout)
        if fields:
            for field_config in fields:
                modal.add_field(**field_config)

        self.modal = modal
        logger.debug(f"Added modal '{title}' to view")
        return modal

    async def _send_status_message(self, content: str) -> None:
        """Create initial status message after modal is sent."""
        if self.message:
            await self.message.edit(content=content, view=None)
        elif self.interaction:
            await self.interaction.followup.send(
                content=content,
                ephemeral=self.ephemeral,
            )
            self.message = await self.interaction.original_response()

    async def initiate_from_interaction(
        self,
        interaction: Interaction,
    ) -> tuple[Optional[Dict[str, str]], Optional[Message]]:
        """Show modal directly from interaction."""
        if self.modal is None:
            raise ValueError("No modal added to view")

        await interaction.response.send_modal(self.modal)
        self.interaction = interaction
        return await self._get_data()

    async def initiate_from_message(
        self,
        message: Message,
    ) -> tuple[Optional[Dict[str, str]], Optional[Message]]:
        """Show modal from existing message."""
        if self.modal is None:
            raise ValueError("No modal added to view")

        if self.modal.interaction is not None:
            await self.modal.interaction.response.send_modal(self.modal)
            self.message = message
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
        if not self._completed and self.modal:
            logger.debug("Waiting for modal submission")
            await self.modal.wait()
            self._completed = True

        if self.modal and self.modal.success:
            logger.debug("Modal submitted successfully")
            await self._send_status_message("Form submitted successfully")
            return self.modal.values, self.message
        else:
            status = (
                "Form input timed out" if self.timeout else "Form submission cancelled"
            )
            logger.debug(status)
            await self._send_status_message(status)
            return None, self.message

    async def on_timeout(self) -> None:
        """Handle view timeout."""
        self.timeout = True
        if not self.message:
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
        timeout: float = 180.0,
        message_prompt: Optional[str] = None,
        button_label: str = "Open Form",
        button_style: ButtonStyle = ButtonStyle.primary,
        ephemeral: bool = True,
    ) -> None:
        super().__init__(timeout=timeout, ephemeral=ephemeral)
        self.message_prompt = message_prompt
        self.button_label = button_label
        self.button_style = button_style

    async def initiate_from_interaction(
        self,
        interaction: Interaction,
        prompt: Optional[str] = None,
    ) -> tuple[Optional[Dict[str, str]], Optional[Message]]:
        """Show button and modal from interaction."""
        if self.modal is None:
            raise ValueError("No modal added to view")

        self.add_item(
            ModalTriggerButton(
                modal=self.modal,
                label=self.button_label,
                style=self.button_style,
            )
        )

        content = (
            prompt
            or self.message_prompt
            or f"Click the button to open '{self.modal.title}'"
        )
        await interaction.response.send_message(
            content=content,
            view=self,
            ephemeral=self.ephemeral,
        )
        self.message = await interaction.original_response()
        return await self._get_data()

    async def initiate_from_message(
        self,
        message: Message,
        prompt: Optional[str] = None,
    ) -> tuple[Optional[Dict[str, str]], Optional[Message]]:
        """Update message with button and wait for modal submission."""
        if self.modal is None:
            raise ValueError("No modal added to view")

        self.add_item(
            ModalTriggerButton(
                modal=self.modal,
                label=self.button_label,
                style=self.button_style,
            )
        )

        content = (
            prompt
            or self.message_prompt
            or f"Click the button to open '{self.modal.title}'"
        )
        await message.edit(
            content=content,
            view=self,
        )
        self.message = message
        return await self._get_data()
