# -*- coding: utf-8 -
#
# This file is part of gunicorn released under the MIT license. 
# See the NOTICE for more information.
import copy
import inspect
import optparse
import os
import textwrap
import types

from pulsar import __version__
from pulsar.utils import system
from pulsar.utils.py2py3 import *


DEFAULT_PORT = 8060

__all__ = ['Config',
           'Setting',
           'validate_string',
           'validate_callable',
           'validate_bool',
           'validate_pos_int',
           'make_settings']


KNOWN_SETTINGS = []

def def_start_server(server):
    pass
    

def def_pre_exec(server):
    pass
    
    
def default_process(worker):
    pass


def def_pre_request(worker, req):
    worker.log.debug("%s %s" % (req.method, req.path))


def def_post_request(worker, req):
    pass


def def_worker_exit(worker):
    pass
    
    
def wrap_method(func):
    def _wrapped(instance, *args, **kwargs):
        return func(*args, **kwargs)
    return _wrapped


def make_settings(ignore=None):
    settings = {}
    ignore = ignore or ()
    for s in KNOWN_SETTINGS:
        setting = s()
        if setting.name in ignore:
            continue
        settings[setting.name] = setting.copy()
    return settings


class Config(object):
        
    def __init__(self, usage=None):
        self.settings = make_settings()
        self.usage = usage
        
    def __getstate__(self):
        d = self.__dict__.copy()
        return d
    
    def __setstate__(self, state):
        self.__dict__['settings'] = state['settings']
        self.__dict__['usage'] = state['usage']
    
    def __getattr__(self, name):
        if name not in self.settings:
            raise AttributeError("No configuration setting for: %s" % name)
        return self.settings[name].get()
    
    def __setattr__(self, name, value):
        if name != "settings" and name in self.settings:
            raise AttributeError("Invalid access!")
        super(Config, self).__setattr__(name, value)
    
    def set(self, name, value):
        if name not in self.settings:
            raise AttributeError("No configuration setting for: %s" % name)
        self.settings[name].set(value)

    def parser(self):
        kwargs = {
            "usage": self.usage,
            "version": __version__
        }
        parser = optparse.OptionParser(**kwargs)

        keys = self.settings.keys()
        sorter = lambda x: (self.settings[x].section, self.settings[x].order)
        
        for k in sorted(keys,key=sorter):
            self.settings[k].add_option(parser)
        return parser

    @property
    def worker_class(self):
        uri = self.settings['worker_class'].get()
        worker_class = system.load_worker_class(uri)
        if hasattr(worker_class, "setup_class"):
            worker_class.setup_class()
        return worker_class

    @property
    def workers(self):
        return self.settings['workers'].get()

    @property
    def address(self):
        bind = self.settings['bind'].get()
        return system.parse_address(to_bytestring(bind))
        
    @property
    def uid(self):
        user = self.settings['user'].get()
        return system.get_uid(user)
        
    @property
    def gid(self):
        group = self.settings['group'].get()
        return system.get_gid(group)
        
    @property
    def proc_name(self):
        pn = self.settings['proc_name'].get()
        if pn is not None:
            return pn
        else:
            return self.settings['default_proc_name'].get()
            
            
class SettingMeta(type):
    def __new__(cls, name, bases, attrs):
        super_new = super(SettingMeta, cls).__new__
        parents = [b for b in bases if isinstance(b, SettingMeta)]
        if not parents or attrs.pop('virtual',False):
            return super_new(cls, name, bases, attrs)            
    
        attrs["order"] = len(KNOWN_SETTINGS)
        attrs["validator"] = wrap_method(attrs["validator"])
        
        new_class = super_new(cls, name, bases, attrs)
        new_class.fmt_desc(attrs['desc'] or '')
        KNOWN_SETTINGS.append(new_class)
        return new_class

    def fmt_desc(cls, desc):
        desc = textwrap.dedent(desc).strip()
        setattr(cls, "desc", desc)
        lines = desc.splitlines()
        setattr(cls, "short", '' if not lines else lines[0])
        
        
# This works for Python 2 and Python 3
BaseSettings =  SettingMeta('BaseSettings', (object, ), {})


class Setting(BaseSettings):
    virtual = True    
    name = None
    value = None
    section = None
    cli = None
    validator = None
    type = None
    meta = None
    action = None
    default = None
    short = None
    desc = None
    
    def __init__(self):
        if self.default is not None:
            self.set(self.default)    
        
    def add_option(self, parser):
        if not self.cli:
            return
        args = tuple(self.cli)
        kwargs = {
            "dest": self.name,
            "metavar": self.meta or None,
            "action": self.action or "store",
            "type": self.type or "string",
            "default": None,
            "help": "%s [%s]" % (self.short, self.default)
        }
        if kwargs["action"] != "store":
            kwargs.pop("type")
        parser.add_option(*args, **kwargs)
    
    def copy(self):
        return copy.copy(self)
    
    def get(self):
        return self.value
    
    def set(self, val):
        assert hasattr(self.validator,'__call__'), "Invalid validator: %s" % self.name
        self.value = self.validator(val)


def validate_bool(val):
    if isinstance(val,bool):
        return val
    if not isinstance(val, string_type):
        raise TypeError("Invalid type for casting: %s" % val)
    if val.lower().strip() == "true":
        return True
    elif val.lower().strip() == "false":
        return False
    else:
        raise ValueError("Invalid boolean: %s" % val)


def validate_pos_int(val):
    if not isinstance(val,int_type):
        val = int(val, 0)
    else:
        # Booleans are ints!
        val = int(val)
    if val < 0:
        raise ValueError("Value must be positive: %s" % val)
    return val


def validate_string(val):
    if val is None:
        return None
    if not is_bytes_or_string(val):
        raise TypeError("Not a string: %s" % val)
    return to_string(val).strip()


def validate_callable(arity):
    def _validate_callable(val):
        if not hasattr(val,'__call__'):
            raise TypeError("Value is not callable: %s" % val)
        if arity != len(inspect.getargspec(val)[0]):
            raise TypeError("Value must have an arity of: %s" % arity)
        return val
    return _validate_callable


class ConfigFile(Setting):
    name = "config"
    section = "Config File"
    cli = ["-c", "--config"]
    meta = "FILE"
    validator = validate_string
    default = 'config.py'
    desc = """\
        The path to a Pulsar config file.
        
        Only has an effect when specified on the command line or as part of an
        application specific configuration.    
        """


class Bind(Setting):
    name = "bind"
    section = "Server Socket"
    cli = ["-b", "--bind"]
    meta = "ADDRESS"
    validator = validate_string
    default = "127.0.0.1:{0}".format(DEFAULT_PORT)
    desc = """\
        The socket to bind.
        
        A string of the form: 'HOST', 'HOST:PORT', 'unix:PATH'. An IP is a valid
        HOST.
        """
        
        
class Backlog(Setting):
    name = "backlog"
    section = "Server Socket"
    cli = ["--backlog"]
    meta = "INT"
    validator = validate_pos_int
    type = "int"
    default = 2048
    desc = """\
        The maximum number of pending connections.    
        
        This refers to the number of clients that can be waiting to be served.
        Exceeding this number results in the client getting an error when
        attempting to connect. It should only affect servers under significant
        load.
        
        Must be a positive integer. Generally set in the 64-2048 range.    
        """


class Workers(Setting):
    name = "workers"
    section = "Worker Processes"
    cli = ["-w", "--workers"]
    meta = "INT"
    validator = validate_pos_int
    type = "int"
    default = 1
    desc = """\
        The number of worker process for handling requests.
        
        A positive integer generally in the 2-4 x $(NUM_CORES) range. You'll
        want to vary this a bit to find the best for your particular
        application's work load.
        """


class WorkerClass(Setting):
    name = "worker_class"
    section = "Worker Processes"
    cli = ["-k", "--worker-class"]
    meta = "STRING"
    validator = validate_string
    default = "http"
    desc = """\
        The type of workers to use.
        
        A string referring to one of the following bundled classes:
        
        * ``sync``
        * ``eventlet`` - Requires eventlet >= 0.9.7
        * ``gevent``   - Requires gevent >= 0.12.2 (?)
        * ``tornado``  - Requires tornado >= 0.2
        
        Optionally, you can provide your own worker by giving pulsar a
        MODULE:CLASS pair where CLASS is a subclass of
        pulsar.Worker.
        """


class WorkerConnections(Setting):
    name = "worker_connections"
    section = "Worker Processes"
    cli = ["--worker-connections"]
    meta = "INT"
    validator = validate_pos_int
    type = "int"
    default = 1000
    desc = """\
        The maximum number of simultaneous clients.
        
        This setting only affects the Eventlet and Gevent worker types.
        """


class MaxRequests(Setting):
    name = "max_requests"
    section = "Worker Processes"
    cli = ["--max-requests"]
    meta = "INT"
    validator = validate_pos_int
    type = "int"
    default = 0
    desc = """\
        The maximum number of requests a worker will process before restarting.
        
        Any value greater than zero will limit the number of requests a work
        will process before automatically restarting. This is a simple method
        to help limit the damage of memory leaks.
        
        If this is set to zero (the default) then the automatic worker
        restarts are disabled.
        """


class Timeout(Setting):
    name = "timeout"
    section = "Worker Processes"
    cli = ["-t", "--timeout"]
    meta = "INT"
    validator = validate_pos_int
    type = "int"
    default = 30
    desc = """\
        Workers silent for more than this many seconds are killed and restarted.
        
        Generally set to thirty seconds. Only set this noticeably higher if
        you're sure of the repercussions for sync workers. For the non sync
        workers it just means that the worker process is still communicating and
        is not tied to the length of time required to handle a single request.
        """


class Keepalive(Setting):
    name = "keepalive"
    section = "Worker Processes"
    cli = ["--keep-alive"]
    meta = "INT"
    validator = validate_pos_int
    type = "int"
    default = 2
    desc = """\
        The number of seconds to wait for requests on a Keep-Alive connection.
        
        Generally set in the 1-5 seconds range.    
        """


class Debug(Setting):
    name = "debug"
    section = "Debugging"
    cli = ["--debug"]
    validator = validate_bool
    action = "store_true"
    default = False
    desc = """\
        Turn on debugging in the server.
        
        This limits the number of worker processes to 1 and changes some error
        handling that's sent to clients.
        """


class Spew(Setting):
    name = "spew"
    section = "Debugging"
    cli = ["--spew"]
    validator = validate_bool
    action = "store_true"
    default = False
    desc = """\
        Install a trace function that spews every line executed by the server.
        
        This is the nuclear option.    
        """


class PreloadApp(Setting):
    name = "preload_app"
    section = "Server Mechanics"
    cli = ["--preload"]
    validator = validate_bool
    action = "store_true"
    default = False
    desc = """\
        Load application code before the worker processes are forked.
        
        By preloading an application you can save some RAM resources as well as
        speed up server boot times. Although, if you defer application loading
        to each worker process, you can reload your application code easily by
        restarting workers.
        """


class Daemon(Setting):
    name = "daemon"
    section = "Server Mechanics"
    cli = ["-D", "--daemon"]
    validator = validate_bool
    action = "store_true"
    default = False
    desc = """\
        Daemonize the Pulsar process.
        
        Detaches the server from the controlling terminal and enters the
        background.
        """


class Pidfile(Setting):
    name = "pidfile"
    section = "Server Mechanics"
    cli = ["-p", "--pid"]
    meta = "FILE"
    validator = validate_string
    default = None
    desc = """\
        A filename to use for the PID file.
        
        If not set, no PID file will be written.
        """


class User(Setting):
    name = "user"
    section = "Server Mechanics"
    cli = ["-u", "--user"]
    meta = "USER"
    validator = validate_string
    default = None
    desc = """\
        Switch worker processes to run as this user.
        
        A valid user id (as an integer) or the name of a user that can be
        retrieved with a call to pwd.getpwnam(value) or None to not change
        the worker process user.
        """
        

class Group(Setting):
    name = "group"
    section = "Server Mechanics"
    cli = ["-g", "--group"]
    meta = "GROUP"
    validator = validate_string
    default = None
    desc = """\
        Switch worker process to run as this group.
        
        A valid group id (as an integer) or the name of a user that can be
        retrieved with a call to pwd.getgrnam(value) or None to not change
        the worker processes group.
        """


class Umask(Setting):
    name = "umask"
    section = "Server Mechanics"
    cli = ["-m", "--umask"]
    meta = "INT"
    validator = validate_pos_int
    type = "int"
    default = 0
    desc = """\
        A bit mask for the file mode on files written by Gunicorn.
        
        Note that this affects unix socket permissions.
        
        A valid value for the os.umask(mode) call or a string compatible with
        int(value, 0) (0 means Python guesses the base, so values like "0",
        "0xFF", "0022" are valid for decimal, hex, and octal representations)
        """


class TmpUploadDir(Setting):
    name = "tmp_upload_dir"
    section = "Server Mechanics"
    meta = "DIR"
    validator = validate_string
    default = None
    desc = """\
        Directory to store temporary request data as they are read.
        
        This may disappear in the near future.
        
        This path should be writable by the process permissions set for Gunicorn
        workers. If not specified, Gunicorn will choose a system generated
        temporary directory.
        """
        

class Httplib(Setting):
    name = "httplib"
    section = "Process Naming"
    cli = ["--http"]
    meta = "STRING"
    validator = validate_string
    default = 'gunicorn'
    desc = """\
        HTTP library used by server.
        
        It defaults to 'gunicorn'.
        """


class Logfile(Setting):
    name = "logfile"
    section = "Logging"
    cli = ["--log-file"]
    meta = "FILE"
    validator = validate_string
    default = "-"
    desc = """\
        The log file to write to.
        
        "-" means log to stdout.
        """


class Loglevel(Setting):
    name = "loglevel"
    section = "Logging"
    cli = ["--log-level"]
    meta = "LEVEL"
    validator = validate_string
    default = "info"
    desc = """\
        The granularity of log outputs.
        
        Valid level names are:
        
        * debug
        * info
        * warning
        * error
        * critical
        """


class Procname(Setting):
    name = "proc_name"
    section = "Process Naming"
    cli = ["-n", "--name"]
    meta = "STRING"
    validator = validate_string
    default = None
    desc = """\
        A base to use with setproctitle for process naming.
        
        This affects things like ``ps`` and ``top``. If you're going to be
        running more than one instance of Pulsar you'll probably want to set a
        name to tell them apart. This requires that you install the setproctitle
        module.
        
        It defaults to 'pulsar'.
        """


class DefaultProcName(Setting):
    name = "default_proc_name"
    section = "Process Naming"
    validator = validate_string
    default = "pulsar"
    desc = """\
        Internal setting that is adjusted for each type of application.
        """


class WhenReady(Setting):
    name = "when_ready"
    section = "Server Hooks"
    validator = validate_callable(1)
    type = "callable"
    default = staticmethod(def_start_server)
    desc = """\
        Called just after the server is started.
        
        The callable needs to accept a single instance variable for the Arbiter.
        """


class Prefork(Setting):
    name = "pre_fork"
    section = "Server Hooks"
    validator = validate_callable(1)
    default = staticmethod(default_process)
    type = "callable"
    desc = """\
        Called just before a worker is forked.
        
        The callable needs to accept two instance variables for the Arbiter and
        new Worker.
        """
        
    
class Postfork(Setting):
    name = "post_fork"
    section = "Server Hooks"
    validator = validate_callable(1)
    type = "callable"
    default = staticmethod(default_process)
    desc = """\
        Called just after a worker has been forked.
        
        The callable needs to accept two instance variables for the Arbiter and
        new Worker.
        """


class PreExec(Setting):
    name = "pre_exec"
    section = "Server Hooks"
    validator = validate_callable(1)
    type = "callable"
    default = staticmethod(def_pre_exec)
    desc = """\
        Called just before a new master process is forked.
        
        The callable needs to accept a single instance variable for the Arbiter.
        """


class PreRequest(Setting):
    name = "pre_request"
    section = "Server Hooks"
    validator = validate_callable(2)
    type = "callable"
    default = staticmethod(def_pre_request)
    desc = """\
        Called just before a worker processes the request.
        
        The callable needs to accept two instance variables for the Worker and
        the Request.
        """


class PostRequest(Setting):
    name = "post_request"
    section = "Server Hooks"
    validator = validate_callable(2)
    type = "callable"
    default = staticmethod(def_post_request)
    desc = """\
        Called after a worker processes the request.

        The callable needs to accept two instance variables for the Worker and
        the Request.
        """


class WorkerExit(Setting):
    name = "worker_exit"
    section = "Server Hooks"
    validator = validate_callable(1)
    type = "callable"
    default = staticmethod(def_worker_exit)
    desc = """\
        Called just after a worker has been exited.

        The callable needs to accept two instance variables for the Arbiter and
        the just-exited Worker.
        """
