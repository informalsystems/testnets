provider "aws" {
    version = "~> 2.14"
    region  = "us-east-1"
}

variable "influxdb_password" {
    type        = string
    description = "The password to apply to the InfluxDB instance running on the monitoring server"
    default     = "changeme"
}

variable "keypair_name" {
    type        = string
    description = "Which AWS keypair to use to allow SSH access to your servers (see https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html)"
    default     = "ec2-keypair"
}

variable "instance_type" {
    type        = string
    description = "The AWS EC2 instance type for the monitoring node to be deployed"
    default     = "t3.small"
}

variable "group" {
    type        = string
    description = "The group ID for this deployment (will be added to tags and prefixed on instance names)"
    default     = "testnet"
}

variable "volume_size" {
    type        = number
    description = "The size of the EBS volume (in GiB) to attach to the monitor node when instantiating it"
    default     = 8
}

output "influxdb_url" {
    value       = "http://${aws_instance.monitor.public_dns}:8086"
    description = "The URL at which the InfluxDB instance can be reached"
}

output "grafana_url" {
    value       = "http://${aws_instance.monitor.public_dns}"
    description = "The URL at which the Grafana instance can be reached"
}

output "host" {
    value = {
        public_dns: aws_instance.monitor.public_dns
        public_ip : aws_instance.monitor.public_ip
    }
}

data "aws_region" "current" {
    provider = "aws"
}

resource "aws_instance" "monitor" {
    provider        = "aws"
    ami             = "ami-0fae0bb71abfebc19"
    instance_type   = "${var.instance_type}"
    key_name        = "${var.keypair_name}"
    user_data       = <<EOF
INFLUXDB_DATABASE=tendermint
INFLUXDB_USERNAME=tendermint
INFLUXDB_PASSWORD="${var.influxdb_password}"
DC="${data.aws_region.current.name}"
GROUP="${var.group}"
EOF
    security_groups = [
        "${aws_security_group.monitor_sg.name}",
    ]
    tags      = {
        Name  = "Tendermint Monitor (${var.group})"
        ID    = "monitor"
        Class = "monitor"
        Group = "${var.group}"
    }

    associate_public_ip_address = true

    root_block_device {
        volume_size = var.volume_size
    }
}

resource "aws_security_group" "monitor_sg" {
    provider    = "aws"
    name        = "${var.group}_monitor_sg"
    description = "Allows inbound SSH and monitoring-related traffic from anywhere, and all outgoing traffic"

    ingress {
        from_port   = 22
        to_port     = 22
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
        description = "SSH"
    }
    ingress {
        from_port   = 80
        to_port     = 80
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
        description = "HTTP"
    }
    ingress {
        from_port   = 8086
        to_port     = 8086
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
        description = "InfluxDB"
    }

    egress {
        from_port   = 0
        to_port     = 0
        protocol    = "-1"
        cidr_blocks = ["0.0.0.0/0"]
        description = "Allow all outbound TCP and UDP traffic"
    }

    tags = {
        Name  = "Tendermint Monitor Security Group (${var.group})"
        Group = "${var.group}"
    }
}
