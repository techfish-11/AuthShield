import discord
from discord.ext import commands
import os
import sys
from dotenv import load_dotenv
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 現在のディレクトリをPythonパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# .envファイルから環境変数をロード
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="as!", intents=intents)

class CogReloader(FileSystemEventHandler):
    def __init__(self, bot):
        self.bot = bot
        self.loop = asyncio.get_event_loop()
        self.pending_reloads = set()

    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            rel_path = os.path.relpath(event.src_path, './src')
            rel_path = os.path.splitext(rel_path)[0]
            module_name = f'src.{rel_path.replace(os.sep, ".")}'
            if module_name in self.pending_reloads:
                return
            self.pending_reloads.add(module_name)
            self.loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self._reload_and_clear(module_name))
            )

    async def _reload_and_clear(self, module_name):
        try:
            await self.reload_cog(module_name)
        finally:
            self.pending_reloads.discard(module_name)

    async def reload_cog(self, module_name):
        try:
            await self.bot.reload_extension(module_name)
            print(f"リロード完了: {module_name}")
            await self.bot.tree.sync()
            print("コマンド再同期完了")
        except Exception as e:
            print(f"リロード失敗 {module_name}: {e}")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

    # コグ（拡張機能）を並列にロード
    tasks = []
    for root, _, files in os.walk('./src'):
        for file in files:
            if file.endswith('.py'):
                relative_path = os.path.relpath(root, './src').replace(os.sep, '.')
                module_name = f'src.{relative_path}.{file[:-3]}' if relative_path != '.' else f'src.{file[:-3]}'
                tasks.append(bot.load_extension(module_name))
    await asyncio.gather(*tasks)
    await bot.tree.sync()
    print("All cogs loaded and commands synced!")
    
    # watchdogの設定と起動（非同期タスクとして実行）
    event_handler = CogReloader(bot)
    observer = Observer()
    observer.schedule(event_handler, path='./src', recursive=True)
    observer.start()
    print("Watchdogを起動しました。srcディレクトリを監視中...")
    
    # ステータス自動更新タスクを開始
    async def update_status():
        while True:
            await bot.change_presence(
                activity=discord.Game(
                    name=f"{len(bot.guilds)}Server || {round(bot.latency * 1000)}ms"
                )
            )
            await asyncio.sleep(30)
    
    asyncio.create_task(update_status())
    print("定期タスクを開始しました")

bot.run(TOKEN)