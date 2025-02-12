"""Test cog for dropdown base functionality."""

from discord.ext import commands
from discord import app_commands, Interaction, Object
from frontend.interactions.bases.dropdown_base import DynamicDropdownView

from config import settings


class DropdownTestCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="test_dropdown")
    async def test_dropdown(self, interaction: Interaction):
        """Test the dropdown base functionality with a single dropdown"""
        view = DynamicDropdownView(ephemeral=False)
        
        view.add_dropdown(
            placeholder="Make your selection",
            max_values=1,
            disable_on_select=True,
            custom_id="simple_select",
            row=0,
            fields=[
                {
                    "label": "Option A",
                    "value": "a",
                    "description": "First choice",
                    "emoji": "🅰️"
                },
                {
                    "label": "Option B",
                    "value": "b", 
                    "description": "Second choice",
                    "emoji": "🅱️"
                },
                {
                    "label": "Option C",
                    "value": "c",
                    "description": "Third choice",
                    "emoji": "©️"
                },
            ]
        )

        selections, message = await view.initiate_from_interaction(
            interaction, "Test a simple dropdown selection with emojis:"
        )

        if selections and message:
            await message.edit(
                content=f"Selected value: {selections}",
                view=None,
            )

    @app_commands.guilds(Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="test_dropdown_with_buttons")
    async def test_dropdown_with_buttons(self, interaction: Interaction):
        """Test the dropdown base with accept/cancel buttons"""
        view = DynamicDropdownView(ephemeral=False, add_buttons=True)

        view.add_dropdown(
            placeholder="Choose a fruit",
            custom_id="fruits",
            row=0,
            fields=[
                {"label": "Apple", "value": "apple", "emoji": "🍎"},
                {"label": "Banana", "value": "banana", "emoji": "🍌"},
                {"label": "Orange", "value": "orange", "emoji": "🍊"},
            ]
        )
        view.add_dropdown(
            placeholder="Choose an animal",
            custom_id="animals",
            row=1,
            fields=[
                {"label": "Dog", "value": "dog", "emoji": "🐕"},
                {"label": "Cat", "value": "cat", "emoji": "🐈"},
                {"label": "Bird", "value": "bird", "emoji": "🐦"},
            ]
        )
        view.add_dropdown(
            placeholder="Choose weather",
            custom_id="weather",
            row=2,
            fields=[
                {"label": "Sunny", "value": "sun", "emoji": "☀️"},
                {"label": "Rainy", "value": "rain", "emoji": "🌧️"},
                {"label": "Cloudy", "value": "cloud", "emoji": "☁️"},
            ]
        )

        selections, message = await view.initiate_from_interaction(
            interaction, "Select from each category:"
        )

        if message:
            content = (
                f"Selected values: {selections}"
                if selections
                else "Selection cancelled."
            )
            await message.edit(content=content, view=None)

    @app_commands.guilds(Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="test_dropdown_sequential")
    async def test_sequential_dropdowns(self, interaction: Interaction):
        """Test sequential dropdowns where each appears after the previous is selected"""
        # First dropdown - Color family
        view1 = DynamicDropdownView(ephemeral=False)
        view1.add_dropdown(
            fields=[
                {
                    "label": "Warm Colors",
                    "value": "warm",
                    "description": "Red, Orange, Yellow family",
                    "emoji": "🔥"
                },
                {
                    "label": "Cool Colors",
                    "value": "cool",
                    "description": "Blue, Green, Purple family",
                    "emoji": "❄️"
                },
                {
                    "label": "Neutral Colors",
                    "value": "neutral",
                    "description": "Black, White, Gray family",
                    "emoji": "⚪"
                },
            ],
            placeholder="Select color family",
            custom_id="color_family",
            max_values=1,
            row=0,
        )
        primary_selection, message = await view1.initiate_from_interaction(
            interaction, "Step 1: Choose a color family:"
        )
        if not primary_selection or not message:
            return

        # Second dropdown - Specific colors
        view2 = DynamicDropdownView(ephemeral=False)
        
        color_options = {
            "warm": [
                {"label": "Red", "value": "red", "emoji": "🔴"},
                {"label": "Orange", "value": "orange", "emoji": "🟠"},
                {"label": "Yellow", "value": "yellow", "emoji": "🟡"},
            ],
            "cool": [
                {"label": "Blue", "value": "blue", "emoji": "🔵"},
                {"label": "Green", "value": "green", "emoji": "🟢"},
                {"label": "Purple", "value": "purple", "emoji": "🟣"},
            ],
            "neutral": [
                {"label": "Black", "value": "black", "emoji": "⚫"},
                {"label": "White", "value": "white", "emoji": "⚪"},
                {"label": "Gray", "value": "gray", "emoji": "⭕"},
            ]
        }

        selected_family = primary_selection["color_family"][0]
        view2.add_dropdown(
            fields=color_options[selected_family],
            placeholder="Select specific colors",
            custom_id="specific_colors",
            min_values=1,
            max_values=2,
            row=0,
        )
        
        secondary_selection, message = await view2.initiate_from_message(
            message, f"Step 2: Choose 1-2 colors from the {selected_family} family:"
        )
        if not secondary_selection or not message:
            return

        # Final step - Additional options
        view3 = DynamicDropdownView(ephemeral=False, add_buttons=True)

        # Finish types dropdown
        view3.add_dropdown(
            fields=[
                {"label": "Matte", "value": "matte", "description": "Matte finish", "emoji": "🎨"},
                {"label": "Gloss", "value": "gloss", "description": "Glossy finish", "emoji": "✨"},
                {"label": "Metallic", "value": "metallic", "description": "Metallic finish", "emoji": "🌟"},
            ],
            placeholder="Select 1-2 finishes",
            custom_id="finishes",
            min_values=1,
            max_values=2,
            row=0,
        )

        # Application method dropdown
        view3.add_dropdown(
            fields=[
                {"label": "Brush", "value": "brush", "description": "Apply with brush", "emoji": "🖌️"},
                {"label": "Spray", "value": "spray", "description": "Apply with spray", "emoji": "💨"},
                {"label": "Roll", "value": "roll", "description": "Apply with roller", "emoji": "🎢"},
            ],
            placeholder="Select application method",
            custom_id="application",
            min_values=1,
            max_values=1,
            row=1,
        )

        application_selections, message = await view3.initiate_from_message(
            message,
            "Step 3: Choose your application preferences:\n"
            "• Select 1-2 finish types\n"
            "• Choose an application method",
        )
        if not application_selections or not message:
            return

        combined_results = {
            "color_family": primary_selection.get("color_family", []),
            "specific_colors": secondary_selection.get("specific_colors", []),
            "finish_types": application_selections.get("finishes", []),
            "application_method": application_selections.get("application", []),
        }

        await message.edit(
            content=(
                "Your paint configuration:\n"
                f"Color Family: {combined_results['color_family']}\n"
                f"Specific Colors: {combined_results['specific_colors']}\n"
                f"Finish Types: {combined_results['finish_types']}\n"
                f"Application Method: {combined_results['application_method']}"
            ),
            view=None,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(DropdownTestCog(bot))
