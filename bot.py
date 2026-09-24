import asyncio
import os
import sqlite3
import time
from typing import Optional
from urllib.parse import urlparse

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

# Existing initial media thread IDs
# DO NOT CHANGE THESE.
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
# SIMPLE PIN / UNPIN
# ============================================================
#
# IMPORTANT:
# This is a LISTENER, not a command.
#
# Therefore:
#     pin
#     unpin
#
# are NOT slash commands and do NOT use !!
#
# This listener is completely separate from the media-thread
# on_message event above.
# ============================================================

@bot.listen("on_message")
async def simple_pin_unpin(message: discord.Message):

    # Ignore bots.
    if message.author.bot:
        return

    # Only work in your server.
    if message.guild is None:
        return

    if message.guild.id != GUILD_ID:
        return

    # Only react to exactly "pin" or "unpin".
    command = message.content.strip().lower()

    if command not in {"pin", "unpin"}:
        return

    # User must have Manage Messages.
    if not message.author.guild_permissions.manage_messages:
        return

    # Must be replying to another message.
    if message.reference is None:
        return

    # Make sure there is an actual message ID.
    if message.reference.message_id is None:
        return

    try:

        # Get the message being replied to.
        target_message = await message.channel.fetch_message(
            message.reference.message_id
        )

        # ----------------------------------------------------
        # PIN
        # ----------------------------------------------------

        if command == "pin":

            # Don't try to pin something already pinned.
            if target_message.pinned:
                return

            await target_message.pin(
                reason=f"Pinned by {message.author}"
            )

            # Remove the "pin" command message.
            await message.delete()

            print(
                f"Pinned message {target_message.id} "
                f"by {message.author} "
                f"in {message.channel}"
            )

        # ----------------------------------------------------
        # UNPIN
        # ----------------------------------------------------

        elif command == "unpin":

            # Don't try to unpin something that isn't pinned.
            if not target_message.pinned:
                return

            await target_message.unpin(
                reason=f"Unpinned by {message.author}"
            )

            # Remove the "unpin" command message.
            await message.delete()

            print(
                f"Unpinned message {target_message.id} "
                f"by {message.author} "
                f"in {message.channel}"
            )

    except discord.Forbidden:

        print(
            "ERROR: I don't have permission "
            "to pin/unpin messages here."
        )

    except discord.NotFound:

        print(
            "ERROR: The replied message "
            "could not be found."
        )

    except discord.HTTPException as e:

        print(
            f"ERROR: Discord failed to pin/unpin: {e}"
        )


# ============================================================
# AFK SYSTEM
# ============================================================
#
# This is intentionally stored in a SEPARATE database file.
# The existing media_threads.db is not touched by the AFK system.
#
# Prefix:
#     !!afk <reason> [media URL]
#     !!afk set <reason> [media URL]
#     !!afk list
#     !!afk remove @member
#     !!afk clear
#
# Slash:
#     /afk set
#     /afk list
#     /afk remove
#     /afk clear
#
# Only currently-active AFK users are stored. When an AFK user
# sends a normal message, their row is deleted immediately.
# ============================================================

AFK_DB_FILE = "afk.db"


# ------------------------------------------------------------
# AFK DATABASE
# ------------------------------------------------------------

def setup_afk_database():
    """Create the separate AFK database and migrate older AFK tables."""

    with sqlite3.connect(AFK_DB_FILE) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS afk_status (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                media_url TEXT,
                created_at REAL NOT NULL,
                original_nickname TEXT,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        # Older versions of the AFK system did not store the member's
        # original nickname. Add the column safely when upgrading.
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(afk_status)").fetchall()
        }

        if "original_nickname" not in columns:
            connection.execute(
                "ALTER TABLE afk_status ADD COLUMN original_nickname TEXT"
            )

        connection.commit()


def set_afk_status(
    guild_id: int,
    user_id: int,
    reason: str,
    media_url: Optional[str],
    original_nickname: Optional[str]
):
    """Create or update a member's AFK status."""

    with sqlite3.connect(AFK_DB_FILE) as connection:
        connection.execute("""
            INSERT INTO afk_status (
                guild_id,
                user_id,
                reason,
                media_url,
                created_at,
                original_nickname
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET
                reason = excluded.reason,
                media_url = excluded.media_url,
                created_at = excluded.created_at,
                original_nickname = COALESCE(original_nickname, excluded.original_nickname)
        """, (
            guild_id,
            user_id,
            reason,
            media_url,
            time.time(),
            original_nickname
        ))

        connection.commit()


def get_afk_status(guild_id: int, user_id: int):
    """Return one AFK record, or None if the member is not AFK."""

    with sqlite3.connect(AFK_DB_FILE) as connection:
        row = connection.execute("""
            SELECT
                user_id,
                reason,
                media_url,
                created_at,
                original_nickname
            FROM afk_status
            WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id)).fetchone()

    return row


def remove_afk_status(guild_id: int, user_id: int) -> bool:
    """Remove one AFK record."""

    with sqlite3.connect(AFK_DB_FILE) as connection:
        cursor = connection.execute("""
            DELETE FROM afk_status
            WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id))

        connection.commit()

    return cursor.rowcount > 0


def clear_afk_statuses(guild_id: int):
    """Return all AFK records for a guild and remove them."""

    with sqlite3.connect(AFK_DB_FILE) as connection:
        rows = connection.execute("""
            SELECT user_id, original_nickname
            FROM afk_status
            WHERE guild_id = ?
        """, (guild_id,)).fetchall()

        connection.execute("""
            DELETE FROM afk_status
            WHERE guild_id = ?
        """, (guild_id,))

        connection.commit()

    return rows


def get_all_afk_statuses(guild_id: int):
    """Return all currently-AFK users in the guild."""

    with sqlite3.connect(AFK_DB_FILE) as connection:
        rows = connection.execute("""
            SELECT
                user_id,
                reason,
                media_url,
                created_at,
                original_nickname
            FROM afk_status
            WHERE guild_id = ?
            ORDER BY created_at ASC
        """, (guild_id,)).fetchall()

    return rows


# ------------------------------------------------------------
# AFK HELPERS
# ------------------------------------------------------------

def is_valid_url(value: Optional[str]) -> bool:
    """Return True when value looks like an HTTP(S) URL."""

    if not value:
        return False

    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False


def looks_like_media_url(value: Optional[str]) -> bool:
    """Return True for a direct image/GIF/video URL."""

    if not is_valid_url(value):
        return False

    path = urlparse(value).path.lower()

    return path.endswith((
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        ".mp4",
        ".webm",
        ".mov",
        ".m4v",
    ))


def parse_afk_text(raw_text: str):
    """Split a prefix AFK message into reason and optional media URL."""

    raw_text = raw_text.strip()

    if not raw_text:
        return None, None

    parts = raw_text.split()
    media_url = None

    # If the final token is a URL, treat it as the optional media URL.
    if parts and is_valid_url(parts[-1]):
        possible_media = parts[-1]

        # Accept any HTTP(S) URL as a media/link URL. Direct image/GIF/video
        # URLs will be rendered directly; other URLs will be shown as links.
        media_url = possible_media
        parts.pop()

    reason = " ".join(parts).strip()

    return reason or None, media_url


def format_afk_duration(created_at: float) -> str:
    """Return a compact human-readable AFK duration."""

    seconds = max(0, int(time.time() - created_at))

    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _ = divmod(seconds, 60)

    pieces = []

    if days:
        pieces.append(f"{days}d")

    if hours:
        pieces.append(f"{hours}h")

    if minutes or not pieces:
        pieces.append(f"{minutes}m")

    return " ".join(pieces)


def build_afk_embed(member: discord.abc.User, reason: str, media_url: Optional[str], created_at: float):
    """Build the public AFK notice embed.

    Images/GIFs are rendered directly inside the embed. Direct video URLs
    are intentionally NOT put into an embed field because Discord can render
    native video previews when the raw URL is sent as normal message content.
    """

    display_name = member.display_name
    if display_name.startswith("[AFK] "):
        display_name = display_name[6:]

    embed = discord.Embed(
        title="💤 AFK",
        description=(
            f"**{display_name} is AFK.**\n"
            f"**Reason:** {reason}\n"
            f"**AFK for:** {format_afk_duration(created_at)}"
        )
    )

    if media_url:
        parsed_path = urlparse(media_url).path.lower()
        image_url = parsed_path.endswith((
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".gif",
        ))

        if image_url:
            embed.set_image(url=media_url)
        elif not parsed_path.endswith((
            ".mp4",
            ".webm",
            ".mov",
            ".m4v",
        )):
            # Non-media URLs still get a clean clickable link.
            embed.add_field(
                name="Media",
                value=f"[Open media]({media_url})",
                inline=False
            )

    return embed


def afk_nickname(member: discord.Member) -> str:
    """Return the nickname Discord should use while the member is AFK."""

    base_name = member.display_name

    # Prevent duplicated prefixes in case the nickname already has [AFK].
    if base_name.startswith("[AFK] "):
        return base_name

    return f"[AFK] {base_name}"


async def set_afk_nickname(member: discord.Member, original_nickname: Optional[str]) -> bool:
    """Set the member's nickname to [AFK] <server display name>."""

    if not member.guild.me:
        return False

    if member == member.guild.me:
        return False

    if not member.guild.me.guild_permissions.manage_nicknames:
        print("AFK nickname skipped: bot does not have Manage Nicknames.")
        return False

    if member.top_role >= member.guild.me.top_role:
        print(
            f"AFK nickname skipped for {member}: member role is above or equal to bot role."
        )
        return False

    # When the member has a custom server nickname, preserve that nickname.
    # When they do not, use Discord's current server display name (which can be
    # different from the account username). This is the name the user sees.
    target_name = original_nickname if original_nickname is not None else member.display_name

    if target_name.startswith("[AFK] "):
        target_name = target_name[6:]

    new_nickname = f"[AFK] {target_name}"

    # Discord nicknames have a 32-character limit.
    new_nickname = new_nickname[:32]

    try:
        await member.edit(
            nick=new_nickname,
            reason="AFK status enabled"
        )
        return True
    except discord.Forbidden:
        print(f"AFK nickname failed for {member}: missing permission/hierarchy.")
    except discord.HTTPException as e:
        print(f"AFK nickname failed for {member}: {e}")

    return False


async def restore_afk_nickname(
    guild: discord.Guild,
    user_id: int,
    original_nickname: Optional[str]
) -> bool:
    """Restore a member's pre-AFK nickname."""

    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except (discord.NotFound, discord.HTTPException):
            return False

    if member == guild.me:
        return False

    if not guild.me or not guild.me.guild_permissions.manage_nicknames:
        print("AFK nickname restore skipped: bot does not have Manage Nicknames.")
        return False

    if member.top_role >= guild.me.top_role:
        print(
            f"AFK nickname restore skipped for {member}: member role is above or equal to bot role."
        )
        return False

    try:
        await member.edit(
            nick=original_nickname,
            reason="AFK status removed"
        )
        return True
    except discord.Forbidden:
        print(f"AFK nickname restore failed for {member}: missing permission/hierarchy.")
    except discord.HTTPException as e:
        print(f"AFK nickname restore failed for {member}: {e}")

    return False


async def send_afk_management_response(
    ctx: commands.Context,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    *,
    ephemeral: bool = False
):
    """Send ephemeral output for slash commands or DM output for prefix commands."""

    if ctx.interaction is not None:
        return await ctx.send(
            content=content,
            embed=embed,
            ephemeral=ephemeral
        )

    try:
        await ctx.author.send(content=content, embed=embed)
    except discord.Forbidden:
        await ctx.send(
            "❌ I couldn't DM you the AFK management result. "
            "Please enable DMs from this server and try again."
        )


async def apply_afk_status(
    ctx: commands.Context,
    reason: Optional[str],
    media_url: Optional[str]
):
    """Set or update the caller's AFK status and nickname."""

    if ctx.guild is None or ctx.guild.id != GUILD_ID:
        return

    reason = (reason or "AFK").strip()

    if not reason:
        await ctx.send(
            "❌ Please provide an AFK reason.\n"
            f"Example: `{PREFIX}afk studying`"
        )
        return

    if media_url and not is_valid_url(media_url):
        media_url = None

    existing = get_afk_status(ctx.guild.id, ctx.author.id)

    # Save the nickname only the first time this AFK status is created.
    # On repeated AFK updates, keep the original nickname from the first entry.
    if existing:
        original_nickname = existing[4]

        # Upgrade-safe handling for AFK records created by the older version
        # before nickname support existed.
        if original_nickname is None and isinstance(ctx.author, discord.Member):
            current_nickname = ctx.author.nick
            if current_nickname and current_nickname.startswith("[AFK] "):
                original_nickname = current_nickname[6:]
            else:
                original_nickname = current_nickname
    else:
        original_nickname = getattr(ctx.author, "nick", None)

    set_afk_status(
        ctx.guild.id,
        ctx.author.id,
        reason,
        media_url,
        original_nickname
    )

    nickname_changed = False

    if isinstance(ctx.author, discord.Member):
        # Apply the nickname when first entering AFK. Also upgrade an old AFK
        # record that predates nickname support.
        if not ctx.author.display_name.startswith("[AFK] "):
            nickname_changed = await set_afk_nickname(
                ctx.author,
                original_nickname
            )

    if existing:
        message = "✅ Your AFK status has been updated."
    else:
        message = "💤 You are now AFK."

    if not nickname_changed and isinstance(ctx.author, discord.Member):
        # Only mention nickname permissions when the bot couldn't apply it.
        if not ctx.guild.me.guild_permissions.manage_nicknames:
            message += "\n⚠️ I couldn't add `[AFK]` to your nickname because I need **Manage Nicknames**."

    await ctx.send(message)


# ------------------------------------------------------------
# /afk + !!afk SET
# ------------------------------------------------------------

@bot.hybrid_group(
    name="afk",
    fallback="set",
    description="Set or manage your AFK status."
)
@commands.guild_only()
async def afk(ctx: commands.Context, reason: Optional[str] = None, media: Optional[str] = None):
    """
    Set AFK status.

    Prefix:
        !!afk <reason> [media URL]
        !!afk set <reason> [media URL]

    Slash:
        /afk set reason media
    """

    # For prefix commands, the entire remainder of the message is parsed
    # manually so reasons can contain spaces and still accept a final URL.
    if ctx.interaction is None:
        raw = ctx.message.content[len(PREFIX + "afk"):].strip()

        if raw.lower() == "set" or raw.lower().startswith("set "):
            remainder = raw[3:].strip()
        else:
            remainder = raw

        reason, media = parse_afk_text(remainder)

    await apply_afk_status(ctx, reason, media)


# ------------------------------------------------------------
# /afk LIST + !!afk list
# ------------------------------------------------------------

@afk.command(
    name="list",
    description="Show everyone who is currently AFK."
)
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
async def afk_list(ctx: commands.Context):
    """Show the current AFK list privately to moderators."""

    if ctx.guild is None or ctx.guild.id != GUILD_ID:
        return

    rows = get_all_afk_statuses(ctx.guild.id)

    if not rows:
        await send_afk_management_response(
            ctx,
            "📭 No members are currently AFK.",
            ephemeral=True
        )
        return

    # Keep the private output comfortably under Discord message limits.
    chunks = []
    current_chunk = [
        f"**💤 Current AFK Members — {len(rows)}**\n"
    ]

    for index, (user_id, reason, media_url, created_at, _original_nickname) in enumerate(rows, start=1):
        line = (
            f"{index}. <@{user_id}> — **{reason}** "
            f"(`{format_afk_duration(created_at)}`)"
        )

        if media_url:
            line += f" — [media]({media_url})"

        # Discord message limit is 2000 characters. Leave a safe margin.
        if sum(len(item) + 1 for item in current_chunk) + len(line) > 1800:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
        else:
            current_chunk.append(line)

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    for index, chunk in enumerate(chunks):
        if ctx.interaction is not None:
            await ctx.send(
                chunk,
                ephemeral=True
            )
        else:
            try:
                await ctx.author.send(chunk)
            except discord.Forbidden:
                await ctx.send(
                    "❌ I couldn't DM you the AFK list. "
                    "Please enable DMs from this server."
                )
                break


# ------------------------------------------------------------
# /afk REMOVE + !!afk remove
# ------------------------------------------------------------

@afk.command(
    name="remove",
    description="Remove AFK status from a specific member."
)
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
async def afk_remove(ctx: commands.Context, member: Optional[discord.Member] = None):
    """Moderator-only removal of a specific member's AFK status."""

    if ctx.guild is None or ctx.guild.id != GUILD_ID:
        return

    if member is None:
        await send_afk_management_response(
            ctx,
            f"❌ Please specify a member. Example: `{PREFIX}afk remove @member`",
            ephemeral=True
        )
        return

    record = get_afk_status(ctx.guild.id, member.id)

    if record is None:
        await send_afk_management_response(
            ctx,
            f"ℹ️ {member.mention} is not currently AFK.",
            ephemeral=True
        )
        return

    original_nickname = record[4]
    removed = remove_afk_status(ctx.guild.id, member.id)

    if not removed:
        await send_afk_management_response(
            ctx,
            f"ℹ️ {member.mention} is not currently AFK.",
            ephemeral=True
        )
        return

    await restore_afk_nickname(
        ctx.guild,
        member.id,
        original_nickname
    )

    await send_afk_management_response(
        ctx,
        f"✅ Removed AFK status from {member.mention}.",
        ephemeral=True
    )


# ------------------------------------------------------------
# /afk CLEAR + !!afk clear
# ------------------------------------------------------------

@afk.command(
    name="clear",
    description="Remove AFK status from every member in the server."
)
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
async def afk_clear(ctx: commands.Context):
    """Moderator-only removal of every AFK record in the server."""

    if ctx.guild is None or ctx.guild.id != GUILD_ID:
        return

    rows = clear_afk_statuses(ctx.guild.id)

    for user_id, original_nickname in rows:
        await restore_afk_nickname(
            ctx.guild,
            user_id,
            original_nickname
        )

    count = len(rows)

    if count == 0:
        message = "ℹ️ There are no active AFK statuses to clear."
    else:
        message = f"✅ Cleared AFK status from **{count}** member(s)."

    await send_afk_management_response(
        ctx,
        message,
        ephemeral=True
    )


# ------------------------------------------------------------
# /afk HELP + !!afk help
# ------------------------------------------------------------

@afk.command(
    name="help",
    description="Show all AFK commands and how to use them."
)
@commands.guild_only()
async def afk_help(ctx: commands.Context):
    """Show the AFK command list privately."""

    message = (
        "**💤 AFK Commands**\n\n"
        f"`{PREFIX}afk <reason> [media URL]` — Set/update your AFK.\n"
        f"`{PREFIX}afk set <reason> [media URL]` — Same as above.\n"
        f"`{PREFIX}afk list` — Moderator-only current AFK list.\n"
        f"`{PREFIX}afk remove @member` — Moderator-only remove for one member.\n"
        f"`{PREFIX}afk clear` — Moderator-only clear for everyone.\n\n"
        "Slash equivalents are available under `/afk`."
    )

    await send_afk_management_response(
        ctx,
        message,
        ephemeral=True
    )


# ------------------------------------------------------------
# AFK MESSAGE LISTENER
# ------------------------------------------------------------
#
# This is a separate listener so the existing media-thread
# on_message event remains unchanged.
# ------------------------------------------------------------

@bot.listen("on_message")
async def afk_message_listener(message: discord.Message):

    # Ignore bots and DMs.
    if message.author.bot:
        return

    if message.guild is None:
        return

    if message.guild.id != GUILD_ID:
        return

    # AFK management commands should not immediately remove the
    # author's AFK status. This lets a moderator manage AFK while AFK.
    command_text = message.content.strip().lower()
    is_afk_command = command_text == f"{PREFIX}afk" or command_text.startswith(f"{PREFIX}afk ")

    # --------------------------------------------------------
    # AUTO-REMOVE AFK WHEN THE MEMBER SPEAKS
    # --------------------------------------------------------

    current_afk = get_afk_status(message.guild.id, message.author.id)

    # The AFK-setting message is itself sent before the AFK record is created,
    # then the command handler creates the record during message processing.
    # Never treat that same message as the member's return message. Using the
    # message timestamp as a second guard also protects against any listener
    # ordering/race condition around prefix command processing.
    message_time = message.created_at.timestamp()
    afk_started_at = current_afk[3] if current_afk else None

    if (
        current_afk
        and not is_afk_command
        and afk_started_at is not None
        and message_time > afk_started_at
    ):
        original_nickname = current_afk[4]

        remove_afk_status(message.guild.id, message.author.id)

        if isinstance(message.author, discord.Member):
            await restore_afk_nickname(
                message.guild,
                message.author.id,
                original_nickname
            )

        try:
            await message.channel.send(
                f"👋 Welcome back, {message.author.mention}! "
                "Your AFK status has been removed."
            )
        except discord.HTTPException:
            pass

        # Do not also process mentions from the same return message.
        return

    # --------------------------------------------------------
    # RESPOND WHEN SOMEONE MENTIONS AN AFK MEMBER
    # --------------------------------------------------------

    if not message.mentions:
        return

    for member in message.mentions:
        if member.bot:
            continue

        afk_record = get_afk_status(message.guild.id, member.id)

        if afk_record is None:
            continue

        user_id, reason, media_url, created_at, _original_nickname = afk_record

        # The mention may resolve to a Member object, which has
        # display_name. For safety, fall back to a generic name.
        display_member = member

        try:
            # Keep the AFK notice as a NORMAL Discord message (no custom
            # embed). This lets Discord's own link preview render an attached
            # image/GIF/video naturally underneath the text, while the AFK
            # information stays visually similar to a normal Dyno-style
            # response.
            display_name = display_member.display_name

            # The member's server nickname already becomes [AFK] <name> while
            # they are AFK. Strip that existing prefix here and add exactly
            # one [AFK] in the public notice.
            if display_name.startswith("[AFK] "):
                display_name = display_name[6:]

            afk_text = (
                f"💤 **[AFK] {display_name} is currently AFK.**\n"
                f"**Reason:** {reason}\n"
                f"**AFK for:** {format_afk_duration(created_at)}"
            )

            # Put the media URL in the SAME message as the AFK text. Discord
            # then generates its native preview for supported image/GIF/video
            # URLs without us adding a second custom embed.
            if media_url:
                afk_text += f"\n\n{media_url}"

            await message.channel.send(
                content=afk_text,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        except discord.HTTPException:
            try:
                await message.channel.send(
                    f"💤 **[AFK] {display_name} is currently AFK.**\n"
                    f"**Reason:** {reason}\n"
                    f"**AFK for:** {format_afk_duration(created_at)}",
                    allowed_mentions=discord.AllowedMentions.none()
                )
            except discord.HTTPException:
                pass


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
setup_afk_database()


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