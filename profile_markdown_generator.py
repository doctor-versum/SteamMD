import requests
import json
import datetime
import time
import os
import shutil
import re

# --- Configuration from environment variables or defaults ---
STEAM_API_KEY = os.getenv("STEAM_API_KEY") or ""
VANITY_URL = os.getenv("VANITY_URL") or ""
STEAM_ID = os.getenv("STEAM_ID") or ""
ASSET_PATH = os.getenv("ASSET_PATH") or "./generated/steamMD/"
FILE_PATH = os.getenv("FILE_PATH") or "./"
SKIP_STORING_ASSETS = os.getenv("SKIP_STORING_ASSETS")
if SKIP_STORING_ASSETS is not None:
    SKIP_STORING_ASSETS = SKIP_STORING_ASSETS.lower() in ("1", "true", "yes")
else:
    SKIP_STORING_ASSETS = False

# --- Configuration validation ---
if not STEAM_API_KEY:
    raise ValueError("STEAM_API_KEY must be set (environment variable or in script).")
if not VANITY_URL:
    if STEAM_ID:
        VANITY_URL = None  # Work directly with SteamID
    else:
        raise ValueError("Either VANITY_URL or STEAM_ID must be set.")

# --- Helper function to save images ---
def download_image(url, dest_path, label=None, emoji='🖼️', indent=0):
    prefix = ' ' * indent
    if label:
        print(f"{prefix}{emoji} Downloading {label} → {dest_path} ...", end=' ')
    try:
        r = requests.get(url, stream=True, timeout=10)
        if r.status_code == 200:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
            if label:
                print("✅ Done!")
            return True
        else:
            if label:
                print(f"❌ Failed (Status {r.status_code})")
    except Exception as e:
        if label:
            print(f"❌ Error: {e}")
    return False

# --- Get friend count ---
def get_friend_count(steamid):
    url = f"https://api.steampowered.com/ISteamUser/GetFriendList/v1/?key={STEAM_API_KEY}&steamid={steamid}"
    resp = requests.get(url).json()
    friends = resp.get('friendslist', {}).get('friends', [])
    return len(friends)

# --- Get community level ---
def get_community_level(steamid):
    url = f"https://api.steampowered.com/IPlayerService/GetSteamLevel/v1/?key={STEAM_API_KEY}&steamid={steamid}"
    resp = requests.get(url).json()
    return resp.get('response', {}).get('player_level', 'Unknown')

# --- Get achievements ---
def get_achievements(steam_id, appid):
    # Get achievement schema
    schema_url = "https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/"
    schema_params = {
        "key": STEAM_API_KEY,
        "appid": appid
    }
    schema_resp = requests.get(schema_url, params=schema_params)
    schema_data = schema_resp.json()

    # Get player achievements
    player_url = "https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/"
    player_params = {
        "key": STEAM_API_KEY,
        "steamid": steam_id,
        "appid": appid
    }
    player_resp = requests.get(player_url, params=player_params)
    player_data = player_resp.json()

    try:
        schema_achievements = {
            a['name']: a for a in schema_data['game']['availableGameStats']['achievements']
        }
        player_achievements = player_data['playerstats']['achievements']

        combined = []
        for pa in player_achievements:
            name = pa['apiname']
            achieved = pa['achieved']
            schema = schema_achievements.get(name, {})
            combined.append({
                'name': schema.get('displayName', name),
                'description': schema.get('description', ''),
                'icon': schema.get('icon'),
                'icon_gray': schema.get('icongray'),
                'achieved': achieved
            })

        return combined

    except (KeyError, TypeError):
        return []  # If anything goes wrong

def resolve_vanity_url(vanity):
    print("Getting user data...")
    url = f"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key={STEAM_API_KEY}&vanityurl={vanity}"
    resp = requests.get(url).json()
    if resp['response']['success'] == 1:
        print("- ✅ done\n")
        return resp['response']['steamid']
    else:
        raise ValueError(f"Vanity URL '{vanity}' could not be resolved.")

def get_player_summary(steamid):
    url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key={STEAM_API_KEY}&steamids={steamid}"
    resp = requests.get(url).json()
    players = resp.get('response', {}).get('players', [])
    if players:
        return players[0]
    else:
        raise ValueError(f"No profile found for SteamID {steamid}.")

def get_owned_games(steamid):
    print("Getting games...")
    url = f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key={STEAM_API_KEY}&steamid={steamid}&include_appinfo=1&include_played_free_games=1"
    resp = requests.get(url).json()
    games = resp.get('response', {}).get('games', [])
    print(f"- ✅ done ({len(games)} games)\n")
    return games

def get_store_details(appid, idx, total, game_name):
    print(f"- {game_name} ({idx}/{total})")
    print("    - Getting overall information")
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&l=english"
    resp = requests.get(url).json()
    data = resp.get(str(appid), {}).get('data', {})

    screenshots = data.get('screenshots', [])
    print(f"    - Getting screenshots")
    for i, _ in enumerate(screenshots, 1):
        print(f"        - Getting screenshot ({i}/{len(screenshots)})")
        # Only simulating here, as only URLs are fetched, no download
        time.sleep(0.05)
    return data

def md_escape(text):
    if not text:
        return ""
    return (text.replace("_", "\\_")
                .replace("*", "\\*")
                .replace("#", "\\#")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))

def safe_filename(name):
    # Only allow letters, numbers, _ and -
    return re.sub(r'[^A-Za-z0-9_\-]', '_', name)

def gfm_anchor(index, emojis, name):
    # Kombiniere Index, Emojis und Name wie in der Überschrift
    anchor_text = f"{index} {name} {' '.join(emojis)}"
    # Umlaute und ß ersetzen
    anchor_text = anchor_text.replace('ä', 'a').replace('ö', 'o').replace('ü', 'u').replace('Ä', 'a').replace('Ö', 'o').replace('Ü', 'u').replace('ß', 's')
    # Sonderzeichen/Satzzeichen (inkl. Emojis) entfernen
    anchor_text = re.sub(r'[^A-Za-z0-9 ]', '', anchor_text)
    # Leerzeichen zu Bindestrich, alles klein
    anchor_text = anchor_text.lower().replace(' ', '-')
    # Mehrere Bindestriche zu einem
    anchor_text = re.sub(r'-+', '-', anchor_text)
    return anchor_text

def replace_and_download_images_in_html(text, appid, asset_path, skip_assets):
    # Findet alle <img src="..."> und ![...](...)
    def repl_img(match):
        url = match.group(1)
        if skip_assets:
            return match.group(0)
        ext = os.path.splitext(url.split('?')[0])[1] or '.jpg'
        local_name = safe_filename(os.path.basename(url.split('?')[0]))
        local_path = os.path.join(asset_path, "descriptions", str(appid), local_name)
        if download_image(url, local_path, label=f"Description image for {appid}", emoji="🖼️", indent=8):
            local_md = local_path.replace('\\', '/')
            # Korrigiert: Tag mit /> schließen
            return f'<img src="{local_md}" />'
        else:
            return match.group(0)
    # HTML <img src="...">
    text = re.sub(r'<img[^>]*src=["\"](.*?)["\"][^>]*>', repl_img, text)
    # Markdown ![...](...)
    def repl_md(match):
        url = match.group(2)
        if skip_assets:
            return match.group(0)
        ext = os.path.splitext(url.split('?')[0])[1] or '.jpg'
        local_name = safe_filename(os.path.basename(url.split('?')[0]))
        local_path = os.path.join(asset_path, "descriptions", str(appid), local_name)
        if download_image(url, local_path, label=f"Description image for {appid}", emoji="🖼️", indent=8):
            local_md = local_path.replace('\\', '/')
            return f'![{match.group(1)}]({local_md})'
        else:
            return match.group(0)
    text = re.sub(r'!\[(.*?)\]\((.*?)\)', repl_md, text)
    return text

def main():
    print("🚀 Starting Steam profile export...")
    if VANITY_URL:
        print(f"🔎 Resolving vanity URL: {VANITY_URL}")
        steamid = resolve_vanity_url(VANITY_URL)
    else:
        print(f"🔎 Using SteamID: {STEAM_ID}")
        steamid = STEAM_ID
    print(f"👤 Getting player summary for {steamid} ...")
    profile = get_player_summary(steamid)
    print(f"🎮 Getting owned games ...")
    games = get_owned_games(steamid)

    # --- Shop Cover (Banner) zuerst herunterladen ---
    print(f"🖼️ Downloading all shop covers ...")
    cover_infos = []  # (index, name, cover_md, anchor, emojis)
    for i, game in enumerate(games, 1):
        appid = game['appid']
        name = game.get('name', 'Unknown')
        store_data = get_store_details(appid, i, len(games), name)
        header_img = store_data.get('header_image')
        if not SKIP_STORING_ASSETS and header_img:
            header_rel = os.path.join(ASSET_PATH, "covers", f"{appid}_header.jpg")
            download_image(header_img, header_rel, label=f"Cover for {name}", emoji="🖼️", indent=2)
            if os.path.exists(header_rel):
                cover_md = header_rel.replace('\\', '/')
            else:
                cover_md = header_img
        else:
            cover_md = header_img
        # Emojis für Plattformen vorbereiten
        platforms = store_data.get('platforms', {})
        platform_emojis = []
        if platforms.get('windows'): platform_emojis.append('🪟')
        if platforms.get('mac'): platform_emojis.append('🍏')
        if platforms.get('linux'): platform_emojis.append('🐧')
        anchor = gfm_anchor(i, platform_emojis, name)
        cover_infos.append((i, name, cover_md, anchor, platform_emojis))
        game['store_data'] = store_data

    print(f"📝 Writing markdown file ...")
    filename = os.path.join(FILE_PATH, f"steam_profile_{VANITY_URL or steamid}.md")
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# Steam Profile of [{profile.get('personaname')}](https://steamcommunity.com/profiles/{steamid})\n\n")
        # Avatar
        avatar_url = profile.get('avatarfull')
        if not SKIP_STORING_ASSETS and avatar_url:
            avatar_rel = os.path.join(ASSET_PATH, "covers", f"avatar_{steamid}.jpg")
            download_image(avatar_url, avatar_rel, label="Avatar", emoji="🧑", indent=2)
            if os.path.exists(avatar_rel):
                avatar_md = avatar_rel.replace('\\', '/')
            else:
                avatar_md = avatar_url
        else:
            avatar_md = avatar_url
        f.write(f"![]({avatar_md})\n\n")
        f.write(f"- **SteamID64:** {steamid}\n")
        last_online = profile.get('lastlogoff')
        if last_online:
            last_online_dt = datetime.datetime.fromtimestamp(last_online)
            last_online_str = last_online_dt.strftime('%Y-%m-%d || %H:%M')
        else:
            last_online_str = 'Unknown'
        f.write(f"- **Last online:** {last_online_str}\n")
        friend_count = get_friend_count(steamid)
        community_level = get_community_level(steamid)
        total_playtime = sum([g.get('playtime_forever', 0) for g in games]) // 60
        f.write(f"- **Community level:** {community_level}\n")
        f.write(f"- **Friends:** {friend_count}\n")
        f.write(f"- **Total playtime:** {total_playtime} hours\n")
        f.write(f"- **Profile description:**\n\n{md_escape(profile.get('realname', 'No information'))}\n\n")
        f.write(f"- **Country:** {profile.get('loccountrycode', 'Unknown')}\n")
        f.write(f"- **Profile URL:** [Link](https://steamcommunity.com/profiles/{steamid})\n\n")

        # --- Details-Block mit Cover-Übersicht ---
        f.write("<details>\n<summary>📜 Table of contents</summary>\n\n")
        for i, name, cover_md, anchor, platform_emojis in cover_infos:
            f.write(f'<a href="#{anchor}"><img src="{cover_md}" alt="cover image" width="80" style="vertical-align:middle; margin-right:8px;"/> {i}. {md_escape(name)} {' '.join(platform_emojis)}</a>\n --- \n')
        f.write("\n</details>\n\n")
        f.write(f"---\n\n")
        f.write(f"## Games ({len(games)})\n\n")

        for i, game in enumerate(games, 1):
            appid = game['appid']
            name = game.get('name', 'Unknown')
            store_data = game.get('store_data')
            platforms = store_data.get('platforms', {})
            platform_emojis = []
            if platforms.get('windows'): platform_emojis.append('🪟')
            if platforms.get('mac'): platform_emojis.append('🍏')
            if platforms.get('linux'): platform_emojis.append('🐧')
            anchor = gfm_anchor(i, platform_emojis, name)
            f.write(f'<a id="{anchor}"></a>\n')
            print(f"\n🎲 [{i}/{len(games)}] {name} (AppID: {appid})")
            playtime_hours = game.get('playtime_forever', 0) // 60
            print(f"  🔗 Getting store details ...")
            store_data = game.get('store_data') or get_store_details(appid, i, len(games), name)

            short_desc = store_data.get('short_description', 'No description')
            long_desc = store_data.get('detailed_description', 'No detailed description').replace('\n', ' ').replace('\r', ' ')
            # Download und Ersetzen von Bildern in den Descriptions
            short_desc = replace_and_download_images_in_html(short_desc, appid, ASSET_PATH, SKIP_STORING_ASSETS)
            long_desc = replace_and_download_images_in_html(long_desc, appid, ASSET_PATH, SKIP_STORING_ASSETS)
            header_img = store_data.get('header_image')
            if not SKIP_STORING_ASSETS and header_img:
                header_rel = os.path.join(ASSET_PATH, "covers", f"{appid}_header.jpg")
                download_image(header_img, header_rel, label=f"Header for {name}", emoji="🖼️", indent=4)
                if os.path.exists(header_rel):
                    header_md = header_rel.replace('\\', '/')
                else:
                    header_md = header_img
            else:
                header_md = header_img
            price_info = store_data.get('price_overview', {})
            price = price_info.get('final_formatted', 'Free or unknown')
            price_value = price_info.get('final', 0) / 100 if price_info else 0
            price_per_hour = f"{(price_value/playtime_hours):.2f} € / h" if playtime_hours > 0 and price_value > 0 else "-"
            developers = store_data.get('developers', [])
            publishers = store_data.get('publishers', [])
            genres = [g['description'] for g in store_data.get('genres', [])]
            screenshots = store_data.get('screenshots', [])
            platforms = store_data.get('platforms', {})
            # Platform emojis
            platform_emojis = []
            if platforms.get('windows'): platform_emojis.append('🪟')
            if platforms.get('mac'): platform_emojis.append('🍏')
            if platforms.get('linux'): platform_emojis.append('🐧')
            # Creator links
            creators = store_data.get('steam_deck_compatibility', {}).get('verified', [])
            if not creators:
                creators = store_data.get('developers', [])
            creator_links = []
            for c in creators:
                creator_links.append(f"[{md_escape(c)}](https://store.steampowered.com/search/?developer={c.replace(' ', '+')})")
            # Achievements
            achievements = get_achievements(steamid, appid)
            achieved = [a for a in achievements if a.get('achieved') == 1]
            total_ach = len(achievements)
            achieved_count = len(achieved)

            f.write(f"### {i}. {md_escape(name)} {' '.join(platform_emojis)}\n")
            if header_md:
                f.write(f'<img src="{header_md}" alt="{md_escape(name)}" width="400px">\n\n')
            f.write(f"- **Playtime:** {playtime_hours} hours\n")
            f.write(f"- **Price:** {price}\n")
            f.write(f"- **Price/hour:** {price_per_hour}\n")
            if creator_links:
                f.write(f"- **Creator:** {', '.join(creator_links)}\n")
            f.write(f"- **Developer:** {', '.join(developers) if developers else 'Unknown'}\n")
            f.write(f"- **Publisher:** {', '.join(publishers) if publishers else 'Unknown'}\n")
            f.write(f"- **Genres:** {', '.join(genres) if genres else 'Unknown'}\n")
            f.write(f"- **Achievements:** {achieved_count}/{total_ach}\n")
            f.write(f"\n**Short description:** {md_escape(short_desc)}\n\n")
            f.write(f"<details>\n<summary>Detailed description</summary>\n\n{long_desc}\n\n</details>\n\n")

            if achievements:
                print(f"  🏆 Downloading achievement icons ...")
                f.write("<details>\n<summary>Achievements Details</summary>\n\n<table>\n")
                for a in achievements:
                    icon_url = (a.get('icon') or a.get('icon_gray')) if a.get('achieved') else (a.get('icon_gray') or a.get('icon'))
                    if not icon_url:
                        icon_url = 'https://community.cloudflare.steamstatic.com/public/images/skin_1/icon_question.gif'
                    if not SKIP_STORING_ASSETS and icon_url:
                        ach_name = safe_filename(a.get('name',''))
                        icon_rel = os.path.join(ASSET_PATH, "achievements", str(appid), f"{ach_name}.jpg")
                        download_image(icon_url, icon_rel, label=f"Achievement '{a.get('name','')}'", emoji="🏅", indent=6)
                        if os.path.exists(icon_rel):
                            icon_md = icon_rel.replace('\\', '/')
                        else:
                            icon_md = icon_url
                    else:
                        icon_md = icon_url
                    name_ = md_escape(a.get('name', 'No name'))
                    desc = md_escape(a.get('description', 'No description'))
                    percent = '🟩' if a.get('achieved') else '🟥'
                    # Only show if at least name, description or icon is present
                    if name_ or desc or icon_md:
                        f.write(f"<tr><td><img src='{icon_md}' width='32'></td><td>{percent}</td><td>{name_}</td><td>{desc}</td>\n")
                f.write("\n</table>\n</details>\n\n")
            # Screenshots
            if screenshots:
                print(f"  📸 Downloading screenshots ...")
                f.write("<details>\n<summary>Screenshots</summary>\n\n")
                for idx, s in enumerate(screenshots):
                    img_url = s.get('path_full')
                    if img_url:
                        if not SKIP_STORING_ASSETS:
                            img_rel = os.path.join(ASSET_PATH, "screenshots", str(appid), f"{idx+1}.jpg")
                            download_image(img_url, img_rel, label=f"Screenshot {idx+1} for {name}", emoji="📸", indent=6)
                            if os.path.exists(img_rel):
                                img_md = img_rel.replace('\\', '/')
                            else:
                                img_md = img_url
                        else:
                            img_md = img_url
                        f.write(f'<img src="{img_md}" alt="Screenshot" width="400px" style="margin:5px 0;">  \n')
                f.write("\n</details>\n\n")

            f.write(f"---\n\n")

            time.sleep(0.3)  # damit API nicht blockt
    print(f"\n✅ Markdown file '{filename}' created.")

if __name__ == "__main__":
    main()