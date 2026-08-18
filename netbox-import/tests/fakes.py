"""Minimal fake of the slice of the pynetbox API this tool uses -- no
network, no real NetBox instance required."""


class FakeObject:
    def __init__(self, id, **attrs):
        self.id = id
        for k, v in attrs.items():
            setattr(self, k, v)
        self.saved = False

    def save(self):
        self.saved = True


class FakeEndpoint:
    def __init__(self):
        self.objects = []
        self._next_id = 1

    def get(self, **filters):
        def matches(o):
            for key, value in filters.items():
                # NetBox filters FK relations two ways: `site=<slug>` and
                # `site_id=<id>`, both against the same underlying `site`
                # field -- mirror that instead of requiring an exact
                # attribute-name match.
                attr = key[: -len("_id")] if key.endswith("_id") and not hasattr(o, key) else key
                if getattr(o, attr, None) != value:
                    return False
            return True

        found = [o for o in self.objects if matches(o)]
        if len(found) > 1:
            raise ValueError(f"multiple matches for {filters}")
        return found[0] if found else None

    def create(self, **fields):
        obj = FakeObject(self._next_id, **fields)
        self._next_id += 1
        self.objects.append(obj)
        return obj


class FakeApp:
    def __init__(self, *endpoint_names):
        for name in endpoint_names:
            setattr(self, name, FakeEndpoint())


class FakeNetbox:
    def __init__(self):
        self.dcim = FakeApp(
            "manufacturers", "device_roles", "device_types", "sites", "racks", "devices", "interfaces"
        )
        self.ipam = FakeApp("vlans", "prefixes", "ip_addresses")
