# CLI Commands

`trellis` is a tiny python/typer cli that boots a local pulsar sandbox and helps you create a default tenant/namespace/topic, then publish test data.

## install (recap)

```bash
pipx install .
trellis --help
```


---

## start

spin up pulsar, pulsar-manager, prometheus, and grafana on podman.

```bash
trellis start
```

services:

* pulsar: `6650` (binary), `8080` (admin/metrics)
* pulsar-manager ui: `9527`
* prometheus: `9090`
* grafana: `3000` (streamnative pulsar dashboards; login: `admin / happypulsaring`)

tips:

* if metrics look empty, make sure prometheus scrapes **`/metrics/`** (trailing slash).

---

## Down

stop and remove all containers that `trellis start` created.

```bash
trellis down
```

---

## Restart

```bash
trellis down && trellis start
```

---

## Status

show running containers + ports.

```bash
trellis status
```

---


## init-space

create (or update) a default tenant, namespace, and partitioned topic, then run a tiny publish smoke test (output → `init-publish-logs.log`).

```bash
trellis init-space
```

options:

```bash
trellis init-space --help
```

* `tenant` (default: `test-pulsar-dev`)
* `namespace` (default: `ingress`)
* `topic` (default: `nums`)
* `partitions` (default: `3`)

examples:

```bash
# defaults: test-pulsar-dev/ingress/nums
trellis init-space

# custom space
trellis init-space myteam ingress api-events --partitions 6
```

what it does:

* detects cluster name (usually `standalone`)
* creates/updates tenant with allowed clusters
* creates namespace if missing
* sets schema compatibility to `BACKWARD`, retention to `1d`
* creates a partitioned topic (N partitions)
* enables topic dedup
* publishes 3 test messages (see `init-publish-logs.log` for details)

---

## test-publish

publish randomized json records (first/last name, order\_no, amount, ts) to a topic. great for demos, dashboards, and perf smoke.

### recommended (fast): python client

first inject the dependency into the pipx’d app:

```bash
pipx inject trellis pulsar-client
```

then:

```bash
trellis test-publish persistent://test-pulsar-dev/ingress/nums -n 150 --rate 200
```

options:

* `-n, --count` — number of messages (default `150`)
* `--rate` — messages/sec (default `0` = as fast as possible)
* `--url` — pulsar service url (default `pulsar://localhost:6650`)
* `--name` — producer name (default `trellis-producer`)

### notes

* names are pulled from a fun pool (kingkiller, dresden, first law, sailor moon, jjk, gideon).
* to keep grafana charts alive, use a non-zero `--rate` and widen the time range to “last 15 min”.

---

## urls quick reference

* pulsar admin api: [http://localhost:8080](http://localhost:8080)
* pulsar manager ui: [http://localhost:9527](http://localhost:9527)
* prometheus: [http://localhost:9090](http://localhost:9090) (check **Status → Targets**)
* grafana: [http://localhost:3000](http://localhost:3000)

---

## env overrides

all of these can be overridden via env vars before `trellis start`:

* `PULSAR_NAME` (default `pulsar`)
* `PM_NAME` (default `pulsar-manager`)
* `PROM_NAME` (default `prom`)
* `GRAF_NAME` (default `graf`)
* `NET_NAME` (default `pulsar-net`)
* `PULSAR_BIN_PORT` (`6650`)
* `PULSAR_HTTP_PORT` (`8080`)
* `PM_UI_PORT` (`9527`)
* `PM_API_PORT` (`7750`)
* `PROM_PORT` (`9090`)
* `GRAF_PORT` (`3000`)
* `PULSAR_CLUSTER_LABEL` (`standalone`)

example:

```bash
PULSAR_HTTP_PORT=18080 GRAF_PORT=33000 trellis start
```

---

## troubleshooting

* **manager ui won’t load**

  * check ports: `podman port pulsar-manager`
  * hit backend health: `curl http://localhost:7750/actuator/health`
  * both `9527` (ui) and `7750` (api) must be published.

* **grafana “local publish rate” is 0**

  * make sure prometheus target is **UP** at `/metrics/` (note the slash).
  * use PromQL directly to confirm data:

    ```
    sum(rate(pulsar_in_messages_total{namespace="test-pulsar-dev/ingress"}[1m]))
    ```

    (metric name may vary by Pulsar version; try `pulsar_incoming_messages_total` if needed.)
  * run a sustained stream:

    ```
    trellis test-publish persistent://test-pulsar-dev/ingress/nums -n 5000 --rate 200
    ```

* **`trellis` command not found**

  * ensure `pipx` is on PATH: `pipx ensurepath`
  * reinstall: `pipx reinstall trellis`

---

## see also

* [quickstart](../Readme.md) — from zero to first publish
* [pulsar manager](https://github.com/apache/pulsar-manager) (ui)
* [apache pulsar](https://pulsar.apache.org/) docs
