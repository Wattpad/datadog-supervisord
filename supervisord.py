import time

from checks import AgentCheck

import xmlrpclib

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = '9001'
DEFAULT_SERVER = 'server'

OK = AgentCheck.OK
CRITICAL = AgentCheck.CRITICAL
UNKNOWN = AgentCheck.UNKNOWN

STATUS_MAP = {
    'STOPPED': CRITICAL,
    'STARTING': OK,
    'RUNNING': OK,
    'BACKOFF': UNKNOWN,
    'STOPPING': CRITICAL,
    'EXITED': CRITICAL,
    'FATAL': CRITICAL,
    'UNKNOWN': UNKNOWN
}

TIME_FORMAT = '%Y-%m-%d %H:%M:%S'


def time_formatter(s):
    return time.strftime(TIME_FORMAT, time.localtime(s))


class SupervisordCheck(AgentCheck):

    def check(self, instance):
        name = instance.get('name', DEFAULT_SERVER)
        server = self._connect(instance)
        count = {
            AgentCheck.OK: 0,
            AgentCheck.CRITICAL: 0,
            AgentCheck.UNKNOWN: 0
        }

        # Report service checks and uptime for each process
        proc_names = instance.get('proc_names', [])
        for proc_name in proc_names:
            tags = ['supervisord',
                    'server:%s' % name,
                    'process:%s' % proc_name]
            info = server.supervisor.getProcessInfo(proc_name)

            # Report Service Check
            status = STATUS_MAP[info['statename']]
            msg = self._build_message(info)
            count[status] += 1
            self.service_check('supervisord.process.check',
                               status, tags=tags, message=msg)
            # Report Uptime
            start, stop, now = int(info['start']), int(info['stop']), int(info['now'])
            uptime = 0 if stop == 0 else now - start
            self.gauge('supervisord.process.uptime', uptime, tags=tags)

        # Report counts by status
        tags = ['supervisord', 'server:%s' % name]
        self.gauge('supervisord.process.total', len(proc_names), tags=tags)
        self.gauge('supervisord.process.up', count[OK], tags=tags)
        self.gauge('supervisord.process.down', count[CRITICAL], tags=tags)
        self.gauge('supervisord.process.unknown', count[UNKNOWN], tags=tags)

    def _connect(self, instance):
        host = instance.get('host', DEFAULT_HOST)
        port = instance.get('port', DEFAULT_PORT)
        user = instance.get('user', None)
        password = instance.get('pass', None)
        auth = '%s:%s@' % (user, password) if user and password else ''
        return xmlrpclib.Server('http://%s%s:%s/RPC2' % (auth, host, port))

    def _build_message(self, proc):
        proc['now_str'] = time_formatter(proc['now'])
        proc['start_str'] = time_formatter(proc['start'])
        proc['stop_str'] = '' if proc['stop'] == 0 else time_formatter(proc['stop'])

        return """Current time: %(now_str)s
Process name: %(name)s
Process group: %(group)s
Description: %(description)s
Error log file: %(stderr_logfile)s
Stdout log file: %(stdout_logfile)s
Log file: %(logfile)s
State: %(statename)s
Start time: %(start_str)s
Stop time: %(stop_str)s
Exit Status: %(exitstatus)s""" % proc