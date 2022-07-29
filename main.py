from __future__ import annotations
import logging
from utils import File
import pathlib
import os
from typing import List
from tkinter import Tk, StringVar, BooleanVar, Label, Button, Checkbutton, filedialog, messagebox
import shutil
from jobs import JobCreator, JobRunner
from configuration import config


class Processer:

    def run(self):
        if not (config.destinationFolder / config.WEIRD_FILES_DIR_NAME).is_dir() and \
                any(config.destinationFolder.iterdir()):
            logging.critical(
                "Destination directory is neither empty nor a result of a run of PhotoDistributor.\n"
                "Exiting"
            )
            return

        jobCreator = JobCreator(self.listFiles())
        jobRunner = JobRunner(jobCreator.createJobs())
        jobRunner.runJobs()
        jobRunner.cleanUp()

    def listFiles(self) -> List[File]:
        filesListing = []
        for sourceDirectory in config.sourceFolders + [config.destinationFolder]:
            sourceDirectory = pathlib.Path(sourceDirectory)
            filesListing.extend(
                filter(
                    lambda file: file.suffix[1:].upper() in config.FORMATS,  # checks whether we care about this file
                    sourceDirectory.rglob('*')  # recursively lists all files under this sourceDirectory
                )
            )
        filesListing = [File(file) for file in filesListing]
        logging.debug("Files found:\n{}".format('\n'.join(map(str, filesListing))))
        return filesListing


class GUI:
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
        copyButton = Button(text='Выполнить!', height=5, width=50,
                            command=self.execute)
        copyButton.pack()

    def addFolder(self):
        directory = filedialog.askdirectory(parent=self.gui)
        if directory != '':
            self.sourcesGuiText.set(f'{self.sourcesGuiText.get()}\n{directory}')
            config.sourceFolders.append(pathlib.Path(directory))

    def setDestination(self):
        directory = filedialog.askdirectory(parent=self.gui)
        logging.info(f"Destination directory set to {directory}")
        self.destinationGuiText.set(f'Destination: {directory}')
        config.destinationFolder = pathlib.Path(directory)

    def execute(self):
        answer = messagebox.askquestion(title='Уверены?',
                                        message="Хотите продолжить?")
        if answer == 'yes':
            self.gui.destroy()
            Processer().run()

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
    # shutil.rmtree("./tmp", ignore_errors=True)
    pathlib.Path("./tmp").mkdir(exist_ok=True)
    config.sourceFolders = [pathlib.Path("./inputDir")]
    config.destinationFolder = pathlib.Path("./tmp")
    Processer().run()


if __name__ == '__main__':
    test()
    # GUI()
