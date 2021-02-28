import time, ifcfg, subprocess, os, speedtest


DEF_GTW = False
OVPN_GTW = False
INTERNAL_SUBNET = os.getenv("INTERNAL_SUBNET")
GTW_MAX_PING_DELAY_MS = 1000
MIN_OVPN_DL_SPEED = 10
MIN_OVPN_UP_SPEED = 10
FNULL = open(os.devnull, 'w')
relative_clock = 1

def periodically_schedule_tasks():
  global MIN_OVPN_DL_SPEED
  global MIN_OVPN_UP_SPEED
  global OVPN_READY
  global relative_clock
  
  if relative_clock >= 60*60*24:
    relative_clock = 0
  
  if relative_clock % 60 * 60 * 3 == 0: #Every 3 hours
    if not OVPN_READY:
      print("Ovpn down. Force restart")
      restart_ovpn()
      return


    qos = _speedtest()
    print("QoS: {}".format(qos))
    if qos["dl"] < MIN_OVPN_DL_SPEED or qos["up"] < MIN_OVPN_UP_SPEED:
      Print("QoS too bad. Restart ovpn")
      restart_ovpn()
      return


def restart_ovpn():
  print("Periodicall ovpn restart for performances purpose")
  global WG_READY
  WG_READY = False
  switch_wireguard_off()
  subprocess.check_call("s6-svc -r /var/run/s6/services/openvpn".split(), stdout=FNULL, stderr=FNULL)
  time.sleep(10)

def _speedtest():
  forced_wg_ip_source = ".".join(INTERNAL_SUBNET.split(".")[:-1] + ["1"])

  print(forced_wg_ip_source)
  s = speedtest.Speedtest(source_address=forced_wg_ip_source)
  s.get_servers([])
  s.get_best_server()
  s.download(threads=1)
  s.upload(threads=1, pre_allocate=False)
  r = s.results.dict()
  return {
    "dl": float("{:.2f}".format(r["download"] *8 / 1000 / 1000)),
    "up": float("{:.2f}".format(r["upload"] *8 / 1000 / 1000)),
    "ping": r["ping"],
  }


def ping(host):
    """
    Returns True if host (str) responds to a ping request.
    Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
    """

    # Option for the number of packets as a function of

    # Building the command. Ex: "ping -c 1 google.com"
    command = ['fping', "-c", '1', "-t", str(GTW_MAX_PING_DELAY_MS), host]
    try:
      subprocess.check_call(command, stdout=FNULL, stderr=FNULL)
      return True
    except:
      return False

def is_wireguard_up():
  try:
    a = fcfg.interfaces()["wg0"]
    return True
  except:
    return False

def create_route_table_if_required():
  rule_already_set = False
  with open('/etc/iproute2/rt_tables', "r") as f:
    if "vpn" in f.read():
      rule_already_set = True
  
  if not rule_already_set:
    print("Create vpn table in ip2routes")
    with open('/etc/iproute2/rt_tables', "a") as f:
      f.write("200     vpn")

def set_wireguard_routes():
  global OVPN_GTW
  global DEF_GTW

  create_route_table_if_required()
  print("ip rule add from {subnet}/24 table vpn".format(subnet=INTERNAL_SUBNET))
  print("ip route add default via {gtw} dev tun0 table vpn".format(gtw=OVPN_GTW))
  subprocess.call("ip rule add from {subnet}/24 table vpn".format(subnet=INTERNAL_SUBNET).split(), stdout=FNULL, stderr=FNULL)
  subprocess.call("ip route add default via {gtw} dev tun0 table vpn".format(gtw=OVPN_GTW).split(), stdout=FNULL, stderr=FNULL)
  subprocess.call("ip route add {def_gtw} via {def_gtw} dev eth0 table vpn".format(def_gtw=DEF_GTW).split(), stdout=FNULL, stderr=FNULL)

def unset_wireguard_routes():
  global OVPN_GTW

  create_route_table_if_required()
  subprocess.call("ip rule del from {subnet}/24 table vpn".format(subnet=INTERNAL_SUBNET).split(), stdout=FNULL, stderr=FNULL)
  subprocess.call("ip route del default via {gtw} dev tun0 table vpn".format(gtw=OVPN_GTW).split(), stdout=FNULL, stderr=FNULL)
  subprocess.call("ip route del {def_gtw} via {def_gtw} dev eth0 table vpn".format(def_gtw=DEF_GTW).split(), stdout=FNULL, stderr=FNULL)


def switch_wireguard_on():
  print("Turn wireguard on")
  set_wireguard_routes()
  subprocess.call(["wg-quick", "up", "wg0"])

def switch_wireguard_off():
  print("Turn wireguard off")
  unset_wireguard_routes()
  subprocess.call(["wg-quick", "down", "wg0"])


def get_default_gateway():
  eth0_interface = ifcfg.interfaces()["eth0"]
  def_gtw = ".".join(eth0_interface["inet"].split(".")[:-1] + ["1"])
  return def_gtw

def is_ovpn_ready():
  global OVPN_GTW
  try:
    ovpn_interface = ifcfg.interfaces()["tun0"]
  except:
    return False
    print("Openvpn not ready")


  ip = ovpn_interface["inet"]
  OVPN_GTW = ".".join(ovpn_interface["inet"].split(".")[:-1] + ["1"])
  is_gtw_responding = ping(OVPN_GTW)
  return is_gtw_responding

DEF_GTW = get_default_gateway()
time.sleep(10)
print("Manager ready")
WG_READY = is_wireguard_up()
OVPN_READY = is_ovpn_ready()



while 1:
  OVPN_READY = is_ovpn_ready()
  if OVPN_READY and not WG_READY:
    switch_wireguard_on()
    WG_READY = True
    _speedtest()
  
  if not OVPN_READY and WG_READY:
    switch_wireguard_off()
    WG_READY = False
  
  relative_clock += 1
  time.sleep(1)
  periodically_schedule_tasks()