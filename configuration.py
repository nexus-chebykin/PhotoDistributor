from __future__ import annotations
import pathlib, os
import logging
from typing import List, Set

logging.basicConfig(format='[%(levelname)s] %(message)s', level=logging.DEBUG)
logging.getLogger('exifread').setLevel(logging.ERROR)

'''This file contains global configuration, shared by all classes'''

def parseConfig():
    for line in open(pathlib.Path(os.path.realpath(__file__)).parent / "formats.conf"):  # Directory with script
        if not line:
            continue
        line = line.split('#')
        if line[0]:
            config.FORMATS.add(line[0].upper().strip())
    logging.info("Formats, which are considered to be photo / video :" +
                 ", ".join(config.FORMATS))

class Configuration:
    FORMATS = set()
    THRESHOLD = 50
    # Two consecutive month will get merged if they together contain <= 2 * THRESHOLD files
    WEIRD_FILES_DIR_NAME = "WeirdFiles"

    sourceFolders: List[pathlib.Path] = []
    destinationFolder: pathlib.Path

    def __init__(self):
        pass


config = Configuration()
parseConfig()
