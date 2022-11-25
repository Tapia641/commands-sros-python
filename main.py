"""
:version 2.1
:author Luis Tapia
:email: luis.e.hernandez.ext@nokia.com

This script is intended to run ATP commands and do analisis to save time.

For further detail about how to use this script please refer to README.md file.
"""

import argparse
from functools import total_ordering
import logging
import sys

import paramiko
import time
import yaml
import re
import os


class SROS:

    # Global variables
    session = None
    data = None
    jumpbox_transport = None
    JUMP_VM = None
    HOTS_GATEWAYS = None
    mac_list = []
    commands = []

    # Constructor of the class
    def __init__(self, args, commands_):
        """
        Constructor of the class, initialize the Global variables
        :param data: 
        :param args:
        """
        stream = open(r'information.yml', 'r')
        yaml_info = yaml.load(stream, Loader=yaml.FullLoader)

        self.args = args
        self.HOTS_GATEWAYS = yaml_info['wbx']['items']
        self.JUMP_VM = yaml_info['jump_vm']
        self.commands = commands_

    def get_wbx_information(self):
        # IF WE HAVE MORE WE NEED TO SELECT THE RIGHT ONE
        if self.JUMP_VM['use']:  # If we use jump vm

            ip = self.JUMP_VM['host']
            logging.info(f'SSH to the JUMP via:{ip}')

            self.connect_to_jump_vm()

            for site in self.HOTS_GATEWAYS:
                logging.info(f"Working over {site['name']} ...")
                self.connect_to_wbx_with_jump(site)
            self.close_jump_vm()

        else:  # IF WE HAVE THE VPN
            for host in self.HOTS_GATEWAYS:
                for site in self.HOTS_GATEWAYS[host]:
                    logging.info(f"Working over {host} - {site['name']} ...")
                    self.connect_to_wbx_with_jump(site)

    def connect_to_jump_vm(self):
        # Configurations of JUMP VM
        jumpbox = paramiko.SSHClient()
        jumpbox.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        jumpbox.connect(
            self.JUMP_VM['host'], username=self.JUMP_VM['user'], password=self.JUMP_VM['password'])
        self.jumpbox_transport = jumpbox.get_transport()

    def close_jump_vm(self):
        self.jumpbox_transport.close()

    def connect_to_wbx_with_jump(self, wbx):
        try:
            ip_wbx = wbx['host']
            name_wbx = wbx['name']

            logging.info(f'SSH to the WBX {name_wbx}:{ip_wbx}')

            # Connect to the WBX through Jump VM
            dest_addr = (wbx['host'], wbx['port'])
            src_addr = ('localhost', 22)

            jumpbox_channel = self.jumpbox_transport.open_channel(
                "direct-tcpip", dest_addr, src_addr)

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(
                paramiko.AutoAddPolicy())

            client.connect(hostname=wbx['host'], port=wbx['port'],
                           username=wbx['user'], password=wbx['password'],
                           look_for_keys=False, allow_agent=False, sock=jumpbox_channel)

            shell = client.invoke_shell()
            active_connection = shell

            bgp_peers_leaves = []
            pass_next_line = False
            total_line = ""
            for num, command in enumerate(self.commands):
                if active_connection.send(f"{command} \r\n") > 0:
                    
                    time.sleep(5)
                    data = active_connection.recv(65535)
                    output = data.decode('utf-8')

                    for line in output.splitlines():
                        total_line+=line + "\n"

                        if num == 2 and "Count" in line:
                            self.chassis_info(line, name_wbx)
                        if num == 3 and "Count" in line:
                            self.card_info(line, name_wbx)
                        if num == 4 and "Count" in line:
                            self.mda_info(line, name_wbx)

            self.export_file(name_wbx, total_line)
            active_connection.close()
            client.close()

        except Exception as error:
            logging.error(f"{error}")
    
    @staticmethod
    def chassis_info(line, name_wbx):
        print("<center><b>",name_wbx,"</b></center>")
        print("##### CHASSIS:")
        print("```")
        if "7 lines" in line:
            print(" OK: We have 5 Fan trays UP.")
            print(" OK: We have 2 Power supplies UP.")
        else:
            print(f" NOT OK: Requires further analysis [go to folder tmp/{name_wbx}]")
        print("```")

    @staticmethod
    def card_info(line, name_wbx):
        print("##### CARD:")
        print("```")
        if "2 lines" in line:
            print(" OK: The iom-32-100g admin & operational is UP.")
            print(" OK: The sfm-210-WBX admin & operational is UP.")
        else:
            print(f" NOT OK: Requires further analysis [go to folder tmp/{name_wbx}]")
        print("```")

    @staticmethod
    def mda_info(line, name_wbx):
        print("##### MDA:")
        print("```")
        if "2 lines" in line:
            print(" OK: The mda 1 m16-100g-qsfp28 admin & operational is UP.")
            print(" OK: The mda 2 m16-100g-qsfp28 admin & operational is UP.")
        else:
            print(f" NOT OK: Requires further analysis [go to folder tmp/{name_wbx}]")
        print("```")

    def export_file(self, name, data):
        try:
            os.makedirs(f"tmp/{name[0:10]}", exist_ok = True)
        except OSError as error:
            print(f"Directory tmp/{name[0:10]} can not be created")

        with open(f"tmp/{name[0:10]}/{name}.log", "w") as text_file:
            text_file.write(data)


if __name__ == '__main__':
    # CHECK IF THE ARGUMENTS ARE PRESENT
    parser = argparse.ArgumentParser()

    # GET ALL ARGUMENTS
    start_time = time.perf_counter()
    args = parser.parse_args()

    # LOGS
    logging.basicConfig(format="%(asctime)s: %(message)s", level=logging.INFO,
                        datefmt="%H:%M:%S")

    # LIST OF COMMANDS
    commands = [
        # 5. HARDWARE TEST
        'environment no more',
        'show time',
        'show chassis | match ": up"  | count',
        'show card | match up  | count',
        'show mda | match up  | count',
        # 'show port | match 1/2/33 post-lines 7 | match Up | count',
        # 'show bof',
        # 'show system ntp servers',
        # 'show router bgp summary',
        # 'show router route-table',
        # 'show vswitch-controller xmpp-server',
        # 'show vswitch-controller vsd',
        # 'show router interface ',
        # 'show vswitch-controller enterprise',
        # 'show vswitch-controller vports type  bridge',
        # '',
        ]
    # DO SOMETHING
    sros_class = SROS(args, commands)
    sros_class.get_wbx_information()
    # sros_class.do_analysis()

    end_time = time.perf_counter() - start_time
    logging.info(f"Script finished in {end_time:0.2f} seconds.")
