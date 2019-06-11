resource "aws_instance" "monitor" {
    ami             = "ami-0dab6a064860e38d5"
    instance_type   = "${var.monitor_instance_type}"
    key_name        = "${var.keypair_name}"
    user_data       = <<EOF
INFLUXDB_DATABASE=tendermint
INFLUXDB_USERNAME=tendermint
INFLUXDB_PASSWORD=${var.influxdb_password}
DEPLOYMENT_GROUP=${var.deployment_group}
EOF
    security_groups = [
        "${aws_security_group.allow_ssh.name}",
        "${aws_security_group.allow_http.name}",
    ]
    tags            = {
        Name  = "Tendermint Monitor"
        ID    = "monitor"
        Group = "${var.deployment_group}"
    }
}

resource "aws_instance" "tendermint" {
    count           = var.tendermint_nodes
    ami             = "ami-06421fc82345cab58"
    instance_type   = "${var.tendermint_instance_type}"
    key_name        = "${var.keypair_name}"
    user_data       = <<EOF
INFLUXDB_URL="http://${aws_instance.monitor.public_dns}:8086"
INFLUXDB_DATABASE=tendermint
INFLUXDB_USERNAME=tendermint
INFLUXDB_PASSWORD=${var.influxdb_password}
TENDERMINT_NODE_ID=node${count.index}
DEPLOYMENT_GROUP=${var.deployment_group}
EOF
    security_groups = [
        "${aws_security_group.allow_ssh.name}",
        "${aws_security_group.allow_tendermint.name}",
        "${aws_security_group.allow_outage_sim.name}",
    ]
    depends_on      = [
        aws_instance.monitor,
    ]
    tags            = {
        Name  = "Tendermint Node ${count.index}"
        ID    = "node${count.index}"
        Group = "${var.deployment_group}"
    }
}
