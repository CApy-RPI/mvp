# stl imports
import asyncio
import logging
import subprocess

# third-party imports
import discord
from discord.ext import commands

# local imports
from src.backend.db.database import Database as db
from src.backend.db.documents.user import User, UserProfile, UserName
from src.backend.mods.email import remove_verified_email, get_verified_email


class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )
        self.major_list = self.load_major_list()

    def load_major_list(self):
        try:
            with open("src/capy_backend/res/majors.txt", "r") as f:
                return [line.strip() for line in f.readlines()]
        except FileNotFoundError:
            self.logger.error("majors.txt not found")
            return []

    @commands.group(
        name="profile", invoke_without_command=True, help="Profile commands."
    )
    async def profile(self, ctx):
        embed = discord.Embed(
            title="Profile Commands",
            description="Below are the profile commands you can use.\n!profile create - Creates your profile.\n!profile update - Updates your profile.\n!profile show - Shows your profile.",
            color=discord.Color.purple(),
        )
        await ctx.send(embed=embed)

    @profile.command(name="create", help="Creates your profile.")
    async def create(self, ctx):

        # Create an embed with a welcome message
        """
        This command will guide you through creating your profile. It will ask for your first name, last name, major, graduation year, RPI email, and RPI RIN. If you have already created a profile, it will ask you if you want to override it. If you do not want to override, it will allow you to exit the profile creation.
        """
        # Send the welcome message to the user
        self.logger.info("Creating user profile...")
        dm_embed = discord.Embed(
            title="Welcome to the RPI Discord!",
            description="We're excited to have you here! Before we get started, we need some information from you to create your profile. Please answer the following questions with your information. (If you made any mistakes, you can update it after completing vertification using the !update command.)",
            color=discord.Color.purple(),
        )
        await ctx.author.send(embed=dm_embed)

        self.logger.info(
            f"Attempting to retrieve user document for user ID: {ctx.author.id}"
        )
        user = db.get_document(User, ctx.author.id)

        if user:
            await ctx.author.send(
                "You already have a profile. Are you sure want to override it? If you do not please use the update command.\n Type Y or N"
            )
            msg = await self.bot.wait_for(
                "message",
                check=lambda message: message.author == ctx.author
                and isinstance(message.channel, discord.DMChannel),
            )
            if msg.content.lower() == "y":
                self.logger.info("Overwriting user profile...")
                await ctx.author.send(
                    "Ok. The profile will be overwritten. If you want to update your profile please use the update command."
                )
            else:
                self.logger.info("Not overwriting user profile")
                await ctx.author.send(
                    "Ok. The profile will not be overwritten. If you want to update your profile please use the update command."
                )
                return

        # Ask for user's first name
        self.logger.info("Asking user for first name")
        first_name = await self.ask_question(
            ctx.author, "What is your (preferred) first name? (Example: John)"
        )
        if first_name is None:
            return  # Handle if user doesn't respond in time
        # Ask for user's last name
        self.logger.info("Asking user for last name")
        last_name = await self.ask_question(
            ctx.author,
            'What is your last name? (Please make sure to capitalize appropriately, e.g "Smith")',
        )
        if last_name is None:
            return
        # Ask for user's major
        self.logger.info("Asking user for major")
        major = await self.ask_major(ctx.author)
        if major is None:
            return

        # Ask for graduation year
        self.logger.info("Asking user for graduation year")
        grad_year = await self.ask_graduation_year(ctx.author)
        if grad_year is None:
            return

        # Ask for user's RPI email
        self.logger.info("Asking user for RPI email")
        rpi_email = await self.ask_email(ctx.author)
        if rpi_email is None:
            return

        # Ask for user's RPI RIN
        self.logger.info("Asking user for RPI RIN")
        rpi_rin = await self.ask_rin(ctx.author)
        if rpi_rin is None:
            return

        # Create an embed with the collected profile information
        profile_embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Profile",
            description="Here is the information you provided:",
            color=discord.Color.purple(),
        )

        # Add the profile information to the embed
        profile_embed.set_thumbnail(url=ctx.author.display_avatar.url)
        profile_embed.add_field(name="First Name", value=first_name, inline=True)
        profile_embed.add_field(name="Last Name", value=last_name, inline=True)
        profile_embed.add_field(name="Major", value=", ".join(major), inline=True)
        profile_embed.add_field(name="Graduation Year", value=grad_year, inline=True)
        profile_embed.add_field(name="RPI Email", value=rpi_email, inline=True)
        profile_embed.add_field(name="RPI RIN", value=rpi_rin, inline=True)

        # Save the collected profile information to the database
        updates = {
            "profile__name__first": first_name,
            "profile__name__last": last_name,
            "profile__major": major,
            "profile__graduation_year": grad_year,
            "profile__school_email": rpi_email,
            "profile__student_id": rpi_rin,
        }

        if user:
            self.logger.info(
                f"Updating existing user with ID {ctx.author.id} in the database."
            )
            db.update_document(user, updates)
            self.logger.info("User information updated successfully.")
        else:
            self.logger.info(f"Creating a new user with ID {ctx.author.id}.")
            new_user = User(
                _id=ctx.author.id,
                profile=UserProfile(
                    name=UserName(first=first_name, last=last_name),
                    major=major,
                    graduation_year=grad_year,
                    school_email=rpi_email,
                    student_id=rpi_rin,
                ),
            )
            db.add_document(new_user)
            self.logger.info("New user created and added to the database.")

        # Send the profile back to the user for confirmation
        await ctx.author.send(embed=profile_embed)

    async def ask_question(self, user, question):
        """
        Sends a question to the user and waits for a response.
        Returns the user's response or None if they don't respond in time.
        """
        try:
            await user.send(question)

            # Wait for the user's reply (timeout in seconds)
            msg = await self.bot.wait_for(
                "message",
                check=lambda message: message.author == user
                and isinstance(message.channel, discord.DMChannel),
                timeout=60,
            )

            await user.send(f"Your response: {msg.content}")

            return msg.content  # Return the response
        except asyncio.TimeoutError:
            await user.send(
                "You took too long to respond! Please start the profile setup again."
            )
            return None

    async def ask_graduation_year(self, user):
        """
        Sends a question to the user regarding the graduation year and waits for a response.
        Checks if the response is a valid year and returns it if it is.
        Return None if the user doesn't respond in time or if the response is not a valid year.
        """
        while True:
            grad_year = await self.ask_question(
                user, "What is your graduation year (YYYY)?"
            )
            if grad_year is None:
                return None

            if grad_year.isdigit() and len(grad_year) == 4:
                return grad_year
            else:
                self.logger.info("User entered an invalid year")
                await user.send(
                    f"{grad_year} is not a valid year. Please enter a valid year (YYYY)."
                )

    async def ask_major(self, user):
        """
        Sends a question to the user regarding the major and waits for a response.
        Checks if the response is a valid major and returns it if it is.
        Return None if the user doesn't respond in time or if the response is not a valid major.
        """
        while True:
            # Create an embed with the list of majors
            major_embed = discord.Embed(
                title="Major List",
                description="Respond with the number(s) that correspond to your current Major.",
            )

            for i, major in enumerate(self.major_list):
                major_embed.description += f"\n{i+1}. {major}"
            await user.send(embed=major_embed)

            # Wait for the user's reply (timeout in seconds)
            msg = await self.bot.wait_for(
                "message",
                check=lambda message: message.author == user
                and isinstance(message.channel, discord.DMChannel),
                timeout=60,
            )

            # Split the message via commas to determine the selected majors
            major_choices = msg.content.split(",")
            major_choices = [choice.strip() for choice in major_choices]

            # Check if the user's reply contains duplicate majors
            if len(major_choices) != len(set(major_choices)):
                await user.send(
                    f"{msg.content} contains duplicate majors. Please enter a valid major."
                )
                continue
            selected_majors = []
            valid = True

            # Check if the user's reply is a valid major
            for choice in major_choices:
                if choice.isdigit() and 0 <= int(choice) - 1 < len(self.major_list):
                    selected_majors.append(self.major_list[int(choice) - 1])
                else:
                    valid = False
                    break

            if valid:
                await user.send(f"Your selected majors: {', '.join(selected_majors)}")
                return selected_majors
            else:
                self.logger.info("User entered an invalid major")
                await user.send(
                    f"{msg.content} is not a valid major. Please enter a valid major."
                )

    async def ask_email(self, user):
        """
        Sends a question to the user regarding the email and waits for a response.
        Checks if the response is a valid email and returns it if it is.
        Return None if the user doesn't respond in time or if the response is not a valid email.
        """
        while True:
            email = await self.ask_question(
                user, "What is your rpi email (john@rpi.edu)"
            )
            if email is None:
                self.logger.info(
                    "User did not respond in time or did not input an email"
                )
                return None

            if email and "@" in email and email.endswith("@rpi.edu"):
                return email
            else:
                await user.send(
                    f"{email} is not a valid RPI email. Please enter a valid RPI email (john@rpi.edu)."
                )

    async def ask_rin(self, user):
        """
        Sends a question to the user regarding the RIN and waits for a response.
        Checks if the response is a valid RIN and returns it if it is.
        Return None if the user doesn't respond in time or if the response is not a valid RIN.
        """
        while True:
            rin = await self.ask_question(
                user, "What is your RIN? (Example: 123456789)"
            )
            if rin is None:
                self.logger.info("User did not respond in time or did not input an RIN")
                return None

            if rin.isdigit() and len(rin) == 9:
                return rin
            else:
                await user.send(
                    f"{rin} is not a valid RIN. Please enter a valid RIN. Make sure it has 9 digits."
                )

    @profile.command(name="update", help="Updates your profile.")
    async def update(self, ctx):
        # Create an embed with a welcome message
        """
        Updates your profile by allowing you to modify each individual aspect of your profile.
        """
        self.logger.info("Updating user profile...")
        updated_user = db.get_document(User, ctx.author.id)
        if not updated_user:
            self.logger.info(
                f"User {ctx.author.id} does not have a profile yet! Please use the !profile command to create one."
            )
            await ctx.send(
                "You do not have a profile yet! Please use the !profile command to create one."
            )
            return

        aspects = [
            "First Name",
            "Last Name",
            "Major",
            "Graduation Year",
            "RIN",
            "RPI Email",
            "Exit",
        ]
        aspects_embed = discord.Embed(
            title="Update Page",
            description="\n".join(
                [f"{i+1}. {aspect}" for i, aspect in enumerate(aspects)]
            ),
            color=discord.Color.pink(),
        )
        while True:
            await ctx.author.send(embed=aspects_embed)
            user_choice = await self.user_choice(ctx.author)

            if user_choice is None:
                return  # Handle if user doesn't respond in time

            if user_choice.isdigit() and 1 <= int(user_choice) <= len(aspects):
                new_value = aspects[int(user_choice) - 1]
                aspect = aspects[int(user_choice) - 1]

                if aspect == "Exit":
                    self.logger.info("Exit update page")
                    await ctx.author.send("Exiting update page.")
                    break
                if aspect == "First Name":
                    await ctx.author.send(
                        "Your previous response was: " + updated_user.profile.name.first
                    )
                    self.logger.info("Updating first name")
                    new_value = await self.ask_question(
                        ctx.author, "What is your updated first name? (Example: John)"
                    )
                    # Create updates dictionary to store all changes
                    updates = {}

                    if aspect == "First Name":
                        updates["profile__name__first"] = new_value
                        updated_user.profile.name.first = new_value
                    elif aspect == "Last Name":
                        await ctx.author.send(
                            f"Your previous response was: {updated_user.profile.name.last}"
                        )
                        self.logger.info("Updating last name")
                        new_value = await self.ask_question(
                            ctx.author,
                            "What is your updated last name? (Example: Smith)",
                        )
                        updates["profile__name__last"] = new_value
                        updated_user.profile.name.last = new_value
                    elif aspect == "Major":
                        await ctx.author.send(
                            "Your previous response was: "
                            + ", ".join(updated_user.profile.major)
                        )
                        self.logger.info("Updating major")
                        new_value = await Profile.ask_major(self, ctx.author)
                        updates["profile__major"] = new_value
                        updated_user.profile.major = new_value
                    elif aspect == "Graduation Year":
                        await ctx.author.send(
                            "Your previous response was: "
                            + str(updated_user.profile.graduation_year)
                        )
                        self.logger.info("Updating graduation year")
                        new_value = await Profile.ask_graduation_year(self, ctx.author)
                        updates["profile__graduation_year"] = new_value
                        updated_user.profile.graduation_year = new_value
                    elif aspect == "RIN":
                        await ctx.author.send(
                            "Your previous response was: "
                            + str(updated_user.profile.student_id)
                        )
                        self.logger.info("Updating RIN")
                        new_value = await Profile.ask_rin(self, ctx.author)
                        updates["profile__student_id"] = new_value
                        updated_user.profile.student_id = new_value
                    elif aspect == "RPI Email":
                        await ctx.author.send(
                            "Your previous response was: "
                            + updated_user.profile.school_email
                        )
                        self.logger.info("Updating RPI Email")
                        new_value = await Profile.ask_email(self, ctx.author)
                        updates["profile__school_email"] = new_value
                        updated_user.profile.school_email = new_value

                    # Update database with all changes at once
                    if updates:
                        db.update_document(updated_user, updates)

                await ctx.author.send(f"Your {aspect} has been updated.")

            else:
                self.logger.info("Invalid choice")
                await ctx.author.send(
                    f"Invalid choice. Please enter a number between 1 and {len(aspects)}"
                )
        await self.show_user_profile(ctx, updated_user)

    async def user_choice(self, user):
        """
        Asks the user to select an aspect of their profile to update.

        :param user: The user to ask.
        :type user: discord.User
        :return: The user's response.
        :rtype: str
        :raises asyncio.TimeoutError: The user took too long to respond.
        """
        self.logger.info(
            "Trying to: ask user to select an aspect of their profile to update."
        )
        try:
            await user.send("What aspect do you want to update?")

            # Wait for the user's reply (timeout in seconds)
            msg = await self.bot.wait_for(
                "message",
                check=lambda message: message.author == user
                and isinstance(message.channel, discord.DMChannel),
                timeout=60,
            )

            return msg.content
        except asyncio.TimeoutError:
            self.logger.error(
                "You took too long to respond! Please start the profile setup again."
            )
            await user.send(
                "You took too long to respond! Please start the profile setup again."
            )
            return None

    async def show_user_profile(self, ctx, user_profile):
        """
        Sends an embed showing the user's updated profile.
        """
        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Updated Profile",
            description="Here is the information you provided:",
            color=discord.Color.purple(),
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.add_field(
            name="First Name", value=user_profile.profile.name.first, inline=True
        )
        embed.add_field(
            name="Last Name", value=user_profile.profile.name.last, inline=True
        )
        embed.add_field(
            name="Major", value=", ".join(user_profile.profile.major), inline=True
        )
        embed.add_field(
            name="Graduation Year",
            value=str(user_profile.profile.graduation_year),
            inline=True,
        )
        embed.add_field(
            name="RPI Email", value=user_profile.profile.school_email, inline=True
        )
        embed.add_field(
            name="RIN", value=str(user_profile.profile.student_id), inline=True
        )

        await ctx.author.send(embed=embed)

    @profile.command(name="show", help="Shows your profile.")
    async def show_profile(self, ctx):
        """
        Shows your profile.
        """
        self.logger.info("Showing user profile!")
        user = db.get_document(User, ctx.author.id)
        if user == -1 or not user:
            await ctx.author.send(
                "You don't have a profile. Please use the !profile command to create one."
            )
            return
        await self.show_user_profile(ctx, user)


async def setup(bot: commands.Bot):
    await bot.add_cog(Profile(bot))
