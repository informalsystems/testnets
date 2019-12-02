provider "aws" {
    version = "~> 2.14"
    region  = "us-east-1"
}

variable "influxdb_url" {
    type        = string
    description = "The URL for the InfluxDB instance to which to submit metrics"
    default     = "http://localhost:8086"
}

variable "influxdb_password" {
    type        = string
    description = "The password to access the InfluxDB instance running on the monitoring server"
    default     = "changeme"
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
    #default     = "t2.micro"
    default     = "t3.small"
}

variable "group" {
    type        = string
    description = "A tag/prefix to add to all of the nodes deployed here to be able to easily identify them through EC2"
    default     = "testnet"
}

variable "tendermint_node_endpoints" {
    type        = string
    description = "A comma-separated list of all of the Tendermint network node endpoints to target (e.g. node0:26657,node1:26657)"
    default     = "localhost:26657"
}

variable "tmbench_time" {
    type        = string
    description = "The time for which to run tm-bench, in seconds"
    default     = "180"
}

variable "tmbench_broadcast_tx_method" {
    type        = string
    description = "The type of broadcast_tx method to use (async, sync or commit)"
    default     = "async"
}

variable "tmbench_connections" {
    type        = string
    description = "The number of concurrent connections to make to each endpoint"
    default     = "1"
}

variable "tmbench_rate" {
    type        = string
    description = "The rate at which to generate transactions from tm-bench"
    default     = "1000"
}

variable "tmbench_size" {
    type        = string
    description = "The size of each transaction to send to the Tendermint nodes"
    default     = "250"
}

variable "tmbench_finish_wait" {
    type        = number
    description = "The amount of time to wait (seconds) after each successive execution of tm-bench (constant for all executions)"
    default     = 0
}

data "aws_region" "current" {
    provider = "aws"
}

output "hosts" {
    value = {for i in aws_instance.tmbench : i.tags.ID => {
        public_dns: i.public_dns,
        public_ip : i.public_ip
    }}
}

resource "aws_instance" "tmbench" {
    count           = var.tmbench_instances
    ami             = "ami-0760f51e3146afbf9"
    instance_type   = "${var.instance_type}"
    key_name        = "${var.keypair_name}"
    user_data       = <<EOF
INFLUXDB_URL="${var.influxdb_url}"
INFLUXDB_DATABASE=tendermint
INFLUXDB_USERNAME=tendermint
INFLUXDB_PASSWORD=${var.influxdb_password}
DC="${data.aws_region.current.name}"
GROUP="${var.group}"

TMBENCH_ENDPOINTS="${var.tendermint_node_endpoints}"
TMBENCH_TIME="${var.tmbench_time}"
TMBENCH_BROADCAST_TX_METHOD="${var.tmbench_broadcast_tx_method}"
TMBENCH_CONNECTIONS="${var.tmbench_connections}"
TMBENCH_RATE="${var.tmbench_rate}"
TMBENCH_SIZE="${var.tmbench_size}"
TMBENCH_FINISH_WAIT="${var.tmbench_finish_wait}"
EOF
    security_groups = [
        "${aws_security_group.tmbench_sg.name}",
    ]
    tags      = {
        Name  = "Tendermint tm-bench ${count.index} (${var.group})"
        ID    = "tmbench${count.index}"
        Class = "tmbench"
        Group = "${var.group}"
    }

    # By default, we terminate this instance once the load test is done
    instance_initiated_shutdown_behavior = "terminate"

    associate_public_ip_address = true
}


resource "aws_security_group" "tmbench_sg" {
    name        = "${var.group}_tmbench_sg"
    description = "Allows SSH inbound traffic from anywhere, and all outbound traffic, for the tm-bench network"

    ingress {
        from_port   = 22
        to_port     = 22
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
        description = "SSH"
    }

    egress {
        from_port   = 0
        to_port     = 0
        protocol    = "-1"
        cidr_blocks = ["0.0.0.0/0"]
        description = "Allow all outbound TCP and UDP traffic"
    }

    tags = {
        Name  = "tm-bench Security Group (${var.group})"
        Group = "${var.group}"
    }
}
