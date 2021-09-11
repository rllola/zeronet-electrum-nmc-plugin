import logging, json, os, re, sys, time, socket, signal
from Plugin import PluginManager
from Config import config
from Debug import Debug
from http.client import HTTPSConnection, HTTPConnection, HTTPException
from base64 import b64encode
import subprocess

allow_reload = False # No reload supported

@PluginManager.registerTo("SiteManager")
class SiteManagerPlugin(object):
    def __del__(self):
        if self.electrum_pid:
            os.kill(self.electrum_pid, signal.SIGTERM)
            self.log.debug("Kill electrum pid : {}".format(self.namecoin_pid))
            return

    def load(self, *args, **kwargs):
        super(SiteManagerPlugin, self).load(*args, **kwargs)
        self.log = logging.getLogger("ZeronameElectrumNMC Plugin")
        self.error_message = None
        self.electrum_pid = None

        electrum_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "Electrum-NMC")

        p = subprocess.Popen([os.path.join(electrum_dir, "run_electrum_nmc"),"daemon","-P"])
        self.electrum_pid = p.pid

        # Need to wait for daemon file to be updated
        time.sleep(2)

        electrum_data_dir = os.path.join(electrum_dir, "electrum_nmc_data")

        with open(os.path.join(electrum_data_dir, "daemon")) as daemon_file:
            daemon_config = daemon_file.read().replace("(", "").replace(")","").split(",")
            host = daemon_config[0].replace("'", "")
            port = int(daemon_config[1])

        with open(os.path.join(electrum_data_dir, "config")) as config_file:
            config_rpc = json.loads(config_file.read())
            rpcuser = config_rpc["rpcuser"]
            rpcpassword = config_rpc["rpcpassword"]
        

        url = "%(host)s:%(port)s" % {"host": host, "port": port}
        self.c = HTTPConnection(url, timeout=3)
        user_pass = "%(user)s:%(password)s" % {"user": rpcuser, "password": rpcpassword}
        userAndPass = b64encode(bytes(user_pass, "utf-8")).decode("ascii")
        self.headers = {"Authorization" : "Basic %s" %  userAndPass, "Content-Type": " application/json " }

        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": "zeronet",
            "method": "ping",
            "params": []
        })

        try:
            self.c.request("POST", "/", payload, headers=self.headers)
            response = self.c.getresponse()
            data = response.read()
            self.c.close()
            if response.status == 200:
                result = json.loads(data.decode())["result"]
            else:
                raise Exception(response.reason)
        except Exception as err:
            self.log.error("The Namecoin node is unreachable. Please check the configuration value are correct. Zeronet will continue working without it.")
            self.error_message = err
        self.cache = dict()

    # Checks if it's a valid address
    def isAddress(self, address):
        return self.isBitDomain(address) or super(SiteManagerPlugin, self).isAddress(address)

    # Return: True if the address is domain
    def isDomain(self, address):
        return self.isBitDomain(address) or super(SiteManagerPlugin, self).isDomain(address)

    # Return: True if the address is .bit domain
    def isBitDomain(self, address):
        return re.match(r"(.*?)([A-Za-z0-9_-]+\.bit)$", address)

    # Return: Site object or None if not found
    def get(self, address):
        if self.isBitDomain(address):  # Its looks like a domain
            address_resolved = self.resolveDomain(address)
            if address_resolved:  # Domain found
                site = self.sites.get(address_resolved)
                if site:
                    site_domain = site.settings.get("domain")
                    if site_domain != address:
                        site.settings["domain"] = address
            else:  # Domain not found
                site = self.sites.get(address)

        else:  # Access by site address
            site = super(SiteManagerPlugin, self).get(address)
        return site

    # Return or create site and start download site files
    # Return: Site or None if dns resolve failed
    def need(self, address, *args, **kwargs):
        if self.isBitDomain(address):  # Its looks like a domain
            address_resolved = self.resolveDomain(address)
            if address_resolved:
                address = address_resolved
            else:
                return None

        return super(SiteManagerPlugin, self).need(address, *args, **kwargs)

    # Resolve domain
    # Return: The address or None
    def resolveDomain(self, domain):
        domain = domain.lower()

        #remove .bit on end
        if domain[-4:] == ".bit":
            domain = domain[0:-4]

        domain_array = domain.split(".")

        if self.error_message:
            self.log.error("Not able to connect to Namecoin node : {!s}".format(self.error_message))
            return None

        if len(domain_array) > 2:
            self.log.error("Too many subdomains! Can only handle one level (eg. staging.mixtape.bit)")
            return None

        subdomain = ""
        if len(domain_array) == 1:
            domain = domain_array[0]
        else:
            subdomain = domain_array[0]
            domain = domain_array[1]

        if domain in self.cache:
            delta = time.time() - self.cache[domain]["time"]
            if delta < 3600:
                # Must have been less than 1hour
                return self.cache[domain]["addresses_resolved"][subdomain]

        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": "zeronet",
            "method": "name_show",
            "params": ["d/"+domain]
        })

        try:
            self.c.request("POST", "/", payload, headers=self.headers)
            response = self.c.getresponse()
            data = response.read()
            self.c.close()
            domain_object = json.loads(data.decode())["result"]
        except Exception as err:
            #domain doesn't exist
            return None

        if "zeronet" in domain_object["value"]:
            zeronet_domains = json.loads(domain_object["value"])["zeronet"]

            if isinstance(zeronet_domains, str):
                # {
                #    "zeronet":"19rXKeKptSdQ9qt7omwN82smehzTuuq6S9"
                # } is valid
                zeronet_domains = {"": zeronet_domains}

            self.cache[domain] = {"addresses_resolved": zeronet_domains, "time": time.time()}

        elif "map" in domain_object["value"]:
            # Namecoin standard use {"map": { "blog": {"zeronet": "1D..."} }}
            data_map = json.loads(domain_object["value"])["map"]

            zeronet_domains = dict()
            for subdomain in data_map:
                if "zeronet" in data_map[subdomain]:
                    zeronet_domains[subdomain] = data_map[subdomain]["zeronet"]
            if "zeronet" in data_map and isinstance(data_map["zeronet"], str):
                # {"map":{
                #    "zeronet":"19rXKeKptSdQ9qt7omwN82smehzTuuq6S9",
                # }}
                zeronet_domains[""] = data_map["zeronet"]

            self.cache[domain] = {"addresses_resolved": zeronet_domains, "time": time.time()}

        else:
            # No Zeronet address registered
            return None

        return self.cache[domain]["addresses_resolved"][subdomain]
