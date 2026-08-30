#!/bin/sh
echo "En attente de l'interface wlan0..."
i=0
while ! ip link show wlan0 > /dev/null 2>&1; do
    i=$((i+1))
    if [ "$i" -gt 30 ]; then
        echo "ERREUR : wlan0 n'est toujours pas disponible après 30s, abandon."
        exit 1
    fi
    sleep 1
done
echo "wlan0 est prêt (après ${i}s d'attente)."

demarrer_ap() {
    ip link show uap0 > /dev/null 2>&1 && iw dev uap0 del 2>/dev/null
    iw dev wlan0 interface add uap0 type __ap
    ip link set uap0 up
    ip addr add 192.168.1.1/24 dev uap0 2>/dev/null
    pkill hostapd 2>/dev/null
    sleep 1
    hostapd /etc/hostapd/hostapd.conf &
}

demarrer_ap

(
  absences=0
  while true; do
    sleep 15
    probleme=0

    if ! ip link show uap0 > /dev/null 2>&1; then
      probleme=1
      echo "Problème : uap0 n'existe plus"
    elif ! ip addr show uap0 | grep -q "192.168.1.1"; then
      ip addr add 192.168.1.1/24 dev uap0 2>/dev/null
    fi

    if ! pgrep hostapd > /dev/null 2>&1; then
      probleme=1
      echo "Problème : hostapd n'est plus en cours d'exécution"
    fi

    if [ "$probleme" -eq 1 ]; then
      absences=$((absences+1))
      echo "Confirmation n°${absences}"
      if [ "$absences" -ge 2 ]; then
        echo "Problème confirmé, redémarrage complet du point d'accès..."
        demarrer_ap
        absences=0
      fi
    else
      absences=0
    fi
  done
) &

sleep 5

iptables -t nat -F PREROUTING
iptables -t nat -A PREROUTING -i uap0 -p tcp --dport 80 -j REDIRECT --to-port 8000

dnsmasq -k -C /etc/dnsmasq.conf
