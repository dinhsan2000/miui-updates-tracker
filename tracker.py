#!/usr/bin/env python3.7
"""MIUI Updates Tracker - By XiaomiFirmwareUpdater"""

import json
from datetime import datetime
from glob import glob
from os import remove, rename, path, environ, system, makedirs
from requests import post, get
import fastboot
import recovery
import ao

# vars
GIT_OAUTH_TOKEN = environ['XFU']
BOT_TOKEN = environ['bottoken']
TG_CHAT = "@MIUIUpdatesTracker"
DISCORD_BOT_TOKEN = environ['DISCORD_BOT_TOKEN']
CHANNEL_ID = "484478392562089995"
CHANGES = []


def initialize():
    """
    creates required folders and copy old files
    """
    makedirs("stable_recovery", exist_ok=True)
    makedirs("stable_fastboot", exist_ok=True)
    makedirs("weekly_recovery", exist_ok=True)
    makedirs("weekly_fastboot", exist_ok=True)
    for file in glob('*_*/*.json'):
        if 'old_' in file:
            continue
        name = 'old_' + file.split('/')[-1].split('.')[0]
        rename(file, '/'.join(file.split('/')[:-1]) + '/' + name)


def load_devices():
    """
    load devices lists
    """
    with open('devices/names.json', 'r') as names_:
        names = json.load(names_)
    with open('devices/sr.json', 'r') as stable_recovery:
        sr_devices = json.load(stable_recovery)
    with open('devices/sf.json', 'r') as stable_fastboot:
        sf_devices = json.load(stable_fastboot)
    with open('devices/wr.json', 'r') as weekly_recovery:
        wr_devices = json.load(weekly_recovery)
    with open('devices/wf.json', 'r') as weekly_fastboot:
        wf_devices = json.load(weekly_fastboot)
    return names, sr_devices, sf_devices, wr_devices, wf_devices


def tg_post(message):
    """
    post message to telegram
    """
    params = (
        ('chat_id', TG_CHAT),
        ('text', message),
        ('parse_mode', "Markdown"),
        ('disable_web_page_preview', "yes")
    )
    telegram_url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
    telegram_req = post(telegram_url, params=params)
    telegram_status = telegram_req.status_code
    if telegram_status == 200:
        pass
    elif telegram_status == 400:
        print("Bad recipient / Wrong text format")
    elif telegram_status == 401:
        print("Wrong / Unauthorized token")
    else:
        print("Unknown error")
        print("Response: " + telegram_req.reason)
    return telegram_status


def discord_post(message):
    """
    post message to discord
    """
    discord_url = "https://discordapp.com/api/channels/{}/messages".format(CHANNEL_ID)
    headers = {"Authorization": "Bot {}".format(DISCORD_BOT_TOKEN),
               "User-Agent": "myBotThing (http://some.url, v0.1)",
               "Content-Type": "application/json", }
    data = json.dumps({"content": message})
    discord_req = post(discord_url, headers=headers, data=data)
    discord_status = discord_req.status_code
    if discord_status == 200:
        pass
    else:
        print("Discord Error")
    return discord_status


def git_commit_push():
    """
    git add - git commit - git push
=    """
    today = str(datetime.today()).split('.')[0]
    system("git add *_recovery/*.json *_fastboot/*.json && "
           "git -c \"user.name=XiaomiFirmwareUpdater\" -c "
           "\"user.email=xiaomifirmwareupdater@gmail.com\" "
           "commit -m \"sync: {}\" && "" \
           ""git push -q https://{}@github.com/XiaomiFirmwareUpdater/"
           "miui-updates-tracker.git HEAD:master"
           .format(today, GIT_OAUTH_TOKEN))


def diff(name):
    """
    compare json files
    """
    try:
        with open(f'{name}/{name}.json', 'r') as new,\
                open(f'{name}/old_{name}', 'r') as old_data:
            latest = json.load(new)
            old = json.load(old_data)
            first_run = False
    except FileNotFoundError:
        print(f"Can't find old {name} files, skipping")
        first_run = True
    if first_run is False:
        for new_, old_ in zip(latest, old):
            if not new_['version'] == old_['version']:
                CHANGES.append(new_)


def rolledback_check(codename, file, version, branch):
    """
    check if this update is rolled-back
    :return: Boolean
    """
    rolled_back = False
    try:
        old_data = json.loads(get(
            "https://raw.githubusercontent.com/XiaomiFirmwareUpdater/" +
            "xiaomifirmwareupdater.github.io/master/data/devices/" +
            "full/{}.json".format(codename.split("_")[0])).content)
    except json.decoder.JSONDecodeError:
        print(f"Working on {codename} for the first time!")
        old_data = []
    if 'MI' in file or 'Global' in file:
        region = 'Global'
    else:
        region = 'China'
    if branch == 'Stable':
        all_versions = [i for i in old_data if i['branch'] == 'stable']
    else:
        all_versions = [i for i in old_data if i['branch'] == 'weekly']
    check = [i for i in all_versions if i['versions']['miui'] == version and i['type'] == region]
    if check:
        print("{}: {} is rolled back ROM!".format(codename, version))
        rolled_back = True
    return rolled_back


def generate_message(update):
    """
    generates telegram message
    """
    android = update['android']
    codename = update['codename'].split('_')[0]
    device = update['device']
    download = update['download']
    filename = update['filename']
    version = update['version']
    if 'V' in version:
        branch = 'Stable'
    else:
        branch = 'Weekly'
    if 'eea_global' in filename or 'EU' in filename:
        region = 'EEA Global'
    elif 'in_global' in filename or 'IN' in filename:
        region = 'India'
    elif 'ru_global' in filename or 'RU' in filename:
        region = 'Russia'
    elif 'global' in filename or 'MI' in filename:
        region = 'Global'
    else:
        region = 'China'
    if '.tgz' in filename:
        rom_type = 'Fastboot'
    else:
        rom_type = 'Recovery'
    rolled_back = rolledback_check(codename, filename, version, region)
    message = ''
    if rolled_back:
        message += f'Rolled back {branch} {rom_type} update!\n'
    else:
        message += f"New {branch} {rom_type} update available!\n"
    message += f"*Device:* {device} \n" \
        f"*Codename:* #{codename} \n" \
        f"*Region:* {region} \n" \
        f"*Version:* `{version}` \n" \
        f"*Android:* {android} \n" \
        f"*Download*: [Here]({download}) \n" \
        "@MIUIUpdatesTracker | @XiaomiFirmwareUpdater"
    status = tg_post(message)
    if status == 200:
        print(f"{codename}: Telegram Message sent")
    discord_separator = '~~                                                     ~~'
    discord_message = message.replace('*', '**')\
        .replace('@MIUIUpdatesTracker | @XiaomiFirmwareUpdater', discord_separator)
    status = discord_post(discord_message)
    if status == 200:
        print(f"{codename}: Discord Message sent")


def main():
    """
    MIUI Updates Tracker
    """
    initialize()
    names, sr_devices, sf_devices, wr_devices, wf_devices = load_devices()
    # versions = {'stable_recovery': {'branch': '1', 'devices': sr_devices},
    #             'stable_fastboot': {'branch': 'F', 'devices': sf_devices},
    #             'weekly_recovery': {'branch': '0', 'devices': wr_devices},
    #             'weekly_fastboot': {'branch': 'X', 'devices': wf_devices}}
    versions = {'stable_fastboot': {'branch': 'F', 'devices': sf_devices},
                'weekly_fastboot': {'branch': 'X', 'devices': wf_devices}}
    ao_run = False
    for name, data in versions.items():
        # fetch based on version
        if "_recovery" in name:
            recovery.fetch(data['devices'], data['branch'], f'{name}/', names)
        elif "_fastboot" in name:
            fastboot.fetch(data['devices'], data['branch'], f'{name}/', names)
        print("Fetched " + name.replace('_', ' '))
        if "stable_fastboot" in name and ao_run is False:
            ao.main()
            ao_run = True
        # Merge files
        print("Creating JSON")
        json_files = [x for x in sorted(glob(f'{name}/*.json')) if not x.startswith('old_')]
        json_data = []
        for file in json_files:
            with open(file, "r") as json_file:
                json_data.append(json.load(json_file))
        with open(f'{name}/{name}', "w") as output:
            json.dump(json_data, output, indent=1)
        # Cleanup
        for file in glob(f'{name}/*.json'):
            remove(file)
        if path.exists(f'{name}/{name}'):
            rename(f'{name}/{name}', f'{name}/{name}.json')
        # Compare
        print("Comparing")
        diff(name)
    if CHANGES:
        for update in CHANGES:
            generate_message(update)
    else:
        print('No new updates found!')
    git_commit_push()
    for file in glob(f'*_*/old_*'):
        remove(file)


if __name__ == '__main__':
    main()
