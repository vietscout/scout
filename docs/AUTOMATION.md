# Profile Automation Guide (Blog RSS, YouTube, Spotify & WakaTime)

Automating **real content** (new articles, videos, coding hours, or music) keeps your profile alive without violating GitHub's anti-spam policies.

---

## 1. Auto-Sync Latest Blog Posts (`blog-rss` plugin)

1. Run `setup.py` with `--plugins blog-rss --var BLOG_RSS_URL=https://yourblog.com/index.xml`.
2. Ensure your `README.md` includes the marker tags:
   ```markdown
   <!-- BLOG-POST-LIST:START -->
   <!-- BLOG-POST-LIST:END -->
   ```
3. In your GitHub repository, go to **Actions → Sync Latest Blog Posts → Run workflow** to test immediately.

---

## 2. Auto-Sync Latest YouTube Videos (`youtube-rss` plugin)

Every YouTube channel has a built-in RSS feed:
```text
https://www.youtube.com/feeds/videos.xml?channel_id=YOUR_CHANNEL_ID
```
1. Find your `UC...` Channel ID in YouTube Studio (**Settings → Channel → Advanced settings** or your channel URL).
2. Run `setup.py` with `--plugins youtube-rss --var YOUTUBE_CHANNEL_ID=UC...`.
3. Note that `comment_tag_name: "YOUTUBE"` is set in `youtube-rss-sync.yml` so it never collides with your Blog RSS section.

---

## 3. Display Spotify Now Playing (`spotify-now-playing` plugin)

1. Authenticate your Spotify account with a public widget provider such as [spotify-github-profile](https://github.com/kittinan/spotify-github-profile) to obtain your `SPOTIFY_UID`.
2. Pass `--plugins spotify-now-playing --var SPOTIFY_UID=your_uid` to `setup.py`.

---

## 4. Auto-Update WakaTime Coding Stats (`wakatime-stats` plugin)

1. Copy your API Key from [WakaTime Account Settings](https://wakatime.com/settings/api-key).
2. In your `<username>/<username>` repository, go to **Settings → Secrets and variables → Actions → New repository secret**.
3. Create a secret named `WAKATIME_API_KEY` with your key.
4. Run `setup.py` with `--plugins wakatime-stats`.

---

## Best Practices for Clean Automation

- **Schedule once per day (or every 12 hours):** Frequent 5-minute crons waste Actions minutes and clutter your commit history.
- **Skip empty commits:** `gautamkrishnar/blog-post-workflow` only commits when new posts appear—keeping your contribution graph authentic.
