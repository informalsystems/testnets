resource "aws_instance" "monitor" {
    ami             = "ami-0fae0bb71abfebc19"
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
        "${aws_security_group.allow_influxdb.name}",
        "${aws_security_group.allow_all_outbound.name}"
    ]
    tags            = {
        Name  = "Tendermint Monitor"
        ID    = "monitor"
        Group = "${var.deployment_group}"
    }

    associate_public_ip_address = true
}

resource "aws_instance" "tendermint" {
    count           = var.tendermint_nodes
    ami             = "ami-0bd0860cdbabfad70"
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
        "${aws_security_group.allow_all_outbound.name}"
    ]
    depends_on      = [
        aws_instance.monitor,
    ]
    tags            = {
        Name  = "Tendermint Node ${count.index}"
        ID    = "node${count.index}"
        Group = "${var.deployment_group}"
    }

    associate_public_ip_address = true
}
