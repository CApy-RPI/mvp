from discord.ext import commands
from discord import app_commands, Interaction, Object, TextStyle, ButtonStyle
from discord.errors import NotFound
from frontend.interactions.bases.modal_base import DynamicModalView

from config import settings


class ModalTestCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="test_modal_direct")
    async def test_modal_direct(self, interaction: Interaction):
        """Test modal without button"""
        view = DynamicModalView(button_enable=False, ephemeral=False)
        view.add_modal(
            title="Direct Modal",
            fields=[
                {
                    "label": "Input",
                    "placeholder": "Enter something",
                },
            ],
        )

        await view.initiate_from_interaction(interaction)
        values, message = await view.get_data()
        if values and message:
            await message.edit(
                content=f"Submitted values:\n"
                + "\n".join(f"{k}: {v}" for k, v in values.items())
            )

    @app_commands.guilds(Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="test_modal_button")
    async def test_modal_button(self, interaction: Interaction):
        """Test modal with custom button"""
        view = DynamicModalView(
            button_enable=True,
            button_label="Open Survey",
            button_style=ButtonStyle.success,
            ephemeral=False,
        )

        view.add_modal(
            title="Feedback Form",
            fields=[
                {
                    "label": "Rating",
                    "placeholder": "1-5",
                    "max_length": 1,
                },
                {
                    "label": "Comments",
                    "placeholder": "Your feedback",
                    "style": TextStyle.paragraph,
                    "required": False,
                },
            ],
        )

        await view.initiate_from_interaction(interaction)
        values, message = await view.get_data()
        if values and message:
            await message.edit(
                content=f"Survey results:\n"
                + "\n".join(f"{k}: {v}" for k, v in values.items())
            )

    @app_commands.guilds(Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="test_modal_sequential")
    async def test_modal_sequential(self, interaction: Interaction):
        """Test sequential modals using message passing"""
        # First modal view
        view1 = DynamicModalView(button_enable=True, ephemeral=False)
        view1.add_modal(
            title="Personal Info",
            fields=[
                {"label": "Name", "placeholder": "Your name"},
                {"label": "Age", "placeholder": "Your age", "max_length": 3},
            ],
        )

        message = await view1.initiate_from_interaction(interaction)
        personal_info, message = await view1.get_data()
        if not personal_info or not message:
            return

        # Second modal view using same message
        view2 = DynamicModalView(
            button_enable=True,
            button_label="Add Contact Info",
            ephemeral=False,
        )
        view2.add_modal(
            title="Contact Info",
            fields=[
                {"label": "Email", "placeholder": "your@email.com"},
                {
                    "label": "Phone",
                    "placeholder": "Optional",
                    "required": False,
                },
            ],
        )

        # Use previous message for next modal
        await view2.initiate_from_message(message)
        contact_info, message = await view2.get_data()
        if not contact_info or not message:
            return

        # Display combined results
        combined = {
            "Personal": personal_info,
            "Contact": contact_info,
        }
        formatted = "\n".join(
            f"{section}:\n" + "\n".join(f"  {k}: {v}" for k, v in info.items())
            for section, info in combined.items()
        )
        await message.edit(content=f"Profile completed:\n{formatted}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ModalTestCog(bot))
