from __future__ import annotations
from datetime import datetime
from typing import List, Union, Dict
import os
from tkinter import filedialog, messagebox
import pathlib
import shutil
from tkinter import *
from abc import ABC, abstractmethod
import exifread
import logging
logging.basicConfig(format='[%(levelname)s] %(message)s', level=logging.DEBUG)
logging.getLogger('exifread').setLevel(logging.ERROR)




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


class Processer:
    FORMATS = set()
    THRESHOLD = 50
    WEIRD_FILES_DIR_NAME = "WeirdFiles"

    sourceFolders = []
    destinationFolder: pathlib.Path
    dummyRun = False
    collisionCounter = 1

    def parseConfig(self):
        for line in open(pathlib.Path(os.path.realpath(__file__)).parent / "formats.conf"):  # Directory with script
            if not line:
                continue
            line = line.split('#')
            if line[0]:
                self.FORMATS.add(line[0].upper().strip())
        logging.info("Formats, which are considered to be photo / video :" +
              ", ".join(self.FORMATS))

    def __init__(self, sourceFolders, destinationFolder, dummyRun):
        self.parseConfig()
        self.sourceFolders = sourceFolders[:]
        self.destinationFolder = pathlib.Path(destinationFolder)
        self.dummyRun = dummyRun

    def run(self):
        self.runJobs(self.createJobs(self.listFiles()))

    def listFiles(self) -> List[File]:
        filesListing = []
        for sourceDirectory in self.sourceFolders:
            sourceDirectory = pathlib.Path(sourceDirectory)
            filesListing.extend(
                filter(
                    lambda file: file.suffix[1:].upper() in self.FORMATS,  # checks whether we care about this file
                    sourceDirectory.rglob('*')  # recursively lists all files under this sourceDirectory
                )
            )
        filesListing = [File(file) for file in filesListing]
        logging.debug("Files found:\n{}".format('\n'.join(map(str, filesListing))))
        return filesListing

    def createJobs(self, filesListing: List[File]):
        filesListing.sort(key=lambda x: x.creationDate)
        dummyRun = self.dummyRun

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
                self.path.mkdir()

            def __str__(self):
                return f"Create directory {self.path}"

        class CopyFileJob(Job):
            def __init__(self, sourceFile: File, destFile: pathlib.Path):
                self.sourceFile = sourceFile
                self.destFile = destFile

            def run(self):
                if dummyRun:
                    newFile = self.destFile.parent / ('_'.join(self.sourceFile.location.parts[1:]) + ".txt")
                    logging.debug(f"Trying to create file {newFile}")
                    open(newFile, 'w')
                else:
                    logging.debug(f"Trying to {self}")
                    shutil.copy2(self.sourceFile.location, self.destFile)

            def __str__(self):
                return f"Copy {self.sourceFile} -> {self.destFile}"

        jobs: List[Job] = [CreateDirectoryJob(self.destinationFolder / self.WEIRD_FILES_DIR_NAME)]
        # Create weird files directory first
        filesIntoSameDirectory: List[File] = []

        def flushFiles():
            # Puts all files in buffer into one directory
            if len(filesIntoSameDirectory) == 0: return

            year = filesIntoSameDirectory[0].creationDate.year

            firstMonth = filesIntoSameDirectory[0].creationDate.month
            lastMonth = filesIntoSameDirectory[-1].creationDate.month
            month = f"{firstMonth:02d} - {lastMonth:02d}" if firstMonth != lastMonth else f"{firstMonth:02d}"

            targetDir = self.destinationFolder / str(year) / month

            jobs.append(CreateDirectoryJob(targetDir))

            nameToFile: Dict[str, File] = dict()

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
                        jobs.append(CopyFileJob(file, targetDir / nameAndExtension))
                        written = True
                    else:
                        otherFileWithSameName = nameToFile[nameAndExtension]
                        if file.creationDate == otherFileWithSameName.creationDate:
                            # Same files, this one in worse resolution
                            folder = self.destinationFolder / self.WEIRD_FILES_DIR_NAME / str(self.collisionCounter)
                            self.collisionCounter += 1
                            jobs.append(CreateDirectoryJob(folder))
                            jobs.append(CopyFileJob(otherFileWithSameName,
                                                    folder / ("chosen_" + otherFileWithSameName.location.name)))
                            jobs.append(CopyFileJob(file, folder / file.location.name))
                            written = True
                        else:
                            # Different files => write us as well
                            currentName = enumerateFilesWithSameNames(file.location.stem, currentName)
                            nameAndExtension = currentName + extension
            filesIntoSameDirectory.clear()

        currentYear = -1

        for file in filesListing:
            if file.creationDate.year != currentYear:
                # Мы обязаны закончить наполнение папки, если сменился год
                flushFiles()
                currentYear = file.creationDate.year
                jobs.append(CreateDirectoryJob(self.destinationFolder / str(currentYear)))
            if len(filesIntoSameDirectory) >= self.THRESHOLD \
                    and filesIntoSameDirectory[-1].creationDate.month < file.creationDate.month:
                # Или если сменился месяц и в папке достаточно файлов
                flushFiles()
            filesIntoSameDirectory.append(file)
        flushFiles()
        logging.debug("Jobs created:\n" + "\n".join(map(str, jobs)))
        return jobs

    def runJobs(self, jobs):
        for job in jobs:
            job.run()


class GUI:
    sourceFolders = []
    destinationFolder = ''
    gui: Tk
    destinationGuiText: StringVar
    sourcesGuiText: StringVar

    class CheckButton:
        def __init__(self, master, title):
            self.var = BooleanVar()
            self.var.set(True)
            self.title = title
            self.button = Checkbutton(
                master, text=title, variable=self.var,
                onvalue=1, offvalue=0
            )
            self.button.pack()

    def prepareGui(self):
        self.sourcesGuiText = StringVar(value='Sources:')
        self.destinationGuiText = StringVar(value='Destination:')

        sourcesListGui = Label(textvariable=self.sourcesGuiText)
        sourcesListGui.pack()
        destinationGui = Label(textvariable=self.destinationGuiText)
        destinationGui.pack()

        addFolderButton = Button(text="Добавить папку", height=5, width=50,
                                 command=self.addFolder)
        addFolderButton.pack()
        destinationButton = Button(text="Конечная папка", height=5, width=50,
                                   command=self.setDestination)
        destinationButton.pack()
        self.dummyRunButton = self.CheckButton(None, "Холостой запуск (не копировать сами фотографии)")
        copyButton = Button(text='Выполнить!', height=5, width=50,
                            command=self.execute)
        copyButton.pack()


    def addFolder(self):
        directory = filedialog.askdirectory(parent=self.gui)
        if directory != '':
            self.sourcesGuiText.set(f'{self.sourcesGuiText.get()}\n{directory}')
            self.sourceFolders.append(directory)

    def setDestination(self):
        directory = filedialog.askdirectory(parent=self.gui)
        logging.info(f"Destination directory set to {directory}")
        self.destinationGuiText.set(f'Destination: {directory}')
        self.destinationFolder = directory

    def execute(self):
        answer = messagebox.askquestion(title='Уверены?',
                                        message="Хотите продолжить?")
        if answer == 'yes':
            self.gui.destroy()
            Processer(self.sourceFolders, self.destinationFolder, dummyRun=self.dummyRunButton.var.get()).run()

    def __init__(self):
        def resolutionFix():
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
                # if your Windows version >= 8.1
            except:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()  # win 8.0 or less
                except:
                    pass
        resolutionFix()
        self.gui = Tk(className='Выбор файлов')
        self.prepareGui()
        self.gui.mainloop()


def test():
    shutil.rmtree("./tmp", ignore_errors=True)
    pathlib.Path("./tmp").mkdir()
    Processer(["./MIPT"], "./tmp", dummyRun=False).run()


GUI()
# test()
