import discord


def is_guild():
    """A decorator to ensure the command is only used in a guild."""

    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.guild is not None

    return discord.app_commands.check(predicate)
