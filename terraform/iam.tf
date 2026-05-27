# IAM Role for EC2 instances
resource "aws_iam_role" "smaos" {
  name = "${var.environment}-smaos-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.environment}-smaos-ec2-role"
    Environment = var.environment
  }
}

# IAM Policy for EC2 to access logs and metrics
resource "aws_iam_role_policy" "smaos_logs_metrics" {
  name = "${var.environment}-smaos-logs-metrics"
  role = aws_iam_role.smaos.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeTags",
          "ec2:DescribeVolumes",
          "ec2:DescribeVpcs"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM Policy for RDS access
resource "aws_iam_role_policy" "smaos_rds" {
  name = "${var.environment}-smaos-rds"
  role = aws_iam_role.smaos.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds:DescribeDBClusters",
          "rds:DescribeDBInstances",
          "rds-db:connect"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM Instance Profile
resource "aws_iam_instance_profile" "smaos" {
  name = "${var.environment}-smaos-instance-profile"
  role = aws_iam_role.smaos.name
}

# Secondary region IAM Role
resource "aws_iam_role" "smaos_secondary" {
  provider = aws.secondary
  name     = "${var.environment}-smaos-ec2-role-secondary"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.environment}-smaos-ec2-role-secondary"
    Environment = var.environment
  }
}

# Secondary region IAM Policy for logs and metrics
resource "aws_iam_role_policy" "smaos_logs_metrics_secondary" {
  provider = aws.secondary
  name     = "${var.environment}-smaos-logs-metrics-secondary"
  role     = aws_iam_role.smaos_secondary.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeTags",
          "ec2:DescribeVolumes",
          "ec2:DescribeVpcs"
        ]
        Resource = "*"
      }
    ]
  })
}

# Secondary region IAM Policy for RDS
resource "aws_iam_role_policy" "smaos_rds_secondary" {
  provider = aws.secondary
  name     = "${var.environment}-smaos-rds-secondary"
  role     = aws_iam_role.smaos_secondary.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds:DescribeDBClusters",
          "rds:DescribeDBInstances",
          "rds-db:connect"
        ]
        Resource = "*"
      }
    ]
  })
}

# Secondary region IAM Instance Profile
resource "aws_iam_instance_profile" "smaos_secondary" {
  provider = aws.secondary
  name     = "${var.environment}-smaos-instance-profile-secondary"
  role     = aws_iam_role.smaos_secondary.name
}
