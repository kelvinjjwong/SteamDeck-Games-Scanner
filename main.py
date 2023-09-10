import os
import subprocess
import sys

from PyQt5.QtCore import QPoint, QFile, QTextStream
from PyQt5.QtWidgets import QApplication, QWidget
import breeze_resources_pyqt5
import asyncio
import pickle
import hashlib
from cryptography.fernet import Fernet


def screenCenter():
    n = app.desktop().screenCount()
    x = app.desktop().screen().rect().center().x() * n
    y = app.desktop().screen().rect().center().y()
    return QPoint(x, y)


def applyBreezeStyleSheets(app):
    style_sheet_file = QFile(":/dark/stylesheet.qss")
    style_sheet_file.open(QFile.ReadOnly | QFile.Text)
    style_sheet_stream = QTextStream(style_sheet_file)
    app.setStyleSheet(style_sheet_stream.readAll())

async def get_local_games():
    games = []

    for game in os.listdir("/home/deck/.steam/steam/steamapps/common"):
        if not game.startswith(".") and not game.startswith("Proton"):
            games.append(game)

    games.sort()
    return games

class SMBError(OSError): pass

async def get_microsd_games():
    games = []

    for game in os.listdir("/run/media/mmcblk0p1/steamapps/common"):
        if not game.startswith(".") and not game.startswith("Proton"):
            games.append(game)

    games.sort()
    return games

async def get_shared_games(config):
    games = []
    folders = await smb_lsdir("/Games/Games.SteamDeck", config)
    for game in folders:
        if game.endswith(".zip") and not game.startswith("."):
            games.append(game.removesuffix(".zip"))

    games.sort()
    return games

async def get_not_archived_games(config):
    (local_games, microsd_games, archived_games) = await asyncio.gather(
        get_local_games(),
        get_microsd_games(),
        get_shared_games(config)
    )

    installed_games = list(set(local_games).union(set(microsd_games)))
    not_archived_games = [game for game in installed_games if game not in archived_games]
    not_archived_games.sort()
    return not_archived_games


async def smb_lsdir(path, config):
    key = config["s"]
    fernet = Fernet(key)
    folders = []
    cmd = ["smbclient"]
    cmd.extend(["--user=%s" % fernet.decrypt(config["uu"]).decode()])
    cmd.extend(["-p=%s" % fernet.decrypt(config["pp"]).decode()])
    cmd.extend(["--password=%s" % fernet.decrypt(config["mm"]).decode()])
    cmd.extend(["'\\%s'" % fernet.decrypt(config["vv"]).decode().replace("/", "\\")])
    cmd.extend(["-c", "'ls %s\*'" % path.replace("/", "\\")])
    cmdline = ' '.join(cmd)
    try:
        result = subprocess.check_output(cmdline, stderr=subprocess.PIPE, shell=True)
    except:
        raise SMBError("Samba connection failed or incorrect path")
    for line in result.strip().decode('utf-8').splitlines():
        if not line.__contains__("blocks of size") and not line.endswith("blocks available"):
            parts = line.split("     ")
            name = parts[0].strip()
            if not name.startswith("."):
                folders.append(name)
    return folders


def saveConfig(config):
    path = '/home/deck/.SteamDeckGamesScanner/config.pk'
    if not os.path.exists(path):
        os.makedirs('/home/deck/.SteamDeckGamesScanner')
    with open('/home/deck/.SteamDeckGamesScanner/config.pk', 'wb') as fp:
        pickle.dump(config, fp)



def loadConfig():
    config = {}
    path = '/home/deck/.SteamDeckGamesScanner/config.pk'
    if os.path.exists(path):
        with open(path, 'rb') as fp:
            config = pickle.load(fp)
        return config
    else:
        saveConfig({})
    return {}

def encrypt(text):
    hash_object = hashlib.sha256()
    hash_object.update(text.encode())
    return hash_object.hexdigest()


if __name__ == '__main__':
    config = loadConfig()
    if len(config) == 0:
        key = Fernet.generate_key()
        fernet = Fernet(key)
        config = {"uu": fernet.encrypt("xxxx".encode()),
                  "mm": fernet.encrypt("yyyy".encode()),
                  "pp": fernet.encrypt("445".encode()),
                  "vv": fernet.encrypt("/path/to/zzzz".encode()),
                  "s": key
                  }
        saveConfig(config)
    app = QApplication(sys.argv)
    applyBreezeStyleSheets(app)

    w = QWidget()
    w.resize(800, 600)
    w.move(screenCenter() - w.rect().center())
    w.setWindowTitle('Games Scanner')

    games = asyncio.run(get_not_archived_games(config))
    print(games)

    # w.show()

    sys.exit(app.exec_())
