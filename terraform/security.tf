# Security Groups
resource "aws_security_group" "smaos_primary" {
  name        = "${var.environment}-smaos-primary-sg"
  description = "Security group for SMAOS primary region"
  vpc_id      = aws_vpc.primary.id

  tags = {
    Name   = "${var.environment}-smaos-primary-sg"
    Region = "primary"
  }
}

resource "aws_security_group" "smaos_secondary" {
  provider    = aws.secondary
  name        = "${var.environment}-smaos-secondary-sg"
  description = "Security group for SMAOS secondary region"
  vpc_id      = aws_vpc.secondary.id

  tags = {
    Name   = "${var.environment}-smaos-secondary-sg"
    Region = "secondary"
  }
}

# Primary Security Group Rules
resource "aws_vpc_security_group_ingress_rule" "primary_http" {
  security_group_id = aws_security_group.smaos_primary.id
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"

  tags = {
    Name = "allow-http-primary"
  }
}

resource "aws_vpc_security_group_ingress_rule" "primary_https" {
  security_group_id = aws_security_group.smaos_primary.id
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"

  tags = {
    Name = "allow-https-primary"
  }
}

resource "aws_vpc_security_group_ingress_rule" "primary_replication" {
  security_group_id = aws_security_group.smaos_primary.id
  from_port         = 9000
  to_port           = 9010
  ip_protocol       = "tcp"
  cidr_ipv4         = aws_vpc.secondary.cidr_block

  tags = {
    Name = "allow-replication-from-secondary"
  }
}

resource "aws_vpc_security_group_ingress_rule" "primary_ssh" {
  security_group_id = aws_security_group.smaos_primary.id
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"

  tags = {
    Name = "allow-ssh-primary"
  }
}

resource "aws_vpc_security_group_egress_rule" "primary_all" {
  security_group_id = aws_security_group.smaos_primary.id
  from_port         = -1
  to_port           = -1
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"

  tags = {
    Name = "allow-all-egress-primary"
  }
}

# Secondary Security Group Rules
resource "aws_vpc_security_group_ingress_rule" "secondary_http" {
  provider          = aws.secondary
  security_group_id = aws_security_group.smaos_secondary.id
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"

  tags = {
    Name = "allow-http-secondary"
  }
}

resource "aws_vpc_security_group_ingress_rule" "secondary_https" {
  provider          = aws.secondary
  security_group_id = aws_security_group.smaos_secondary.id
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"

  tags = {
    Name = "allow-https-secondary"
  }
}

resource "aws_vpc_security_group_ingress_rule" "secondary_replication" {
  provider          = aws.secondary
  security_group_id = aws_security_group.smaos_secondary.id
  from_port         = 9000
  to_port           = 9010
  ip_protocol       = "tcp"
  cidr_ipv4         = aws_vpc.primary.cidr_block

  tags = {
    Name = "allow-replication-from-primary"
  }
}

resource "aws_vpc_security_group_ingress_rule" "secondary_ssh" {
  provider          = aws.secondary
  security_group_id = aws_security_group.smaos_secondary.id
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"

  tags = {
    Name = "allow-ssh-secondary"
  }
}

resource "aws_vpc_security_group_egress_rule" "secondary_all" {
  provider          = aws.secondary
  security_group_id = aws_security_group.smaos_secondary.id
  from_port         = -1
  to_port           = -1
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"

  tags = {
    Name = "allow-all-egress-secondary"
  }
}
