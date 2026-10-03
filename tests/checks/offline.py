"""No request leaves a check: every process a check starts refuses a connection to any host but this machine's own, and the
refusal is written down so the check fails.

A request is the one failure a code path can swallow (a holder that did not answer is a normal run), so refusing it is not
enough: start() installs the guard in this process and, through the interpreter's own startup hook
(offline_site/sitecustomize.py, put first on PYTHONPATH), in every subprocess, each appending what it was refused to one
log. sent() reads the log back: tools/check.py fails on what no scenario claimed, and each scenario on what its own
processes tried. An answer a check is served comes from data planted before the run (the resolver's caches, run_step's fake
fetch), never from a socket.
"""
import atexit, ipaddress, json, os, socket, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LOG, WHO = "CHECK_NETWORK_LOG", "CHECK_NETWORK_WHO"

def local(host):
    """Whether a host is this machine: localhost, a loopback address, or no host at all."""
    if host in (None, "", "localhost"): return True
    try: return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError: return False

def refuse(host, port):
    """The refusal: written to the log with the check it happened in and the process that tried, then raised as the connection that
    never answers, which is how the code under check already treats an offline holder."""
    line = json.dumps({"who": os.environ.get(WHO, ""), "host": str(host), "port": port, "process": " ".join(sys.argv[:3])})
    fd = os.open(os.environ[LOG], os.O_WRONLY | os.O_APPEND | os.O_CREAT)
    try: os.write(fd, (line + "\n").encode())
    finally: os.close(fd)
    raise OSError(f"the harness has no network: {host}")

def install():
    """The guard on this process: name lookups and connections to anything but this machine."""
    if getattr(socket, "_check_offline", False) or not os.environ.get(LOG): return
    socket._check_offline = True
    lookup, connect, connect_ex = socket.getaddrinfo, socket.socket.connect, socket.socket.connect_ex
    def getaddrinfo(host, port, *a, **k):
        if not local(host): refuse(host, port)
        return lookup(host, port, *a, **k)
    def guarded(call):
        def inner(self, address):
            if isinstance(address, tuple) and not local(address[0]): refuse(address[0], address[1])
            return call(self, address)
        return inner
    socket.getaddrinfo = getaddrinfo
    socket.socket.connect, socket.socket.connect_ex = guarded(connect), guarded(connect_ex)

def start():
    """The guard on this process and every one it starts: a fresh log, the startup hook first on PYTHONPATH. Returns the log's path."""
    fd, path = tempfile.mkstemp(prefix="tree-check-network-", suffix=".log"); os.close(fd)
    os.environ[LOG] = path; atexit.register(os.remove, path)
    os.environ["PYTHONPATH"] = os.pathsep.join(p for p in (os.path.join(HERE, "offline_site"), HERE, os.environ.get("PYTHONPATH")) if p)
    install()
    return path

def sent(who=None):
    """The requests refused so far, once each: as {who, host, port, process}; with `who`, only a check's own, with None
    only those no check claimed."""
    seen, out = set(), []
    with open(os.environ[LOG], encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            key = (r["who"], r["host"], r["port"], r["process"])
            if r["who"] == (who or "") and key not in seen: seen.add(key); out.append(r)
    return out

def words(requests):
    """Each refused request as a failure reason."""
    return [f"a request went out that no planted answer serves: {r['host']}:{r['port']}" + (f", from {r['process']}" if r["process"] else "") for r in requests]
