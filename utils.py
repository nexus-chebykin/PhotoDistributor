from __future__ import annotations
from datetime import datetime
from typing import Union
import os
import pathlib
import logging
import exifread
import configuration



def enumerateFilesWithSameNames(initialName, currentName):
    # Both names should be without extensions.
    # Converts "hello.jpg" -> "hello_1.jpg"
    # Converts "hello_1.jpg" -> "hello_2.jpg" if initialName is hello
    # Converts "hello_1.jpg" -> "hello_1_1.jpg" if initialName is hello_1
    if currentName == initialName:
        # We are the second different file with same name
        return currentName + "_1"
    else:
        # We are third+
        separator = currentName.rfind('_')
        return currentName[:separator] + '_' + str(int(currentName[separator + 1:]) + 1)

def createSymlink(pointingFrom: pathlib.Path, pointingTo: pathlib.Path):
    os.symlink(pointingTo.absolute(), pointingFrom.absolute(), target_is_directory=False)

class File:
    location: pathlib.Path
    creationDate: datetime  # Might not actually be creation date

    def __init__(self, location: Union[str, bytes, os.PathLike]):
        self.location = pathlib.Path(location)

        try:
            tags = exifread.process_file(open(self.location, 'rb'))
            datetimeTags = ['EXIF DateTimeOriginal', 'Image DateTimeOriginal']
            # Which tag is present depends on the camera and format
            suitableDatetimeTagIndex = -1
            for i in range(len(datetimeTags)):
                if datetimeTags[i] in tags:
                    suitableDatetimeTagIndex = i
                    break
            else:
                raise Exception("No suitable tags found")  # Так не очень хорошо делать
            self.creationDate = datetime.strptime(str(tags[datetimeTags[suitableDatetimeTagIndex]]),
                                                  '%Y:%m:%d %H:%M:%S')
        except Exception as exc:
            logging.warning(f"Could not get the date of creation from EXIF for {self.location}. Reason: {exc}")
            self.creationDate = datetime.fromtimestamp(self.location.stat().st_ctime)

    def getSize(self):
        return self.location.stat().st_size

    def __repr__(self):
        return f"File({self.location}: {self.creationDate.date()})"

    def __str__(self):
        return f"{self.location}: {self.creationDate.date()}"

    def __lt__(self, other: File):
        """Sort by creationDate. If they are the same, bigger files should appear first"""
        if self.creationDate != other.creationDate: return self.creationDate < other.creationDate
        return self.getSize() > other.getSize()
