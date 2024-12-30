#!/bin/bash

declare -A seenCards

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
		port_num=1
	else
		echo
		card_num="${seenCards["${card_name}"]}"
		if [[ -z ${card_num} ]]; then
			card_num=0
		fi
		seenCards["${card_name}"]=$((card_num+1))
		port_num=0
	fi
	name="${card_name}-${card_num}-${port_num}"
	echo "dev ${dev} { name ${name} num-tx-queues 8 num-rx-queues 8 num-tx-desc 4096 num-rx-desc 2048 devargs mprq_en=1,rxqs_min_mprq=1,mprq_log_stride_num=8,txq_inline_mpw=128,rxq_pkt_pad_en=1 }"
	OLD_DEV=${dev_main}
done
IFS=${OLD_IFS}
