import discord
from discord.ext import commands
import json
import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get token and user ID from environment variables
TOKEN = os.getenv('DISCORD_TOKEN')
ALLOWED_USER_ID = int(os.getenv('ALLOWED_USER_ID'))

# Set up intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

# Initialize bot
bot = commands.Bot(command_prefix='!', intents=intents)

class MemeManager:
    def __init__(self, filename='memes.txt'):
        self.filename = filename
        self.posted_filename = 'posted_memes.txt'
        self.memes = []
        self.posted_memes = {}
        self.load_memes()
        self.load_posted_memes()

    def load_memes(self):
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as file:
                    self.memes = json.load(file)
        except Exception as e:
            print(f"Error loading memes: {e}")
            self.memes = []

    def save_memes(self):
        try:
            with open(self.filename, 'w') as file:
                json.dump(self.memes, file, indent=4)
        except Exception as e:
            print(f"Error saving memes: {e}")

    def load_posted_memes(self):
        try:
            if os.path.exists(self.posted_filename):
                with open(self.posted_filename, 'r') as file:
                    self.posted_memes = json.load(file)
            else:
                self.posted_memes = {}
        except Exception as e:
            print(f"Error loading posted memes: {e}")
            self.posted_memes = {}

    def save_posted_memes(self):
        try:
            with open(self.posted_filename, 'w') as file:
                json.dump(self.posted_memes, file, indent=4)
        except Exception as e:
            print(f"Error saving posted memes: {e}")

    def add_meme(self, url):
        if url not in self.memes:
            self.memes.append(url)
            self.save_memes()
            return True
        return False

    def remove_meme(self, url):
        if url in self.memes:
            self.memes.remove(url)
            self.save_memes()
            return True
        return False

    def get_unposted_memes(self, channel_id):
        channel_key = str(channel_id)  # Convert channel ID to string
        if channel_key not in self.posted_memes:
            self.posted_memes[channel_key] = []
        return [meme for meme in self.memes if meme not in self.posted_memes[channel_key]]

    def mark_as_posted(self, channel_id, meme_url):
        channel_key = str(channel_id)
        if channel_key not in self.posted_memes:
            self.posted_memes[channel_key] = []
        if meme_url not in self.posted_memes[channel_key]:
            self.posted_memes[channel_key].append(meme_url)
            self.save_posted_memes()

# Initialize MemeManager
meme_manager = MemeManager()

@bot.event
async def on_ready():
    print('Bot is online')
    print(f'Logged in as {bot.user.name}')
    print(f'Bot ID: {bot.user.id}')
    print(f'Loaded {len(meme_manager.memes)} memes')

@bot.command(name='upload_memes')
async def upload_memes(ctx):
    # Check if user is authorized
    if ctx.author.id != ALLOWED_USER_ID:
        await ctx.send("You don't have permission to use this command!")
        return

    # Check if command is used in DMs
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("Please use this command in DMs!")
        return

    await ctx.send("Please send your images or videos. Type 'done' when you're finished.")

    def check(m):
        return m.author.id == ALLOWED_USER_ID and m.channel == ctx.channel

    # List of allowed file extensions
    allowed_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.mp4', '.mov', '.webm']

    while True:
        try:
            message = await bot.wait_for('message', timeout=60.0, check=check)
            
            if message.content.lower() == 'done':
                await ctx.send("Upload session completed!")
                break

            if message.attachments:
                for attachment in message.attachments:
                    if any(attachment.filename.lower().endswith(ext) for ext in allowed_extensions):
                        # Check file size (8MB limit for free Discord servers)
                        if attachment.size > 8 * 1024 * 1024:  # 8MB in bytes
                            await ctx.send(f"Warning: {attachment.filename} is over 8MB and might not play in some servers!")
                            
                        if meme_manager.add_meme(attachment.url):
                            await ctx.send(f"Added: {attachment.url}")
                        else:
                            await ctx.send(f"This file was already in the list!")
                    else:
                        await ctx.send(f"Skipped {attachment.filename} - not a supported format. Allowed formats: {', '.join(allowed_extensions)}")
            else:
                await ctx.send("No files found in message. Please send images/videos or type 'done' to finish.")

        except TimeoutError:
            await ctx.send("Upload session timed out after 60 seconds of inactivity.")
            break

@bot.command(name='removememe')
async def remove_meme(ctx, url):
    if ctx.author.id != ALLOWED_USER_ID:
        await ctx.send("You don't have permission to use this command!")
        return
        
    if meme_manager.remove_meme(url):
        await ctx.send(f'Meme removed successfully!')
    else:
        await ctx.send('That meme was not found in the list!')

@bot.command(name='listmemes')
async def list_memes(ctx):
    if meme_manager.memes:
        meme_list = '\n'.join(meme_manager.memes)
        await ctx.send(f'Stored memes:\n{meme_list}')
    else:
        await ctx.send('No memes stored yet!')

@bot.command(name='post_memes')
async def post_memes(ctx, *, channel_name='general'):
    if not ctx.guild:
        await ctx.send("This command can only be used in a server!")
        return

    # Handle channel mentions
    if ctx.message.channel_mentions:
        target_channel = ctx.message.channel_mentions[0]
    else:
        channel_name = channel_name.strip('#').lower()
        target_channel = discord.utils.get(ctx.guild.channels, 
                                         name=channel_name.replace(' ', '-'))

    if not target_channel:
        await ctx.send(f"Couldn't find the #{channel_name} channel!")
        return

    # Get unposted memes for this channel
    unposted_memes = meme_manager.get_unposted_memes(target_channel.id)

    if not unposted_memes:
        await ctx.send("No new memes to post!")
        return

    # Send single status message
    message_sent = False  # Flag to track if we've sent the completion message
    
    try:
        for meme_url in unposted_memes:
            await target_channel.send(meme_url)
            meme_manager.mark_as_posted(target_channel.id, meme_url)
            await asyncio.sleep(1)
        
        if not message_sent:
            await ctx.send("Finished posting all new memes!")
            message_sent = True
            
    except Exception as e:
        if not message_sent:
            await ctx.send(f"An error occurred while posting memes: {str(e)}")

@bot.event
async def on_message_delete(message):
    try:
        # Check if the deleted message was from our bot
        if message.author.id != bot.user.id:
            return
            
        # Function to extract meme URL from message
        def extract_meme_url(content):
            for meme in meme_manager.memes:
                if meme in content:
                    return meme
            return None

        # Check if the message contains one of our memes
        meme_url = extract_meme_url(message.content)
        if meme_url:
            try:
                # Get the audit log entry for this deletion
                async for entry in message.guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=1):
                    if entry.target.id == bot.user.id:
                        deleter = entry.user
                        # Don't repost if the bot owner deleted it
                        if deleter.id == ALLOWED_USER_ID:
                            return
                        await message.channel.send(f"{deleter.mention} deleted my meme! Here it is again:")
                        await message.channel.send(meme_url)
                        return

                # If we couldn't find the deleter in audit logs
                await message.channel.send("Someone deleted my meme! Here it is again:")
                await message.channel.send(meme_url)
                        
            except Exception as e:
                print(f"Failed to repost meme: {e}")
                # Try to repost anyway if there was an error checking audit logs
                await message.channel.send("Someone deleted my meme! Here it is again:")
                await message.channel.send(meme_url)

    except Exception as e:
        print(f"Error in on_message_delete: {e}")

@bot.command(name='clear_posted')
async def clear_posted(ctx, channel_name=None):
    if ctx.author.id != ALLOWED_USER_ID:
        await ctx.send("You don't have permission to use this command!")
        return

    if ctx.message.channel_mentions:
        target_channel = ctx.message.channel_mentions[0]
    elif channel_name:
        channel_name = channel_name.strip('#')
        target_channel = discord.utils.get(ctx.guild.channels, name=channel_name)
    else:
        target_channel = ctx.channel

    if not target_channel:
        await ctx.send(f"Couldn't find the specified channel!")
        return

    channel_key = str(target_channel.id)
    if channel_key in meme_manager.posted_memes:
        meme_manager.posted_memes[channel_key] = []
        meme_manager.save_posted_memes()
        await ctx.send(f"Cleared posted memes tracking for #{target_channel.name}")
    else:
        await ctx.send(f"No posted memes were tracked for #{target_channel.name}")

# Replace with your bot token
bot.run(TOKEN)