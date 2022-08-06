# --------------------------------------------------------------------------
# Description : this code read 2 TeleInfo counters on a FTDi interface from
#               CarteElectronic (https://www.cartelectronic.fr/)
#               v1.0 from David ROUMANET. Date: 2021-05-24.
#               * v1.1 correction INSTI and EAIT for Production
#               + v1.2 added mySQL write
#               - v1.3 remove mySQL and change filename (2022-07-30)
#               + v1.4 broadcast to UDP port (2022-08-01)
#               * v1.5 enhance and securize code (2022-08-05)
# --------------------------------------------------------------------------

# pip install pylibftdi
from pylibftdi import Device
from time import time, process_time, sleep
import datetime
import socket
import json
import logging
# code for log to systemd isn't working : from systemd import Journal

# ============= Variables Declaration =============================================================
version = 1.5

# Choose an UDP port number which will receive broadcast messages
dst_port = 65432

# Object to transmit via UDP broadcast
compteurConso = {
    "TYPE": "CONSOMMATION",
    "DATE": "",
    "PRM": "",
    "EASF01": "",
    "EASF02": "",
    "IRMS1": "",
    "URMS1": "",
    "SINSTS": "",
    "UMOY1": "",
    "NGTF": "",
    "NTARF": "",
    "MSG1": "",
    "SMAXSN": "",
    "SMAXSN1": "",
    "RELAIS": ""
}
compteurProd = {
    "TYPE": "PRODUCTION",
    "DATE": "",
    "PRM": "",
    "EASF01": "",
    "EAIT": "",
    "IRMS1": "",
    "URMS1": "",
    "SINSTI": "",
    "SMAXIN": "",
    "SMAXIN1": "",
    "NGTF": "",
    "MSG1": ""
}

# When TeleInfo key could not be used with JSON Format. Add yours other exceptions here
keyword_replacement = {"SMAXSN-1":"SMAXSN1", "SMAXIN-1":"SMAXIN1" }

# attributes we want to read, you can add or remove some of them for your own needs
ListeConso = ["DATE", "EASF01", "SMAXSN", "SMAXSN-1", "NTARF", "IRMS1",
              "URMS1", "UMOY1", "MSG1", "PRM", "RELAIS", "PREF", "SINSTS", "NGTF", "PCOUP"]
ListeProd = ["DATE", "EASF01", "EAIT", "IRMS1", "URMS1", "MSG1",
             "PRM", "RELAIS", "PREF", "SINSTI", "SMAXIN", "SMAXIN-1", "NGTF"]

HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
Src_port = 0  # Source Port (0 means auto selection by the OS)

logging.basicConfig(filename='teleinfo.log', filemode='w', format='%(levelname)s - %(message)s')
logging.info("Démarrage")


# === Error with system importation, so cannot use this
# journal = JournaldLogHandler()
# journal.setFormatter(logging.Formatter( '[%(levelname)s] %(message)s' ))
# logger.addHandler(journal.journaldLoghandler())
# logger.setLevel(logging.INFO)

error_numbers = 0


# ============= Functions Declaration ============================================================

def log_messages(error_msg, error_code=0):
    global error_numbers

    error_numbers = error_numbers + 1
    # Do not log after 5x
    if error_numbers < 6 or (error_numbers % 50) == 0:
        x = str(datetime.datetime.now())
        # Log and wait
        if error_code:
            print("CRITICAL ",error_msg)
            logging.error((x+" TeleInfo message for " + str(error_numbers)+" times. "+error_msg))
            sleep(60)
        else:
            print("INFO ",error_msg)
            logging.info((x+" TeleInfo message for " + str(error_numbers)+" times. "+error_msg))
        


def checksum(x):
    # Frame : <0x0A> ETIQUETTE <0x09> DONNEE <0x09> Checksum <0x0D>
    #          (LF)             (HT)        (HT)            (CR)
    # La checksum est calculée sur l'ensemble des caractères allant du début du champ Etiquette à la fin du champ Donnée, caractères < HT > inclus.
    # Le principe de calcul de la Checksum est le suivant :
    # - calcul de la somme « S1 » de tous les caractères allant du début du champ « Etiquette » jusqu’au délimiteur (inclus) entre les
    #   champs « Donnée » et « Checksum ») ;
    # - cette somme déduite est tronquée sur 6 bits (cette opération est faite à l’aide d’un ET logique avec 0x3F) ;
    # - pour obtenir le résultat checksum, on additionne le résultat précédent S2 à 0x20.
    # En résumé : Checksum = (S1 & 0x3F) + 0x20
    # Le résultat sera toujours un caractère ASCII imprimable compris entre 0x20 et 0x5F.

    start_frame = 0
    if ord(x[0]) == 0x0A:
        start_frame = 1                        # avoid LF char
    end_frame = (len(x)-1)-start_frame - 2     # avoid 3 chars : HT Checksum CR
    csum = 0
    for t in range(start_frame, end_frame):
        if ord(x[t]) > 0x19 or ord(x[t]) == 0x09:
            csum = (csum + ord(x[t]))
    csum = (csum & 0x3F) + 0x20  # offset +32 to ensure ASCII visible caracter
    # print('Checksum():['+chr(csum)+'] should be ['+x[len(x)-3]+"] #"+x[start_frame:end_frame]+"#" )
    if chr(csum) == x[len(x)-3]:
        return True
    log_messages("Checksum problem (Troubleshoot wired connexion)", False)
    return False

# Function to clean up FTDi buffer (TeleInfo 2 have one component and 2 channels)
def clear_teleinfo():
    chrono_start = time()
    while time()-chrono_start < 1:
        try:
            dev.readline(50)
        except Exception as e:
            log_messages("Cannot read FTDi stream ("+e+")", True)

# Function to read specific properties of TeleInfo (not all)
def read_teleinfo(compteur, liste_travail):
    # compteur is the JSON structure to fill
    # liste_travail is the list of keywords to listen
    global error_numbers

    # listeTravail is a pointer: this function copy the original list and will remove element when found in frames
    liste_temp = liste_travail.copy()
    tableau = []
    chaine = ""
    clear_teleinfo()
    # Start a loop for 4 seconds or less if all attributes were found
    chrono_start = time()
    while time()-chrono_start < 5 and len(liste_temp) > 0:
        try:
            chaine = dev.readline(50)
        except Exception as e:
            log_messages("Cannot read FTDi stream ("+e+")", True)
        finally:
            tableau = chaine.split()
            # print(tableau)
            if len(tableau) > 1:

                trouve = ""
                # Check all attributes : remove it from the list if found
                for mot in liste_temp:
                    if tableau[0] == mot and checksum(chaine) == True:
                        error_numbers = 0    # Reset Error
                        trouve = mot
                        # tableau[0] = "SMAXSN-1" : not possible in JSON format, convert "SMAXSN1"
                        try:
                            if keyword_replacement[tableau[0]]:
                                tableau[0] = keyword_replacement[tableau[0]]
                        except KeyError:
                            pass
                        # delete old value to avoid cumulative string
                        compteur[tableau[0]] = ""
                        # exception for MSG1, SMAXSN.. which have many words
                        if len(tableau) > 1:
                            for t in range(1, len(tableau)-1):
                                compteur[tableau[0]] = compteur[tableau[0]] + tableau[t] + " " 
                                # print(tableau[0], " => ",str(t)+": ["+tableau[t],"]  soit ", compteur[tableau[0]])
                            compteur[tableau[0]] = compteur[tableau[0]].strip()
                            # checksumchar((chaine)) for DEBUG
                        else:
                            compteur[tableau[0]] = tableau[1][:-1]  # Remove last char of tableau[1]
                if trouve > "":
                    liste_temp.pop(liste_temp.index(trouve))
    if len(liste_temp) > 0:
        log_messages("All TAGS not found. Unread Tags: " + str(len(liste_temp)), False)
    return compteur


# ==================================================================================================



####################  MAIN PART  ##########################


# Start UDP broadcast server
server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
server.settimeout(0.2)
server.bind(("", Src_port))
txt_start = "UDP Teleinfo Broadcast server v"+str(version)+" started"
print(txt_start)
log_messages(txt_start, False)

# Read TeleInfo device
with Device(mode='t') as dev:
    print(dev.baudrate)
    # set 8 bit data, 2 stop bits, no parity
    dev.ftdi_fn.ftdi_set_line_property(7, 1, 1)

    while True:
        # set channel one (0x11)
        dev.ftdi_fn.ftdi_set_bitmode(0x11, 0x20)
        # print("Reading channel 1 (CONSO) --------------------")
        read_teleinfo(compteurConso, ListeConso)
        # print("  puissance CONSOMMEE: " +compteurConso['SINSTS']+"w  Max: "+compteurConso['SMAXSN']+"w")

        if compteurConso['SINSTS'] == "":       # BUG: should never be empty but sometime it is
            log_messages("Bad value SINSTS: "+compteurConso['SINSTS']+"  (PRM:"+compteurConso['PRM']+"  Max:"+compteurConso['SMAXSN']+")")
        else:
            server.sendto(json.dumps(compteurConso).encode(), ('<broadcast>', dst_port))

        # set channel two (0x22)
        dev.ftdi_fn.ftdi_set_bitmode(0x22, 0x20)
        # print("Reading channel 2 (PROD) --------------------")
        read_teleinfo(compteurProd, ListeProd)
        # print("  puissance PROD: " + compteurProd['SINSTI']+"w  Max: "+compteurProd['SMAXIN']+"w")
        server.sendto(json.dumps(compteurProd).encode(), ('<broadcast>', dst_port))
        sleep(3)
