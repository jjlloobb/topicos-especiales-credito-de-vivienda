"""NFR-U1-22: aserciones compartidas sobre el `pg_hba` de un `Cluster` renderizado."""


def assert_postgres_requires_tls(cluster, name):
    parameters = cluster["spec"]["postgresql"]
    rules = [line.split() for line in parameters["pg_hba"]]
    assert rules, name
    for rule in rules:
        assert rule[0] in {"hostssl", "hostnossl"}, (name, rule)
        assert rule[0] == "hostssl" or rule[-1] == "reject", (name, rule)
    # Sin este rechazo, la regla `host ... scram-sha-256` que el operador agrega al final admite texto plano.
    assert ["hostnossl", "all", "all", "all", "reject"] in rules, name
    assert any(r[0] == "hostssl" and r[-1] == "scram-sha-256" for r in rules), name
