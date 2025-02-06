"""Discord cog for handling Ollama LLM interactions."""

import discord
from discord.ext import commands
import logging
import ollama
import typing

from config import settings


class OllamaCog(commands.Cog):
    """Cog for handling Ollama LLM interactions with Discord."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the cog with model and conversation tracking.

        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )
        
        ollama.pull(settings.MODEL_NAME)
        self.user_conversations: typing.Dict[
            int, typing.List[typing.Dict[str, str]]
        ] = {}
        self.channel_conversations: typing.Dict[
            int, typing.List[typing.Dict[str, str]]
        ] = {}

    def chunk_message(self, text: str) -> typing.List[str]:
        """Split message into chunks, respecting think tags and message limits.

        Args:
            text: The message to chunk

        Returns:
            List of message chunks
        """
        chunks = []
        current_chunk = ""

        for line in text.split("\n"):
            # Handle think tags
            if "<think>" in line or "</think>" in line:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                chunks.append(line)
                current_chunk = ""
                continue

            # Handle length limits
            if len(current_chunk) + len(line) + 1 > settings.MESSAGE_LIMIT:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return [c for c in chunks if c]  # Remove empty chunks

    async def delete_think_block_messages(
        self, ctx: commands.Context[typing.Any], messages: typing.List[discord.Message]
    ) -> None:
        """Delete messages between think tags.

        Args:
            ctx: Discord context
            messages: List of messages to check
        """
        to_delete = []
        in_think_block = False

        for msg in messages:
            if msg.author == self.bot.user:
                content = msg.content
                if "<think>" in content:
                    in_think_block = True
                    to_delete.append(msg)
                elif "</think>" in content:
                    in_think_block = False
                    to_delete.append(msg)
                elif in_think_block:
                    to_delete.append(msg)

        for msg in to_delete:
            await msg.delete()

    async def handle_chat_response(
        self,
        ctx: commands.Context[typing.Any],
        messages: typing.List[typing.Dict[str, str]],
    ) -> str:
        """Handle chat interaction with Ollama.

        Args:
            ctx: Discord context
            messages: List of chat messages

        Returns:
            The model's response
        """
        client = ollama.AsyncClient()
        buffer = ""
        sent_messages: typing.List[discord.Message] = []
        complete_response = ""

        async for part in await client.chat(
            model=settings.MODEL_NAME,
            messages=messages,
            stream=True,
        ):
            content: str = part["message"]["content"]
            buffer += content
            complete_response += content

            chunks = self.chunk_message(buffer)
            if len(chunks) > 1:  # If we have complete chunks
                for chunk in chunks[:-1]:  # Send all but the last chunk
                    if chunk.strip():
                        self.logger.info(chunk)
                        sent_msg = await ctx.send(chunk)
                        sent_messages.append(sent_msg)
                buffer = chunks[-1]  # Keep the last partial chunk in buffer

        # Send any remaining content
        if buffer.strip():
            chunks = self.chunk_message(buffer)
            for chunk in chunks:
                self.logger.info(chunk)
                sent_msg = await ctx.send(chunk)
                sent_messages.append(sent_msg)

        await self.delete_think_block_messages(ctx, sent_messages)
        return complete_response

    async def handle_conversation(
        self,
        ctx: commands.Context[typing.Any],
        message: str,
        is_channel_chat: bool = False,
    ) -> None:
        """Handle ongoing conversation with context.

        Args:
            ctx: Discord context
            message: User's message
            is_channel_chat: Whether this is a channel chat or user conversation
        """
        if is_channel_chat:
            conversation = self.channel_conversations.get(ctx.channel.id, [])
        else:
            conversation = self.user_conversations.get(ctx.author.id, [])

        conversation.append({"role": "user", "content": message})
        response = await self.handle_chat_response(ctx, conversation)
        conversation.append({"role": "assistant", "content": response})

        # Store conversation in appropriate dictionary
        if is_channel_chat:
            self.channel_conversations[ctx.channel.id] = conversation
        else:
            self.user_conversations[ctx.author.id] = conversation

    @commands.command(name="prompt", aliases=["p"], help="Prompt chatbot with context.")
    async def prompt(
        self, ctx: commands.Context[typing.Any], n: int = 0, *, message: str
    ) -> None:
        """Prompt the chatbot with optional context.

        Args:
            ctx: Discord context
            n: Number of previous messages for context
            message: User's message
        """
        context = message
        if n > 0:
            messages = []
            async for msg in ctx.channel.history(limit=n):
                messages.append(msg)
            context = (
                "\n".join([msg.content for msg in reversed(messages)]) + f"\n{message}"
            )

        await self.handle_chat_response(ctx, [{"role": "user", "content": context}])

    @commands.command(name="ask", aliases=["a"], help="Ask chatbot without context.")
    async def ask(self, ctx: commands.Context[typing.Any], *, message: str) -> None:
        """Ask the chatbot a one-off question.

        Args:
            ctx: Discord context
            message: User's question
        """
        await self.prompt(ctx, 0, message=message)

    @commands.command(
        name="delete", aliases=["d"], help="Delete the last chatbot response."
    )
    async def delete_last_message(self, ctx: commands.Context[typing.Any]) -> None:
        async for message in ctx.channel.history(limit=100):
            if message.author == self.bot.user:
                await message.delete()
            if message.content.startswith("!"):
                await message.delete()
                break
        await ctx.message.delete()

    @commands.command(name="converse", aliases=["c"], help="Start a conversation.")
    async def converse(
        self, ctx: commands.Context[typing.Any], *, message: str
    ) -> None:
        """Start or continue a conversation with context memory.

        Args:
            ctx: Discord context
            message: User's message
        """
        await self.handle_conversation(ctx, message)

    @commands.command(name="stop", aliases=["s"], help="Stop the current conversation.")
    async def stop_conversation(self, ctx: commands.Context[typing.Any]) -> None:
        """Stop the current conversation and clear context.

        Args:
            ctx: Discord context
        """
        user_id = ctx.author.id
        if user_id in self.user_conversations:
            del self.user_conversations[user_id]
            await ctx.send("Personal conversation ended.")

    @commands.command(
        name="chat", aliases=["ch"], help="Start an interactive chat session"
    )
    async def chat(self, ctx: commands.Context[typing.Any]) -> None:
        """Start an interactive chat session in the channel with context memory.

        Args:
            ctx: Discord context
        """
        channel_id = ctx.channel.id
        if channel_id in self.channel_conversations:
            await ctx.send("A chat session is already active in this channel.")
            return

        self.channel_conversations[channel_id] = []
        await ctx.send(
            "Starting chat session. Send messages to chat, type 'stop' to end."
        )

        def check(m: discord.Message) -> bool:
            return (
                m.channel == ctx.channel
                and not m.author.bot
                and not m.content.startswith("!")
            )

        try:
            while True:
                message = await self.bot.wait_for("message", timeout=300.0, check=check)

                if message.content.lower() == "stop":
                    del self.channel_conversations[channel_id]
                    await ctx.send("Chat session ended.")
                    break

                await self.handle_conversation(
                    ctx, message.content, is_channel_chat=True
                )

        except TimeoutError:
            del self.channel_conversations[channel_id]
            await ctx.send("Chat session timed out due to inactivity.")

        except Exception as e:
            del self.channel_conversations[channel_id]
            self.logger.error(f"Error in chat session: {e}")
            await ctx.send("Chat session ended due to an error.")

    @commands.command(name="clear", aliases=["cl"], help="Clear chat history")
    async def clear_history(
        self, ctx: commands.Context[typing.Any], target: str = "all"
    ) -> None:
        """Clear conversation history.

        Args:
            ctx: Discord context
            target: Which history to clear ("channel", "user", or "all")
        """
        channel_id = ctx.channel.id
        user_id = ctx.author.id

        if target in ["channel", "all"]:
            if channel_id in self.channel_conversations:
                del self.channel_conversations[channel_id]
                await ctx.send("Channel chat history cleared.")

        if target in ["user", "all"]:
            if user_id in self.user_conversations:
                del self.user_conversations[user_id]
                await ctx.send("Personal chat history cleared.")


async def setup(bot: commands.Bot) -> None:
    """Set up the Ollama cog.

    Args:
        bot: The Discord bot instance
    """
    if settings.ENABLE_CHATBOT:
        await bot.add_cog(OllamaCog(bot))
