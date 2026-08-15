import os
import discord
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# The thread where media-only rules apply
MEDIA_THREAD_IDS = {
    1538218357508153455
}

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    print("SCB Personal is online!")


@client.event
async def on_message(message):

    # Ignore messages from bots
    if message.author.bot:
        return

    # Only apply the rule to our selected thread(s)
    if message.channel.id not in MEDIA_THREAD_IDS:
        return

    # If the message has an attachment, allow it
    if message.attachments:
        return

    # No attachment = delete the message
    try:
        await message.delete()
        print(
            f"Deleted text-only message from {message.author} "
            f"in thread {message.channel.name}"
        )
    except discord.Forbidden:
        print("ERROR: I don't have permission to delete this message.")
    except discord.HTTPException as e:
        print(f"ERROR: Discord failed to delete the message: {e}")


client.run(TOKEN)