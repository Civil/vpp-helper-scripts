#!/bin/bash

declare -A seenCards

# Example result, per card
# set int mtu 2026 cx6-0-0
# set int mtu 2026 cx6-0-1
# set int state cx6-0-0 up
# set int state cx6-0-1 up
# set int l2 xconnect cx6-0-0 cx6-0-1
# set int l2 xconnect cx6-0-1 cx6-0-0

OLD_IFS=${IFS}
IFS=$'\n'
OLD_DEV="0"
card_num=0
port_num=0
for c in $(lspci | grep Ether | grep -i mella | grep -v '4 Lx'); do
	dev=$(awk '{print $1}' <<< ${c})
	dev_main=$(cut -d'.' -f 1 <<< ${dev})
	card_name="cx$(grep -E -o 'ConnectX-[0-9]+' <<< ${c} | cut -d'-' -f 2)"
	if [[ ${dev_main} == ${OLD_DEV} ]]; then
		continue
	fi
	card_num="${seenCards["${card_name}"]}"
	if [[ -z ${card_num} ]]; then
		card_num=0
	fi
	seenCards["${card_name}"]=$((card_num+1))
	name="${card_name}-${card_num}"
	echo "set int mtu 2026 ${name}-0"
	echo "set int mtu 2026 ${name}-1"
	echo "set int state ${name}-0 up"
	echo "set int state ${name}-1 up"
	echo "set int l2 xconnect ${name}-0 ${name}-1"
	echo "set int l2 xconnect ${name}-1 ${name}-0"

	OLD_DEV=${dev_main}
	echo
done
IFS=${OLD_IFS}
