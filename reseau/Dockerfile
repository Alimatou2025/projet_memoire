# Utilisation d'une image Debian légère (Bookworm-slim) pour économiser de l'espace
FROM debian:bookworm-slim

# Mise à jour des dépôts et installation des outils réseau indispensables
# hostapd : pour créer le point d'accès Wi-Fi
# dnsmasq : pour donner des adresses IP (DHCP) et gérer le nom de domaine (DNS)
# iw & net-tools : pour configurer la carte réseau physique
RUN apt-get update && apt-get install -y \
    hostapd \
    dnsmasq \
    iw \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Expose les ports standards pour le réseau
# Port 53 (UDP) : Service DNS (résolution de noms)
# Port 67 (UDP) : Service DHCP (attribution des IPs aux élèves)
EXPOSE 53/udp 67/udp

# La commande de démarrage (ENTRYPOINT)
# On lance hostapd en arrière-plan (&) puis dnsmasq au premier plan (-k)
# -k force dnsmasq à rester actif pour que le conteneur ne s'arrête pas
CMD hostapd /etc/hostapd/hostapd.conf & dnsmasq -k -C /etc/dnsmasq.conf
