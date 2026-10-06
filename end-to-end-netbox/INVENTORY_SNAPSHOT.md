While NetBox is reachable, replace the input below with your NetBox plugin inventory file:
```bash
ansible-inventory -i netbox_inventory.yml --list --yaml --export --output inventory_snapshot.yml
```
Use the snapshot offline with `-i inventory_snapshot.yml`; keep any separate `group_vars` files alongside it.
