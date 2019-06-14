# Tendermint Test Networks
This repository aims to contain various different configurations of test
networks for, and relating to, Tendermint.

At present, there are several networks provided:

* [`monitor`](./monitor/README.md) - A monitoring host running Grafana/InfluxDB
  that can easily be deployed and configured to display Tendermint network
  metrics.
* [`tendermint`](./tendermint/README.md) - A rudimentary Tendermint network that
  can be easily deployed across multiple regions on AWS.
* [`tm-bench`](./tm-bench/README.md) - A simple way of instantiating EC2 nodes
  running the Tendermint `tm-bench` tool to submit large quantities of
  transactions to one or more Tendermint nodes.

## License
Copyright 2019 Interchain Foundation

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
