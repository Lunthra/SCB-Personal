import os
import re
import sqlite3

import discord
from discord.ext import commands
from dotenv import load_dotenv


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 1459779308884197588

PREFIX = "!!"

DATABASE_FILE = "media_threads.db"


# Existing media threads
DEFAULT_MEDIA_THREAD_IDS = {
    1538146295489761331,
    1538183584102481932,
}


# ============================================================
# DATABASE
# ============================================================

def get_db():
    return sqlite3.connect(DATABASE_FILE)


def setup_database():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS media_threads (
                thread_id INTEGER PRIMARY KEY
            )
        """)

        for thread_id in DEFAULT_MEDIA_THREAD_IDS:
            db.execute(
                "INSERT OR IGNORE INTO media_threads (thread_id) VALUES (?)",
                (thread_id,)
            )

        db.commit()


def get_media_thread_ids():
    with get_db() as db:
        rows = db.execute(
            "SELECT thread_id FROM media_threads"
        ).fetchall()

    return {row[0] for row in rows}


def add_media_thread(thread_id):
    with get_db() as db:
        db.execute(
            "INSERT OR IGNORE INTO media_threads (thread_id) VALUES (?)",
            (thread_id,)
        )
        db.commit()


def remove_media_thread(thread_id):
    with get_db() as db:
        db.execute(
            "DELETE FROM media_threads WHERE thread_id = ?",
            (thread_id,)
        )
        db.commit()


# ============================================================
# BOT SETUP
# ============================================================

intents = discord.Intents.default()

# Required so the bot can read normal messages such as:
# pin
# unpin
# !!register_media
intents.message_content = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents,
    help_command=None
)


# ============================================================
# STARTUP
# ============================================================

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")
    print("SCB Personal is online!")

    # Sync slash commands only to your server
    guild = discord.Object(id=GUILD_ID)

    try:
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} slash command(s).")

    except Exception as e:
        print(f"Failed to sync slash commands: {e}")


# ============================================================
# PIN / UNPIN
# ============================================================

async def handle_pin_command(message):

    # Ignore anything that isn't exactly:
    #
    # pin
    # unpin
    #
    content = message.content.lower().strip()

    if content not in {"pin", "unpin"}:
        return False

    # It must be a reply to another message
    if not message.reference:
        return False

    # Only allow users who can manage messages
    if not message.author.guild_permissions.manage_messages:
        return False

    try:

        message_id = message.reference.message_id

        if message_id is None:
            return False

        target_message = await message.channel.fetch_message(
            message_id
        )

        # ----------------------------
        # PIN
        # ----------------------------

        if content == "pin":

            await target_message.pin(
                reason=f"Pinned by {message.author}"
            )

            await message.delete()

            print(
                f"Pinnned message {target_message.id} "
                f"by {message.author}"
            )

            return True

        # ----------------------------
        # UNPIN
        # ----------------------------

        if content == "unpin":

            await target_message.unpin(
                reason=f"Unpinned by {message.author}"
            )

            await message.delete()

            print(
                f"Unpinned message {target_message.id} "
                f"by {message.author}"
            )

            return True

    except discord.Forbidden:

        print(
            "ERROR: I don't have permission to pin/unpin "
            "messages in this channel."
        )

    except discord.NotFound:

        print("ERROR: The target message was not found.")

    except discord.HTTPException as e:

        print(
            f"ERROR: Discord failed to pin/unpin the message: {e}"
        )

    return True


# ============================================================
# MESSAGE EVENT
# ============================================================

@bot.event
async def on_message(message):

    # Ignore bot messages
    if message.author.bot:
        return

    # --------------------------------------------------------
    # PIN / UNPIN
    # --------------------------------------------------------

    # This works anywhere in the server.
    #
    # Reply to a message:
    #
    # pin
    #
    # or:
    #
    # unpin
    #
    # No prefix required.

    pin_handled = await handle_pin_command(message)

    if pin_handled:
        return

    # --------------------------------------------------------
    # NORMAL COMMANDS
    # --------------------------------------------------------

    # Important:
    # Since we override on_message, we must manually process
    # normal commands.
    await bot.process_commands(message)


    # --------------------------------------------------------
    # MEDIA THREAD SYSTEM
    # --------------------------------------------------------

    # Only apply media-only rules inside registered threads.
    media_thread_ids = get_media_thread_ids()

    if message.channel.id not in media_thread_ids:
        return

    # If message has an attachment, allow it.
    if message.attachments:
        return

    # Text-only message = delete it.
    try:

        await message.delete()

        print(
            f"Deleted text-only message from "
            f"{message.author} "
            f"in thread {message.channel.name}"
        )

    except discord.Forbidden:

        print(
            "ERROR: I don't have permission to delete "
            "messages in this thread."
        )

    except discord.HTTPException as e:

        print(
            f"ERROR: Discord failed to delete the message: {e}"
        )


# ============================================================
# REGISTER MEDIA THREAD
# ============================================================

@bot.hybrid_command(
    name="register_media",
    description="Register a thread as a media-only thread."
)
@commands.guild_only()
@commands.has_permissions(manage_messages=True)
async def register_media(
    ctx: commands.Context,
    thread: str
):

    if ctx.guild is None:
        return

    # Only allow this in your server
    if ctx.guild.id != GUILD_ID:
        return

    # --------------------------------------------------------
    # Extract thread ID
    # --------------------------------------------------------

    # Supports:
    #
    # <#123456789>
    #
    # or:
    #
    # 123456789
    #

    match = re.fullmatch(
        r"<#(\d+)>",
        thread.strip()
    )

    if match:
        thread_id = int(match.group(1))

    elif thread.strip().isdigit():
        thread_id = int(thread.strip())

    else:

        await ctx.send(
            "❌ Please mention a thread or provide its ID.",
            ephemeral=True
        )

        return

    # --------------------------------------------------------
    # Fetch the thread
    # --------------------------------------------------------

    try:

        target = await bot.fetch_channel(thread_id)

    except discord.NotFound:

        await ctx.send(
            "❌ I couldn't find that thread.",
            ephemeral=True
        )

        return

    except discord.Forbidden:

        await ctx.send(
            "❌ I don't have permission to access that thread.",
            ephemeral=True
        )

        return

    except discord.HTTPException as e:

        await ctx.send(
            f"❌ Discord returned an error: `{e}`",
            ephemeral=True
        )

        return

    # --------------------------------------------------------
    # Make sure it is actually a thread
    # --------------------------------------------------------

    if not isinstance(target, discord.Thread):

        await ctx.send(
            "❌ That isn't a thread. Please mention a thread.",
            ephemeral=True
        )

        return

    # Make sure the thread belongs to this server
    if target.guild.id != GUILD_ID:

        await ctx.send(
            "❌ That thread isn't from this server.",
            ephemeral=True
        )

        return

    # --------------------------------------------------------
    # Save thread
    # --------------------------------------------------------

    add_media_thread(target.id)

    await ctx.send(
        f"✅ {target.mention} is now a **media-only thread**.",
        ephemeral=True
    )

    print(
        f"Registered media thread: "
        f"{target.name} ({target.id})"
    )


# ============================================================
# UNREGISTER MEDIA THREAD
# ============================================================

@bot.hybrid_command(
    name="unregister_media",
    description="Remove a thread from the media-only system."
)
@commands.guild_only()
@commands.has_permissions(manage_messages=True)
async def unregister_media(
    ctx: commands.Context,
    thread: str
):

    if ctx.guild is None:
        return

    if ctx.guild.id != GUILD_ID:
        return

    # Extract thread ID
    match = re.fullmatch(
        r"<#(\d+)>",
        thread.strip()
    )

    if match:
        thread_id = int(match.group(1))

    elif thread.strip().isdigit():
        thread_id = int(thread.strip())

    else:

        await ctx.send(
            "❌ Please mention a thread or provide its ID.",
            ephemeral=True
        )

        return

    # Remove from database
    remove_media_thread(thread_id)

    await ctx.send(
        f"✅ Thread `{thread_id}` is no longer a media-only thread.",
        ephemeral=True
    )

    print(
        f"Unregistered media thread: {thread_id}"
    )


# ============================================================
# LIST MEDIA THREADS
# ============================================================

@bot.hybrid_command(
    name="media_threads",
    description="Show all registered media-only threads."
)
@commands.guild_only()
async def media_threads(ctx: commands.Context):

    if ctx.guild is None:
        return

    if ctx.guild.id != GUILD_ID:
        return

    thread_ids = get_media_thread_ids()

    if not thread_ids:

        await ctx.send(
            "There are currently no registered media threads.",
            ephemeral=True
        )

        return

    lines = []

    for thread_id in sorted(thread_ids):

        try:

            channel = bot.get_channel(thread_id)

            if channel is not None:
                lines.append(
                    f"• {channel.mention} (`{thread_id}`)"
                )

            else:
                lines.append(
                    f"• `{thread_id}`"
                )

        except Exception:

            lines.append(
                f"• `{thread_id}`"
            )

    await ctx.send(
        "📁 **Registered Media Threads**\n\n"
        + "\n".join(lines),
        ephemeral=True
    )


# ============================================================
# COMMAND ERROR HANDLER
# ============================================================

@bot.event
async def on_command_error(ctx, error):

    # Ignore commands that don't exist
    if isinstance(error, commands.CommandNotFound):
        return

    # Permission error
    if isinstance(error, commands.MissingPermissions):

        await ctx.send(
            "❌ You need **Manage Messages** permission to use this command.",
            ephemeral=True
        )

        return

    # Missing argument
    if isinstance(error, commands.MissingRequiredArgument):

        await ctx.send(
            "❌ You're missing an argument. "
            "Mention the thread you want to register.",
            ephemeral=True
        )

        return

    print(
        f"Command error: {error}"
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

setup_database()


# ============================================================
# START BOT
# ============================================================

if not TOKEN:

    raise RuntimeError(
        "DISCORD_TOKEN was not found in the environment."
    )


bot.run(TOKEN)