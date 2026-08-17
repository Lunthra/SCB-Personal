import os
import sqlite3

import discord
from discord.ext import commands
from dotenv import load_dotenv


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# Your Discord server ID
GUILD_ID = 1459779308884197588

# Prefix commands
PREFIX = "!!"

# SQLite database
DB_FILE = "media_threads.db"

# These are your currently registered threads.
# They are inserted only when the database is completely new.
INITIAL_MEDIA_THREAD_IDS = {
    1538146295489761331,
    1538183584102481932,
}


# ============================================================
# DATABASE
# ============================================================

def setup_database():
    """Create the database and seed the initial threads once."""

    with sqlite3.connect(DB_FILE) as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS media_threads (
                thread_id INTEGER PRIMARY KEY
            )
        """)

        # Check whether the table is empty.
        count = connection.execute(
            "SELECT COUNT(*) FROM media_threads"
        ).fetchone()[0]

        # Only add the initial threads to a brand-new/empty database.
        if count == 0:
            for thread_id in INITIAL_MEDIA_THREAD_IDS:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO media_threads (thread_id)
                    VALUES (?)
                    """,
                    (thread_id,)
                )

        connection.commit()


def is_media_thread(thread_id):
    """Check whether a thread is registered as a media-only thread."""

    with sqlite3.connect(DB_FILE) as connection:

        result = connection.execute(
            """
            SELECT 1
            FROM media_threads
            WHERE thread_id = ?
            """,
            (thread_id,)
        ).fetchone()

    return result is not None


def register_media_thread(thread_id):
    """Register a thread as a media-only thread."""

    with sqlite3.connect(DB_FILE) as connection:

        connection.execute(
            """
            INSERT OR IGNORE INTO media_threads (thread_id)
            VALUES (?)
            """,
            (thread_id,)
        )

        connection.commit()


def unregister_media_thread(thread_id):
    """Remove a thread from the media-only list."""

    with sqlite3.connect(DB_FILE) as connection:

        cursor = connection.execute(
            """
            DELETE FROM media_threads
            WHERE thread_id = ?
            """,
            (thread_id,)
        )

        connection.commit()

    return cursor.rowcount > 0


def get_media_threads():
    """Return all registered media thread IDs."""

    with sqlite3.connect(DB_FILE) as connection:

        rows = connection.execute(
            """
            SELECT thread_id
            FROM media_threads
            ORDER BY thread_id
            """
        ).fetchall()

    return [row[0] for row in rows]


# ============================================================
# BOT
# ============================================================

intents = discord.Intents.default()

# Required for:
# - prefix commands
# - reading message content
# - media-only message handling
intents.message_content = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents,
    help_command=None
)


# ============================================================
# SLASH COMMAND SYNC
# ============================================================

@bot.event
async def setup_hook():

    guild = discord.Object(id=GUILD_ID)

    # Copy hybrid commands to this specific server.
    bot.tree.copy_global_to(guild=guild)

    # Sync slash commands.
    await bot.tree.sync(guild=guild)

    print("Slash commands synced.")


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")
    print("SCB Personal is online!")

    print(
        f"Registered media threads: "
        f"{len(get_media_threads())}"
    )


# ============================================================
# REGISTER MEDIA THREAD
# ============================================================

@bot.hybrid_command(
    name="register-media",
    description="Register the current thread as a media-only thread."
)
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
async def register_media(ctx: commands.Context):

    # Make sure the command is being used in your server.
    if ctx.guild is None or ctx.guild.id != GUILD_ID:
        return

    channel = ctx.channel

    # Must be used inside a thread.
    if not isinstance(channel, discord.Thread):

        await ctx.send(
            "❌ This command must be used inside a thread.",
            ephemeral=True
        )

        return

    thread_id = channel.id

    # Already registered.
    if is_media_thread(thread_id):

        await ctx.send(
            "ℹ️ This thread is already registered as a "
            "media-only thread.",
            ephemeral=True
        )

        return

    # Register.
    register_media_thread(thread_id)

    await ctx.send(
        f"✅ **{channel.name}** is now a media-only thread.\n"
        f"Thread ID: `{thread_id}`",
        ephemeral=True
    )

    print(
        f"Registered media thread: "
        f"{channel.name} ({thread_id})"
    )


# ============================================================
# UNREGISTER MEDIA THREAD
# ============================================================

@bot.hybrid_command(
    name="unregister-media",
    description="Remove the current thread from the media-only list."
)
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
async def unregister_media(ctx: commands.Context):

    if ctx.guild is None or ctx.guild.id != GUILD_ID:
        return

    channel = ctx.channel

    # Must be used inside a thread.
    if not isinstance(channel, discord.Thread):

        await ctx.send(
            "❌ This command must be used inside a thread.",
            ephemeral=True
        )

        return

    thread_id = channel.id

    removed = unregister_media_thread(thread_id)

    if not removed:

        await ctx.send(
            "ℹ️ This thread isn't registered as a "
            "media-only thread.",
            ephemeral=True
        )

        return

    await ctx.send(
        f"✅ **{channel.name}** is no longer a "
        "media-only thread.",
        ephemeral=True
    )

    print(
        f"Unregistered media thread: "
        f"{channel.name} ({thread_id})"
    )


# ============================================================
# LIST MEDIA THREADS
# ============================================================

@bot.hybrid_command(
    name="media-threads",
    description="Show all registered media-only threads."
)
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
async def media_threads(ctx: commands.Context):

    if ctx.guild is None or ctx.guild.id != GUILD_ID:
        return

    thread_ids = get_media_threads()

    if not thread_ids:

        await ctx.send(
            "📭 No media-only threads are currently registered.",
            ephemeral=True
        )

        return

    lines = []

    for thread_id in thread_ids:

        channel = bot.get_channel(thread_id)

        if channel:

            lines.append(
                f"• {channel.mention} — `{thread_id}`"
            )

        else:

            lines.append(
                f"• <#{thread_id}> — `{thread_id}`"
            )

    await ctx.send(
        "**📸 Registered Media Threads**\n\n"
        + "\n".join(lines),
        ephemeral=True
    )


# ============================================================
# PIN / UNPIN MESSAGE
# ============================================================

@bot.hybrid_command(
    name="pin",
    description="Pin or unpin the message you are replying to."
)
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
async def pin(ctx: commands.Context):

    if ctx.guild is None or ctx.guild.id != GUILD_ID:
        return

    # Must be used as a reply to another message.
    if not ctx.message or not ctx.message.reference:

        if ctx.interaction:
            await ctx.send(
                "❌ Reply to a message with `/pin` to pin or unpin it.",
                ephemeral=True
            )
        else:
            await ctx.send(
                "❌ Reply to a message with `!!pin` to pin or unpin it."
            )

        return

    try:

        message_id = ctx.message.reference.message_id

        target_message = await ctx.channel.fetch_message(
            message_id
        )

        # ----------------------------------------------------
        # ALREADY PINNED → UNPIN
        # ----------------------------------------------------

        if target_message.pinned:

            await target_message.unpin(
                reason=f"Unpinned by {ctx.author}"
            )

            if ctx.interaction:
                await ctx.send(
                    "📌 Message unpinned!",
                    ephemeral=True
                )
            else:
                await ctx.send(
                    "📌 Message unpinned!"
                )

            print(
                f"Unpinned message {target_message.id} "
                f"by {ctx.author} "
                f"in {ctx.channel}"
            )

        # ----------------------------------------------------
        # NOT PINNED → PIN
        # ----------------------------------------------------

        else:

            await target_message.pin(
                reason=f"Pinned by {ctx.author}"
            )

            if ctx.interaction:
                await ctx.send(
                    "📌 Message pinned!",
                    ephemeral=True
                )
            else:
                await ctx.send(
                    "📌 Message pinned!"
                )

            print(
                f"Pinned message {target_message.id} "
                f"by {ctx.author} "
                f"in {ctx.channel}"
            )

    except discord.Forbidden:

        if ctx.interaction:
            await ctx.send(
                "❌ I don't have permission to pin or unpin messages here.",
                ephemeral=True
            )
        else:
            await ctx.send(
                "❌ I don't have permission to pin or unpin messages here."
            )

    except discord.NotFound:

        if ctx.interaction:
            await ctx.send(
                "❌ I couldn't find that message.",
                ephemeral=True
            )
        else:
            await ctx.send(
                "❌ I couldn't find that message."
            )

    except discord.HTTPException as e:

        if ctx.interaction:
            await ctx.send(
                f"❌ Failed to pin/unpin the message: `{e}`",
                ephemeral=True
            )
        else:
            await ctx.send(
                f"❌ Failed to pin/unpin the message: `{e}`"
            )


# ============================================================
# MEDIA-ONLY MESSAGE SYSTEM
# ============================================================

@bot.event
async def on_message(message: discord.Message):

    # Ignore bots.
    if message.author.bot:
        return

    # --------------------------------------------------------
    # PREFIX COMMANDS
    # --------------------------------------------------------

    # Always allow the command system to process the message.
    # This is important because we override on_message.
    await bot.process_commands(message)

    # --------------------------------------------------------
    # ONLY OUR SERVER
    # --------------------------------------------------------

    if message.guild is None:
        return

    if message.guild.id != GUILD_ID:
        return

    # --------------------------------------------------------
    # ONLY REGISTERED MEDIA THREADS
    # --------------------------------------------------------

    if not is_media_thread(message.channel.id):
        return

    # --------------------------------------------------------
    # ALLOW PREFIX COMMANDS
    # --------------------------------------------------------

    if message.content.startswith(PREFIX):
        return

    # --------------------------------------------------------
    # ALLOW ATTACHMENTS
    # --------------------------------------------------------

    if message.attachments:
        return

    # --------------------------------------------------------
    # DELETE TEXT-ONLY MESSAGE
    # --------------------------------------------------------

    try:

        await message.delete()

        print(
            f"Deleted text-only message from "
            f"{message.author} "
            f"in thread {message.channel.name}"
        )

    except discord.Forbidden:

        print(
            "ERROR: I don't have permission "
            "to delete this message."
        )

    except discord.HTTPException as e:

        print(
            f"ERROR: Discord failed to delete "
            f"the message: {e}"
        )


# ============================================================
# COMMAND ERROR HANDLING
# ============================================================

@bot.event
async def on_command_error(
    ctx: commands.Context,
    error: commands.CommandError
):

    # Ignore unknown commands.
    if isinstance(error, commands.CommandNotFound):
        return

    # Missing Manage Messages permission.
    if isinstance(
        error,
        commands.MissingPermissions
    ):

        if ctx.interaction:
            await ctx.send(
                "❌ You need **Manage Messages** permission "
                "to use this command.",
                ephemeral=True
            )
        else:
            await ctx.send(
                "❌ You need **Manage Messages** permission "
                "to use this command."
            )

        return

    # Command used outside a server.
    if isinstance(
        error,
        commands.NoPrivateMessage
    ):

        if ctx.interaction:
            await ctx.send(
                "❌ This command can only be used inside a server.",
                ephemeral=True
            )
        else:
            await ctx.send(
                "❌ This command can only be used inside a server."
            )

        return

    print(f"Command error: {error}")


# ============================================================
# DATABASE SETUP
# ============================================================

setup_database()


# ============================================================
# TOKEN CHECK
# ============================================================

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN was not found in the environment."
    )


# ============================================================
# START BOT
# ============================================================

bot.run(TOKEN)