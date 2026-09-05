# EC2 instances for SMAOS in primary region
resource "aws_instance" "smaos_primary_1" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.primary_a.id
  vpc_security_group_ids = [aws_security_group.smaos_primary.id]
  iam_instance_profile   = aws_iam_instance_profile.smaos.name
  associate_public_ip_address = true

  root_block_device {
    volume_size           = 100
    volume_type           = "gp3"
    delete_on_termination = true
  }

  user_data = base64encode(templatefile("${path.module}/user-data.sh", {
    region = var.primary_region
    role   = "primary"
  }))

  tags = {
    Name        = "${var.environment}-smaos-primary-1"
    Environment = var.environment
    Region      = "primary"
    Role        = "primary"
  }

  depends_on = [aws_internet_gateway.primary]
}

resource "aws_instance" "smaos_primary_2" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.primary_b.id
  vpc_security_group_ids = [aws_security_group.smaos_primary.id]
  iam_instance_profile   = aws_iam_instance_profile.smaos.name
  associate_public_ip_address = true

  root_block_device {
    volume_size           = 100
    volume_type           = "gp3"
    delete_on_termination = true
  }

  user_data = base64encode(templatefile("${path.module}/user-data.sh", {
    region = var.primary_region
    role   = "primary"
  }))

  tags = {
    Name        = "${var.environment}-smaos-primary-2"
    Environment = var.environment
    Region      = "primary"
    Role        = "primary"
  }

  depends_on = [aws_internet_gateway.primary]
}

# EC2 instances for SMAOS in secondary region
resource "aws_instance" "smaos_secondary_1" {
  provider               = aws.secondary
  ami                    = data.aws_ami.ubuntu_secondary.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.secondary_a.id
  vpc_security_group_ids = [aws_security_group.smaos_secondary.id]
  iam_instance_profile   = aws_iam_instance_profile.smaos_secondary.name
  associate_public_ip_address = true

  root_block_device {
    volume_size           = 100
    volume_type           = "gp3"
    delete_on_termination = true
  }

  user_data = base64encode(templatefile("${path.module}/user-data.sh", {
    region = var.secondary_region
    role   = "secondary"
  }))

  tags = {
    Name        = "${var.environment}-smaos-secondary-1"
    Environment = var.environment
    Region      = "secondary"
    Role        = "secondary"
  }

  depends_on = [aws_internet_gateway.secondary]
}

resource "aws_instance" "smaos_secondary_2" {
  provider               = aws.secondary
  ami                    = data.aws_ami.ubuntu_secondary.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.secondary_b.id
  vpc_security_group_ids = [aws_security_group.smaos_secondary.id]
  iam_instance_profile   = aws_iam_instance_profile.smaos_secondary.name
  associate_public_ip_address = true

  root_block_device {
    volume_size           = 100
    volume_type           = "gp3"
    delete_on_termination = true
  }

  user_data = base64encode(templatefile("${path.module}/user-data.sh", {
    region = var.secondary_region
    role   = "secondary"
  }))

  tags = {
    Name        = "${var.environment}-smaos-secondary-2"
    Environment = var.environment
    Region      = "secondary"
    Role        = "secondary"
  }

  depends_on = [aws_internet_gateway.secondary]
}

# Network Load Balancer for Primary Region
resource "aws_lb" "primary" {
  name               = "${var.environment}-smaos-primary-nlb"
  internal           = false
  load_balancer_type = "network"
  subnets            = [aws_subnet.primary_a.id, aws_subnet.primary_b.id]

  tags = {
    Name   = "${var.environment}-smaos-primary-nlb"
    Region = "primary"
  }
}

resource "aws_lb_target_group" "primary" {
  name     = "${var.environment}-smaos-primary-tg"
  port     = 9000
  protocol = "TCP"
  vpc_id   = aws_vpc.primary.id

  health_check {
    healthy_threshold   = 3
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    port                = "9001"
    protocol            = "TCP"
  }

  tags = {
    Name   = "${var.environment}-smaos-primary-tg"
    Region = "primary"
  }
}

resource "aws_lb_target_group_attachment" "primary_1" {
  target_group_arn = aws_lb_target_group.primary.arn
  target_id        = aws_instance.smaos_primary_1.id
  port             = 9000
}

resource "aws_lb_target_group_attachment" "primary_2" {
  target_group_arn = aws_lb_target_group.primary.arn
  target_id        = aws_instance.smaos_primary_2.id
  port             = 9000
}

resource "aws_lb_listener" "primary" {
  load_balancer_arn = aws_lb.primary.arn
  port              = "9000"
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.primary.arn
  }
}

# Network Load Balancer for Secondary Region
resource "aws_lb" "secondary" {
  provider           = aws.secondary
  name               = "${var.environment}-smaos-secondary-nlb"
  internal           = false
  load_balancer_type = "network"
  subnets            = [aws_subnet.secondary_a.id, aws_subnet.secondary_b.id]

  tags = {
    Name   = "${var.environment}-smaos-secondary-nlb"
    Region = "secondary"
  }
}

resource "aws_lb_target_group" "secondary" {
  provider = aws.secondary
  name     = "${var.environment}-smaos-secondary-tg"
  port     = 9000
  protocol = "TCP"
  vpc_id   = aws_vpc.secondary.id

  health_check {
    healthy_threshold   = 3
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    port                = "9001"
    protocol            = "TCP"
  }

  tags = {
    Name   = "${var.environment}-smaos-secondary-tg"
    Region = "secondary"
  }
}

resource "aws_lb_target_group_attachment" "secondary_1" {
  provider         = aws.secondary
  target_group_arn = aws_lb_target_group.secondary.arn
  target_id        = aws_instance.smaos_secondary_1.id
  port             = 9000
}

resource "aws_lb_target_group_attachment" "secondary_2" {
  provider         = aws.secondary
  target_group_arn = aws_lb_target_group.secondary.arn
  target_id        = aws_instance.smaos_secondary_2.id
  port             = 9000
}

resource "aws_lb_listener" "secondary" {
  provider          = aws.secondary
  load_balancer_arn = aws_lb.secondary.arn
  port              = "9000"
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.secondary.arn
  }
}

# RDS PostgreSQL for Primary Region
resource "aws_db_subnet_group" "primary" {
  name       = "${var.environment}-primary-db-subnet"
  subnet_ids = [aws_subnet.primary_a.id, aws_subnet.primary_b.id]

  tags = {
    Name   = "${var.environment}-primary-db-subnet"
    Region = "primary"
  }
}

resource "aws_rds_cluster" "primary" {
  cluster_identifier              = "${var.environment}-smaos-primary"
  engine                          = "aurora-postgresql"
  engine_version                  = "15.2"
  database_name                   = "smaos"
  master_username                 = "postgres"
  master_password                 = random_password.db_password.result
  db_subnet_group_name            = aws_db_subnet_group.primary.name
  vpc_security_group_ids          = [aws_security_group.smaos_primary.id]
  backup_retention_period         = 7
  copy_tags_to_snapshot           = true
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${var.environment}-smaos-primary-final-snapshot"
  enabled_cloudwatch_logs_exports = ["postgresql"]

  tags = {
    Name   = "${var.environment}-smaos-primary-cluster"
    Region = "primary"
  }
}

resource "aws_rds_cluster_instance" "primary" {
  cluster_identifier      = aws_rds_cluster.primary.id
  instance_class          = "db.r6i.large"
  engine                  = aws_rds_cluster.primary.engine
  engine_version          = aws_rds_cluster.primary.engine_version
  publicly_accessible     = false
  auto_minor_version_upgrade = true

  tags = {
    Name   = "${var.environment}-smaos-primary-instance"
    Region = "primary"
  }
}

# RDS PostgreSQL for Secondary Region
resource "aws_db_subnet_group" "secondary" {
  provider   = aws.secondary
  name       = "${var.environment}-secondary-db-subnet"
  subnet_ids = [aws_subnet.secondary_a.id, aws_subnet.secondary_b.id]

  tags = {
    Name   = "${var.environment}-secondary-db-subnet"
    Region = "secondary"
  }
}

resource "aws_rds_cluster" "secondary" {
  provider                        = aws.secondary
  cluster_identifier              = "${var.environment}-smaos-secondary"
  engine                          = "aurora-postgresql"
  engine_version                  = "15.2"
  database_name                   = "smaos"
  master_username                 = "postgres"
  master_password                 = random_password.db_password.result
  db_subnet_group_name            = aws_db_subnet_group.secondary.name
  vpc_security_group_ids          = [aws_security_group.smaos_secondary.id]
  backup_retention_period         = 7
  copy_tags_to_snapshot           = true
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${var.environment}-smaos-secondary-final-snapshot"
  enabled_cloudwatch_logs_exports = ["postgresql"]

  tags = {
    Name   = "${var.environment}-smaos-secondary-cluster"
    Region = "secondary"
  }
}

resource "aws_rds_cluster_instance" "secondary" {
  provider                   = aws.secondary
  cluster_identifier         = aws_rds_cluster.secondary.id
  instance_class             = "db.r6i.large"
  engine                     = aws_rds_cluster.secondary.engine
  engine_version             = aws_rds_cluster.secondary.engine_version
  publicly_accessible        = false
  auto_minor_version_upgrade = true

  tags = {
    Name   = "${var.environment}-smaos-secondary-instance"
    Region = "secondary"
  }
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "primary" {
  name              = "/aws/smaos/${var.environment}/primary"
  retention_in_days = 30

  tags = {
    Name   = "${var.environment}-smaos-primary-logs"
    Region = "primary"
  }
}

resource "aws_cloudwatch_log_group" "secondary" {
  provider          = aws.secondary
  name              = "/aws/smaos/${var.environment}/secondary"
  retention_in_days = 30

  tags = {
    Name   = "${var.environment}-smaos-secondary-logs"
    Region = "secondary"
  }
}

# Random password for RDS
resource "random_password" "db_password" {
  length  = 32
  special = true
}

# Data source for Ubuntu AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_ami" "ubuntu_secondary" {
  provider    = aws.secondary
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
