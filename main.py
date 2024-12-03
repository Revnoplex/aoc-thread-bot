#!./.venv/bin/python3.12
import datetime
import errno
import gzip
import os
import shutil
import socket
import sys
import discord
from discord.ext import tasks
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv


load_dotenv("./.env")


if __name__ == "__main__":
    print("starting...")


def sd_notify(message: bytes):
    """From https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html#Standalone%20Implementations"""

    if not message:
        raise ValueError("notify() requires a message")

    socket_path = os.environ.get("NOTIFY_SOCKET")
    if not socket_path:
        return

    if socket_path[0] not in ("/", "@"):
        raise OSError(errno.EAFNOSUPPORT, "Unsupported socket type")

    # Handle abstract socket.
    if socket_path[0] == "@":
        socket_path = "\0" + socket_path[1:]

    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM | socket.SOCK_CLOEXEC) as sock:
        sock.connect(socket_path)
        sock.sendall(message)


class AoCTBot(discord.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.thread_task.start()
        self.aoc_channel = None

    async def on_ready(self):
        if "--systemd" in sys.argv:
            sd_notify(
                b"READY=1\nSTATUS=Logged on as "
                + self.user.__str__().encode("utf-8")
            )
        print(f"Logged on as\033[1;92m {self.user}\033[0m")

        channel_env = os.getenv(f"AOC_CHANNEL")
        if (not channel_env) or (not channel_env.isdecimal()):
            raise RuntimeError("Missing or bad AOC_CHANNEL env variable")

        self.aoc_channel = self.get_channel(int(channel_env))
        assert self.aoc_channel is not None

        if not isinstance(self.aoc_channel, discord.TextChannel):
            raise RuntimeError("Specified channel is not text channel")

        if (not self.aoc_channel.can_send()) or (
                not self.aoc_channel.permissions_for(self.aoc_channel.guild.me).create_public_threads
        ):
            raise RuntimeError(
                "Missing appropriate permissions to create thread. "
                "Please make sure I have 'send messages' and "
                "'create public threads' permissions in the set channel"
            )

    @tasks.loop(
        time=datetime.time(5, 0, tzinfo=datetime.timezone.utc)
    )
    async def thread_task(self):
        await self.wait_until_ready()

        current_time = datetime.datetime.now(tz=datetime.timezone.utc)
        if current_time.month != 12 or (not 1 <= current_time.day <= 25):
            return

        thread_title = f"\U0001f31f AOC Day {current_time.day} Answers Thread"

        message = await self.aoc_channel.send("## " + thread_title)
        await self.aoc_channel.create_thread(name=thread_title, message=message)


intents = discord.Intents.default()
client = AoCTBot(intents=intents)


def namer(name):
    return name + ".gz"


def rotator(source, destination):
    with open(source, 'rb') as f_in:
        with gzip.open(destination, 'wb') as f_out:
            # noinspection PyTypeChecker
            shutil.copyfileobj(f_in, f_out)
    os.remove(source)


logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    filename='discord.log',
    encoding='utf-8',
    mode='w',
    maxBytes=512*1024,
    backupCount=16
)
handler.rotator = rotator
handler.namer = namer
# noinspection SpellCheckingInspection
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


client.run(os.getenv("TOKEN"))
