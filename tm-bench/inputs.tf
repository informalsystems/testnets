variable "influxdb_url" {
    type        = string
    description = "The URL for the InfluxDB instance to which to submit metrics"
}

variable "influxdb_password" {
    type        = string
    description = "The password to access the InfluxDB instance running on the monitoring server"
    default     = "somepassword"
}

variable "keypair_name" {
    type        = string
    description = "Which AWS keypair to use to allow SSH access to your servers (see https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html)"
    default     = "ec2-keypair"
}

variable "tmbench_instances" {
    type        = number
    description = "The number of tm-bench node instances to launch"
    default     = 1
}

variable "instance_type" {
    type        = string
    description = "The AWS EC2 instance type for the tm-bench nodes to be deployed"
    default     = "t3.small"
}

variable "deployment_group" {
    type        = string
    description = "A tag to add to all of the nodes deployed here to be able to easily identify them through EC2"
    default     = "testnet"
}

variable "tendermint_node_endpoints" {
    type        = string
    description = "A comma-separated list of all of the Tendermint network node endpoints to target (e.g. node0:26657,node1:26657)"
}

variable "tmbench_time" {
    type        = number
    description = "The time for which to run tm-bench, in seconds"
    default     = 180
}

variable "tmbench_broadcast_tx_method" {
    type        = string
    description = "The type of broadcast_tx method to use (async, sync or commit)"
    default     = "async"
}

variable "tmbench_connections" {
    type        = number
    description = "The number of concurrent connections to make to each endpoint"
    default     = 1
}

variable "tmbench_rate" {
    type        = number
    description = "The rate at which to generate transactions from tm-bench"
    default     = 1000
}

variable "tmbench_size" {
    type        = number
    description = "The size of each transaction to send to the Tendermint nodes"
    default     = 250
}
