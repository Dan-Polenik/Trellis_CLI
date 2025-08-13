# quickstart

this guide gets you from a fresh macOS install to running `trellis` and publishing your first test messages to a local pulsar instance.

## prerequisites

* macOS (intel or apple silicon)
* [homebrew](https://brew.sh) installed
* internet access for downloading dependencies

---

## 1. install dependencies

```bash
# install podman (container runtime)
brew install podman

# initialize podman (first-time setup)
podman machine init
podman machine start

# install python 3 and pipx
brew install python
brew install pipx
pipx inject trellis pulsar-client
pipx ensurepath
```

---

## 2. clone and install trellis cli
Clone the repo and run pipx install in the directory you cloned. Should be the one that has pyproject.toml.

```bash

# install trellis into an isolated environment via pipx
pipx install .
```

you should now have `trellis` available on your path:

```bash
trellis --help
```

---

## 3. Start the Sandbox

this sets up pulsar + pulsar manager locally.

```bash
trellis start
```

---

## 4. Set Up a Default Space (optional)

if you don’t want to create your own user/ingress namespace, run:

```bash
trellis init-space
```

---

## 5. Publish Test Messages

pick a topic name (or use the default space you just created):

```bash
trellis test-publish persistent://test-pulsar-dev/ingress/nums
```

this will publish 150 random records containing:

* first name
* last name
* order number
* dollar amount

---

## 6. Check Grafana

open [http://localhost:3000/](http://localhost:3000) in your browser.

username and password are provided in the CLI output.

---

## 7. Next Steps

* view the [cli command reference](./trellis_cli/CLI_Command_Reference.md) for all available commands
* read the [architecture overview](../../wiki/Architecture) for how trellis fits into your data platform(TODO)

