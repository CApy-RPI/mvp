import discord
from discord import TextStyle


class RequestModal(discord.ui.Modal, title="Ticket"):
    def __init__(
        self, modal_title: str, message: str = "Describe your request here..."
    ):
        if not isinstance(modal_title, str) or not modal_title:
            raise ValueError("Modal title must be a non-empty string")
        super().__init__(title=modal_title)

        self.title_input = discord.ui.TextInput(
            label="Title",
            style=TextStyle.short,
            placeholder="Enter a title for your request",
            required=True,
            max_length=100,
        )

        self.description_input = discord.ui.TextInput(
            label="Description",
            style=TextStyle.long,
            placeholder=message,
            required=True,
            max_length=1000,
        )

        self.add_item(self.title_input)
        self.add_item(self.description_input)

        self.title = None
        self.description = None

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.title = self.title_input.value
        self.description = self.description_input.value
