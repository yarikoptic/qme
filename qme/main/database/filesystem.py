"""

Copyright (C) 2020 Vanessa Sochat.

This Source Code Form is subject to the terms of the
Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""

from qme.utils.file import (
    write_json,
    mkdir_p,
    read_json,
    recursive_find,
    get_latest_modified,
)
from qme.main.database.base import Database
from qme.main.executor import get_named_executor
from qme.logger import bot
from glob import glob
import shutil
import uuid
import os
import sys


class FileSystemDatabase(Database):
    """A FileSystemDatabase writes raw json to files at $HOME/.qme/database
       This is the default flat database for qme, and on init we ensure
       that the database folder is created in QME_HOME.
    """

    database = "filesystem"

    def __init__(self, config_dir):
        """init for the filesystem ensures that the base folder (named 
           according to the studyid) exists.
        """
        self.create_database(config_dir)

    def create_database(self, config_dir):
        """Create the database. The parent folder must exist.
        """
        self.data_base = os.path.abspath(os.path.join(config_dir, "database"))
        if not os.path.exists(config_dir):
            sys.exit(f"{config_dir} must exist to create database there.")
        if not os.path.exists(self.data_base):
            mkdir_p(self.data_base)

    # Global

    def clear(self):
        """clear (delete) all tasks.
        """
        for executor_dir in self.iter_executors(fullpath=True):
            if os.path.exists(executor_dir):
                bot.info(f"Removing {executor_dir}")
                shutil.rmtree(executor_dir)

    # Add or Update requires executor

    def add_task(self, executor):
        """Create a filesystem task based on an executor type. The executor controls
           what data is exported and the uid, the task object just handles saving it.
        """
        return FileSystemTask(executor, data_base=self.data_base)

    def update_task(self, executor, updates=None):
        """update a task with a json dictionary.
        """
        task = FileSystemTask(executor, exists=True, data_base=self.data_base)
        task.update({"data": executor.export()})

    # Get, delete, etc. only require taskid

    def get_task(self, taskid=None):
        """Get a task based on a taskid. Exits on error if doesn't exist. If
           a task id is not provided, get the last run task.
        """
        if not taskid:
            taskid = os.path.basename(
                get_latest_modified(self.data_base, pattern="*.json")
            ).replace(".json", "")
        executor = taskid.split("-", 1)[0]
        executor = get_named_executor(executor, taskid)
        return FileSystemTask(executor, exists=True, data_base=self.data_base)

    def delete_task(self, taskid):
        """delete a task based on a specific task id. All task ids must be
           in the format of <taskid>-<uid> without extra dashes so we can
           reliably split based on the first dash.
        """
        task = self.get_task(taskid)
        if not task:
            bot.exit(f"{taskid} does not exist in the database.")
        os.remove(task.filename)
        bot.info(f"{taskid} has been removed.")

    def delete_executor(self, name):
        """delete all tasks for an executor, based on executor's name (str).
        """
        executor_dir = os.path.join(self.data_base, name)
        if not os.path.exists(executor_dir):
            bot.exit(f"Executor {executor} does not exist.")
        shutil.rmtree(executor_dir)

    def iter_executors(self, fullpath=False):
        """list executors based on the subfolders in the base database folder.
        """
        for contender in os.listdir(self.data_base):
            contender = os.path.join(self.data_base, contender)
            if os.path.isdir(contender):
                if not fullpath:
                    yield os.path.basename(contender)
                else:
                    yield contender

    def list_tasks(self, name=None):
        """list tasks, either under a particular executor name (if provided)
           or just the executors.
        """
        listpath = self.data_base
        if name:
            listpath = os.path.join(listpath, name)
        rows = []
        for filename in recursive_find(listpath, pattern="*.json"):
            rows.append([os.path.basename(filename).replace(".json", "")])
        bot.table(rows)


class FileSystemTask:
    """A Filesystem Task can take a task id, determine if the task exists,
       and then interact with the data. If the task is instantiated without
       a taskid it is assumed to not exist yet, otherwise it must already
       exist
    """

    def __init__(self, executor, data_base, exists=False):
        """A FileSystem task tasks some task id and command for an executor.
           We provide a simple interface to retrieve the data file, and 
           do an initial creation if it doesn't exist.

           Arguments:
             taskid (str) : the executor-uuid for the task
             command (list) : the command to be executed
             data_base (str) : the path where the database exists.
             exists (bool) : if True, must already exists (default is False)
        """
        self.executor = executor
        self.data_base = data_base
        self.create(exists)

    @property
    def filename(self):
        return "%s.json" % os.path.join(self.executor_dir, self.executor.taskid)

    @property
    def executor_dir(self):
        return os.path.join(self.data_base, self.executor.name)

    def update(self, updates=None):
        """Update a data file. This means reading, updating, and writing
        """
        updates = updates or {}
        data = self.load()
        if data and updates:
            data.update(updates)
            self.save(data)

    def create(self, should_exist=False):
        """create the filename if it doesn't exist, otherwise if it should (and
           does not) exit on error.
        """
        if should_exist and not os.path.exists(self.filename):
            bot.exit(
                f"{self.executor.taskid} does not exist in the filesystem database"
            )
        if not os.path.exists(self.executor_dir):
            os.mkdir(self.executor_dir)

        # If it's the first time saving, create basic file
        if not should_exist:
            self.save(
                {
                    "executor": self.executor.name,
                    "uid": self.executor.taskid,
                    "data": self.executor.export(),
                }
            )

    def save(self, data):
        """Save a json object to the task.
        """
        write_json(data, self.filename)

    def summary(self):
        return self.executor.summary()

    def load(self):
        """Given a task, load the filename
        """
        if os.path.exists(self.filename):
            return read_json(self.filename)
