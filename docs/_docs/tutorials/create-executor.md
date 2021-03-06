---
title: Creating an Executor
category: Tutorials
permalink: /tutorials/create-executor/index.html
order: 3
---

For this tutorial we will discuss creation of the Slurm Executor. You will need to:

 1. [Create your Executor](#create-your-executor): Create a file `<executor-name>.py` in the qme/main/executors folder.
 2. [Define it's functionality](#define-functionality) (optionally being subclass to a parent like the ShellExecutor), along with a name and matchstring
 3. [Import](#add-to-executors-init) the executor into the `__init__.py`
 4. [Actions](#define-actions): Add any custom actions that you executor exposes
 5. [Write tests](#write-tests) for your executor
 6. [Write documentation](#write-documentation) for your executor
 7. [Create a Dashboard](#create-dashboard): for your executor, meaning a template to render it.

The following sections will discuss these points.

<a id="create-your-executor">
## 1. Create your Executor File

The first thing to do is decide if your executor warrants a parent class. For
most terminal commands, a ShellExecutor base would be most appropriate, as it
already handles parsing the command, and collecting output, error, and a return
code. For example, below we see importing the `ShellExecutor` into a new file,
`slurm.py`, and instantiating the `execute` function that will call the
already existing shell's _execute that will run the command.  Where are these files
stored? Each executor has it's own module file, which is located under "qme/main/executors."
For example, here we see a structure that provides a base, shell, and slurm executor:

```
$ tree qme/main/executor/
qme/main/executor/
├── base.py
├── __init__.py
├── shell.py
└── slurm.py
```
In the `__init__.py` file, there is basic logic to run a command over a number
of regular expressions, and to return the executor class that matches.
Here is a basic example with two executors, shell and slurm, early in the library
development:


```python
def matches(Executor, command):
    """Given a command, determine if it matches the regular expression
       that determines to use the executor or not. This applies to all
       executors except for the shell executor. This means that all non-shell
       classes need to have a matchstring defined.
    """
    if not hasattr(Executor, "matchstring"):
        raise NotImplementedError

    if isinstance(command, list):
        command = " ".join(command)
    return not re.search(Executor.matchstring, command) == None


def get_executor(command=None):
    """get executor will return the correct executor depending on a command (or
       other string) matching a regular expression. If nothing matches, we 
       default to a shell executor. Each non-shell executor should expose
       a common "matches" function (provided by the base class) that will
       handle parsing the command (a list) to a single string, and checking
       if it matches a regular expression.
    """
    # Slurm Executor
    if matches(SlurmExecutor, command):
        return SlurmExecutor(command=command)

    # Default is standard shell command
    return ShellExecutor(command=command)
```

You'll also notice each executor type is imported at the top of the file:

```python
from .shell import ShellExecutor
from .slurm import SlurmExecutor
```



<a id="define-functionality">
## 2. Define it's Functionality

Great! We have a new file. We now need to make sure that we give it a `name`
(slurm) and have chosen a `matchstring`, a class variable, that will determine
that we have an sbatch command.

```python
from .shell import ShellExecutor


class SlurmExecutor(ShellExecutor):
    """A slurm executor parses an srun command and exposes options for getting
       a job status.
    """

    name = "slurm"
    matchstring = "^sbatch"

    def execute(self, cmd=None):
        """Execute a system command and return output and error. Execute
           should take a cmd (a string or list) and execute it according to
           the executor. Attributes should be set on the class that are
           added to self.export. Since the functions here are likely needed
           by most executors, we create a self._execute() class that is called
           instead, and can be used by the other executors.
        """
        self._execute(cmd)
        # Do custom parsing of self.out, self.err, self.returncode here
```

We might also want to add some custom class variables, and instead of using
the init class verbatim, create our own init that uses super and adds some extra
metadata items like a jobid.

```python
    def __init__(self, taskid=None, command=None):
        super().__init__(taskid, command)
        self.jobid = None
```

You might want to be aware of the class `self.status` variable - you can
update this at different steps in your execution to update the user on a status.
It should be one of "complete" "running" or "cancelled".
Finally, what about slurm output and error? If there is no file defined with
`--out` and `--err` the output and error will go to output and error flies
named according to the jobid, and likely prefixed with slurm:

```bsah
slurm-889035.out  slurm-889036.out  slurm-889074.out
```

But perhaps we should have a little more control of that, or minimally
parse if the user has provided one, and default to something else if not?
We have two choices here - we either do away with the default files produced
and define our own (giving us certainty they will exist) or we try to honor the
defaults and user choices. I decided on an intermediate:

 - if an output or error file is defined in the command, honor it.
 - if no output or error file is defined in the command, default to the job's present working directory (where it was submit) plus the job id.
 - in all cases, always check that the file exists first before trying to read it.

The above steps make the assumption that either the user is lazy and doesn't 
directly define output and error (and we figure it out) or they do, and do
so on the command line. The case that we can't well handle is when there is an SBATCH directive in the
job file to detect the output and error. Parsing SBATCH directives from
a job file might be interesting functionality to add at some point, but
not for this first step.

<a id="add-to-executors-init">
## 3. Add to the Executors init file

As we showed earlier, you next need to add your executor to the get_executor
function, and check if it matches based on the matchstring. Here is
that snippet again in `get_executor`:

```python
    # Slurm Executor
    if matches(SlurmExecutor, command):
        return SlurmExecutor(command=command)
```

### Development Tips

At this point you might bring it onto a cluster, add an `IPython.embed()` in the
execute function, and interactively develop and write the code. You would
clone your feature branch, install qme from it, and then run a command
that should match:

```bash
$ git clone -b add/slurm-executor git@github.com:vsoch/qme.git
$ pip install -e .[all]
$ which qme
$ qme run sbatch --partition normal --time 00:00:10 run_job.sh
```

When I tested this with `IPython.embed()` I was able to see that the self.out
and self.err was set to `(['Submitted batch job 889074\n'], [])`, and
then I could check the return code, and extract the job id from the output
string.

```python
    def execute(self, cmd=None):
        """Execute a system command and return output and error. Execute
           should take a cmd (a string or list) and execute it according to
           the executor. Attributes should be set on the class that are
           added to self.export. Since the functions here are likely needed
           by most executors, we create a self._execute() class that is called
           instead, and can be used by the other executors.
        """
        self._execute(cmd)
        if self.returncode == 0:
             match = re.search('[0-9]+', self.out[0])
             if not match:
                bot.exit(f"Unable to derive job id from {self.out}")
             self.jobid = match.group()
``` 

This is also where I could add logic for parsing output and error files.

### Updating Data

Each executor by default has a data attribute (self.data) that you should
add executor-specific data to that you want to export. The base executor will
export a common set of metadata (user, present working directory, and a timestamp)
and then add the self.data to it. That looks like this:

```python
    def export(self):
        """return data as json. This is intended to save to the task database.
           Any important output, returncode, etc. from the execute() function
           should be provided here. Required strings are "command" and "status"
           that must be one of "running" or "complete" or "cancelled." Suggested
           fields are output, error, and returncode. self._export_common() should
           be called first.
        """
        # Get common context (e.g., pwd)
        common = self._export_common()
        common.update(self.data)
        return common
```

The `_export_common` function is what adds pwd (present working directory),
 a timestamp, and a user id to the bsaic metadata. Note that this data doesn't
include the outer level metadata about the executor, namely the executor name, 
taskid, and data. This is handled by the database when it does the export, and you
don't need to worry about it. You also don't need to subclass the export function.
What you might want to do, however, is update self.data with any executor-specific
metadata that you might have. For example, for slurm when we run execute, we
add `self.data['jobid']` along with an outputfile and errorfile. This will
then be exported to the database and available to future actions.

### Logging

You can import a logger to write messages to the user:

```bash
import logging
logger = logging.getLogger("qme.main.executor.slurm")

bot.info("This is an information message in purple")
logger.warning("This is a warning in yellow")
logger.error("This is an error in red")
logger.debug("This is a debug message in aqua.")
```

If you need to format a list of lists into a table, or if you need a spinner
or other colored output, you can import the QueueMeMessage class:

```bash
from qme.logger import bot
bot.table([["1", "1", "1"],["2","2", "2"]]) 
1  1	1	1
2  2	2	2
```

We don't currently have executor-specific logging files, but this can be added
if it's needed and requested.

<a id="define-actions">
## 4. Define Actions

Great! We have an executor that runs a command, and then grabs a jobid and
does it's best to guess where an output and error file will be generated.
We now need to think about actions. What actions might a user want to do
for a slurm job?

 - **status**: get the status of a job
 - **cancel**: cancel a running job
 - **outputs**: view the output or error files, if we got them right.

Re-running a job is already is provided by qme, so we can nix this one. Let's focus on
these three actions. The first thing to know is that the base class already provides
us with a `run_action` function, which takes a named action, and then any keyword
arguments, and runs it if it is defined for the executor:

```python
    def run_action(self, name, data, **kwargs):
        """Check for a named action in the executors list.
           The user should be able to run an action by name, e.g.,
           executor.action('status')
        """
        if name in self.actions:
            return self.actions[name](data, **kwargs)
```

Notice that we are passing in a data object, which is provided by the calling
task that is on the level of the database. This snippet of code
also tells us that each executor has a self.actions variable, a dictionary
that serves as a lookup by name. By default, an executor doesn't have any actions
(the base class):

```python
self.actions = {}
```

so in our case, we want to add actions to our init, and make sure to map to
functions that our class exposes. Here is an example for the listing above:

```python
    def __init__(self, taskid=None, command=None):
        super().__init__(taskid, command)
        self.jobid = None
        self.actions = {
            "status": self.action_get_status,
            "output": self.action_get_output,
            "error": self.action_get_error,
            "outputs": self.action_get_outputs,
            "cancel": self.action_cancel,
        }
```

Note that we define them _after_ the super call, since the super call will
do an essentially empty definition. Note that the base class also has a function
to easily get the names of actions, so we don't need to implement that:

```python
    def get_actions(self):
        return list(self.actions)
```

We might then create the empty functions for each action. Note that since the
database (on the level of the task) and the executor sit next to one another,
we actually run the run_action function by way of the task, and the task adds
any current data (that was exported via the export() function) as a variable.
For example, when we have a task (which is associated with a particular database)
it also has an executor:

```python
from qme.main import Queue
queue = Queue()
Database: sqlite

# Here is the task, which has an executor associated (e.g., slurm or shell)
task = queue.get() 
task.executor
 <qme.main.executor.shell.ShellExecutor at 0x7f8c6c107910>
```

And then we can call task.run_action to run an action, and ensure that data gets passed
to the executor.

```python
task.run_action('name')
```
Under the hood, the task is handing it's data and the task name off to task.executor.run_task,
which requires both. However for shell we don't have any actions, so there is nothing
to do :)

```python
task.executor.get_actions()                                                                                               
[]
```

Now that we know each action function needs to take data (minimally) as input,
let's write skeleton functions for our actions:

```python
    def action_get_status(self, data):
        """Get the status with squeue, given a jobid
        """
        pass

    def action_get_error(self, data):
        """Get error stream, if the file exists.
        """
        pass

    def action_get_output(self, data):
        """Get just output stream, if the file exists.
        """
        pass

    def action_get_outputs(self, data):
        """Get *both* output and error streams, if files exist.
        """
        pass

    def action_cancel(self, data):
        """Cancel a job if there is a jobid
        """
        pass
```

To give you a explicit example of data, let's remember above that we exported
the job id to the "jobid" key under self.data:

```python
self.data['jobid'] = jobid
```

So for the same slurm executor loaded from the database that exported a jobid to it's data object,
we would get that jobid again like this:

```python
jobid = data.get("jobid")
```

And here is a full example in the context of the action function.

```python
    def action_get_status(self, data):
        """Get the status with squeue, given a jobid. This returns information
           for the job that is based on a format string, default looks like:

		{'jobid': '904366',
		 'jobname': 'run_job.sh',
		 'partition': 'owners',
		 'alloccpus': '1',
		 'elapsed': '00:00:00',
		 'state': 'PENDING',
		 'exitcode': '0:0'}
        """
        fmt = self.get_setting(
            "sacct_format", "jobid,jobname,partition,alloccpus,elapsed,state,exitcode"
        )
        jobid = data.get("jobid")
        if jobid:
            capture = self.capture(
                ["sacct", "--job", jobid, "--format=%s" % fmt, "--noheader"]
            )
            values = {}
            output = [x for x in capture.output[0].strip().split(" ") if x]
            for i, varname in enumerate(fmt.split(",")):
                values[varname] = output[i]
            return values
```

Notice how we are also grabbing a configuration setting, discussed next.

### Environment

If you want to define custom environment variables, other than adding them
to the documentation page for your executor, you should namespace them
starting with QME, then the executor name, and then the envar. For example,
a format string for the sacct action might be obtained via:

```python
fmt = os.environ.get('QME_SLURM_SACCT_FORMAT', "jobid,jobname,partition,alloccpus,elapsed,state,exitcode")
```

but actually, we can do better - what if the user wanted to set a value
for `QME_SLURM_SACCT_FORMAT` that would persist? They can do this via:

```bash
$ qme config --set slurm sacct_format jobid,jobname,partition,alloccpus,elapsed,state,exitcode
```

And then we can retrieve it in our executor like this:

```python
fmt = self.get_setting("sacct_format", "jobid,jobname,partition,alloccpus,elapsed,state,exitcode")
```

For the above, we look for the key `sacct_format` in the config file, and since
we are running the slurm executor, it's looked for in a section called `executor.slurm`.
But since the user could also export `QME_<executor>_<key>` or for this case,
`QME_SLURM_SACCT_VALUE` we first check the environment. If we don't find it in the
environment or the config, we default to the second value (the long format string).

### Shell Capture

The base class provides a helpful function, capture, which is intended
to capture the complete output and error for a shell command, along with
other metdata like the pid, and returncode. You might find this helpful
to use in your actions. Here is an example:

```python
capture = self.capture(["scancel", self.jobid])
# capture.output
# caputre.error
# capture.returncode
# capture.pid
return capture.output
```

At this point when writing actions I like to add another IPython.embed() in the execute 
or task.run_action command so I can develop each action.


<a id="write-tests">
## 5. Write Tests

Each executor should have it's own file under tests, e.g., tests/test_executor_shell.py.
If an executor requires dependencies that aren't available (e.g., slurm) and you can't
mock it, then write tests elsewhere that can be run in the correct environment to
test it, and then share these tests in your pull request or contribution.

<a id="write-documentation">
## 6. Write Documentation

Each executor has it's own documentation page, a section under `docs/_docs/getting-started/executors.md`
that renders to [here]({{ site.baseurl }}/docs/getting-started/executors). Be sure to include:

 - the name of your executor
 - the matchstring that it uses to match commands to it
 - general usage examples
 - any environment variables needed
 - actions that are exposed


<a id="create-dashboard">
## 7. Create a Dashboard

Each executor will render based on it's custom dashboard. This means that you need
to add a view for it to `qme/app/views/executors.py`. For example, clicking a link
to a url that ends in `/executor/shell-<taskid>` will hit this backend view:

```python
@app.route("/executor/<taskid>")
def shell_executor(taskid):

    task = app.queue.get(taskid)
    return render_template(
        "executors/shell.html", task=task.load(), database=app.queue.database
    )
```

And then render the template in `qme/app/templates/executors/shell.html`. You should
add one, named according to your executor, and be sure to export any variables
that are needed by the template (as we do above).

If you want some help with your executor, please don't be afraid to [reach out](https://github.com/{{ site.repo }}/issues).
