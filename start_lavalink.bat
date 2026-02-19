@echo off
cd lavalink
if not exist Lavalink.jar (
    echo Lavalink.jar not found! Please download it from https://github.com/lavalink-devs/Lavalink/releases
    echo and place it in the lavalink folder.
    pause
    exit /b
)
echo Starting Lavalink...
java -jar Lavalink.jar
pause
