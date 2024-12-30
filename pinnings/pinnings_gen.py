#!/usr/bin/env python3
import collections
import subprocess
import re
import sys

def parse_lstopo():
    result = subprocess.run(['/usr/bin/lstopo'], capture_output=True, check=True)
    numa2core = collections.defaultdict(list)
    numa2ht = collections.defaultdict(list)
    pci2numa = collections.defaultdict(int)
    pci2netdev = collections.defaultdict(list)

    was_pu = False
    numa_node_re = re.compile(r'^\s+NUMANode L#([0-9]+)')
    core_re = re.compile(r'^\s+PU L#[0-9]+ \(P#([0-9]+)')
    l2_re = re.compile(r'^\s+L2')
    pci_re = re.compile(r'^\s+PCI\s+([^ ]+)\s+')
    netdev_re = re.compile(r'^\s+Net\s+"(.*)"')

    numa_node = 0
    core = 0
    pci = ""
    netdev = ""
    for l in str(result.stdout).split("\\n"):
        m = numa_node_re.match(l)
        if m:
            numa_node = int(m.group(1))
            continue
        m = core_re.match(l)
        if m:
            core = int(m.group(1))
            if was_pu:
                numa2ht[numa_node].append(core)
            else:
                numa2core[numa_node].append(core)
                was_pu = True
            continue
        m = l2_re.match(l)
        if m:
            was_pu = False
            continue
        m = pci_re.match(l)
        if m:
            pci = m.group(1)
            pci2numa[pci] = numa_node
            continue
        m = netdev_re.match(l)
        if m:
            netdev = m.group(1)
            pci2netdev[pci] = netdev
            continue

    return (numa2core, numa2ht, pci2numa, pci2netdev)


def parse_dev_line(params):
    res = {}
    tokens = params.split()
    i = 0
    while True:
        res[tokens[i]] = tokens[i+1]
        i = i+2
        if i == len(tokens):
            break
    return res


def parse_corelist(corelist):
    res = []
    core_groups = corelist.split(',')
    for group in core_groups:
        core_range = group.split('-')
        if len(core_range) == 1:
            res.append(int(core_range))
            continue
        for c in range(int(core_range[0]), int(core_range[1])+1):
            res.append(c)

    return res

def generate_pinnings(filename="/etc/vpp/startup.conf"):
    numa2core, numa2ht, pci2numa, _ = parse_lstopo()
    core2worker = {}
    exclude_cores = []
    allowed_cores = []
    dpdk_section = False
    main_core_re = re.compile(r'^\s+main-core\s+([0-9]+)')
    corelist_re = re.compile(r'^\s+corelist-workers\s+([-0-9,]+)')
    dev_re = re.compile(r'^\s+dev\s+([^ ]+)\s+{\s*(.*?)\s*}(.*)$')
    used_cores = {}
    with open(filename, 'r', encoding='utf-8') as cfg:
        for line in cfg:
            if not dpdk_section:
                m = main_core_re.match(line)
                if m:
                    exclude_cores.append(int(m.group(1)))
                    continue
                m = corelist_re.match(line)
                if m:
                    allowed_cores = parse_corelist(m.group(1))
                if line.startswith("dpdk"):
                    dpdk_section = True
                    if len(exclude_cores) == 0:
                        exclude_cores.append(0)

                    worker = 0
                    for numa in sorted(numa2core):
                        cores_to_remove = []
                        for core in sorted(numa2core[numa]):
                            if core in exclude_cores:
                                cores_to_remove.append(core)
                                continue
                            if core not in allowed_cores:
                                cores_to_remove.append(core)
                                continue
                            core2worker[core] = worker
                            worker = worker+1
                        for core in cores_to_remove:
                            numa2core[numa].remove(core)
                    for numa in sorted(numa2ht):
                        cores_to_remove = []
                        for core in sorted(numa2ht[numa]):
                            if core in exclude_cores:
                                cores_to_remove.append(core)
                                continue
                            if core not in allowed_cores:
                                cores_to_remove.append(core)
                                continue
                            core2worker[core] = worker
                            worker = worker+1

                        for core in cores_to_remove:
                            numa2ht[numa].remove(core)

                continue
            if line.startswith("}"):
                break
            m = dev_re.match(line)
            if m:
                pci_id = m.group(1)
                pci_id = pci_id.replace("0000:", "")
                params = parse_dev_line(m.group(2))
                comments = m.group(3)

                use_ht = False
                if "use_ht" in comments:
                    use_ht = True
                numa = pci2numa[pci_id]
                for i in range(int(params["num-rx-queues"])):
                    core = 0
                    try:
                        if use_ht:
                            core = numa2ht[numa].pop(0)
                        else:
                            core = numa2core[numa].pop(0)
                    except IndexError:
                        print(f'ERROR! Cannot get core in numa={numa} for dev={pci_id} name={params["name"]} queue={i} - no cores left in the pool', flush=True, file=sys.stderr)
                        sys.exit(1)

                    if core in used_cores:
                        print(f'ERROR! Core {core} was already used by {used_cores[core]}', flush=True, file=sys.stderr)
                        sys.exit(1)
                    used_cores[core] = params["name"]
                    print(f'set int rx-placement {params["name"]} queue {i} worker {core2worker[core]}', flush=True, file=sys.stdout)
                print()


if __name__ == '__main__':
    generate_pinnings()
