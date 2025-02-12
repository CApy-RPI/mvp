"""Test cog for dropdown base functionality."""

from discord.ext import commands
from discord import app_commands, Interaction, Object
from discord.errors import NotFound
from frontend.interactions.bases.dropdown_base import DynamicDropdownView

from config import settings


class DropdownTestCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="test_dropdown")
    async def test_dropdown(self, interaction: Interaction):
        """Test the dropdown base functionality with a single dropdown"""
        view = DynamicDropdownView()

        view.add_dropdown(
            options_dict={
                "Option A": {"value": "a", "description": "First choice"},
                "Option B": {"value": "b", "description": "Second choice"},
                "Option C": {"value": "c", "description": "Third choice"},
            },
            placeholder="Make your selection",
            max_values=1,
            disable_on_select=True,
            custom_id="simple_select",
            row=0,
        )

        selections, message = await view.initiate_from_interaction(
            interaction, "Test a simple dropdown selection:"
        )

        if selections and message:
            await message.edit(
                content=f"Selected value: {selections}",
                view=None,
                delete_after=10,
            )

    @app_commands.guilds(Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="test_dropdown_with_buttons")
    async def test_dropdown_with_buttons(self, interaction: Interaction):
        """Test the dropdown base with accept/cancel buttons"""
        view = DynamicDropdownView(timeout=180.0)

        # Add dropdowns in different rows
        view.add_dropdown(
            options_dict={"Option A": {"value": "a"}},
            placeholder="Row 0 select",
            custom_id="row0",
            row=0,
        )
        view.add_dropdown(
            options_dict={"Option B": {"value": "b"}},
            placeholder="Row 1 select",
            custom_id="row1",
            row=1,
        )
        view.add_dropdown(
            options_dict={"Option C": {"value": "c"}},
            placeholder="Row 2 select",
            custom_id="row2",
            row=2,
        )
        view.add_accept_cancel_buttons()

        selections, message = await view.initiate_from_interaction(
            interaction, "Make your selections and click accept when done:"
        )

        if message:
            content = (
                f"Selected values: {selections}"
                if selections
                else "Selection cancelled."
            )
            await message.edit(content=content, view=None, delete_after=10)

    @app_commands.guilds(Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="test_dropdown_sequential")
    async def test_sequential_dropdowns(self, interaction: Interaction):
        """Test sequential dropdowns where each appears after the previous is selected"""
        # First dropdown - single select
        view1 = DynamicDropdownView(timeout=180.0)
        view1.add_dropdown(
            options_dict={
                "Red": {"value": "red", "description": "Primary red"},
                "Blue": {"value": "blue", "description": "Primary blue"},
                "Green": {"value": "green", "description": "Primary green"},
            },
            placeholder="Select ONE primary color",
            custom_id="primary_color",
            max_values=1,
            row=0,
        )
        primary_selection, message = await view1.initiate_from_interaction(
            interaction, "Step 1: Choose exactly one primary color:"
        )
        if not primary_selection or not message:
            return

        # Second dropdown - multi select (1-2)
        view2 = DynamicDropdownView(timeout=180.0)
        view2.add_dropdown(
            options_dict={
                "Yellow": {"value": "yellow", "description": "Mix with yellow"},
                "Purple": {"value": "purple", "description": "Mix with purple"},
                "Orange": {"value": "orange", "description": "Mix with orange"},
                "White": {"value": "white", "description": "Mix with white"},
            },
            placeholder="Select 1-2 secondary colors",
            custom_id="secondary_colors",
            min_values=1,
            max_values=2,
            row=0,
        )
        secondary_selection, message = await view2.initiate_from_message(
            message, "Step 2: Choose one or two secondary colors to mix:"
        )
        if not secondary_selection or not message:
            return

        # Third step - multiple concurrent dropdowns
        view3 = DynamicDropdownView(timeout=180.0)

        # Finish types dropdown
        view3.add_dropdown(
            options_dict={
                "Matte": {"value": "matte", "description": "Matte finish"},
                "Gloss": {"value": "gloss", "description": "Glossy finish"},
                "Metallic": {"value": "metallic", "description": "Metallic finish"},
            },
            placeholder="Select 1-2 finishes",
            custom_id="finishes",
            min_values=1,
            max_values=2,
            row=0,
        )

        # Application method dropdown
        view3.add_dropdown(
            options_dict={
                "Brush": {"value": "brush", "description": "Apply with brush"},
                "Spray": {"value": "spray", "description": "Apply with spray"},
                "Roll": {"value": "roll", "description": "Apply with roller"},
            },
            placeholder="Select application method",
            custom_id="application",
            min_values=1,
            max_values=1,
            row=1,
        )

        # Coating layers dropdown
        view3.add_dropdown(
            options_dict={
                "Single": {"value": "1", "description": "One coat"},
                "Double": {"value": "2", "description": "Two coats"},
                "Triple": {"value": "3", "description": "Three coats"},
            },
            placeholder="Select number of coats",
            custom_id="coats",
            min_values=1,
            max_values=1,
            row=2,
        )

        application_selections, message = await view3.initiate_from_message(
            message,
            "Step 3: Choose your application preferences:\n"
            "• Select 1-2 finish types\n"
            "• Choose an application method\n"
            "• Specify number of coats",
        )
        if not application_selections or not message:
            return

        combined_results = {
            "primary": primary_selection.get("primary_color", []),
            "secondary": secondary_selection.get("secondary_colors", []),
            "finish_types": application_selections.get("finishes", []),
            "application_method": application_selections.get("application", []),
            "coating_layers": application_selections.get("coats", []),
        }

        await message.edit(
            content=(
                "Your paint configuration:\n"
                f"Primary Color: {combined_results['primary']}\n"
                f"Secondary Colors: {combined_results['secondary']}\n"
                f"Finish Types: {combined_results['finish_types']}\n"
                f"Application Method: {combined_results['application_method']}\n"
                f"Number of Coats: {combined_results['coating_layers']}"
            ),
            view=None,
            delete_after=15,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(DropdownTestCog(bot))
