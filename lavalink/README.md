# Lavalink Setup

This directory contains the required configuration to run Lavalink for Flake Music, with the necessary plugins and settings to support playing music from YouTube, Spotify, and more.

## Prerequisites

1.  **Java 17 or newer**: Lavalink requires Java to run.
2.  **Lavalink Runtime**: Download the `Lavalink.jar` file from the [official Lavalink releases page](https://github.com/lavalink-devs/Lavalink/releases) (ensure you use version v4.0.0 or higher). Place it in this directory.

## Configuration Setup

The provided `application.yml` disables Lavalink's default native YouTube capabilities and instead relies on `dev.lavalink.youtube:youtube-plugin:1.18.0` and `com.github.topi314.lavasrc:lavasrc-plugin:4.8.1`. This provides significantly better stability against YouTube blocks.

Before running Lavalink, you **must** update the `application.yml` file with your own credentials where placeholders exist:

### 1. Spotify (Optional but Recommended)
To support Spotify links (`spsearch:`, etc.):
1.  Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
2.  Create an application to obtain your **Client ID** and **Client Secret**.
3.  Replace `YOUR_SPOTIFY_CLIENT_ID` and `YOUR_SPOTIFY_CLIENT_SECRET` in `application.yml`.

### 2. YouTube Authentication (Crucial for Reliability)
YouTube frequently blocks datacenter IPs from streaming audio. The `youtube-plugin` requires authentication to bypass restrictions.

**OAuth Flow (Refresh Token)**
The configuration uses OAuth flow. If you do not have a refresh token:
1.  Leave `refreshToken: "YOUR_YOUTUBE_REFRESH_TOKEN"` as empty or `""`, and start Lavalink.
2.  Check the server console. It will prompt you with a link (e.g., `https://www.google.com/device`) and a code.
3.  **IMPORTANT:** Log in using a **burner** Google account. Entering this code using your main account could place your account at risk of suspension!
4.  Once authorized, Lavalink will print your permanent `refreshToken` in the console. Paste that back into `application.yml` at `refreshToken: "1//..."` so you stay logged in permanently.

**PoToken (Visitor Data)**
Additionally, the web clients rely on a Proof of Authorization token (`poToken`) to avoid Captchas.
1.  Use the `youtube-po-token-generator` tool to generate a payload. Example via Node.js tool:
    ```bash
    npx -y youtube-po-token-generator
    ```
2.  Replace `YOUR_YOUTUBE_POTOKEN` and `YOUR_YOUTUBE_VISITORDATA` with the values generated.

## Running the Server

Once configuration is ready, run Lavalink with:

```bash
java -jar Lavalink.jar
```

The server will start on port `25566` (as configured at the bottom of the yaml file) and accepts the default password `youshallnotpass`. Make sure your bot's `.env` configuration matches this endpoint!
