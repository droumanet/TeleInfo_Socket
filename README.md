# TeleInfo_Socket
Create an UDP server able to broadcast TeleInfo read on 'CarteElectronic' device (with 2 counters)
The device is [TeleInfo 2 compteurs](https://www.cartelectronic.fr/teleinfo-compteur-enedis/8-teleinfo-2-compteurs-usb-3760313520103.html)
You may have to adapt this script for other products.
The script use "Standard" mode and not "Historic" mode: you'll have to ask a modification on linky, by Enedis.


## What it does
The script does two important things :
* Reading each channel of the device. It's one channel at a time, so, values aren't in continuous (reading all counters took around 7 seconds)
* Broadcasting two JSON object (CPT-1 and CPT-2) on UDP port 65432

That way, any service listening on the same LAN could receive the information. Example with Wireshark:
![image](https://user-images.githubusercontent.com/24438463/183285469-3aeec6df-a58b-4b07-afa3-49999aadd229.png)


## How to run it
The project use Python 3 or more to run.
It is a simple Python script, with some import, so you need to use de `pip install`command :
* pylibftdi (this part needs some drivers installed on the system: `apt install...` commands)
* time
* socket
* json
* logging

Simply launch the script `python3 ./teleinfo_socket.py`, you will see only one line informing the script is running
In case of error, you'll have to consult teleinfo.log (for example, `tail -f teleinfo.log`)


## How to install it as service
This part is simple and easy, but I'm going to give some troubleshooting tips.

1. Install the script file in the place you want it to be run
   `mv ./teleinfo_socket.py <anywhere>`
2. With root permission (sudo), create a new file `teleinfo.service` in `/etc/systemd/system/` with following information :
```
[Unit]
Description=TeleInfo broadcast (on UDP port 65432) service
After=multi-user.target

[Service]
ExecStart=/usr/bin/python3 <anywhere>/teleinfo_socket.py
Type=simple
Restart=always
PIDFile=/run/teleinfo.pid

[Install]
WantedBy=multi-user.target

```
3. Check your file is correct for systemd : `sudo systemd-analyze verify teleinfo.service`
4. Restart system control : `sudo systemctl daemon-reload`
5. Enable teleinfo service (it will automaticaly run on startup) : `sudo systemctl enable teleinfo.service`
6. Start manually teleinfo service : `sudo systemctl start`


## Result
I'm reading values for my Home Automation system, here is what my Node.JS app shows me.
![image](https://user-images.githubusercontent.com/24438463/183285577-5bcf3749-4237-4da3-936c-190d52f8d5c9.png)
