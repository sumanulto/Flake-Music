import discord
import wavelink

class MusicView(discord.ui.View):
    def __init__(self, bot, player: wavelink.Player, dashboard_url: str | None = None):
        super().__init__(timeout=None)
        self.bot = bot
        self.player = player
        if dashboard_url:
            self.add_item(
                discord.ui.Button(
                    label="Dashboard",
                    style=discord.ButtonStyle.link,
                    url=dashboard_url,
                    row=2,
                )
            )
        self.update_buttons()

    def update_buttons(self):
        # Update Play/Pause button
        play_pause_btn = [x for x in self.children if x.custom_id == "play_pause"][0]
        if self.player.paused:
            play_pause_btn.emoji = "▶️"
            play_pause_btn.style = discord.ButtonStyle.success
        else:
            play_pause_btn.emoji = "⏸️" 
            play_pause_btn.style = discord.ButtonStyle.secondary

        # Update Loop button
        loop_btn = [x for x in self.children if x.custom_id == "loop"][0]
        if self.player.queue.mode == wavelink.QueueMode.normal:
            loop_btn.emoji = "🔁"
            loop_btn.style = discord.ButtonStyle.secondary
        elif self.player.queue.mode == wavelink.QueueMode.loop_all:
            loop_btn.emoji = "🔁"
            loop_btn.style = discord.ButtonStyle.success
        elif self.player.queue.mode == wavelink.QueueMode.loop:
            loop_btn.emoji = "🔂"
            loop_btn.style = discord.ButtonStyle.success

    async def refresh_ui(self, interaction: discord.Interaction):
        self.update_buttons()
        await interaction.message.edit(view=self)
        # Also trigger cog refresh to ensure consistency if needed, 
        # but editing the message directly here is faster for the button click response.
        
    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, row=0, custom_id="prev")
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Wavelink doesn't have a built-in previous, usually requires history management
        # For now, just defer or notify
        if not self.player: return
        history = getattr(self.player.queue, "history", None)
        if history:
             # Logic to play previous would go here. 
             # Wavelink 3.x Queue has history?
             await interaction.response.send_message("Previous track logic to be implemented.", ephemeral=True)
        else:
             await interaction.response.send_message("No history available.", ephemeral=True)

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.secondary, row=0, custom_id="play_pause")
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player: return
        await self.player.pause(not self.player.paused)
        await self.refresh_ui(interaction)
        await interaction.response.defer()

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=0, custom_id="next")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player: return
        await self.player.skip(force=True)
        await interaction.response.defer()

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, row=0, custom_id="stop")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player: return
        await self.player.stop()
        self.player.queue.clear()
        await self.player.disconnect()
        await interaction.response.send_message("Stopped.", ephemeral=True)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=1, custom_id="shuffle")
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player: return
        if hasattr(self.player.queue, "shuffle"):
            self.player.queue.shuffle()
        else:
            import random
            random.shuffle(self.player.queue)
        await interaction.response.send_message("Shuffled queue.", ephemeral=True)
        # Refresh to show queue update if we had a queue list in embed
        
    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, row=1, custom_id="vol_down")
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player: return
        vol = max(0, self.player.volume - 10)
        await self.player.set_volume(vol)
        await interaction.response.defer()
        
    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=1, custom_id="vol_up")
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player: return
        vol = min(100, self.player.volume + 10)
        await self.player.set_volume(vol)
        await interaction.response.defer()

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=1, custom_id="loop")
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player: return
        
        # Cycle: Normal -> Loop All -> Loop One -> Normal
        if self.player.queue.mode == wavelink.QueueMode.normal:
            self.player.queue.mode = wavelink.QueueMode.loop_all
        elif self.player.queue.mode == wavelink.QueueMode.loop_all:
             self.player.queue.mode = wavelink.QueueMode.loop
        else:
             self.player.queue.mode = wavelink.QueueMode.normal
             
        await self.refresh_ui(interaction)
        await interaction.response.defer()
