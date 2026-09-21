#!/bin/sh
echo "En attente de l'interface wlan1 (clé USB)..."
i=0
while ! ip link show wlan1 > /dev/null 2>&1; do
    i=$((i+1))
    if [ "$i" -gt 30 ]; then
        echo "ERREUR : wlan1 n'est toujours pas disponible après 30s, abandon."
        exit 1
    fi
    sleep 1
done
echo "wlan1 est prêt (après ${i}s d'attente)."

ip link set wlan1 up
ip addr add 192.168.1.1/24 dev wlan1 2>/dev/null

pkill hostapd 2>/dev/null
sleep 1
hostapd /etc/hostapd/hostapd.conf &

sleep 5

iptables -t nat -F PREROUTING
iptables -t nat -A PREROUTING -i wlan1 -p tcp --dport 80 -j REDIRECT --to-port 8000

dnsmasq -k -C /etc/dnsmasq.conf
