import discord


def is_owner():
    def predicate(interaction: discord.Interaction):
        if not interaction.guild:
            return False

        if interaction.user.id == interaction.guild.owner_id:
            return True

    return discord.app_commands.check(predicate)
