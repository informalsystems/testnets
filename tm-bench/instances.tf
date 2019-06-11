resource "aws_instance" "tmbench" {
    count           = var.tmbench_instances
    ami             = "ami-01a7f3616737e7806"
    instance_type   = "${var.instance_type}"
    key_name        = "${var.keypair_name}"
    user_data       = <<EOF
INFLUXDB_URL="${var.influxdb_url}"
INFLUXDB_DATABASE=tendermint
INFLUXDB_USERNAME=tendermint
INFLUXDB_PASSWORD=${var.influxdb_password}
DEPLOYMENT_GROUP=${var.deployment_group}

TMBENCH_ENDPOINTS="${var.tendermint_node_endpoints}"
TMBENCH_TIME=${var.tmbench_time}
TMBENCH_BROADCAST_TX_METHOD=${var.tmbench_broadcast_tx_method}
TMBENCH_CONNECTIONS=${var.tmbench_connections}
TMBENCH_RATE=${var.tmbench_rate}
TMBENCH_SIZE=${var.tmbench_size}
EOF
    security_groups = [
        "${aws_security_group.allow_ssh_tmbench.name}",
        "${aws_security_group.allow_all_outbound_tmbench.name}",
    ]
    tags            = {
        Name  = "Tendermint tm-bench ${count.index}"
        ID    = "tmbench${count.index}"
        Group = "${var.deployment_group}"
    }

    # By default, we terminate this instance once the load test is done
    instance_initiated_shutdown_behavior = "terminate"

    associate_public_ip_address = true
}
