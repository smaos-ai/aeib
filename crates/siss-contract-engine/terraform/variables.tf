variable "environment" {
  description = "Environment (dev, staging, production)"
  type        = string
  default     = "production"
}

variable "region_defense" {
  description = "AWS GovCloud region for Defense vertical"
  type        = string
  default     = "us-gov-west-1"
}

variable "region_healthcare" {
  description = "EU region for Healthcare vertical (GDPR)"
  type        = string
  default     = "eu-central-1"
}

variable "region_finance" {
  description = "PCI-DSS compliant region for Finance vertical"
  type        = string
  default     = "eu-west-1"
}

variable "instance_type" {
  description = "EC2 instance type for all verticals"
  type        = string
  default     = "c6i.4xlarge"
}

variable "pilot_duration_days" {
  description = "Duration of pilot in days"
  type        = number
  default     = 90
}

variable "uptime_sla_target" {
  description = "Target uptime SLA percentage"
  type        = number
  default     = 99.99
}

variable "latency_p99_target_ms" {
  description = "Target p99 latency in milliseconds"
  type        = number
  default     = 100
}

variable "arr_commitment_defense" {
  description = "ARR commitment for Defense vertical in cents (€)"
  type        = number
  default     = 166666700
}

variable "arr_commitment_healthcare" {
  description = "ARR commitment for Healthcare vertical in cents (€)"
  type        = number
  default     = 166666700
}

variable "arr_commitment_finance" {
  description = "ARR commitment for Finance vertical in cents (€)"
  type        = number
  default     = 166666600
}
