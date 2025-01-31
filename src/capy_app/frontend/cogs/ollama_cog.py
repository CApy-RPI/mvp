# cogs.ollama.py

import logging
from discord.ext import commands
import ollama
from ollama import AsyncClient


class OllamaCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        ollama.pull("deepseek-r1:14b")
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )

    @commands.command(name="prompt", help="Talk with a bot.")
    async def prompt(self, ctx, n: int, *, message: str):
        messages = []
        async for msg in ctx.channel.history(limit=n):
            messages.append(msg)
        context = (
            "\n".join([msg.content for msg in reversed(messages)]) + f"\n{message}"
        )
        thinking_msg = await ctx.send("thinking...")
        client = AsyncClient()
        buffer = ""
        skip = False
        async for part in await client.chat(
            model="deepseek-r1:14b",
            messages=[{"role": "user", "content": context}],
            stream=True,
        ):
            content = part["message"]["content"]
            if "<think>" in content:
                skip = True
                continue
            if "</think>" in content:
                skip = False
                continue
            if skip:
                continue

            buffer += content
            if buffer.strip() == "":
                buffer = ""
                continue
            if "\n\n" in buffer:
                self.logger.info(buffer)
                await thinking_msg.delete()
                await ctx.send(f"{buffer}\n\n")
                buffer = ""

    @commands.command(name="delete", help="Delete the last chatbot message.")
    async def delete_last_message(self, ctx):
        async for message in ctx.channel.history(limit=100):
            if message.author == self.bot.user:
                await message.delete()
            if message.content.startswith("!prompt"):
                await message.delete()
                break
        await ctx.message.delete()


async def setup(bot: commands.Bot):
    await bot.add_cog(OllamaCog(bot))
