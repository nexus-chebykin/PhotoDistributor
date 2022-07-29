from __future__ import annotations
import logging
import pathlib
from abc import ABC, abstractmethod

from configuration import config, Configuration
from utils import File, enumerateFilesWithSameNames, createSymlink
import shutil
from typing import List, Dict, Set


class Job(ABC):
    @abstractmethod
    def run(self):
        ...

    @abstractmethod
    def __str__(self):
        ...


class CreateDirectoryJob(Job):
    def __init__(self, path: pathlib.Path):
        self.path = path

    def run(self):
        logging.debug(f"Trying to create directory {self.path}")
        self.path.mkdir(exist_ok=True)

    def __str__(self):
        return f"Create directory {self.path}"


class CopyFileJob(Job):
    def __init__(self, sourceFile: File, destFile: pathlib.Path):
        self.sourceFile = sourceFile
        self.destFile = destFile

    def run(self):
        logging.debug(f"Trying to {self}")
        shutil.copy2(self.sourceFile.location, self.destFile)

    def __str__(self):
        return f"Copy {self.sourceFile.location} -> {self.destFile}"


class MoveFileJob(Job):
    def __init__(self, sourceFile: File, destFile: pathlib.Path):
        self.sourceFile = sourceFile
        self.destFile = destFile

    def run(self):
        logging.debug(f"Trying to {self}")
        shutil.move(self.sourceFile.location, self.destFile)
        self.sourceFile.location = self.destFile

    def __str__(self):
        return f"Move {self.sourceFile.location} -> {self.destFile}"


class JobCreator:
    collisionCounter = 1
    filesListing: List[File]

    def __init__(self, filesListing):
        previousWeirdDir = (config.destinationFolder / config.WEIRD_FILES_DIR_NAME)
        if previousWeirdDir.is_dir() and any(previousWeirdDir.iterdir()):
            # Not the first run on same output dir
            self.collisionCounter = int(max(previousWeirdDir.iterdir()).stem) + 1
        self.filesListing = filesListing[:]

    def flushFiles(self, filesIntoSameDirectory, jobs):
        # Puts all files in buffer into one directory
        if len(filesIntoSameDirectory) == 0: return

        year = filesIntoSameDirectory[0].creationDate.year

        firstMonth = filesIntoSameDirectory[0].creationDate.month
        lastMonth = filesIntoSameDirectory[-1].creationDate.month
        month = f"{firstMonth:02d} - {lastMonth:02d}" if firstMonth != lastMonth else f"{firstMonth:02d}"

        targetDir = config.destinationFolder / str(year) / month

        jobs.append(CreateDirectoryJob(targetDir))

        nameToFile: Dict[str, File] = dict()
        # If it is not the first time we run on the same output folder,
        # We need to take existing files into account
        if targetDir.exists():
            for filePath in targetDir.iterdir():
                nameToFile[filePath.name] = File(filePath)
        for file in filesIntoSameDirectory:
            currentName = file.location.stem  # Without extension
            extension = file.location.suffix
            nameAndExtension = file.location.name
            # In theory, we can have 3+ files with same name, and all of them are different :)
            written = False
            while not written:
                if nameAndExtension not in nameToFile:
                    # We are the first file with this name
                    nameToFile[nameAndExtension] = file

                    jobType = MoveFileJob if file.alreadyExisted else CopyFileJob
                    # If the file is already result of PhotoDistributor, we probably want to move it
                    jobs.append(jobType(file, targetDir / nameAndExtension))
                    written = True
                else:
                    otherFileWithSameName = nameToFile[nameAndExtension]
                    if file.creationDate == otherFileWithSameName.creationDate:
                        # Same files, this one in worse resolution

                        if file.getSize() == otherFileWithSameName.getSize():
                            # Exactly same files => do not write anything new at all
                            break

                        folder = config.destinationFolder / config.WEIRD_FILES_DIR_NAME

                        jobs.append(CreateDirectoryJob(folder))
                        jobs.append(CopyFileJob(otherFileWithSameName,
                                                folder / (f"chosen_{self.collisionCounter}")))
                        jobs.append(CopyFileJob(file, folder / f"{self.collisionCounter}"))
                        self.collisionCounter += 1
                        written = True
                    else:
                        # "file" and "other file with same name" are different.
                        # Maybe there is another file which is same as this but with enumerated name?
                        currentName = enumerateFilesWithSameNames(file.location.stem, currentName)
                        nameAndExtension = currentName + extension
        filesIntoSameDirectory.clear()

    def createJobs(self):
        self.filesListing.sort()

        filesGroupedByMonth: List[List[File]] = []
        currentYear = -1
        years: Set[int] = set()
        currentMonth = -1
        for file in self.filesListing:
            if file.creationDate.year != currentYear or file.creationDate.month != currentMonth:
                # Сменился месяц или год
                filesGroupedByMonth.append([])
                currentYear = file.creationDate.year
                years.add(currentYear)
                currentMonth = file.creationDate.month
            filesGroupedByMonth[-1].append(file)

        jobs: List[Job] = [CreateDirectoryJob(config.destinationFolder / config.WEIRD_FILES_DIR_NAME)] + \
                          [CreateDirectoryJob(config.destinationFolder / str(year)) for year in years]
        # Create weird files directory and years directories first

        filesIntoSameDirectory: List[File] = []
        for month in filesGroupedByMonth:
            if filesIntoSameDirectory:
                if len(filesIntoSameDirectory) + len(month) > 2 * config.THRESHOLD \
                        or month[0].creationDate.year > filesIntoSameDirectory[-1].creationDate.year:
                    # Если с добавлением нового месяца станет слишком много фотографий или сменится год, то запишем что есть
                    self.flushFiles(filesIntoSameDirectory, jobs)
            # В любом случае нас нужно добавить
            filesIntoSameDirectory.extend(month)

        self.flushFiles(filesIntoSameDirectory, jobs)
        logging.debug("Jobs created:\n" + "\n".join(map(str, jobs)))

        return jobs


class JobRunner:
    jobs: List[Job]

    def __init__(self, jobs):
        self.jobs = jobs

    def runJobs(self):
        for job in self.jobs:
            job.run()

    def cleanUp(self):
        for directory in config.destinationFolder.glob(f"{config.destinationFolder}/**"):
            # Lists all directories under destination folder
            if not any(directory.iterdir()):
                directory.rmdir()
