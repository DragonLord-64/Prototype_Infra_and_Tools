# Add one FPGA discovery block

Copy a named discovery block before the comparison block in `bootstrap.yml`.
Use the actual vendor's documented **read-only** command and parser; no vendor
SDK command is assumed or executed by this example. Set this optional variable
only after confirming its read-only contract.

```yaml
    - name: Discover FPGA inventory with the chosen SDK
      tags: [fpga, compare, apply]
      become: true
      environment:
        PATH: /opt/YOUR_SDK/bin:/usr/sbin:/usr/bin:/sbin:/bin
        LC_ALL: C
      when: fpga_readonly_command_argv is defined
      block:
        - name: Run the reviewed FPGA information command
          ansible.builtin.command:
            argv: "{{ fpga_readonly_command_argv }}"
          register: fpga_probe
          changed_when: false
          failed_when: false
          check_mode: false

        - name: Report missing or failed FPGA discovery
          ansible.builtin.debug:
            msg: "{{ fpga_probe.stderr | default(fpga_probe.msg | default('Unavailable')) }}"
          when: fpga_probe.rc != 0
        # Add the SDK-specific parser here only after inspecting real output.
```

For each card, append a dictionary to `discovered_components` with a stable
slot-based `name`, `kind: FPGA`, and available `part`/`serial` strings. The
existing apply block creates/updates the inventory item; an unavailable value
must be an empty string so apply omits it. Do not invent firmware/serial/IP
fields or copy simulated output onto real hosts. If firmware is needed, first
add a deliberate NetBox field and explicit mapping from that SDK's output.

`--tags fpga` runs facts plus FPGA discovery; `--tags fpga,compare --check`
previews all selected discovery without NetBox writes. Add corresponding tiny
test-container stubs/fixtures and expected NetBox assertions before applying
against real hardware. No FPGA SDK has been installed or tested in this demo.

## Inventory-item record contract

The playbook has a named `fpga` mapping block for `bootstrap_fpga_cards`.
Supply records with a stable `name`, available `part`/`serial`, and optional
verified `interface`. An SDK block can set this list before the mapping block.
The mapping creates **inventory items**, never NetBox modules or module bays.
Missing values preserve existing part/serial data; duplicate names fail before
writes. [cards.example.yml](cards.example.yml) starts with empty lists and
commented field examples, so merely loading it creates no placeholder cards.

For NIC vendor discovery, use the equivalent `bootstrap_nic_cards` contract.
Disable `bootstrap_collect_pci_nics` if supplying a different physical-card
grouping, so one card is not duplicated as several PCI-function records.
Standard sysfs metadata identifies PCI functions and their interfaces, not
necessarily whole multi-function physical cards, catalog part numbers, or
serials. Mellanox-specific identifiers require the user's reviewed read-only
command/output; none is assumed here. Automatic interface association occurs
only for one interface per PCI function; multi-port records remain unbound.
